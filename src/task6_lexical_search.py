"""Task 6 - BM25 lexical search over the same chunks used for indexing."""

from __future__ import annotations

import re

from .task4_chunking_indexing import chunk_documents, load_documents

CORPUS: list[dict] = []
BM25 = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


def build_bm25_index(corpus: list[dict]):
    tokenized_corpus = [_tokenize(doc["content"]) for doc in corpus]
    try:
        from rank_bm25 import BM25Okapi

        return BM25Okapi(tokenized_corpus)
    except Exception:
        return tokenized_corpus


def _ensure_index():
    global CORPUS, BM25
    if CORPUS and BM25 is not None:
        return
    CORPUS = chunk_documents(load_documents())
    BM25 = build_bm25_index(CORPUS)


def _fallback_scores(tokenized_query: list[str], tokenized_corpus: list[list[str]]) -> list[float]:
    query = set(tokenized_query)
    return [float(sum(1 for token in doc if token in query)) for doc in tokenized_corpus]


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    if not query.strip() or top_k <= 0:
        return []

    _ensure_index()
    if not CORPUS:
        return []

    tokenized_query = _tokenize(query)
    if hasattr(BM25, "get_scores"):
        scores = [float(score) for score in BM25.get_scores(tokenized_query)]
    else:
        scores = _fallback_scores(tokenized_query, BM25)

    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    results = []
    for index, score in ranked[:top_k]:
        results.append(
            {
                "content": CORPUS[index]["content"],
                "score": score,
                "metadata": CORPUS[index]["metadata"],
            }
        )
    return results


if __name__ == "__main__":
    for result in lexical_search("phương thức thanh toán shopee", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
