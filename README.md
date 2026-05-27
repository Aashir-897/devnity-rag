---
title: rag-devnity
emoji: 📘
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: app.py
pinned: false
---

# rag-devnity — Intelligent PDF AI System

Upload PDFs, get AI summaries, generate MCQs/quiz, ask questions via RAG chat, and review performance analytics.

## Features

- **PDF Text Extraction** — extracts text and images from PDFs via PyMuPDF
- **OCR for Scanned Pages** — automatic PaddleOCR fallback when pages lack extractable text
- **Image / Chart Analysis** — routes document images to a Vision LLM for description
- **RAG Q&A** — ask natural-language questions; answers are grounded in retrieved chunks
- **PDF.js Document Viewer** — inline PDF rendering with page-level line highlighting
- **MCQ & Quiz Generation** — generate and take timed quizzes; results scored and reviewed
- **Q&A / Chat Persistence** — Q&A pairs and chat history saved to localStorage, restored on reload
- **Real-Time Progress** — SSE stream shows processing status (Extract → OCR → Images → Embeddings → Summary → Done)
- **Performance Analytics** — score dial, topic breakdown charts, question-by-question review with AI remediation notes

## Quick Start

```powershell
git clone <repo>
cd rag-devnity
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `.env` (gitignored) in the project root:

```ini
GROQ_API_KEY=gsk_...
HF_TOKEN=hf_...          # optional — primary LLM provider
```

Run the app:

```powershell
.\venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000` in a browser.

## API Endpoints

| Route | Method | Description |
|---|---|---|
| `/` | GET | Dashboard with stats, upload zone, recent docs |
| `/dashboard` | GET | My Documents — document listing with search/filter/actions |
| `/upload` | POST | Upload a PDF — returns `pdf_id` immediately |
| `/progress/<pdf_id>` | GET | SSE stream of processing progress |
| `/study/<pdf_id>` | GET | Study room with PDF.js viewer, summary, Q&A, takeaways, chat |
| `/quiz/<pdf_id>` | GET | Quiz page with timer, question navigation, flagging |
| `/quiz/submit` | POST | Submit quiz answers; returns scored results |
| `/mcqs` | POST | Generate MCQs from a processed PDF |
| `/qa` | POST | Generate Q&A pairs from a processed PDF |
| `/chat` | POST | Ask a question about a processed PDF |
| `/pdf/<pdf_id>` | DELETE | Delete a PDF and its embedded chunks |
| `/mock-test` | GET | Quick redirect to last opened document's quiz |
| `/analytics-page` | GET | Quiz results: score dial, topic charts, question review |
| `/health` | GET | Health check (returns document count) |

## Architecture

```
┌──────────┐    ┌────────────┐    ┌──────────────┐
│  Browser │◄──►│  Flask app │◄──►│  ChromaDB    │
│  (UI)    │    │  (app.py)  │    │  (vector_db/)│
└──────────┘    └─────┬──────┘    └──────────────┘
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
     ┌────────────┐     ┌──────────────┐
     │ PyMuPDF    │     │ PaddleOCR    │
     │ (text+img) │     │ (scanned pg) │
     └────────────┘     └──────────────┘
            │
            ▼
     ┌──────────────────────┐
     │ LLM (HF → Groq)     │
     │ Summary / MCQs / QA │
     │ Vision (images)     │
     └──────────────────────┘
```

### Key Design Points

- **In-memory store**: `pdf_store` is a plain dict — data is lost on restart
- **Paragraph-aware chunking**: splits by `\n\n`, groups paragraphs up to `CHUNK_SIZE`, never cuts mid-paragraph
- **Lazy-loaded services**: embedding model (BGE), PaddleOCR, and ChromaDB initialize on first use; the first request after startup is slow
- **Dual LLM routing**: primary calls go through Hugging Face Router (`https://router.huggingface.co/v1`) using the OpenAI SDK; model names with `:groq` suffix route to Groq infra. Falls back to direct Groq SDK on failure
- **All config tunables** (chunk size, image thresholds, model selection, etc.) are in `config.py` — no hard-coded magic numbers

## Tech Stack

| Category | Tools |
|---|---|
| Backend | Python, Flask, Flask-CORS, SQLAlchemy |
| PDF Processing | PyMuPDF (fitz) |
| OCR | PaddleOCR + PaddlePaddle |
| Embeddings | BAAI/bge-base-en-v1.5 (sentence-transformers) |
| Vector Store | ChromaDB (persistent, cosine similarity) |
| LLM | Hugging Face Router (primary) / Groq (fallback) |
| Chunking | Custom paragraph-aware splitter (no LangChain) |
| Viewer | PDF.js (CDN) with canvas rendering + line highlighting |
| UI | HTML + vanilla JS (Bootstrap Icons, Chart.js) |

## Docker / Hugging Face Spaces

This project includes a `Dockerfile` configured for Hugging Face Spaces (Docker SDK):

```dockerfile
FROM python:3.11-slim
# Installs PaddleOCR system deps, creates user 1000,
# sets PORT=7860, HOST=0.0.0.0
```

Build and run locally:

```powershell
docker build -t rag-devnity .
docker run -p 7860:7860 --env-file .env rag-devnity
```

**Important**: The `.env` file must contain `GROQ_API_KEY` at minimum.

## Project Structure

```
rag-devnity/
├── app.py                  # Flask entrypoint + all routes
├── config.py               # All tunable configuration
├── models.py               # SQLAlchemy models (User, Document)
├── requirements.txt        # Python dependencies
├── Dockerfile              # HF Spaces Docker build
├── .dockerignore           # Docker build exclusions
├── cleanup.py              # Data reset script
├── routes/
│   └── auth.py             # Auth blueprint (login, register, logout)
├── services/
│   ├── pdf_processor.py    # Text + image extraction
│   ├── ocr_service.py      # PaddleOCR for scanned pages
│   ├── image_service.py    # Route images to OCR / Vision
│   ├── embeddings.py       # BGE embeddings + ChromaDB storage/retrieval
│   ├── groq_service.py     # LLM calls (summary, MCQs, Q&A, vision)
│   ├── vector_service.py   # Qdrant storage/retrieval (conditional)
│   ├── storage_service.py  # DigitalOcean Spaces (conditional)
│   └── email_service.py    # SMTP email (conditional)
├── templates/
│   ├── base.html           # Base layout (sidebar, nav, toast, modal)
│   ├── index.html          # Dashboard (stats, upload, recent docs)
│   ├── dashboard.html      # My Documents (document listing)
│   ├── study.html          # Study room (PDF.js, Q&A, chat)
│   ├── quiz.html           # Quiz (timer, nav, options)
│   └── analytics.html      # Quiz results (charts, review)
├── static/
│   ├── css/
│   │   ├── style.css       # Shared styles (variables, sidebar, cards, etc.)
│   │   ├── study.css       # Study room styles
│   │   ├── quiz.css        # Quiz page styles
│   │   └── analytics.css   # Analytics page styles
│   └── js/
│       └── app.js          # Shared JS (sidebar toggle, SSE, delete modal)
├── storage/                # Temp uploads + extracted images (gitignored)
└── vector_db/              # ChromaDB persistent data (gitignored)
```

## Notes

- `AGENTS.md` contains guidance for AI coding agents working on this repo — it's gitignored by default
- The app uses `print()` for logging — no logging framework
- Stale temp files in `storage/temp/` and `storage/images/` are cleaned on startup
- Use `cleanup.py` to reset all data (MySQL, Qdrant, DO Spaces, local storage)
