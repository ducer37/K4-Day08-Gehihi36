"""Task 5 - Semantic search over the Chroma index from Task 4."""

from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    if not query.strip() or top_k <= 0:
        return []

    try:
        collection = get_collection()
    except ModuleNotFoundError:
        return []
    if collection.count() == 0:
        return []

    query_vector = embed_texts([query])[0]
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
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
