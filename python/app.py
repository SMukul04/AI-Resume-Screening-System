import os
import re
import json
import uuid
import logging
import threading
import zipfile
from collections import Counter
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import fitz  # PyMuPDF
import docx  # python-docx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ============================
# Logging Configuration
# ============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("resume_screening")

# ============================
# Paths and App Configuration
# ============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'html'))
CSS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'css'))
JS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'javascript'))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
DATA_BACKUP_FILE = os.path.join(BASE_DIR, 'data.json.bak')

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=HTML_DIR, static_url_path='')
CORS(app)

# Security: Enforce 16 MB max content length
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
FILE_LOCK = threading.Lock()

# Load Sentence Transformer model
logger.info("Initializing SentenceTransformer model: all-MiniLM-L6-v2")
model = SentenceTransformer('all-MiniLM-L6-v2')


# ============================
# Error Handlers
# ============================
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({
        "error": "File size exceeds the maximum allowed limit of 16 MB."
    }), 413


# ============================
# Data Persistence & Atomic Writes
# ============================
def get_default_data():
    return {
        "stats": {
            "total_screenings": 0,
            "resumes_uploaded": 0,
            "avg_match_score": 0,
            "top_candidate_score": 0
        },
        "current_screening": {
            "job_title": "",
            "resumes_uploaded": 0,
            "qualified": 0,
            "jd_added": False,
            "processing_status": "Not started"
        },
        "workflow": {
            "jd_added": False,
            "resumes_count": 0,
            "processing_status": "Not started",
            "results_ready": False
        },
        "recent_screenings": [],
        "job_descriptions": [],
        "resumes": [],
        "results": []
    }


def load_data():
    with FILE_LOCK:
        data = None
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as exc:
                logger.warning("Failed to parse data.json (%s). Attempting backup...", exc)
                if os.path.exists(DATA_BACKUP_FILE):
                    try:
                        with open(DATA_BACKUP_FILE, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        logger.info("Recovered state from data.json.bak")
                    except Exception as b_exc:
                        logger.error("Backup also unreadable: %s", b_exc)
                        data = None

        if data is None:
            data = get_default_data()

        defaults = get_default_data()
        for k, v in defaults.items():
            if k not in data or data[k] is None:
                data[k] = v
            elif isinstance(v, dict) and isinstance(data[k], dict):
                for sub_k, sub_v in v.items():
                    data[k].setdefault(sub_k, sub_v)

        return data


def save_data(data):
    with FILE_LOCK:
        temp_file = f"{DATA_FILE}.tmp.{uuid.uuid4().hex[:8]}"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            if os.path.exists(DATA_FILE):
                try:
                    import shutil
                    shutil.copy2(DATA_FILE, DATA_BACKUP_FILE)
                except Exception as b_err:
                    logger.warning("Could not refresh backup: %s", b_err)

            os.replace(temp_file, DATA_FILE)
        except Exception as exc:
            logger.error("Failed to write data atomically: %s", exc)
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            raise


def generate_screening_id(recent_screenings):
    """Generate collision-resistant SCR-xxx ID by finding max numeric ID."""
    max_num = 0
    pattern = re.compile(r"^SCR-(\d+)$")
    for item in recent_screenings:
        sid = str(item.get("id", ""))
        m = pattern.match(sid)
        if m:
            num = int(m.group(1))
            if num > max_num:
                max_num = num

    next_id = max_num + 1
    candidate_id = f"SCR-{next_id:03d}"
    existing_ids = {s.get("id") for s in recent_screenings}
    while candidate_id in existing_ids:
        next_id += 1
        candidate_id = f"SCR-{next_id:03d}"
    return candidate_id


# ============================
# File Validation & Parsing Helpers
# ============================
def get_file_extension(filename):
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower().strip()


def validate_file_content(file_storage, ext):
    """Validate file content signature to reject empty or spoofed files."""
    header = file_storage.read(2048)
    file_storage.seek(0)

    if not header or len(header.strip()) == 0:
        return False, "File is completely empty (0 bytes)."

    if ext == 'pdf':
        if not header.startswith(b'%PDF-'):
            return False, "Invalid PDF header signature. File is not a valid PDF document."
    elif ext == 'docx':
        if not header.startswith(b'PK\x03\x04'):
            return False, "Invalid DOCX header signature. File is not a valid Office Open XML package."
        try:
            with zipfile.ZipFile(file_storage) as z:
                names = z.namelist()
                if 'word/document.xml' not in names:
                    file_storage.seek(0)
                    return False, "Invalid DOCX structure: missing word/document.xml."
            file_storage.seek(0)
        except Exception:
            file_storage.seek(0)
            return False, "Malformed or corrupt DOCX archive."

    return True, None


def extract_text_from_pdf(filepath):
    text = ""
    doc = fitz.open(filepath)
    for page in doc:
        page_text = page.get_text()
        if page_text:
            text += page_text + "\n"
    doc.close()
    return text.strip()


def extract_text_from_docx(filepath):
    doc = docx.Document(filepath)
    text_chunks = []
    for p in doc.paragraphs:
        if p.text:
            text_chunks.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    text_chunks.append(cell.text)
    return "\n".join(text_chunks).strip()


def extract_text(filepath):
    """Unified text extractor supporting PDF and DOCX with clear error messages."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found on server storage: {os.path.basename(filepath)}")

    ext = get_file_extension(filepath)
    if ext == 'pdf':
        return extract_text_from_pdf(filepath)
    elif ext == 'docx':
        return extract_text_from_docx(filepath)
    elif ext == 'doc':
        raise ValueError("Legacy .doc format is not supported. Please convert to .docx or .pdf.")
    else:
        raise ValueError(f"Unsupported document format: .{ext}")


def match_skills(text, skills_list):
    """Regex word-boundary skill matching to prevent false substring matches."""
    if not text:
        return []
    matched = []
    text_lower = text.lower()
    for skill in skills_list:
        s_str = str(skill).strip()
        if not s_str:
            continue
        pattern = r'(?:\b|_)' + re.escape(s_str.lower()) + r'(?:\b|_)'
        if re.search(pattern, text_lower):
            matched.append(s_str)
    return matched


# ============================
# Static Frontend Routes
# ============================
@app.route('/')
def index():
    return send_from_directory(HTML_DIR, 'dashboard.html')


@app.route('/<page>.html')
def serve_page(page):
    safe_page = secure_filename(f"{page}.html")
    return send_from_directory(HTML_DIR, safe_page)


@app.route('/css/<path:filename>')
def serve_css(filename):
    safe_css = os.path.basename(filename)
    return send_from_directory(CSS_DIR, safe_css)


@app.route('/javascript/<path:filename>')
def serve_js(filename):
    safe_js = os.path.basename(filename)
    return send_from_directory(JS_DIR, safe_js)


@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename or '..' in filename:
        return jsonify({"error": "Invalid file path"}), 400
    return send_from_directory(UPLOAD_DIR, safe_name)


# ============================
# API Routes
# ============================
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    data = load_data()
    results = data.get("results", [])
    recent_screenings = data.get("recent_screenings", [])

    total_resumes_from_history = sum(
        int(s.get("resumes", 0) or 0) for s in recent_screenings
    )
    data.setdefault("stats", {})
    data["stats"]["resumes_uploaded"] = total_resumes_from_history
    data["stats"]["total_screenings"] = len(recent_screenings)

    all_skills = []
    for r in results:
        all_skills.extend(r.get("skills", []))
    top_skills = Counter(all_skills).most_common(5)

    return jsonify({
        "stats": data["stats"],
        "current_screening": data["current_screening"],
        "workflow": data["workflow"],
        "recent_screenings": recent_screenings,
        "top_skills": [{"skill": s, "count": c} for s, c in top_skills]
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    data = load_data()
    recent_screenings = data.get("recent_screenings", [])
    data.setdefault("stats", {})
    data["stats"]["resumes_uploaded"] = sum(
        int(s.get("resumes", 0) or 0) for s in recent_screenings
    )
    data["stats"]["total_screenings"] = len(recent_screenings)
    return jsonify(data["stats"])


@app.route('/api/job-description', methods=['GET', 'POST'])
def job_description():
    data = load_data()

    if request.method == 'POST':
        body = request.get_json(silent=True) or {}

        title = str(body.get("title", "")).strip()
        description = str(body.get("description", "")).strip()
        skills = body.get("skills", [])
        if not isinstance(skills, list):
            skills = []

        if not title:
            return jsonify({"error": "Job title is required."}), 400

        data.setdefault("job_descriptions", [])
        data["job_descriptions"].append({
            "title": title,
            "description": description,
            "skills": skills,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        data.setdefault("workflow", {})
        data.setdefault("current_screening", {})
        data.setdefault("results", [])

        data["workflow"]["jd_added"] = True
        data["workflow"]["processing_status"] = "Not started"
        data["workflow"]["results_ready"] = False

        data["current_screening"]["jd_added"] = True
        data["current_screening"]["job_title"] = title
        data["current_screening"]["processing_status"] = "Pending"
        data["results"] = []

        save_data(data)
        return jsonify({"message": "Job description added successfully."}), 201

    return jsonify({
        "job_descriptions": data.get("job_descriptions", []),
        "current": data["current_screening"]
    })


@app.route('/api/upload-resumes', methods=['GET', 'POST'])
def upload_resumes():
    data = load_data()

    if request.method == 'GET':
        resumes = data.get("resumes", [])
        result = []
        for r in reversed(resumes):
            filename = r.get("filename", "")
            original_name = r.get("original_filename") or filename
            filepath = os.path.join(UPLOAD_DIR, filename)
            size = os.path.getsize(filepath) if filename and os.path.exists(filepath) else 0
            result.append({
                "filename": filename,
                "display_name": original_name,
                "uploaded_at": r.get("uploaded_at", ""),
                "size": size,
                "status": r.get("status", "Uploaded"),
                "url": f"/uploads/{filename}" if filename else ""
            })

        return jsonify({"resumes": result})

    # POST Handling
    if 'resumes' not in request.files:
        return jsonify({"error": "No resume files received in the upload request."}), 400

    files = request.files.getlist('resumes')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "No files selected for upload."}), 400

    uploaded_records = []
    errors = []

    for file in files:
        if not file or not file.filename:
            continue

        raw_filename = file.filename
        ext = get_file_extension(raw_filename)

        if ext == 'doc':
            errors.append(f"'{raw_filename}': Legacy .doc format is not supported. Please upload as .docx or .pdf.")
            continue

        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"'{raw_filename}': Unsupported format. Allowed formats are PDF and DOCX.")
            continue

        valid_content, err_msg = validate_file_content(file, ext)
        if not valid_content:
            errors.append(f"'{raw_filename}': {err_msg}")
            continue

        safe_basename = secure_filename(raw_filename) or f"resume.{ext}"
        unique_stored_name = f"{uuid.uuid4().hex[:12]}_{safe_basename}"
        filepath = os.path.join(UPLOAD_DIR, unique_stored_name)

        try:
            file.save(filepath)
            uploaded_records.append({
                "filename": unique_stored_name,
                "original_filename": raw_filename,
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status": "Uploaded"
            })
        except Exception as save_err:
            logger.error("Failed to save file '%s': %s", raw_filename, save_err)
            errors.append(f"'{raw_filename}': Server could not save file.")

    if not uploaded_records and errors:
        return jsonify({"error": "Upload failed", "details": errors}), 400

    data.setdefault("resumes", [])
    data.setdefault("workflow", {})
    data.setdefault("current_screening", {})
    data.setdefault("stats", {})

    data["resumes"].extend(uploaded_records)

    resumes_count = len(data["resumes"])
    data["workflow"]["resumes_count"] = resumes_count
    data["current_screening"]["resumes_uploaded"] = resumes_count
    data["stats"]["resumes_uploaded"] = data["stats"].get("resumes_uploaded", 0) + len(uploaded_records)

    data["workflow"]["processing_status"] = "Not started"
    data["workflow"]["results_ready"] = False
    data["current_screening"]["processing_status"] = "Pending"
    data["results"] = []

    save_data(data)

    response_payload = {
        "message": f"Successfully uploaded {len(uploaded_records)} resume(s).",
        "uploaded_count": len(uploaded_records)
    }
    if errors:
        response_payload["warnings"] = errors

    return jsonify(response_payload), 200


@app.route('/api/process', methods=['POST'])
def process_resumes():
    data = load_data()

    job_descriptions = data.get("job_descriptions", [])
    resumes = data.get("resumes", [])

    if len(job_descriptions) == 0:
        return jsonify({"error": "No job description found. Please add a job description before processing."}), 400

    if len(resumes) == 0:
        return jsonify({"error": "No resumes found. Please upload at least one candidate resume."}), 400

    latest_jd = job_descriptions[-1]
    job_desc = latest_jd.get("description", "").strip()
    jd_skills = latest_jd.get("skills", [])

    if not job_desc:
        job_desc = latest_jd.get("title", "")

    # Extract text from resumes
    valid_resume_indices = []
    valid_resume_texts = []

    for idx, r in enumerate(resumes):
        text = r.get("text")
        if text is None:
            filename = r.get("filename", "")
            file_path = os.path.join(UPLOAD_DIR, filename)

            try:
                text = extract_text(file_path)
                r["text"] = text
                if not text:
                    r["extraction_error"] = "No extractable text found (scanned or empty document)."
            except Exception as exc:
                logger.warning("Text extraction failed for '%s': %s", filename, exc)
                text = ""
                r["text"] = ""
                r["extraction_error"] = str(exc)

        if text and len(text.strip()) > 0:
            valid_resume_indices.append(idx)
            valid_resume_texts.append(text)

    # Compute similarity embeddings for valid resumes
    scores_dict = {}
    if valid_resume_texts:
        documents = [job_desc] + valid_resume_texts
        embeddings = model.encode(documents)

        job_vector = embeddings[0]
        resume_vectors = embeddings[1:]

        raw_scores = cosine_similarity([job_vector], resume_vectors)[0]
        for v_idx, score in zip(valid_resume_indices, raw_scores):
            scores_dict[v_idx] = float(round(score * 100, 2))

    results = []
    for i, r in enumerate(resumes):
        resume_text = r.get("text", "")
        display_name = r.get("original_filename") or r.get("filename", f"Candidate {i+1}")
        matched = match_skills(resume_text, jd_skills)
        candidate_score = scores_dict.get(i, 0.0)

        record = {
            "name": display_name,
            "filename": r.get("filename"),
            "score": candidate_score,
            "skills": matched,
            "text": resume_text[:1000] if resume_text else ""
        }
        if r.get("extraction_error"):
            record["extraction_error"] = r["extraction_error"]

        results.append(record)

    # Step 3.2 Fix: Sort candidates by score descending first (deterministic tie-breaker by name)
    results.sort(key=lambda x: (-x["score"], x["name"].lower()))

    # Assign ranks strictly AFTER sorting
    for rank_idx, item in enumerate(results, 1):
        item["rank"] = rank_idx

    # Step 3.3 Fix: Collision-resistant screening ID generation
    data.setdefault("recent_screenings", [])
    job_title = latest_jd.get("title", "Untitled Role")
    screening_id = generate_screening_id(data["recent_screenings"])
    top_score = results[0]["score"] if results else 0.0

    screening_entry = {
        "id": screening_id,
        "job_title": job_title,
        "resumes": len(resumes),
        "date": datetime.now().strftime("%d %b"),
        "top_score": top_score,
        "results": results
    }
    data["recent_screenings"].insert(0, screening_entry)

    data["results"] = results
    data.setdefault("workflow", {})
    data["workflow"]["processing_status"] = "Completed"
    data["workflow"]["results_ready"] = True

    data.setdefault("current_screening", {})
    data["current_screening"]["processing_status"] = "Completed"
    data["current_screening"]["qualified"] = len([r for r in results if r.get("score", 0) >= 50])

    data["resumes"] = resumes

    data.setdefault("stats", {})
    data["stats"]["total_screenings"] = len(data["recent_screenings"])
    if results:
        data["stats"]["avg_match_score"] = round(
            sum(r.get("score", 0) for r in results) / len(results)
        )
        data["stats"]["top_candidate_score"] = round(max(r.get("score", 0) for r in results))

    save_data(data)
    logger.info("Screening %s completed for job '%s' with %d candidates.", screening_id, job_title, len(results))

    return jsonify({
        "message": "Processing complete",
        "screening_id": screening_id,
        "total_processed": len(results)
    })


@app.route('/api/results', methods=['GET'])
def get_results():
    data = load_data()
    return jsonify({
        "results": data.get("results", [])
    })


@app.route('/api/resume/<filename>', methods=['GET'])
def get_resume_details(filename):
    data = load_data()
    safe_filename = os.path.basename(filename)

    resume = next(
        (r for r in data.get("resumes", []) if r.get("filename") == safe_filename or r.get("original_filename") == safe_filename),
        None
    )

    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    # Sanitize response: do not expose server internal file paths
    return jsonify({
        "filename": resume.get("filename"),
        "original_filename": resume.get("original_filename") or resume.get("filename"),
        "uploaded_at": resume.get("uploaded_at"),
        "text": resume.get("text", "")[:2000]  # preview
    })


@app.route('/api/screening/<screening_id>', methods=['GET'])
def get_screening(screening_id):
    data = load_data()
    screening = next(
        (s for s in data.get("recent_screenings", []) if s.get("id") == screening_id),
        None
    )
    if screening:
        return jsonify(screening)
    return jsonify({"error": "Screening not found"}), 404


@app.route('/api/screening/<screening_id>', methods=['DELETE'])
def delete_screening(screening_id):
    data = load_data()
    screenings = data.get("recent_screenings", [])
    data["recent_screenings"] = [s for s in screenings if s.get("id") != screening_id]
    data["stats"]["total_screenings"] = len(data["recent_screenings"])
    save_data(data)
    return jsonify({"message": f"Screening {screening_id} deleted successfully."})


@app.route('/api/screening/new', methods=['POST'])
def new_screening():
    data = load_data()
    data["job_descriptions"] = []
    data["resumes"] = []
    data["results"] = []

    data["workflow"] = {
        "jd_added": False,
        "resumes_count": 0,
        "processing_status": "Not started",
        "results_ready": False
    }
    data["current_screening"] = {
        "job_title": "",
        "resumes_uploaded": 0,
        "qualified": 0,
        "jd_added": False,
        "processing_status": "Not started"
    }

    save_data(data)
    return jsonify({"message": "Started new screening session."})


@app.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset all data to defaults (useful for demo/clean state)."""
    data = get_default_data()
    save_data(data)
    return jsonify({"message": "Data reset to defaults."})


# ============================
# Server Runner
# ============================
if __name__ == '__main__':
    if not os.path.exists(DATA_FILE):
        save_data(get_default_data())

    # Step 2.2 Fix: Configurable debug mode via environment variable, defaulting to False
    flask_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    flask_port = int(os.environ.get("PORT", 5000))

    print("\n  Resume Screening System")
    print(f"  Dashboard:  http://127.0.0.1:{flask_port}")
    print(f"  API:        http://127.0.0.1:{flask_port}/api/dashboard")
    print(f"  Debug Mode: {'ENABLED (Dev only)' if flask_debug else 'DISABLED (Secure)'}\n")

    app.run(debug=flask_debug, host='127.0.0.1', port=flask_port)
