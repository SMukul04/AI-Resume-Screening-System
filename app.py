from collections import Counter

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import fitz  # PyMuPDF
import os
import json
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__, static_folder='../html', static_url_path='')
CORS(app)

model = SentenceTransformer('all-MiniLM-L6-v2')

COMMON_SKILLS = [
    "python", "java", "c++", "sql", "machine learning",
    "data analysis", "html", "css", "javascript",
    "react", "node", "excel", "pandas", "numpy"
]


def extract_skills(text):
    text = text.lower()
    found = [skill for skill in COMMON_SKILLS if skill in text]
    return found


# ============================
# In-Memory Data Store
# ============================
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')


def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {
            "job_descriptions": [],
            "resumes": [],
            "results": [],
            "workflow": {}
        }

    defaults = get_default_data()

    # Top-level defaults (so dashboard doesn't crash when file is cleared/minimal)
    data.setdefault("stats", defaults.get("stats", {}))
    data.setdefault("current_screening", defaults.get("current_screening", {}))
    data.setdefault("workflow", data.get("workflow") or defaults.get("workflow", {}))
    data.setdefault("recent_screenings", defaults.get("recent_screenings", []))

    data.setdefault("job_descriptions", defaults.get("job_descriptions", []))
    data.setdefault("resumes", defaults.get("resumes", []))
    data.setdefault("results", defaults.get("results", []))

    # Merge nested dict defaults
    if isinstance(defaults.get("workflow"), dict):
        data["workflow"] = data.get("workflow") or {}
        for k, v in defaults["workflow"].items():
            data["workflow"].setdefault(k, v)

    if isinstance(defaults.get("current_screening"), dict):
        data["current_screening"] = data.get("current_screening") or {}
        for k, v in defaults["current_screening"].items():
            data["current_screening"].setdefault(k, v)

    return data


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def extract_text_from_pdf(filepath):
    text = ""
    doc = fitz.open(filepath)
    for page in doc:
        text += page.get_text()
    return text


def calculate_similarity(job_desc, resumes):
    documents = [job_desc] + resumes

    embeddings = model.encode(documents)

    job_vector = embeddings[0]
    resume_vectors = embeddings[1:]

    scores = cosine_similarity([job_vector], resume_vectors)[0]

    return scores


def enhanced_score(base_score, skills, jd_skills):
    match_count = len(set(skills) & set(jd_skills))
    bonus = match_count * 5   # +5% per skill match
    return min(100, base_score * 100 + bonus)


def get_default_data():
    return {
        "stats": {
            "total_screenings": 8,
            "resumes_uploaded": 124,
            "avg_match_score": 67,
            "top_candidate_score": 91
        },
        "current_screening": {
            "job_title": "Data Analyst",
            "resumes_uploaded": 15,
            "qualified": 9,
            "jd_added": True,
            "processing_status": "Pending"
        },
        "workflow": {
            "jd_added": False,
            "resumes_count": 0,
            "processing_status": "Not started",
            "results_ready": False
        },
        "recent_screenings": [
            {
                "id": "SCR-001",
                "job_title": "Data Analyst",
                "resumes": 12,
                "date": "20 Feb",
                "top_score": 89
            },
            {
                "id": "SCR-002",
                "job_title": "Web Developer",
                "resumes": 8,
                "date": "18 Feb",
                "top_score": 76
            },
            {
                "id": "SCR-003",
                "job_title": "ML Engineer",
                "resumes": 20,
                "date": "15 Feb",
                "top_score": 92
            },
            {
                "id": "SCR-004",
                "job_title": "Python Developer",
                "resumes": 15,
                "date": "12 Feb",
                "top_score": 71
            }
        ],
        "job_descriptions": [],
        "resumes": []
    }


# ============================
# Serve Frontend
# ============================
@app.route('/')
def index():
    return send_from_directory('../html', 'dashboard.html')


@app.route('/<page>.html')
def serve_page(page):
    """Serve HTML pages: results, processing, upload-resumes, job-description, history."""
    return send_from_directory('../html', f'{page}.html')


@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('../css', filename)


@app.route('/javascript/<path:filename>')
def serve_js(filename):
    return send_from_directory('../javascript', filename)


@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    return send_from_directory(upload_dir, filename)


# ============================
# API Routes
# ============================
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    data = load_data()
    results = data.get("results", [])
    recent_screenings = data.get("recent_screenings", [])

    # Keep dashboard cards synchronized with history table values.
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
        body = request.json or {}

        title = body.get("title", "")
        description = body.get("description", "")
        skills = body.get("skills", [])

        data = load_data()

        if "job_descriptions" not in data:
            data["job_descriptions"] = []

        data["job_descriptions"].append({
            "title": title,
            "description": description,
            "skills": skills,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        # Keep dashboard state in sync with current workflow step.
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

        return jsonify({"message": "Job description added"}), 201

    return jsonify({
        "job_descriptions": data.get("job_descriptions", []),
        "current": data["current_screening"]
    })


@app.route('/api/upload-resumes', methods=['GET', 'POST'])
def upload_resumes():
    data = load_data()

    if request.method == 'GET':
        upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
        resumes = data.get("resumes", [])

        # Show newest uploads first
        result = []
        for r in reversed(resumes):
            filename = r.get("filename", "")
            filepath = os.path.join(upload_dir, filename)
            size = os.path.getsize(filepath) if filename and os.path.exists(filepath) else 0
            result.append({
                "filename": filename,
                "uploaded_at": r.get("uploaded_at", ""),
                "size": size,
                "status": "Uploaded",
                "url": f"/uploads/{filename}" if filename else ""
            })

        return jsonify({"resumes": result})

    files = request.files.getlist('resumes')

    if "resumes" not in data:
        data["resumes"] = []

    data.setdefault("workflow", {})
    data.setdefault("current_screening", {})
    data.setdefault("stats", {})

    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    for file in files:
        filename = file.filename
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        data["resumes"].append({
            "filename": filename,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

    # Sync dashboard counters/state.
    resumes_count = len(data.get("resumes", []))
    data["workflow"]["resumes_count"] = resumes_count
    data["current_screening"]["resumes_uploaded"] = resumes_count
    data["stats"]["resumes_uploaded"] = data["stats"].get("resumes_uploaded", 0) + len(files)

    data["workflow"]["processing_status"] = "Not started"
    data["workflow"]["results_ready"] = False
    data["current_screening"]["processing_status"] = "Pending"
    data["results"] = []

    save_data(data)

    return jsonify({"message": "Resumes uploaded successfully"})


@app.route('/api/process', methods=['POST'])
def process_resumes():
    data = load_data()

    job_descriptions = data.get("job_descriptions", [])
    resumes = data.get("resumes", [])

    if len(job_descriptions) == 0 or len(resumes) == 0:
        return jsonify({"error": "Missing data"}), 400

    latest_jd = job_descriptions[-1]
    job_desc = latest_jd["description"]
    jd_skills = latest_jd.get("skills", [])
    resume_texts = []

    for r in resumes:
        if "text" in r:
            resume_texts.append(r["text"])
        else:
            # Read PDF again if extracted text isn't present
            file_path = os.path.join("uploads", r["filename"])
            text = ""

            try:
                doc = fitz.open(file_path)
                for page in doc:
                    text += page.get_text()
            except:
                text = ""

            resume_texts.append(text)
            r["text"] = text  # save for future

    # AI similarity
    documents = [job_desc] + resume_texts
    embeddings = model.encode(documents)

    job_vector = embeddings[0]
    resume_vectors = embeddings[1:]

    scores = cosine_similarity([job_vector], resume_vectors)[0]

    results = []

    for i, score in enumerate(scores):
        resume_text_lower = resumes[i].get("text", "").lower()
        matched_skills = [s for s in jd_skills if str(s).lower() in resume_text_lower]

        results.append({
            "rank": i + 1,
            "name": resumes[i]["filename"],
            "score": float(round(score * 100, 2)),
            # Show JD-selected skills that actually appear in this resume.
            "skills": matched_skills,
            "text": resumes[i]["text"]
        })

    # sort
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Save screening into history so dashboard "View" can show old results
    data.setdefault("recent_screenings", [])
    job_title = job_descriptions[-1].get("title", "") if job_descriptions else ""
    screening_id = f"SCR-{len(data['recent_screenings']) + 1:03d}"
    top_score = results[0]["score"] if results else 0

    screening_entry = {
        "id": screening_id,
        "job_title": job_title,
        "resumes": len(resumes),
        "date": datetime.now().strftime("%d %b"),
        "top_score": top_score,
        # Keep full results for this screening (used by results.html with ?screening=)
        "results": results
    }
    data["recent_screenings"].insert(0, screening_entry)

    # SAVE (MOST IMPORTANT)
    data["results"] = results

    # Ensure workflow exists
    if "workflow" not in data:
        data["workflow"] = {}

    data["workflow"]["processing_status"] = "Completed"
    data["workflow"]["results_ready"] = True
    data.setdefault("current_screening", {})
    data["current_screening"]["processing_status"] = "Completed"
    data["current_screening"]["qualified"] = len([r for r in results if r.get("score", 0) >= 50])

    data["resumes"] = resumes

    # Sync headline dashboard stats.
    data.setdefault("stats", {})
    data["stats"]["total_screenings"] = len(data.get("recent_screenings", []))
    if results:
        data["stats"]["avg_match_score"] = round(
            sum(r.get("score", 0) for r in results) / len(results)
        )
        data["stats"]["top_candidate_score"] = round(max(r.get("score", 0) for r in results))

    save_data(data)

    return jsonify({"message": "Processing complete"})


@app.route('/api/results', methods=['GET'])
def get_results():
    data = load_data()
    return jsonify({
        "results": data.get("results", [])
    })


@app.route('/api/resume/<filename>', methods=['GET'])
def get_resume_details(filename):
    data = load_data()

    resume = next(
        (r for r in data.get("resumes", []) if r["filename"] == filename),
        None
    )

    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    return jsonify(resume)


@app.route('/api/screening/<screening_id>', methods=['GET'])
def get_screening(screening_id):
    data = load_data()
    screening = next(
        (s for s in data["recent_screenings"] if s["id"] == screening_id),
        None
    )
    if screening:
        return jsonify(screening)
    return jsonify({"error": "Screening not found"}), 404


@app.route('/api/screening/<screening_id>', methods=['DELETE'])
def delete_screening(screening_id):
    data = load_data()
    data["recent_screenings"] = [
        s for s in data["recent_screenings"] if s["id"] != screening_id
    ]
    data["stats"]["total_screenings"] = len(data["recent_screenings"])
    save_data(data)
    return jsonify({"message": f"Screening {screening_id} deleted"})


@app.route('/api/screening/new', methods=['POST'])
def new_screening():
    data = load_data()
    # Clear active session data
    data["job_descriptions"] = []
    data["resumes"] = []
    data["results"] = []
    
    # Reset workflow and current screening
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
    return jsonify({"message": "Started new screening session"})


@app.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset all data to defaults (useful for demo)."""
    data = get_default_data()
    save_data(data)
    return jsonify({"message": "Data reset to defaults"})


# ============================
# Run Server
# ============================
if __name__ == '__main__':
    if not os.path.exists(DATA_FILE):
        save_data(get_default_data())
    print("\n  Resume Screening System")
    print("  Dashboard: http://127.0.0.1:5000")
    print("  API:       http://127.0.0.1:5000/api/dashboard\n")
    app.run(debug=True, port=5000)
