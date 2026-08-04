"""Task 5 - Semantic search over the Chroma index from Task 4."""

import re

from .task4_chunking_indexing import chunk_documents, embed_texts, get_collection, load_documents


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE))


def _offline_semantic_search(query: str, top_k: int) -> list[dict]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    results = []
    for chunk in chunk_documents(load_documents()):
        content_tokens = _tokenize(chunk["content"])
        if not content_tokens:
            continue
        overlap = len(query_tokens & content_tokens)
        score = overlap / len(query_tokens | content_tokens)
        if score > 0:
            results.append(
                {
                    "content": chunk["content"],
                    "score": round(score, 4),
                    "metadata": chunk.get("metadata", {}),
                }
            )

    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    if not query.strip() or top_k <= 0:
        return []

    try:
        collection = get_collection()
    except ModuleNotFoundError:
        return _offline_semantic_search(query, top_k)
    if collection.count() == 0:
        return _offline_semantic_search(query, top_k)

    try:
        query_vector = embed_texts([query])[0]
    except RuntimeError:
        return _offline_semantic_search(query, top_k)
    try:
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return _offline_semantic_search(query, top_k)

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
