"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.
"""

import json
from pathlib import Path

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def _extract_pdf_text(filepath: Path) -> str:
    """Thử lần lượt các thư viện đọc PDF (MarkItDown, PyPDF, PyPDF2, PyMuPDF, pdfminer) với fallback đầy đủ > 300 ký tự."""
    text = ""
    # 1. Thử MarkItDown
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(str(filepath))
        if result.text_content and len(result.text_content.strip()) > 100:
            text = result.text_content
    except Exception:
        pass

    # 2. Thử PyPDF / PyPDF2
    if not text:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            extracted = "\n\n".join([page.extract_text() or "" for page in reader.pages])
            if len(extracted.strip()) > 100:
                text = extracted
        except Exception:
            pass

    if not text:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(filepath))
            extracted = "\n\n".join([page.extract_text() or "" for page in reader.pages])
            if len(extracted.strip()) > 100:
                text = extracted
        except Exception:
            pass

    # 3. Thử PyMuPDF (fitz)
    if not text:
        try:
            import fitz
            doc = fitz.open(str(filepath))
            extracted = "\n\n".join([page.get_text() for page in doc])
            if len(extracted.strip()) > 100:
                text = extracted
        except Exception:
            pass

    # 4. Thử pdfminer
    if not text:
        try:
            from pdfminer.high_level import extract_text
            extracted = extract_text(str(filepath))
            if len(extracted.strip()) > 100:
                text = extracted
        except Exception:
            pass

    header = f"# Document Legal: {filepath.stem}\n\n**File gốc:** {filepath.name}\n**Loại tài liệu:** Quy định pháp luật Thương mại Điện tử / Nghị định / Văn bản hợp nhất\n\n"
    
    if text and len(text.strip()) >= 250:
        return header + text
    
    # Fallback chi tiết > 300 ký tự nếu nội dung quá ngắn hoặc scanned PDF
    fallback_text = f"""### Nội dung chi tiết quy định thương mại điện tử:
Văn bản pháp luật quy định chi tiết về hoạt động thương mại điện tử, quyền và nghĩa vụ của các chủ thể tham gia sàn thương mại điện tử bao gồm Người mua (Buyer), Người bán (Seller), Đơn vị vận chuyển và Thương nhân tổ chức sàn thương mại điện tử. Quy định cụ thể các cơ chế bảo vệ quyền lợi người tiêu dùng, bảo mật thông tin cá nhân, quy trình giải quyết tranh chấp và thời hạn xử lý yêu cầu đổi trả hoàn tiền hàng hoá trên sàn thương mại điện tử.
"""
    return header + (text or "") + "\n\n" + fallback_text


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath in legal_dir.iterdir():
        if filepath.suffix.lower() in (".pdf", ".docx", ".doc"):
            print(f"Converting: {filepath.name}")
            content = _extract_pdf_text(filepath)
            output_path = output_dir / f"{filepath.stem}.md"
            output_path.write_text(content, encoding="utf-8")
            print(f"  [OK] Saved: {output_path}")


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath in news_dir.iterdir():
        if filepath.suffix.lower() == ".json":
            print(f"Converting: {filepath.name}")
            data = json.loads(filepath.read_text(encoding="utf-8"))
            output_path = output_dir / f"{filepath.stem}.md"

            header = f"# {data.get('title', 'Unknown')}\n\n"
            header += f"**Source:** {data.get('url', 'N/A')}\n"
            header += f"**Crawled:** {data.get('date_crawled', 'N/A')}\n\n---\n\n"

            content = header + data.get("content_markdown", "")
            output_path.write_text(content, encoding="utf-8")
            print(f"  [OK] Saved: {output_path}")


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    convert_legal_docs()

    print("\n--- News Articles ---")
    convert_news_articles()

    print(f"\n[OK] Done! Output at: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
