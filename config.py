import os
from dotenv import load_dotenv

load_dotenv()

# ── Groq API ──────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"       # Summary, MCQs, Q&A
GROQ_VISION_MODEL = "llama-3.2-11b-vision-preview" # Image understanding

# ── Embeddings ────────────────────────────────────────
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

# ── ChromaDB ──────────────────────────────────────────
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")
CHROMA_COLLECTION = "pdf_chunks"

# ── Storage ───────────────────────────────────────────
BASE_DIR       = os.path.dirname(__file__)
TEMP_DIR       = os.path.join(BASE_DIR, "storage", "temp")
IMAGES_DIR     = os.path.join(BASE_DIR, "storage", "images")

# ── PDF Processing ────────────────────────────────────
MAX_PDF_SIZE_MB   = 50
MIN_IMAGE_WIDTH   = 100   # pixels — smaller images are decorative
MIN_IMAGE_HEIGHT  = 100

# ── Chunking ──────────────────────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150

# ── Retrieval ─────────────────────────────────────────
TOP_K_CHUNKS = 5

# ── Flask ─────────────────────────────────────────────
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
PORT  = int(os.getenv("PORT", 5000))
