# Báo Cáo Cá Nhân - Nguyễn Tuấn Đức

## 1. Thông Tin Cá Nhân

| Mục | Thông tin |
|---|---|
| Họ và tên | Nguyễn Tuấn Đức |
| MSSV | 2A202601380 |
| Vai trò trong nhóm | Nhóm trưởng, RAG Architect |
| Chủ đề lab | E-commerce Support RAG Chatbot |
| Domain dữ liệu | Chính sách thương mại điện tử và hỗ trợ khách hàng Shopee Vietnam |

## 2. Phạm Vi Phụ Trách

Trong bài lab, tôi phụ trách vai trò điều phối nhóm và thiết kế kiến trúc RAG tổng thể. Trọng tâm công việc là đảm bảo các phần dữ liệu, chunking, indexing, retrieval, generation, demo UI và evaluation được nối với nhau thành một pipeline có thể chạy end-to-end.

Các phần chính tôi phụ trách:

- Thiết kế kiến trúc Hybrid RAG.
- Chọn cấu hình model và embedding phù hợp với chi phí.
- Rà soát logic retrieval pipeline Task 9.
- Rà soát generation có citation Task 10.
- Điều phối việc tích hợp demo UI và evaluation.
- Kiểm tra các tiêu chí pass checkpoint cá nhân và nhóm.

## 3. Đóng Góp Kỹ Thuật

### 3.1 Kiến trúc RAG

Pipeline được thiết kế theo hướng:

```text
User question
-> Semantic search trên ChromaDB
-> BM25 lexical search
-> RRF reranking
-> Kiểm tra confidence/cosine threshold
-> PageIndex fallback khi thiếu bằng chứng
-> Reorder context
-> LLM generation có citation
```

Thiết kế này giúp hệ thống kết hợp được ưu điểm của semantic search và keyword search. Semantic search phù hợp với câu hỏi diễn đạt tự nhiên, còn BM25 giúp bắt các cụm từ chính xác như "trả hàng", "hoàn tiền", "Shopee Mall", "đồng kiểm".

### 3.2 Cấu hình model

Do model local khó setup và tốn tài nguyên, nhóm sử dụng OpenAI:

- Embedding: `text-embedding-3-small`
- Generation/evaluation judge: `gpt-5-nano`

Lựa chọn này giúp giảm chi phí, dễ chạy trên máy cá nhân và vẫn đủ tốt cho dữ liệu tiếng Việt trong phạm vi lab.

### 3.3 Retrieval pipeline

Ở Task 9, pipeline dùng ngưỡng `0.48` trên điểm cosine gốc của dense retrieval. Đây là điểm quan trọng vì không được so sánh ngưỡng này với điểm RRF. Điểm RRF chỉ dùng để gộp thứ hạng và thường rất nhỏ, nên nếu dùng RRF để quyết định fallback sẽ sai logic.

Logic mong muốn:

```text
if dense_results[0]["score"] < 0.48:
    use PageIndex fallback
else:
    use hybrid RRF results
```

### 3.4 Generation có citation

Ở Task 10, tôi rà soát phần sinh câu trả lời để đảm bảo:

- Câu trả lời chỉ dựa trên retrieved contexts.
- Có citation/source trong câu trả lời.
- Nếu thiếu bằng chứng thì không bịa.
- Nếu câu hỏi ngoài phạm vi Shopee thì yêu cầu người dùng hỏi lại hoặc cung cấp thêm nguồn.

### 3.5 Demo và observability

Phần demo được thiết kế để thể hiện rõ pipeline RAG khi chạy:

- Có chọn sẵn golden testcase.
- Có chỉnh `top_k`, threshold và bật/tắt rerank.
- Có streaming answer.
- Có agent trace hiển thị ngay trong câu trả lời.
- Có danh sách retrieval sources kèm `vector sim`, `RRF`, raw score, role và document type.

## 4. Kết Quả Kiểm Thử

### 4.1 Individual test

Lệnh kiểm thử:

```powershell
python -m pytest tests/test_individual.py -v
```

Kết quả mục tiêu của lab:

```text
35 passed
```

Kết quả này tương ứng hoàn thành phần cá nhân 50/50 điểm theo checkpoint CP4.

### 4.2 Group evaluation

Nhóm xây dựng bộ golden dataset và chạy RAGAS:

```powershell
python -m group_project.evaluation.eval_pipeline
```

Kết quả được lưu tại:

```text
group_project/evaluation/results.md
```

Các chỉ số đánh giá gồm:

- Faithfulness
- Answer relevancy
- Context recall
- Context precision

## 5. Kết Quả RAGAS Tóm Tắt

Theo kết quả trong `group_project/evaluation/results.md`, cấu hình Hybrid RAG có kết quả trung bình tốt hơn nhẹ so với cấu hình không rerank.

| Metric | Hybrid + RRF | No Rerank |
|---|---:|---:|
| Faithfulness | 0.992 | 0.971 |
| Answer relevancy | 0.860 | 0.866 |
| Context recall | 0.933 | 0.933 |
| Context precision | 0.745 | 0.752 |
| Average | 0.883 | 0.881 |

Nhận xét: Hybrid + RRF cải thiện rõ nhất ở Faithfulness, tức câu trả lời bám sát tài liệu hơn. Context precision chưa vượt cấu hình no-rerank, cho thấy vẫn có thể tối ưu thêm phần lọc context hoặc threshold.

## 6. Bài Học Rút Ra

Qua lab này, tôi hiểu rõ hơn cách xây dựng một hệ thống RAG thực tế không chỉ dừng ở vector search. Một pipeline tốt cần có dữ liệu sạch, chunking hợp lý, retrieval kết hợp nhiều chiến lược, fallback khi thiếu bằng chứng và evaluation định lượng.

Phần quan trọng nhất với vai trò RAG Architect là giữ cho pipeline có thể giải thích được: biết vì sao một nguồn được chọn, điểm confidence là gì, khi nào nên fallback và khi nào không nên trả lời.

## 7. Câu Hỏi Bonus Có Thể Trình Bày

| Câu hỏi | Câu trả lời ngắn |
|---|---|
| Vì sao cần `customer_role`? | Để phân biệt chính sách cho buyer, seller hoặc cả hai, tránh lấy nhầm nguồn khi trả lời. |
| Vì sao dùng OpenAI embedding? | `text-embedding-3-small` rẻ, ổn định, dễ setup hơn model local và đủ tốt cho dữ liệu tiếng Việt của lab. |
| Vì sao cần BM25 nếu đã có vector search? | BM25 bắt từ khóa chính xác tốt hơn, còn semantic search bắt ý nghĩa; hybrid giúp tăng recall. |
| Vì sao dùng RRF? | Cosine và BM25 khác thang điểm, RRF gộp theo thứ hạng nên công bằng hơn. |
| Vì sao threshold `0.48`? | Đây là ngưỡng trên cosine gốc để phát hiện khi vector search thiếu bằng chứng, từ đó fallback hoặc từ chối trả lời. |
| Vì sao không dùng RRF score làm confidence? | RRF chỉ là điểm gộp thứ hạng, thường rất nhỏ và không phản ánh độ tương đồng semantic thật. |
| Vì sao reorder context? | Đưa đoạn quan trọng ra đầu/cuối prompt để giảm lost-in-the-middle. |
| Vì sao cần citation? | Để kiểm chứng nguồn, minh bạch câu trả lời và giảm hallucination. |

## 8. Checklist Cá Nhân

| Hạng mục | Trạng thái |
|---|---|
| Nắm yêu cầu Task 1-10 | Hoàn thành |
| Thiết kế kiến trúc Hybrid RAG | Hoàn thành |
| Rà soát Task 9 retrieval pipeline | Hoàn thành |
| Rà soát Task 10 generation citation | Hoàn thành |
| Kiểm tra pass individual tests | Hoàn thành |
| Điều phối demo UI và RAGAS evaluation | Hoàn thành |
| Viết báo cáo cá nhân | Hoàn thành |
