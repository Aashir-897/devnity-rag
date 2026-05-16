"""Route PDF images to OCR or Groq Vision for text descriptions."""
import os
from services.groq_service import understand_image
from services.ocr_service  import run_ocr_on_image
from config import MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT


def process_pdf_images(pages: list[dict]) -> list[dict]:
    """Process all images across all PDF pages."""
    image_descriptions = []

    for page in pages:
        page_num = page["page_num"]
        images   = page.get("images", [])

        for image_path in images:
            if not os.path.exists(image_path):
                continue

            print(f"Processing image: {os.path.basename(image_path)}")

            result = process_single_image(
                image_path=image_path,
                page_context=page.get("text", ""),
                page_num=page_num
            )

            if result:
                image_descriptions.append(result)

    return image_descriptions


def process_single_image(image_path: str, page_context: str = "", page_num: int = 0) -> dict | None:
    """Process a single image — OCR first, fall back to Vision."""
    try:
        ocr_text = run_ocr_on_image(image_path)

        if ocr_text and len(ocr_text.strip()) > 30:
            return {
                "page_num": page_num,
                "image_path": image_path,
                "type": "ocr",
                "description": f"[Image text - Page {page_num}]: {ocr_text.strip()}"
            }
        else:
            vision_desc = understand_image(image_path, context=page_context)

            if vision_desc:
                return {
                    "page_num": page_num,
                    "image_path": image_path,
                    "type": "vision",
                    "description": f"[Image description - Page {page_num}]: {vision_desc.strip()}"
                }

    except Exception as e:
        print(f"Image processing error ({os.path.basename(image_path)}): {e}")

    return None


def cleanup_images(image_paths: list[str]):
    """Delete processed image files from disk."""
    for path in image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Could not delete {path}: {e}")
