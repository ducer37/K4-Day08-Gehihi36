"""
Task 5 — Semantic Search Module (Sử dụng OpenAI API — Không tải Local Model).

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
    - Sử dụng OpenAI text-embedding-3-small qua API (không tải local model)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Config ChromaDB
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "ecommerce_support_docs"
EMBEDDING_MODEL = "text-embedding-3-small"


def _get_collection():
    """Lấy ChromaDB collection với OpenAI Embedding Function (gọi API)."""
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
    Tìm kiếm ngữ nghĩa bằng OpenAI API Embedding + ChromaDB.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict
        }
        Sorted by score descending.
    """
    collection = _get_collection()

    count = collection.count()
    if count == 0:
        print("⚠ Collection rỗng — hãy chạy Task 4 trước để index dữ liệu.")
        return []

    # Query ChromaDB (ChromaDB tự gọi OpenAI API để embed câu truy vấn)
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        score = max(0.0, 1.0 - dist)  # Cosine distance → Similarity score
        output.append({"content": doc, "score": round(score, 4), "metadata": meta})

    output.sort(key=lambda x: x["score"], reverse=True)
    return output[:top_k]


if __name__ == "__main__":
    results = semantic_search("quy định trả hàng hoàn tiền shopee", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
