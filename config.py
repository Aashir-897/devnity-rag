import os
from dotenv import load_dotenv

load_dotenv()

# ── Hugging Face (primary) ──────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_TEXT_MODEL = os.getenv("HF_TEXT_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
HF_VISION_MODEL = os.getenv("HF_VISION_MODEL", "meta-llama/Llama-3.2-11B-Vision-Instruct")

# ── Groq (fallback) ────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# ── Embeddings ────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

# ── ChromaDB ──────────────────────────────────────────
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")
CHROMA_COLLECTION = "pdf_chunks"

# ── Storage ───────────────────────────────────────────
BASE_DIR       = os.path.dirname(__file__)
TEMP_DIR       = os.path.join(BASE_DIR, "storage", "temp")
IMAGES_DIR     = os.path.join(BASE_DIR, "storage", "images")

# ── PDF Processing ────────────────────────────────────
MAX_PDF_SIZE_MB      = 30
MIN_IMAGE_WIDTH      = 100   # pixels — smaller images are decorative
MIN_IMAGE_HEIGHT     = 100
MAX_IMAGES_TOTAL     = 50    # max images to process (Vision API limit)
MAX_IMAGES_PER_PAGE  = 5     # max images per page
VISION_DELAY_SEC     = 1.5   # delay between Vision API calls (avoids 429)

# ── Chunking ──────────────────────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150

# ── Retrieval ─────────────────────────────────────────
TOP_K_CHUNKS = 5

# ── Flask ─────────────────────────────────────────────
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
PORT  = int(os.getenv("PORT", 5000))
HOST  = os.getenv("HOST", "127.0.0.1")
