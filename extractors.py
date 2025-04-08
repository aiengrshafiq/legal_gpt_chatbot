import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from bs4 import BeautifulSoup

def extract_text(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append((i + 1, text))
        if not pages:
            print(f"[OCR] No text found in {pdf_path}, running Tesseract OCR...")
            images = convert_from_path(pdf_path)
            for i, img in enumerate(images):
                text = pytesseract.image_to_string(img, lang='eng+ara')
                if text.strip():
                    pages.append((i + 1, text))
        return pages
    except Exception as e:
        print(f"Error extracting text: {e}")
        return []

def extract_text_from_html(html_path):
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
            soup = BeautifulSoup(html, "html.parser")

            title = soup.title.string.strip() if soup.title else "Untitled"
            source_url = "Unknown"

            for comment in soup.find_all(string=lambda text: isinstance(text, str) and "SOURCE_URL:" in text):
                if "SOURCE_URL:" in comment:
                    source_url = comment.split("SOURCE_URL:")[-1].strip()
                    break

            text = soup.get_text(separator="\n")
            return [(1, text, title, source_url)]

    except Exception as e:
        print(f"[ERROR] Couldn't extract HTML text from {html_path}: {e}")
        return []
