# RAG Evaluation Results

- Framework: RAGAS
- LLM judge: OpenAI `gpt-5-nano`
- Generated: 2026-08-04T20:40:05
- Golden dataset: 15 questions

## Overall Scores

| Metric | Config A: hybrid + RRF | Config B: hybrid no rerank | Delta |
|---|---:|---:|---:|
| faithfulness | 0.992 | 0.971 | +0.020 |
| answer_relevancy | 0.860 | 0.866 | -0.006 |
| context_recall | 0.933 | 0.933 | +0.000 |
| context_precision | 0.745 | 0.752 | -0.007 |
| average | 0.883 | 0.881 | +0.002 |

## A/B Comparison

- Config A: semantic + BM25 + RRF rerank + PageIndex fallback.
- Config B: semantic + BM25 without reranking + PageIndex fallback.

## Worst Performers

| # | Question | Faithfulness | Relevancy | Recall | Precision | Source Count |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Shopee hiện có hỗ trợ đổi hàng trực tiếp không? | 1.000 | 0.782 | 0.000 | 0.950 | 5 |
| 2 | Nếu yêu cầu trả hàng/hoàn tiền hiển thị trạng thái Shopee đang xem xét thì khi nào người mua nhận được kết quả? | 1.000 | 0.890 | 1.000 | 0.200 | 5 |
| 3 | Nếu Shopee chấp nhận phương án Trả hàng & Hoàn tiền, người mua phải gửi trả hàng trong bao lâu? | 1.000 | 0.895 | 1.000 | 0.333 | 5 |

## Recommendations

- Prefer the config with higher average score for the final demo.
- Inspect bottom-3 questions and add/clean source documents where recall or precision is low.
- Keep the fallback rule based on original vector similarity, not the RRF score.
