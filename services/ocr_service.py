"""
OCR Service — scanned PDFs ke liye PaddleOCR use karta hai
"""
import os
import fitz  # PyMuPDF — page ko image mein convert karne ke liye
from config import TEMP_DIR


# Lazy load — pehli baar use pe initialize hoga (slow startup avoid)
_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr


# ── Main Functions ────────────────────────────────────────────────────────────

def run_ocr_on_image(image_path: str) -> str:
    """
    Ek image file pe OCR run karta hai.
    Returns extracted text string.
    """
    try:
        ocr = get_ocr()
        result = ocr.ocr(image_path, cls=True)
        return parse_ocr_result(result)
    except Exception as e:
        print(f"⚠️  OCR error on {image_path}: {e}")
        return ""


def run_ocr_on_pdf_page(pdf_path: str, page_num: int) -> str:
    """
    PDF ke ek page ko image mein convert karke OCR run karta hai.
    Scanned PDFs ke liye use hota hai.
    """
    temp_image_path = os.path.join(TEMP_DIR, f"ocr_page_{page_num}.png")

    try:
        # Page ko image mein convert karo
        doc  = fitz.open(pdf_path)
        page = doc[page_num - 1]

        # 2x zoom for better OCR accuracy
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        pix.save(temp_image_path)
        doc.close()

        # OCR run karo
        text = run_ocr_on_image(temp_image_path)
        return text

    except Exception as e:
        print(f"⚠️  OCR page error (page {page_num}): {e}")
        return ""

    finally:
        # Temp file delete karo
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)


def run_ocr_on_full_pdf(pdf_path: str) -> dict:
    """
    Poore PDF pe page by page OCR run karta hai.
    Returns: {page_num: text}
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    results = {}
    print(f"🔍 OCR starting on {total_pages} pages...")

    for page_num in range(1, total_pages + 1):
        print(f"   OCR page {page_num}/{total_pages}")
        text = run_ocr_on_pdf_page(pdf_path, page_num)
        results[page_num] = text

    return results


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_ocr_result(result) -> str:
    """PaddleOCR result ko clean text string mein convert karta hai."""
    if not result:
        return ""

    lines = []
    for page_result in result:
        if not page_result:
            continue
        for line in page_result:
            # line format: [[bbox], (text, confidence)]
            if line and len(line) >= 2:
                text, confidence = line[1]
                if confidence > 0.6:  # Low confidence text ignore
                    lines.append(text)

    return "\n".join(lines)
