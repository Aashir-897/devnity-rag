"""
PDF Processor — text + image extract karta hai PyMuPDF se
"""
import os
import re
import fitz   # PyMuPDF
from config import TEMP_DIR, IMAGES_DIR, MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT


# ── Main Entry Point ──────────────────────────────────────────────────────────

def process_pdf(pdf_path: str) -> dict:
    """
    PDF se text aur images extract karta hai.
    Returns:
        {
            "pages": [{"page_num": 1, "text": "...", "images": ["path1", ...]}, ...],
            "full_text": "...",
            "total_pages": N
        }
    """
    doc = fitz.open(pdf_path)
    pages = []
    full_text_parts = []

    for page_num, page in enumerate(doc, start=1):
        # 1. Text extract
        raw_text = page.get_text("text")
        clean = clean_text(raw_text)

        # 2. Images extract
        image_paths = extract_images_from_page(doc, page, page_num)

        pages.append({
            "page_num": page_num,
            "text": clean,
            "images": image_paths
        })

        if clean:
            full_text_parts.append(f"[Page {page_num}]\n{clean}")

    doc.close()

    return {
        "pages": pages,
        "full_text": "\n\n".join(full_text_parts),
        "total_pages": len(pages)
    }


# ── Image Extraction ──────────────────────────────────────────────────────────

def extract_images_from_page(doc, page, page_num: int) -> list[str]:
    """Page se meaningful images extract karke save karta hai."""
    saved_paths = []
    image_list = page.get_images(full=True)

    for img_index, img_ref in enumerate(image_list):
        xref = img_ref[0]
        try:
            base_image = doc.extract_image(xref)
            width  = base_image["width"]
            height = base_image["height"]

            # Choti/decorative images skip karo
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                continue

            img_bytes = base_image["image"]
            ext       = base_image["ext"]
            filename  = f"page{page_num}_img{img_index}.{ext}"
            save_path = os.path.join(IMAGES_DIR, filename)

            with open(save_path, "wb") as f:
                f.write(img_bytes)

            saved_paths.append(save_path)

        except Exception as e:
            print(f"⚠️  Image extract error (page {page_num}, img {img_index}): {e}")
            continue

    return saved_paths


# ── Text Cleaning ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Raw PDF text clean karta hai."""
    if not text:
        return ""

    # Extra whitespace / newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    # Page numbers (standalone numbers on a line)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Common header/footer patterns
    text = re.sub(r'(confidential|all rights reserved|www\.\S+)', '',
                  text, flags=re.IGNORECASE)

    return text.strip()


# ── Helper ────────────────────────────────────────────────────────────────────

def is_text_empty(text: str) -> bool:
    """Check karta hai ke meaningful text hai ya nahi."""
    return len(text.strip()) < 50
