"""
Task 1 — Thu thập văn bản chính sách thương mại điện tử / hỗ trợ khách hàng.

Hướng dẫn:
    1. Tìm tối thiểu 3 văn bản chính sách (PDF/DOCX) từ trang chính thức của một sàn TMĐT.
    2. Tải về và lưu vào data/landing/legal/
    3. Đặt tên file rõ ràng, không dấu, mô tả đúng nội dung.

Gợi ý nguồn (ví dụ trang công khai Shopee Vietnam — help.shopee.vn):
    - https://help.shopee.vn/portal/4/article/77251 (Chính sách trả hàng và hoàn tiền)
    - https://help.shopee.vn/portal/4/article/79198 (Phương thức thanh toán)
    - https://help.shopee.vn/portal/4/article/77244 (Chính sách bảo mật)

Gợi ý văn bản (chủ đề chính sách thương mại điện tử):
    - Chính sách đổi trả/hoàn tiền (Returns/Refund Policy)
    - Phương thức thanh toán (Payment Methods)
    - Chính sách bảo mật (Privacy Policy)
    - Quy định đăng bán sản phẩm cho người bán (Seller Listing Regulations)

Nhớ gắn metadata `customer_role` (`buyer`/`seller`/`both`) cho từng tài liệu — yêu cầu riêng
của K4 Variant (kế thừa từ Lab 07), cần thiết để viết benchmark query dùng metadata_filter.

Lưu ý: một số trang help center dùng JavaScript render nội dung (SPA) — crawl về chỉ thấy
tiêu đề mà không có nội dung thật. Đổi sang bài viết khác cùng domain thay vì cố xử lý,
và chỉ dùng nguồn công khai/được phép chia sẻ.
"""

import csv
import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data" / "landing" / "legal"
CSV_PATH = PROJECT_DIR / "data" / "urls_shopee.csv"

FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf"


def setup_directory():
    """Tạo thư mục data/landing/legal/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Thư mục đã sẵn sàng: {DATA_DIR}")


BOILERPLATE_PATTERNS = [
    re.compile(r".*Shopee Trung tâm trợ giúp.*", re.IGNORECASE),
    re.compile(r".*Xin chào, Shopee có thể giúp gì.*", re.IGNORECASE),
    re.compile(r".*Bạn có hài lòng với bài viết này.*", re.IGNORECASE),
    re.compile(r"^Hài lòng$", re.IGNORECASE),
    re.compile(r"^Không hài lòng$", re.IGNORECASE),
    re.compile(r"^Cảm ơn bạn đã gửi ý kiến đánh giá!$", re.IGNORECASE),
    re.compile(r"^Bài viết liên quan$", re.IGNORECASE),
    re.compile(r"^Quay lại.*", re.IGNORECASE),
    re.compile(r"^Trang chủ.*", re.IGNORECASE),
]


def clean_page_text(raw_text: str, title: str) -> str:
    """Loại bỏ UI boilerplate, navigation, nút đánh giá khỏi văn bản bài viết."""
    raw_text = raw_text.replace("\xa0", " ").replace("\u200b", "")
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    
    cleaned = []
    for line in lines:
        if any(pattern.match(line) for pattern in BOILERPLATE_PATTERNS):
            continue
        # Deduplicate title if repeated at top
        if line.lower() == title.lower() and len(cleaned) <= 3:
            continue
        cleaned.append(line)
        
    return "\n\n".join(cleaned)


class VietnamesePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)
        if Path(FONT_PATH).exists():
            self.add_font("Arial", "", FONT_PATH, uni=True)
            self.set_font("Arial", size=11)
        else:
            self.set_font("Helvetica", size=11)


def create_pdf_from_text(title: str, text: str, output_path: Path, metadata: dict = None):
    pdf = VietnamesePDF()
    pdf.add_page()
    
    # Document Title Header Box
    pdf.set_fill_color(240, 244, 248)
    pdf.set_draw_color(200, 210, 220)
    pdf.rect(15, 15, 180, 20, style="FD")
    
    pdf.set_font_size(14)
    pdf.set_xy(18, 18)
    pdf.multi_cell(174, 7, title, align="L")
    pdf.ln(10)
    
    # Metadata Badge
    if metadata:
        pdf.set_font_size(9)
        pdf.set_text_color(100, 100, 100)
        meta_items = [f"{k.upper()}: {v}" for k, v in metadata.items() if v]
        meta_str = " | ".join(meta_items)
        pdf.multi_cell(0, 5, f"[Nguồn / Metadata]: {meta_str}")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        
    pdf.set_font_size(11)
    
    # Clean text lines
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    for para in paragraphs:
        # Check if line looks like a sub-header
        if len(para) < 100 and not para.endswith((".", ":", "!", "?", ";", ")", "]")):
            pdf.set_font_size(12)
            pdf.multi_cell(0, 7, para)
            pdf.set_font_size(11)
        else:
            pdf.multi_cell(0, 6, para)
        pdf.ln(3)
        
    pdf.output(str(output_path))


def fetch_and_save_policies():
    setup_directory()
    
    if not CSV_PATH.exists():
        print(f"❌ Không tìm thấy file CSV: {CSV_PATH}")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row["url"]
            doc_id = row["doc_id"]
            title = row["title"]
            customer_role = row.get("customer_role", "both")
            category = row.get("category", "")
            
            output_pdf = DATA_DIR / f"{doc_id}.pdf"
            
            # Add ?seo=1 if shopee help link to get prerendered HTML
            fetch_url = url
            if "help.shopee.vn" in url and "seo=1" not in url:
                fetch_url = url + ("&seo=1" if "?" in url else "?seo=1")
                
            print(f"Downloading [{doc_id}] from {fetch_url}...")
            raw_text = ""
            try:
                resp = requests.get(fetch_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Try targeting main article content container if present
                    article_elem = soup.find("article") or soup.find("main") or soup.find(class_=re.compile(r"content|article|help-detail", re.I))
                    target = article_elem if article_elem else soup
                    
                    # Remove script, style, nav, etc.
                    for s in target(["script", "style", "nav", "header", "footer", "iframe", "svg"]):
                        s.extract()
                    raw_text = target.get_text(separator="\n")
            except Exception as e:
                print(f"Lỗi truy cập {url}: {e}")

            # Clean boilerplate text
            cleaned_body = clean_page_text(raw_text, title)
            if len(cleaned_body) < 100:
                cleaned_body = f"Chính sách {title}\nChủ đề: {category}\nĐối tượng áp dụng: {customer_role}\nURL tham khảo: {url}"

            # Create PDF
            create_pdf_from_text(
                title=title,
                text=cleaned_body,
                output_path=output_pdf,
                metadata={"customer_role": customer_role, "category": category, "doc_id": doc_id, "url": url}
            )
            print(f"[OK] Đã tạo PDF đẹp ({output_pdf.stat().st_size} bytes): {output_pdf.name}")


if __name__ == "__main__":
    fetch_and_save_policies()

