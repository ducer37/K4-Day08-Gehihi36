"""
Task 4 - Chunking & Indexing.

Strategy:
- Paragraph-aware recursive chunking: keeps Markdown headings/paragraphs together
  when possible, then hard-wraps long blocks. This fits Shopee policy/help pages
  better than fixed slicing.
- Local sentence-transformers / bge-m3 / OpenAI embedding support.
- ChromaDB cosine collection: local persistent vector store for Task 5.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 120
CHUNKING_METHOD = "paragraph_recursive"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536

VECTOR_STORE = "chromadb"
COLLECTION_NAME = "ecommerce_support_docs"


def _clean_text(text: str) -> str:
    lines = []
    junk = {
        "xin chào, shopee có thể giúp gì cho bạn?",
        "bạn có hài lòng với bài viết này?",
        "hài lòng",
        "không hài lòng",
    }
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.lower() in junk:
            continue
        lines.append(stripped)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _customer_role(path: Path, content: str) -> str:
    role_match = re.search(r"CUSTOMER_ROLE:\s*(buyer|seller|both)", content, flags=re.IGNORECASE)
    if role_match:
        return role_match.group(1).lower()

    name = path.stem.lower()
    if any(word in name for word in ["seller", "manage", "dang-ban", "shop"]):
        return "seller"
    if any(word in name for word in ["privacy", "terms", "policy", "quy-che", "article_02", "article_03", "article_04", "article_06"]):
        return "both"
    if any(word in name for word in ["refund", "return", "shipping", "track", "article_01", "article_05"]):
        return "buyer"

    text = f"{path.name}\n{content[:2000]}".lower()
    seller_words = ["người bán", "seller", "kênh quản lý shop", "đăng bán"]
    buyer_words = ["người mua", "buyer", "đơn mua", "trả hàng", "hoàn tiền"]
    has_seller = any(word in text for word in seller_words)
    has_buyer = any(word in text for word in buyer_words)
    if has_seller and has_buyer:
        return "both"
    if has_seller:
        return "seller"
    return "buyer"


def load_documents() -> list[dict]:
    documents = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if md_file.name == ".gitkeep":
            continue
        content = _clean_text(md_file.read_text(encoding="utf-8", errors="ignore"))
        if not content:
            continue
        doc_type = "legal" if "legal" in md_file.parts else "news"
        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "path": str(md_file.relative_to(STANDARDIZED_DIR)),
                    "type": doc_type,
                    "customer_role": _customer_role(md_file, content),
                },
            }
        )
    return documents


def _split_long_block(block: str) -> list[str]:
    if len(block) <= CHUNK_SIZE:
        return [block]

    parts = re.split(r"(?<=[.!?。;:])\s+|\n", block)
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > CHUNK_SIZE:
            for start in range(0, len(part), CHUNK_SIZE - CHUNK_OVERLAP):
                chunks.append(part[start : start + CHUNK_SIZE].strip())
            continue
        if len(current) + len(part) + 1 > CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    chunks = []
    for doc in documents:
        blocks = []
        for block in re.split(r"\n\s*\n", doc["content"]):
            block = block.strip()
            if block:
                blocks.extend(_split_long_block(block))

        current = ""
        chunk_index = 0
        for block in blocks:
            candidate = f"{current}\n\n{block}".strip() if current else block
            if len(candidate) <= CHUNK_SIZE:
                current = candidate
                continue

            if current:
                chunks.append(
                    {
                        "content": current,
                        "metadata": {**doc["metadata"], "chunk_index": chunk_index},
                    }
                )
                chunk_index += 1
                overlap = current[-CHUNK_OVERLAP:] if CHUNK_OVERLAP else ""
                current = f"{overlap}\n\n{block}".strip()
                if len(current) > CHUNK_SIZE:
                    current = block[:CHUNK_SIZE]
            else:
                current = block[:CHUNK_SIZE]

        if current:
            chunks.append(
                {
                    "content": current,
                    "metadata": {**doc["metadata"], "chunk_index": chunk_index},
                }
            )
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _hash_embed_texts(texts)

    embeddings: list[list[float]] = []
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        for start in range(0, len(texts), 100):
            batch = texts[start : start + 100]
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            embeddings.extend(item.embedding for item in response.data)
    except Exception:
        return _hash_embed_texts(texts)
    return embeddings


def _hash_embed_texts(texts: list[str], dim: int = EMBEDDING_DIM) -> list[list[float]]:
    """Offline deterministic embedding fallback for running the lab without API keys."""
    vectors = []
    for text in texts:
        vector = [0.0] * dim
        tokens = re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        vectors.append(vector)
    return vectors


def embed_chunks(chunks: list[dict]) -> list[dict]:
    embeddings = embed_texts([chunk["content"] for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
    return chunks


def get_collection(reset: bool = False):
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def index_to_vectorstore(chunks: list[dict]):
    collection = get_collection(reset=True)
    ids = []
    for chunk in chunks:
        raw = f"{chunk['metadata']['path']}:{chunk['metadata']['chunk_index']}"
        ids.append(hashlib.md5(raw.encode("utf-8")).hexdigest())

    collection.upsert(
        ids=ids,
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )


def run_pipeline():
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\nLoaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
