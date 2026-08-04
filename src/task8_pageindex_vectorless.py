"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.

Cài đặt:
    pip install pageindex

Hướng dẫn:
    1. Đăng ký account tại pageindex.ai
    2. Lấy API key
    3. Upload documents
    4. Query sử dụng PageIndex API

Lưu ý: API `/retrieval` của PageIndex hiện đã deprecated (vẫn hoạt động, nhưng response
có field "deprecation" cảnh báo) và trả kết quả trong "retrieved_nodes" — mỗi node có
"relevant_contents": list[list[{section_title, relevant_content}]]. In response thật ra
(json.dumps(...)) trước khi viết logic parse, đừng đoán schema từ ví dụ code cũ.
"""

import json
import time
from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
PDF_CACHE_DIR = Path(__file__).parent.parent / "data" / "pageindex_pdfs"
DOC_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "pageindex_doc_ids.json"

# PageIndex chỉ nhận PDF, không nhận .md — dùng font Arial của Windows để giữ
# đúng dấu tiếng Việt khi convert (Helvetica core font không hỗ trợ unicode).
WINDOWS_UNICODE_FONT = Path(r"C:\Windows\Fonts\arial.ttf")


def _load_registry() -> dict:
    if DOC_REGISTRY_PATH.exists():
        return json.loads(DOC_REGISTRY_PATH.read_text(encoding="utf-8"))
    return {}


def _save_registry(registry: dict) -> None:
    DOC_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _markdown_to_pdf(md_path: Path, pdf_path: Path) -> None:
    """Convert 1 file markdown sang PDF đơn giản (chỉ cần đủ text cho PageIndex OCR)."""
    import textwrap

    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    if WINDOWS_UNICODE_FONT.exists():
        pdf.add_font("Unicode", "", str(WINDOWS_UNICODE_FONT))
        pdf.set_font("Unicode", size=11)
    else:
        pdf.set_font("Helvetica", size=11)

    # Wrap thủ công bằng textwrap trước (nhanh, O(n)) thay vì để fpdf tự đo bề rộng
    # từng ký tự — với dòng dài (bài báo không xuống dòng) fpdf multi_cell dò kích
    # thước bằng WORD/CHAR mode có thể rất chậm.
    text = md_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        wrapped = textwrap.wrap(line, width=100, break_long_words=True) or [""]
        for chunk in wrapped:
            pdf.cell(0, 6, chunk, new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(pdf_path))


def upload_documents() -> dict:
    """
    Upload toàn bộ markdown documents trong data/standardized/ lên PageIndex.

    Mỗi file .md được convert sang PDF (fpdf2) trước khi submit, vì PageIndex chỉ
    nhận PDF. doc_id trả về được lưu vào data/pageindex_docs.json để pageindex_search()
    dùng lại giữa các lần chạy, và các file đã upload sẽ được bỏ qua ở lần chạy sau.

    Returns:
        dict mapping "đường dẫn tương đối .md" -> doc_id
    """
    from pageindex.client import PageIndexClient, PageIndexAPIError

    if not PAGEINDEX_API_KEY:
        raise RuntimeError("PAGEINDEX_API_KEY chưa được set trong .env")

    client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    registry = _load_registry()
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        key = str(md_file.relative_to(STANDARDIZED_DIR))
        if key in registry:
            print(f"  = Skip (đã upload): {md_file.name} -> {registry[key]}")
            continue

        pdf_path = PDF_CACHE_DIR / f"{md_file.stem}.pdf"
        _markdown_to_pdf(md_file, pdf_path)

        try:
            resp = client.submit_document(str(pdf_path))
        except PageIndexAPIError as exc:
            print(f"  x Upload thất bại: {md_file.name} ({exc})")
            continue

        doc_id = resp.get("doc_id") or resp.get("id")
        registry[key] = doc_id
        print(f"  v Uploaded: {md_file.name} -> {doc_id}")

    _save_registry(registry)
    return registry


def _wait_until_ready(client, doc_id: str, timeout: int = 300, interval: int = 5) -> bool:
    """Poll get_tree() cho đến khi document sẵn sàng retrieval hoặc hết timeout."""
    elapsed = 0
    while elapsed < timeout:
        if client.is_retrieval_ready(doc_id):
            return True
        time.sleep(interval)
        elapsed += interval
    return False


def _poll_retrieval(client, retrieval_id: str, timeout: int = 60, interval: int = 3) -> dict:
    """Poll get_retrieval() cho đến khi status hoàn tất hoặc hết timeout."""
    retrieval = client.get_retrieval(retrieval_id)
    elapsed = 0
    while retrieval.get("status") not in ("completed", "failed") and elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
        retrieval = client.get_retrieval(retrieval_id)
    return retrieval


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    from pageindex.client import PageIndexClient, PageIndexAPIError

    if not PAGEINDEX_API_KEY:
        raise RuntimeError("PAGEINDEX_API_KEY chưa được set trong .env")

    client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    registry = _load_registry()
    if not registry:
        print("  ⚠ Chưa có document nào được upload — gọi upload_documents() trước.")
        return []

    results = []
    for filename, doc_id in registry.items():
        if not _wait_until_ready(client, doc_id, timeout=60):
            print(f"  ⚠ Document chưa sẵn sàng retrieval, bỏ qua: {filename} ({doc_id})")
            continue

        try:
            submit_resp = client.submit_query(doc_id=doc_id, query=query)
            retrieval_id = submit_resp.get("retrieval_id") or submit_resp.get("id")
            retrieval = _poll_retrieval(client, retrieval_id)
        except PageIndexAPIError as exc:
            print(f"  x Query thất bại trên {filename}: {exc}")
            continue

        # In response thật trước khi parse — đừng đoán schema từ ví dụ code cũ.
        print(f"  [debug] raw retrieval response ({filename}):")
        print(json.dumps(retrieval, ensure_ascii=False, indent=2)[:2000])

        for node in retrieval.get("retrieved_nodes", []):
            for group in node.get("relevant_contents", []):
                for item in group:
                    results.append(
                        {
                            "content": item.get("relevant_content", ""),
                            "score": 0.0,  # PageIndex không trả score — gán lại theo rank bên dưới
                            "metadata": {
                                "section": item.get("section_title"),
                                "source_file": filename,
                                "doc_id": doc_id,
                            },
                            "source": "pageindex",
                        }
                    )

    # PageIndex không trả điểm số trực tiếp -> gán score giảm dần theo thứ hạng trả về
    for rank, item in enumerate(results):
        item["score"] = round(1.0 / (rank + 1), 4)

    return results[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("danh sách sản phẩm cấm đăng bán", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
