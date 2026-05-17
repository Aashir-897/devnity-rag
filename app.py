"""Flask app — PDF upload, RAG chat, MCQ generation."""
import os
import json
import uuid
import time
import threading
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS

from config import TEMP_DIR, IMAGES_DIR, PORT, HOST, DEBUG
from services.pdf_processor import process_pdf, is_text_empty
from services.ocr_service   import run_ocr_on_pdf_page
from services.image_service import process_pdf_images, cleanup_images
from services.embeddings    import chunk_text, store_chunks, retrieve_chunks, delete_pdf_chunks
from services.groq_service  import generate_summary, generate_mcqs, answer_question


app = Flask(__name__)
CORS(app)

pdf_store = {}  # pdf_id -> {filename, summary, status}
_processing_status = {}  # pdf_id -> {step, progress, message, done, error, result}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


def _update_status(pdf_id, step, progress, message="", done=False, error=False, result=None):
    _processing_status[pdf_id] = {
        "step": step, "progress": progress, "message": message,
        "done": done, "error": error, "result": result,
    }


def _process_pdf_background(pdf_path, filename, pdf_id):
    """Run PDF processing in a background thread, updating SSE progress."""
    try:
        _update_status(pdf_id, "Extracting", 5, "Extracting text and images from PDF...")
        print(f"\nProcessing PDF: {filename} (id: {pdf_id})")

        _update_status(pdf_id, "Extracting", 10, "Step 1: Extracting text and images...")
        result  = process_pdf(pdf_path)
        pages   = result["pages"]
        full_text = result["full_text"]

        _update_status(pdf_id, "OCR", 20, "Step 2: Checking for scanned pages...")
        all_text_parts = [full_text] if full_text else []
        total_pages = len(pages)
        scanned_pages = 0

        for page in pages:
            if is_text_empty(page["text"]):
                scanned_pages += 1
                pct = 20 + int((scanned_pages / max(total_pages, 1)) * 15)
                _update_status(pdf_id, "OCR", pct, f"Running OCR on page {page['page_num']}...")
                ocr_text = run_ocr_on_pdf_page(pdf_path, page["page_num"])
                if ocr_text:
                    page["text"] = ocr_text
                    all_text_parts.append(f"[Page {page['page_num']}]\n{ocr_text}")

        _update_status(pdf_id, "Images", 35, "Step 3: Processing images...")
        image_results = process_pdf_images(pages)
        for img_result in image_results:
            all_text_parts.append(img_result["description"])

        combined_text = "\n\n".join(all_text_parts)

        if not combined_text.strip():
            _update_status(pdf_id, "Error", 0, "Could not extract text from PDF", error=True)
            return

        _update_status(pdf_id, "Embeddings", 55, "Step 4: Creating embeddings (this may take a minute)...")
        chunks     = chunk_text(combined_text)
        num_chunks = store_chunks(chunks, pdf_id)

        _update_status(pdf_id, "Summary", 80, "Step 5: Generating summary...")
        summary = generate_summary(combined_text)

        _update_status(pdf_id, "Cleanup", 95, "Cleaning up...")
        all_image_paths = [img["image_path"] for img in image_results]
        cleanup_images(all_image_paths)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        pdf_store[pdf_id] = {
            "filename": filename,
            "summary": summary,
            "num_chunks": num_chunks,
            "total_pages": result["total_pages"],
            "status": "ready"
        }

        print(f"PDF processed successfully! Chunks: {num_chunks}")

        _update_status(pdf_id, "Done", 100, "Ready!", done=True, result={
            "pdf_id": pdf_id,
            "filename": filename,
            "total_pages": result["total_pages"],
            "num_chunks": num_chunks,
            "summary": summary,
            "status": "ready"
        })

    except Exception as e:
        print(f"Error: {e}")
        _update_status(pdf_id, "Error", 0, str(e), error=True)
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass


@app.route("/upload", methods=["POST"])
def upload_pdf():
    """Upload PDF and start background processing."""

    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

    file = request.files["pdf"]
    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files allowed"}), 400

    pdf_id   = str(uuid.uuid4())[:8]
    filename = f"{pdf_id}_{file.filename}"
    pdf_path = os.path.join(TEMP_DIR, filename)
    file.save(pdf_path)

    thread = threading.Thread(
        target=_process_pdf_background,
        args=(pdf_path, file.filename, pdf_id),
        daemon=True,
    )
    thread.start()

    return jsonify({"pdf_id": pdf_id, "status": "processing"})


@app.route("/progress/<pdf_id>")
def progress_stream(pdf_id):
    """SSE endpoint — real-time processing progress."""
    def generate():
        while True:
            status = _processing_status.get(pdf_id, {})
            yield f"data: {json.dumps(status)}\n\n"
            if status.get("done") or status.get("error"):
                if pdf_id in _processing_status:
                    del _processing_status[pdf_id]
                break
            time.sleep(0.5)
    return Response(generate(), mimetype="text/event-stream")


@app.route("/mcqs", methods=["POST"])
def get_mcqs():
    """Generate MCQs from a processed PDF."""
    data = request.json
    pdf_id       = data.get("pdf_id")
    num_questions = data.get("num_questions", 5)

    if pdf_id not in pdf_store:
        return jsonify({"error": "PDF not found"}), 404

    text = pdf_store[pdf_id]["summary"]
    mcqs = generate_mcqs(text, num_questions=num_questions)

    return jsonify({"pdf_id": pdf_id, "mcqs": mcqs})


@app.route("/chat", methods=["POST"])
def chat():
    """Answer a question using retrieved PDF chunks."""
    data     = request.json
    pdf_id   = data.get("pdf_id")
    question = data.get("question", "").strip()

    if not pdf_id or pdf_id not in pdf_store:
        return jsonify({"error": "PDF not found"}), 404

    if not question:
        return jsonify({"error": "Question is required"}), 400

    chunks = retrieve_chunks(question, pdf_id, top_k=5)

    if not chunks:
        return jsonify({"answer": "I couldn't find relevant information in this document."})

    answer = answer_question(question, chunks)

    return jsonify({
        "pdf_id": pdf_id,
        "question": question,
        "answer": answer
    })


@app.route("/pdf/<pdf_id>", methods=["DELETE"])
def delete_pdf(pdf_id):
    """Delete a PDF and its chunks."""
    if pdf_id not in pdf_store:
        return jsonify({"error": "PDF not found"}), 404

    delete_pdf_chunks(pdf_id)
    del pdf_store[pdf_id]

    return jsonify({"message": "PDF deleted successfully"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "pdfs_loaded": len(pdf_store)})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Cleanup stale temp files on startup
    for d in (TEMP_DIR, IMAGES_DIR):
        for f in os.listdir(d):
            fpath = os.path.join(d, f)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except Exception:
                pass

    app.run(debug=DEBUG, host=HOST, port=PORT)
