"""Flask app — PDF upload, RAG chat, MCQ generation."""
import os
import uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from config import TEMP_DIR, IMAGES_DIR, PORT, DEBUG
from services.pdf_processor import process_pdf, is_text_empty
from services.ocr_service   import run_ocr_on_full_pdf
from services.image_service import process_pdf_images, cleanup_images
from services.embeddings    import chunk_text, store_chunks, retrieve_chunks, delete_pdf_chunks
from services.groq_service  import generate_summary, generate_mcqs, answer_question


app = Flask(__name__)
CORS(app)

pdf_store = {}  # pdf_id -> {filename, summary, status}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():
    """PDF upload + full processing pipeline."""

    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

    file = request.files["pdf"]
    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files allowed"}), 400

    # Save PDF
    pdf_id   = str(uuid.uuid4())[:8]
    filename = f"{pdf_id}_{file.filename}"
    pdf_path = os.path.join(TEMP_DIR, filename)
    file.save(pdf_path)

    print(f"\nProcessing PDF: {file.filename} (id: {pdf_id})")

    try:
        # ── Step 1: Extract text + images ────────────────────────────────
        print("Step 1: Extracting text and images...")
        result  = process_pdf(pdf_path)
        pages   = result["pages"]
        full_text = result["full_text"]

        # ── Step 2: OCR for empty pages ───────────────────────────────────
        print("Step 2: Checking for scanned pages...")
        all_text_parts = [full_text] if full_text else []

        for page in pages:
            if is_text_empty(page["text"]):
                print(f"   OCR needed for page {page['page_num']}")
                from services.ocr_service import run_ocr_on_pdf_page
                ocr_text = run_ocr_on_pdf_page(pdf_path, page["page_num"])
                if ocr_text:
                    page["text"] = ocr_text
                    all_text_parts.append(f"[Page {page['page_num']}]\n{ocr_text}")

        # ── Step 3: Process Images ────────────────────────────────────────
        print("Step 3: Processing images...")
        image_results = process_pdf_images(pages)

        for img_result in image_results:
            all_text_parts.append(img_result["description"])

        # ── Step 4: Combine all text ──────────────────────────────────────
        combined_text = "\n\n".join(all_text_parts)

        if not combined_text.strip():
            return jsonify({"error": "Could not extract text from PDF"}), 422

        # ── Step 5: Chunk + Embed + Store ─────────────────────────────────
        print("Step 4: Creating embeddings...")
        chunks     = chunk_text(combined_text)
        num_chunks = store_chunks(chunks, pdf_id)

        # ── Step 6: Generate Summary ──────────────────────────────────────
        print("Step 5: Generating summary...")
        summary = generate_summary(combined_text)

        # ── Step 7: Cleanup ───────────────────────────────────────────────
        all_image_paths = [img["image_path"] for img in image_results]
        cleanup_images(all_image_paths)
        os.remove(pdf_path)

        # ── Store in memory ───────────────────────────────────────────────
        pdf_store[pdf_id] = {
            "filename": file.filename,
            "summary": summary,
            "num_chunks": num_chunks,
            "total_pages": result["total_pages"],
            "status": "ready"
        }

        print(f"PDF processed successfully! Chunks: {num_chunks}")

        return jsonify({
            "pdf_id": pdf_id,
            "filename": file.filename,
            "total_pages": result["total_pages"],
            "num_chunks": num_chunks,
            "summary": summary,
            "status": "ready"
        })

    except Exception as e:
        print(f"Error: {e}")
        # Cleanup on error
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return jsonify({"error": str(e)}), 500


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

    app.run(debug=DEBUG, port=PORT)
