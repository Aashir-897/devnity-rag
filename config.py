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

# ── Database ──────────────────────────────────────────
DATABASE_URL   = os.getenv("DATABASE_URL", "")  # SQLite for dev, PostgreSQL for prod
SESSION_SECRET = os.getenv("SESSION_SECRET", "")

# ── Vector DB (legacy — ChromaDB, will be replaced) ──
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")
CHROMA_COLLECTION = "pdf_chunks"

# ── Qdrant ────────────────────────────────────────────
QDRANT_URL        = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY    = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = "pdf_chunks"

# ── DigitalOcean Spaces ──────────────────────────────
DO_SPACES_KEY      = os.getenv("DO_SPACES_KEY", "")
DO_SPACES_SECRET   = os.getenv("DO_SPACES_SECRET", "")
DO_SPACES_REGION   = os.getenv("DO_SPACES_REGION", "nyc3")
DO_SPACES_BUCKET   = os.getenv("DO_SPACES_BUCKET", "rag-devnity")
DO_SPACES_ENDPOINT = f"https://{DO_SPACES_REGION}.digitaloceanspaces.com"

# ── Storage ───────────────────────────────────────────
BASE_DIR       = os.path.dirname(__file__)
TEMP_DIR       = os.path.join(BASE_DIR, "storage", "temp")
IMAGES_DIR     = os.path.join(BASE_DIR, "storage", "images")
PDFS_DIR       = os.path.join(BASE_DIR, "storage", "pdfs")

# ── PDF Processing ────────────────────────────────────
MAX_PDF_SIZE_MB      = 30
MIN_IMAGE_WIDTH      = 100
MIN_IMAGE_HEIGHT     = 100
MAX_IMAGES_TOTAL     = 50
MAX_IMAGES_PER_PAGE  = 5
VISION_DELAY_SEC     = 1.5

# ── Chunking ──────────────────────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150

# ── Retrieval ─────────────────────────────────────────
TOP_K_CHUNKS = 5

# ── Email (SMTP) ──────────────────────────────────────
SMTP_SERVER   = os.getenv("SMTP_SERVER", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM     = os.getenv("MAIL_FROM", "noreply@devnity.ai")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Devnity AI")
APP_URL       = os.getenv("APP_URL", "http://localhost:5000")

# ── Flask ─────────────────────────────────────────────
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
PORT  = int(os.getenv("PORT", 5000))
HOST  = os.getenv("HOST", "127.0.0.1")
