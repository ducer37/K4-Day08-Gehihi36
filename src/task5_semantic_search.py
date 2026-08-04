"""Task 5 - Semantic search over the Chroma index from Task 4."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "ecommerce_support_docs"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def _get_collection():
    """Lấy ChromaDB collection."""
    try:
        from .task4_chunking_indexing import get_collection
        return get_collection()
    except Exception:
        import chromadb
        from chromadb.utils import embedding_functions

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("Chưa cài OPENAI_API_KEY trong file .env!")

        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=EMBEDDING_MODEL,
        )

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=openai_ef,
            metadata={"hnsw:space": "cosine"},
        )


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa bằng Embedding + ChromaDB.
    """
    if not query.strip() or top_k <= 0:
        return []

    try:
        collection = _get_collection()
    except Exception:
        return []

    count = collection.count()
    if count == 0:
        return []

    try:
        from .task4_chunking_indexing import embed_texts
        query_vector = embed_texts([query])[0]
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

    output = []
    for doc, meta, distance in zip(
        results.get("documents", [[]])[0],
        results.get("metadatas", [[]])[0],
        results.get("distances", [[]])[0],
    ):
        output.append(
            {
                "content": doc,
                "score": round(max(0.0, 1.0 - float(distance)), 4),
                "metadata": meta or {},
            }
        )

    return sorted(output, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for result in semantic_search("quy định trả hàng hoàn tiền shopee", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
