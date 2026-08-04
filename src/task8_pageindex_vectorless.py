"""
Task 8 — PageIndex Vectorless RAG (Fallback).

Ý tưởng:
    - Truy vấn tài liệu theo cấu trúc Mục lục (Tree Hierarchy) thay vì chunking 800 ký tự.
    - Tự động fallback sang Structural Section Retrieval nếu API Key chưa khả dụng
      hoặc PageIndex API gặp lỗi.

Cài đặt:
    pip install pageindex fpdf2

Output format:
    List of {
        'content': str,
        'score': float,
        'metadata': dict,
        'source': 'pageindex'
    }
"""

import json
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CACHE_FILE = Path(__file__).parent.parent / "pageindex_doc_ids.json"
PDF_TMP_DIR = Path(__file__).parent.parent / "data" / "_tmp_pdf"


def _convert_md_to_pdf(md_path: Path, pdf_path: Path):
    """Chuyển đổi file Markdown sang PDF để upload lên PageIndex."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    content = md_path.read_text(encoding="utf-8", errors="ignore")
    # Lọc ký tự unicode tiếng Việt cho FPDF standard font
    clean_lines = []
    for line in content.split("\n"):
        # Chuyển đổi cơ bản để không nổ FPDF font
        clean_lines.append(line.encode("latin-1", "replace").decode("latin-1"))

    text = "\n".join(clean_lines)
    pdf.multi_cell(0, 8, text)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))


def upload_documents() -> list[str]:
    """
    Upload toàn bộ markdown documents lên PageIndex.
    Lưu danh sách doc_ids vào file pageindex_doc_ids.json.
    """
    if not PAGEINDEX_API_KEY:
        print("⚠ PAGEINDEX_API_KEY chưa được thiết lập trong .env")
        return []

    try:
        from pageindex import PageIndexClient, PageIndexAPIError

        client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
        doc_ids = []

        md_files = list(STANDARDIZED_DIR.rglob("*.md"))
        if not md_files:
            print("⚠ Không tìm thấy file markdown trong data/standardized/")
            return []

        PDF_TMP_DIR.mkdir(parents=True, exist_ok=True)

        for md_file in md_files:
            pdf_path = PDF_TMP_DIR / f"{md_file.stem}.pdf"
            _convert_md_to_pdf(md_file, pdf_path)

            try:
                resp = client.submit_document(str(pdf_path))
                doc_id = resp.get("doc_id") or resp.get("id")
                if doc_id:
                    doc_ids.append(doc_id)
                    print(f"  ✓ Uploaded: {md_file.name} -> {doc_id}")
            except PageIndexAPIError as e:
                print(f"  ✗ Lỗi upload {md_file.name}: {e}")

        if doc_ids:
            CACHE_FILE.write_text(json.dumps(doc_ids, indent=2), encoding="utf-8")
        return doc_ids

    except Exception as e:
        print(f"⚠ Không thể kết nối PageIndex API: {e}")
        return []


def _structural_fallback_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Fallback: Tìm kiếm theo cấu trúc tiêu đề (Headings / Sections) trực tiếp từ Markdown
    khi PageIndex API không khả dụng.
    """
    query_words = set(re.findall(r"\w+", query.lower()))
    results = []

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Phân tách tài liệu thành các Section theo `# Heading`
        sections = re.split(r"\n(?=#+\s)", content)
        for idx, sec in enumerate(sections):
            sec_clean = sec.strip()
            if not sec_clean:
                continue

            lines = sec_clean.split("\n")
            title = lines[0].lstrip("#").strip() if lines else md_file.stem
            sec_words = set(re.findall(r"\w+", sec_clean.lower()))

            match_count = len(query_words.intersection(sec_words))
            if match_count > 0:
                score = round(match_count / max(1, len(query_words)), 4)
                results.append(
                    {
                        "content": sec_clean,
                        "score": score,
                        "metadata": {
                            "source": md_file.name,
                            "section": title,
                            "section_index": idx,
                        },
                        "source": "pageindex",
                    }
                )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex API với fallback tự động.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'
        }
    """
    if not query or top_k <= 0:
        return []

    # 1. Thử gọi PageIndex API nếu có API key và cache doc_ids
    if PAGEINDEX_API_KEY and CACHE_FILE.exists():
        try:
            from pageindex import PageIndexClient

            client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
            doc_ids = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

            if doc_ids:
                results = []
                for doc_id in doc_ids[:3]:  # Query top 3 docs
                    resp = client.submit_query(doc_id=doc_id, query=query)
                    retrieval_id = resp.get("retrieval_id") or resp.get("id")

                    if not retrieval_id:
                        continue

                    # Poll status
                    for _ in range(5):
                        retrieval = client.get_retrieval(retrieval_id)
                        status = retrieval.get("status")
                        if status == "completed":
                            for node in retrieval.get("retrieved_nodes", []):
                                for group in node.get("relevant_contents", []):
                                    for item in group:
                                        results.append(
                                            {
                                                "content": item.get("relevant_content", ""),
                                                "score": 1.0,
                                                "metadata": {
                                                    "section": item.get("section_title", "")
                                                },
                                                "source": "pageindex",
                                            }
                                        )
                            break
                        time.sleep(1)

                if results:
                    return results[:top_k]

        except Exception as e:
            print(f"⚠ PageIndex API call failed ({e}), using structural fallback...")

    # 2. Structural Fallback Search
    return _structural_fallback_search(query, top_k=top_k)


if __name__ == "__main__":
    print("=== Task 8: PageIndex Vectorless RAG ===")
    if PAGEINDEX_API_KEY:
        print("Uploading documents to PageIndex...")
        upload_documents()

    print("\nExecuting test search:")
    test_results = pageindex_search("quy định trả hàng hoàn tiền", top_k=3)
    for r in test_results:
        print(f"[{r['source']}] Score: {r['score']:.2f} | {r['content'][:100]}...")
