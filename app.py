"""Flask app — PDF upload, RAG chat, MCQ generation, auth."""
import os
import json
import uuid
import time
import shutil
import threading
from flask import Flask, request, jsonify, render_template, Response, send_file, send_from_directory, redirect, url_for, session, flash
from flask_cors import CORS
from flask_login import LoginManager, login_required, login_user, current_user
from flask_migrate import Migrate

from config import TEMP_DIR, IMAGES_DIR, PDFS_DIR, PORT, HOST, DEBUG, DATABASE_URL, SESSION_SECRET
from models import db, User, Document, QuizResult
from routes.auth import auth_bp
from services.pdf_processor import process_pdf, is_text_empty
from services.ocr_service   import run_ocr_on_pdf_page
from services.image_service import process_pdf_images, cleanup_images
from services.embeddings     import chunk_text
from services.vector_service import store_chunks, retrieve_chunks, delete_pdf_chunks
from services.groq_service import generate_summary, generate_mcqs, generate_qa_pairs, answer_question, generate_takeaways, generate_terminology, classify_document
from services import storage_service


app = Flask(__name__)
# Strip ssl-mode param (PyMySQL doesn't support it)
_db_url = DATABASE_URL
if _db_url:
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    _parsed = urlparse(_db_url)
    if _parsed.query:
        _qs = parse_qs(_parsed.query)
        _qs.pop("ssl-mode", None)
        _parsed = _parsed._replace(query=urlencode(_qs, doseq=True))
        _db_url = urlunparse(_parsed)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = SESSION_SECRET
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_HTTPONLY"] = True

CORS(app, supports_credentials=True)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


with app.app_context():
    from flask_migrate import upgrade
    try:
        upgrade()
    except Exception as e:
        print(f"Migration skipped (tables may already exist): {e}")
    db.create_all()
    import sqlalchemy as sa
    try:
        with db.engine.connect() as conn:
            conn.execute(sa.text("ALTER TABLE documents ADD COLUMN mcqs JSON"))
            conn.execute(sa.text("ALTER TABLE documents ADD COLUMN qa_pairs JSON"))
            conn.execute(sa.text("ALTER TABLE documents ADD COLUMN doc_type VARCHAR(20) DEFAULT 'unknown'"))
            conn.commit()
    except Exception:
        pass  # columns already exist

app.register_blueprint(auth_bp)

_processing_status = {}  # {user_id}:{pdf_id} -> {step, progress, message, done, error, result}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    docs = Document.query.filter_by(user_id=current_user.id, status="ready")\
        .order_by(Document.created_at.desc()).all()
    total_docs = len(docs)
    total_chunks = sum(d.num_chunks for d in docs)
    from sqlalchemy import func
    avg = db.session.query(func.avg(QuizResult.percentage)).filter(
        QuizResult.user_id == current_user.id
    ).scalar()
    stats = {
        "total_docs": total_docs,
        "ai_queries": total_chunks,
        "avg_score": round(avg) if avg else 0,
    }
    return render_template("index.html", documents=docs, stats=stats)


def _status_key(user_id, pdf_id):
    return f"{user_id}:{pdf_id}"


def _update_status(user_id, pdf_id, step, progress, message="", done=False, error=False, result=None):
    key = _status_key(user_id, pdf_id)
    _processing_status[key] = {
        "step": step, "progress": progress, "message": message,
        "done": done, "error": error, "result": result,
    }


def _process_pdf_background(pdf_path, filename, pdf_id, user_id):
    """Run PDF processing in a background thread, updating SSE progress."""
    with app.app_context():
        try:
            _update_status(user_id, pdf_id, "Extracting", 5, "Extracting text and images from PDF...")
            print(f"\nProcessing PDF: {filename} (id: {pdf_id}, user: {user_id})")

            _update_status(user_id, pdf_id, "Extracting", 10, "Step 1: Extracting text and images...")
            result    = process_pdf(pdf_path)
            pages     = result["pages"]
            full_text = result["full_text"]
            lines_data = result.get("lines_data", {})

            _update_status(user_id, pdf_id, "OCR", 20, "Step 2: Checking for scanned pages...")
            all_text_parts = [full_text] if full_text else []
            total_pages = len(pages)
            scanned_pages = 0

            for page in pages:
                if is_text_empty(page["text"]):
                    scanned_pages += 1
                    pct = 20 + int((scanned_pages / max(total_pages, 1)) * 15)
                    _update_status(user_id, pdf_id, "OCR", pct, f"Running OCR on page {page['page_num']}...")
                    ocr_text = run_ocr_on_pdf_page(pdf_path, page["page_num"])
                    if ocr_text:
                        page["text"] = ocr_text
                        all_text_parts.append(f"[Page {page['page_num']}]\n{ocr_text}")

            _update_status(user_id, pdf_id, "Images", 35, "Step 3: Processing images...")
            image_results = process_pdf_images(pages)
            for img_result in image_results:
                all_text_parts.append(img_result["description"])

            combined_text = "\n\n".join(all_text_parts)

            if not combined_text.strip():
                _update_status(user_id, pdf_id, "Error", 0, "Could not extract text from PDF", error=True)
                doc = db.session.get(Document, pdf_id)
                if doc:
                    doc.status = "error"
                    doc.error_message = "Could not extract text from PDF"
                    db.session.commit()
                return

            _update_status(user_id, pdf_id, "Embeddings", 55, "Step 4: Creating embeddings (this may take a minute)...")
            chunks     = chunk_text(combined_text)
            num_chunks = store_chunks(chunks, pdf_id, user_id=user_id)

            _update_status(user_id, pdf_id, "Summary", 80, "Step 5: Generating summary...")
            summary = generate_summary(combined_text)

            _update_status(user_id, pdf_id, "Classification", 85, "Step 6: Classifying document type...")
            doc_type = classify_document(combined_text)

            # Save PDF permanently for viewer
            storage_key = storage_service.upload_file(pdf_path, pdf_id)

            _update_status(user_id, pdf_id, "Cleanup", 95, "Cleaning up...")
            all_image_paths = [img["image_path"] for img in image_results]
            cleanup_images(all_image_paths)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            # Update Document record in DB
            doc = db.session.get(Document, pdf_id)
            if doc:
                doc.doc_type = doc_type
                doc.summary = summary
                doc.full_text = combined_text
                doc.lines_data = lines_data
                doc.num_chunks = num_chunks
                doc.total_pages = result["total_pages"]
                doc.storage_key = storage_key
                doc.status = "ready"
                db.session.commit()

            print(f"PDF processed successfully! Chunks: {num_chunks}")

            _update_status(user_id, pdf_id, "Done", 100, "Ready!", done=True, result={
                "pdf_id": pdf_id,
                "filename": filename,
                "total_pages": result["total_pages"],
                "num_chunks": num_chunks,
                "summary": summary,
                "status": "ready"
            })

        except Exception as e:
            print(f"Error: {e}")
            _update_status(user_id, pdf_id, "Error", 0, str(e), error=True)
            doc = db.session.get(Document, pdf_id)
            if doc:
                doc.status = "error"
                doc.error_message = str(e)
                db.session.commit()
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass


@app.route("/upload", methods=["POST"])
@login_required
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

    # Create Document record
    doc = Document(
        id=pdf_id,
        user_id=current_user.id,
        original_name=file.filename,
        status="processing",
    )
    db.session.add(doc)
    db.session.commit()

    thread = threading.Thread(
        target=_process_pdf_background,
        args=(pdf_path, file.filename, pdf_id, current_user.id),
        daemon=True,
    )
    thread.start()

    return jsonify({"pdf_id": pdf_id, "status": "processing"})


@app.route("/progress/<pdf_id>")
@login_required
def progress_stream(pdf_id):
    """SSE endpoint — real-time processing progress."""
    key = _status_key(current_user.id, pdf_id)

    def generate():
        while True:
            status = _processing_status.get(key, {})
            yield f"data: {json.dumps(status)}\n\n"
            if status.get("done") or status.get("error"):
                if key in _processing_status:
                    del _processing_status[key]
                break
            time.sleep(0.5)
    return Response(generate(), mimetype="text/event-stream")


def _get_doc_or_404(pdf_id):
    """Helper: fetch Document owned by current user or return 404."""
    doc = Document.query.filter_by(id=pdf_id, user_id=current_user.id).first()
    if not doc:
        return None
    return doc


@app.route("/mcqs", methods=["POST"])
@login_required
def get_mcqs():
    """Generate MCQs from a processed PDF (cached)."""
    data = request.json
    pdf_id       = data.get("pdf_id")
    num_questions = max(1, min(data.get("num_questions", 5), 5))

    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404

    if doc.doc_type and doc.doc_type not in ("educational", "technical", "unknown"):
        return jsonify({"error": "This document type is not suitable for quiz generation.", "doc_type": doc.doc_type}), 400

    if doc.mcqs and isinstance(doc.mcqs, list) and len(doc.mcqs) >= num_questions:
        return jsonify({"pdf_id": pdf_id, "mcqs": doc.mcqs[:num_questions], "cached": True})

    text = doc.full_text or doc.summary or ""
    mcqs = generate_mcqs(text, num_questions=num_questions)
    doc.mcqs = mcqs
    db.session.commit()

    return jsonify({"pdf_id": pdf_id, "mcqs": mcqs, "cached": False})


@app.route("/qa", methods=["POST"])
@login_required
def get_qa():
    """Generate Q&A pairs from a processed PDF (cached + conflict modal)."""
    data = request.json
    pdf_id    = data.get("pdf_id")
    num_pairs = max(1, min(data.get("num_pairs", 5), 5))
    force     = data.get("force", False)

    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404

    if doc.doc_type and doc.doc_type not in ("educational", "technical", "unknown"):
        return jsonify({"error": "This document type is not suitable for Q&A.", "doc_type": doc.doc_type}), 400

    if not force and doc.qa_pairs and isinstance(doc.qa_pairs, list):
        if len(doc.qa_pairs) >= num_pairs:
            return jsonify({"qa_pairs": doc.qa_pairs[:num_pairs], "cached": True})
        else:
            return jsonify({
                "conflict": True, "cached_count": len(doc.qa_pairs), "requested": num_pairs,
                "message": f"Already have {len(doc.qa_pairs)} Q&A pairs. Generate {num_pairs} fresh ones?"
            })

    text = doc.full_text or doc.summary or ""
    pairs = generate_qa_pairs(text, num_pairs=num_pairs)
    doc.qa_pairs = pairs
    db.session.commit()

    return jsonify({"qa_pairs": pairs, "cached": False})


@app.route("/chat", methods=["POST"])
@login_required
def chat():
    """Answer a question using retrieved PDF chunks."""
    data     = request.json
    pdf_id   = data.get("pdf_id")
    question = data.get("question", "").strip()

    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404

    if not question:
        return jsonify({"error": "Question is required"}), 400

    sources = retrieve_chunks(question, pdf_id, user_id=current_user.id, top_k=5)

    if not sources:
        return jsonify({"answer": "I couldn't find relevant information in this document."})

    chunks_text = [s["text"] for s in sources]
    answer = answer_question(question, chunks_text)

    chat_sources = []
    for s in sources:
        chat_sources.append({
            "text": s["text"],
            "pages": s.get("pages", []),
            "lines": s.get("lines", []),
            "chunk_index": s.get("chunk_index", 0),
        })

    return jsonify({
        "pdf_id": pdf_id,
        "question": question,
        "answer": answer,
        "sources": chat_sources
    })


@app.route("/pdf/<pdf_id>/info")
@login_required
def pdf_info(pdf_id):
    """Return document metadata for restoring state on existing doc selection."""
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404
    return jsonify({
        "pdf_id": doc.id,
        "filename": doc.original_name,
        "total_pages": doc.total_pages,
        "num_chunks": doc.num_chunks,
        "summary": doc.summary or "",
    })


@app.route("/pdf/<pdf_id>/file")
@login_required
def serve_pdf(pdf_id):
    """Serve the original PDF file for the viewer via presigned URL or local file."""
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404

    url = storage_service.get_presigned_url(pdf_id)
    if url:
        return redirect(url)

    local_path = storage_service.get_local_path(pdf_id)
    if local_path and os.path.exists(local_path):
        return send_file(local_path, mimetype="application/pdf", as_attachment=False)

    return jsonify({"error": "PDF file not available"}), 404


@app.route("/pdf/<pdf_id>/lines")
@login_required
def serve_pdf_lines(pdf_id):
    """Serve line-level metadata for highlighting."""
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404
    return jsonify(doc.lines_data or {})


@app.route("/pdf/<pdf_id>", methods=["DELETE"])
@login_required
def delete_pdf(pdf_id):
    """Delete a PDF and its chunks."""
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404

    storage_service.delete_file(pdf_id)

    delete_pdf_chunks(pdf_id, user_id=current_user.id)
    db.session.delete(doc)
    db.session.commit()

    return jsonify({"message": "PDF deleted successfully"})


@app.route("/dashboard")
@login_required
def dashboard():
    docs = Document.query.filter_by(user_id=current_user.id)\
        .order_by(Document.created_at.desc()).all()
    return render_template("dashboard.html", documents=docs)


@app.route("/study/<pdf_id>")
@login_required
def study_room(pdf_id):
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404
    session["last_pdf_id"] = pdf_id
    return render_template("study.html", doc=doc, pdf_url=url_for("serve_pdf", pdf_id=pdf_id))


@app.route("/quiz/<pdf_id>")
@login_required
def quiz_page(pdf_id):
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404
    session["last_pdf_id"] = pdf_id
    return render_template("quiz.html", doc=doc, total_questions=5)


@app.route("/quiz/submit", methods=["POST"])
@login_required
def quiz_submit():
    data = request.json
    pdf_id = data.get("pdf_id", "")
    questions = data.get("questions", [])
    answers = data.get("answers", {})
    duration_seconds = data.get("duration_seconds", 0)
    
    correct = 0
    total = len(questions)
    results = []
    for i, q in enumerate(questions):
        qid = str(i)
        user_ans = answers.get(qid)
        correct_ans = q.get("answer", "")
        is_correct = user_ans == correct_ans
        if is_correct:
            correct += 1
        results.append({
            "id": qid,
            "question": q.get("question", ""),
            "options": q.get("options", {}),
            "correct": is_correct,
            "user_answer": user_ans,
            "correct_answer": correct_ans,
            "explanation": q.get("explanation", ""),
            "source": q.get("source", ""),
        })
    
    score_pct = round((correct / total) * 100) if total > 0 else 0
    doc = Document.query.filter_by(id=pdf_id, user_id=current_user.id).first()
    doc_name = doc.original_name if doc else "Quiz completed"
    result_data = {
        "pdf_id": pdf_id,
        "doc_name": doc_name,
        "score": correct,
        "total": total,
        "percentage": score_pct,
        "results": results,
        "duration_seconds": duration_seconds,
    }
    session["last_quiz_result"] = result_data
    try:
        db.session.add(QuizResult(
            user_id=current_user.id, document_id=pdf_id,
            score=correct, total_questions=total,
            percentage=score_pct, duration_seconds=duration_seconds,
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Failed to save quiz result: {e}")
    return jsonify(result_data)


@app.route("/analytics", methods=["POST"])
@login_required
def analytics():
    data = request.json
    return render_template("analytics.html", data=data)


@app.route("/study-room")
@login_required
def study_room_list():
    last_id = session.get("last_pdf_id")
    if not last_id:
        flash("Open a document from the dashboard first.", "error")
        return redirect(url_for("index"))
    return redirect(url_for("study_room", pdf_id=last_id))


@app.route("/mock-test")
@login_required
def mock_test_list():
    last_id = session.get("last_pdf_id")
    if not last_id:
        flash("Open a document from the dashboard first.", "error")
        return redirect(url_for("index"))
    return redirect(url_for("quiz_page", pdf_id=last_id))


@app.route("/analytics-page")
@login_required
def analytics_page():
    last_result = session.get("last_quiz_result")
    if not last_result:
        flash("Complete a quiz first to see analytics.", "error")
        return redirect(url_for("index"))
    return render_template("analytics.html", data=last_result)


@app.route("/takeaways", methods=["POST"])
@login_required
def get_takeaways():
    data = request.json
    pdf_id = data.get("pdf_id")
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404
    if doc.doc_type and doc.doc_type not in ("educational", "technical", "unknown"):
        return jsonify({"error": "This document type is not suitable for takeaways.", "doc_type": doc.doc_type}), 400
    text = doc.full_text or doc.summary or ""
    if not text.strip():
        return jsonify({"takeaways": []})
    takeaways = generate_takeaways(text)
    return jsonify({"takeaways": takeaways})


@app.route("/terminology", methods=["POST"])
@login_required
def get_terminology():
    data = request.json
    pdf_id = data.get("pdf_id")
    doc = _get_doc_or_404(pdf_id)
    if not doc:
        return jsonify({"error": "PDF not found"}), 404
    if doc.doc_type and doc.doc_type not in ("educational", "technical", "unknown"):
        return jsonify({"error": "This document type is not suitable for terminology.", "doc_type": doc.doc_type}), 400
    text = doc.full_text or doc.summary or ""
    if not text.strip():
        return jsonify({"terms": []})
    terms = generate_terminology(text)
    return jsonify({"terms": terms})


@app.route("/health", methods=["GET"])
def health():
    doc_count = Document.query.count() if Document else 0
    return jsonify({"status": "ok", "documents": doc_count})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(PDFS_DIR, exist_ok=True)

    # Cleanup stale temp files on startup (only on first start, not reload)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        for d in (TEMP_DIR, IMAGES_DIR):
            for f in os.listdir(d):
                fpath = os.path.join(d, f)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except Exception:
                    pass

    app.run(debug=DEBUG, host=HOST, port=PORT)