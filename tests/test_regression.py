import os
import io
import re
import json
import pytest
import docx
import fitz

# Import the application from the python package directory
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'python'))

import app


# ==========================================
# Test Fixtures & Synthetic File Generators
# ==========================================
def create_synthetic_pdf(text="Senior Python Software Engineer with Machine Learning and SQL expertise."):
    """Generate a valid, synthetic in-memory PDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return io.BytesIO(pdf_bytes)


def create_synthetic_docx(text="Data Analyst proficient in Python, SQL, pandas and statistical analysis."):
    """Generate a valid, synthetic in-memory DOCX."""
    doc = docx.Document()
    doc.add_heading("Candidate Resume", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """
    Isolate tests in a temporary directory to guarantee zero contamination
    of real data.json or uploaded resumes.
    """
    test_upload_dir = tmp_path / "uploads"
    test_upload_dir.mkdir()
    test_data_file = tmp_path / "data.json"
    test_backup_file = tmp_path / "data.json.bak"

    # Seed isolated data
    initial_data = app.get_default_data()
    with open(test_data_file, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, indent=4)

    monkeypatch.setattr(app, 'UPLOAD_DIR', str(test_upload_dir))
    monkeypatch.setattr(app, 'DATA_FILE', str(test_data_file))
    monkeypatch.setattr(app, 'DATA_BACKUP_FILE', str(test_backup_file))

    yield {
        "upload_dir": str(test_upload_dir),
        "data_file": str(test_data_file),
        "backup_file": str(test_backup_file)
    }


@pytest.fixture
def client(isolated_env):
    """Flask test client running against isolated test environment."""
    app.app.config['TESTING'] = True
    with app.app.test_client() as client:
        yield client


# ==========================================
# 1. Application Initialization & Config
# ==========================================
def test_app_initialization():
    """Verify Flask application is initialized with expected security settings."""
    assert app.app is not None
    assert app.app.config['MAX_CONTENT_LENGTH'] == 16 * 1024 * 1024
    assert 'pdf' in app.ALLOWED_EXTENSIONS
    assert 'docx' in app.ALLOWED_EXTENSIONS


# ==========================================
# 2. Existing GET Routes
# ==========================================
@pytest.mark.parametrize("route", [
    '/',
    '/dashboard.html',
    '/job-description.html',
    '/upload-resumes.html',
    '/processing.html',
    '/results.html',
    '/history.html',
    '/resume-details.html',
    '/api/dashboard',
    '/api/stats',
    '/api/job-description',
    '/api/upload-resumes',
    '/api/results'
])
def test_existing_get_routes(client, route):
    """Ensure all core pages and API endpoints return HTTP 200."""
    res = client.get(route)
    assert res.status_code == 200, f"Route {route} failed with status {res.status_code}"


# ==========================================
# 3. Valid PDF Upload
# ==========================================
def test_valid_pdf_upload(client):
    """Verify valid PDF resumes are accepted, safely named, and stored."""
    pdf_stream = create_synthetic_pdf()
    data = {
        'resumes': (pdf_stream, 'john_doe_resume.pdf')
    }
    res = client.post('/api/upload-resumes', data=data, content_type='multipart/form-data')
    assert res.status_code == 200
    json_data = res.get_json()
    assert "Successfully uploaded 1 resume(s)" in json_data['message']

    # Check listing
    get_res = client.get('/api/upload-resumes')
    resumes = get_res.get_json()['resumes']
    assert len(resumes) == 1
    assert resumes[0]['display_name'] == 'john_doe_resume.pdf'
    assert resumes[0]['filename'].endswith('_john_doe_resume.pdf')


# ==========================================
# 4. Valid DOCX Upload
# ==========================================
def test_valid_docx_upload(client):
    """Verify valid DOCX resumes are accepted, validated, and listed."""
    docx_stream = create_synthetic_docx()
    data = {
        'resumes': (docx_stream, 'jane_smith_resume.docx')
    }
    res = client.post('/api/upload-resumes', data=data, content_type='multipart/form-data')
    assert res.status_code == 200

    get_res = client.get('/api/upload-resumes')
    resumes = get_res.get_json()['resumes']
    assert any(r['display_name'] == 'jane_smith_resume.docx' for r in resumes)


# ==========================================
# 5. Invalid File Extension Rejection
# ==========================================
def test_invalid_extension_and_legacy_doc_rejection(client):
    """Verify malicious files (.exe) and legacy (.doc) files are rejected with clear errors."""
    # 5a: Malicious executable
    bad_stream = io.BytesIO(b"malicious script")
    res = client.post(
        '/api/upload-resumes',
        data={'resumes': (bad_stream, 'exploit.exe')},
        content_type='multipart/form-data'
    )
    assert res.status_code == 400
    assert "Unsupported format" in res.get_json()['details'][0]

    # 5b: Legacy .doc file
    doc_stream = io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1 legacy word")
    res2 = client.post(
        '/api/upload-resumes',
        data={'resumes': (doc_stream, 'legacy_resume.doc')},
        content_type='multipart/form-data'
    )
    assert res2.status_code == 400
    assert "Legacy .doc format is not supported" in res2.get_json()['details'][0]


# ==========================================
# 6. Oversized Upload Rejection
# ==========================================
def test_oversized_upload_rejection(client):
    """Verify uploads exceeding 16 MB are rejected by Flask with HTTP 413."""
    oversized_data = io.BytesIO(b"0" * (16 * 1024 * 1024 + 1024))
    res = client.post(
        '/api/upload-resumes',
        data={'resumes': (oversized_data, 'huge.pdf')},
        content_type='multipart/form-data'
    )
    assert res.status_code == 413
    assert "File size exceeds the maximum allowed limit" in res.get_json()['error']


# ==========================================
# 7. Path Traversal Prevention
# ==========================================
def test_path_traversal_prevention(client, isolated_env):
    """Verify path traversal characters in filenames are sanitized and cannot escape upload directory."""
    pdf_stream = create_synthetic_pdf()
    traversal_name = "../../../system_attack.pdf"
    res = client.post(
        '/api/upload-resumes',
        data={'resumes': (pdf_stream, traversal_name)},
        content_type='multipart/form-data'
    )
    assert res.status_code == 200

    # Ensure no file was created outside isolated_env['upload_dir']
    parent_dir = os.path.dirname(isolated_env['upload_dir'])
    assert not os.path.exists(os.path.join(parent_dir, "system_attack.pdf"))

    # Ensure get /uploads/ rejects path traversal attempts
    res_exploit = client.get('/uploads/..%2f..%2fdata.json')
    assert res_exploit.status_code in (400, 404)


# ==========================================
# 8. PDF Text Extraction
# ==========================================
def test_pdf_text_extraction(tmp_path):
    """Verify PyMuPDF extracts text correctly from a PDF document."""
    pdf_path = tmp_path / "sample.pdf"
    expected_content = "Antigravity AI Engineer with deep knowledge of Python and PyTorch."
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), expected_content)
    doc.save(str(pdf_path))
    doc.close()

    extracted = app.extract_text(str(pdf_path))
    assert "Antigravity AI Engineer" in extracted
    assert "PyTorch" in extracted


# ==========================================
# 9. DOCX Text Extraction
# ==========================================
def test_docx_text_extraction(tmp_path):
    """Verify python-docx extracts paragraphs and tables from a DOCX document."""
    docx_path = tmp_path / "sample.docx"
    doc = docx.Document()
    doc.add_paragraph("Machine Learning Specialist with Python skills.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "SQL Database"
    table.rows[0].cells[1].text = "Cloud AWS"
    doc.save(str(docx_path))

    extracted = app.extract_text(str(docx_path))
    assert "Machine Learning Specialist" in extracted
    assert "SQL Database" in extracted
    assert "Cloud AWS" in extracted


# ==========================================
# 10. Missing or Corrupted File Handling
# ==========================================
def test_missing_or_corrupted_file_handling(tmp_path):
    """Verify corrupted or non-existent files fail gracefully with explicit errors."""
    # Non-existent file
    with pytest.raises(FileNotFoundError):
        app.extract_text(str(tmp_path / "does_not_exist.pdf"))

    # Corrupted PDF
    corrupt_pdf = tmp_path / "corrupt.pdf"
    with open(corrupt_pdf, 'wb') as f:
        f.write(b"%PDF-1.4\ncorrupted gibberish that is not valid pdf structure")

    with pytest.raises(Exception):
        app.extract_text_from_pdf(str(corrupt_pdf))


# ==========================================
# 11 & 12. Candidate Score Ordering & Rank Consistency
# ==========================================
def test_candidate_score_ordering_and_rank_consistency(client):
    """
    Verify candidates are sorted in descending score order and
    ranks (1, 2, 3...) are assigned strictly AFTER sorting.
    """
    # 1. Post a Job Description looking for Python and Machine Learning
    client.post('/api/job-description', json={
        "title": "Senior AI Engineer",
        "description": "Looking for Python, Machine Learning, Deep Learning, PyTorch and NLP.",
        "skills": ["Python", "Machine Learning", "NLP"]
    })

    # 2. Upload three synthetic resumes with differing relevance
    # Resume A: Highly relevant
    resume_a = create_synthetic_pdf(
        "Senior AI Engineer with extensive Python, Machine Learning, Deep Learning, PyTorch and NLP experience."
    )
    # Resume B: Moderately relevant
    resume_b = create_synthetic_pdf(
        "Software developer familiar with Python and basic web development."
    )
    # Resume C: Irrelevant
    resume_c = create_synthetic_pdf(
        "Experienced accountant specializing in payroll, tax audits and balance sheets."
    )

    client.post('/api/upload-resumes', data={
        'resumes': [
            (resume_a, 'resume_expert.pdf'),
            (resume_b, 'resume_moderate.pdf'),
            (resume_c, 'resume_accountant.pdf')
        ]
    }, content_type='multipart/form-data')

    # 3. Trigger processing
    proc_res = client.post('/api/process')
    assert proc_res.status_code == 200

    # 4. Fetch results
    results_res = client.get('/api/results')
    assert results_res.status_code == 200
    results = results_res.get_json()['results']
    assert len(results) == 3

    # Assert scores are strictly non-increasing (descending order)
    scores = [r['score'] for r in results]
    assert scores == sorted(scores, reverse=True), f"Scores are not sorted descending: {scores}"

    # Assert ranks are 1, 2, 3 in order
    ranks = [r['rank'] for r in results]
    assert ranks == [1, 2, 3], f"Ranks are inconsistent: {ranks}"

    # Verify top candidate is the AI expert
    assert results[0]['name'] == 'resume_expert.pdf'
    assert results[0]['score'] > results[1]['score']
    assert results[1]['score'] > results[2]['score']


# ==========================================
# 13. Collision-Resistant Screening ID Generation
# ==========================================
def test_collision_resistant_screening_id():
    """Verify screening IDs are monotonic and never collide, even after deletion."""
    screenings = [
        {"id": "SCR-001", "job_title": "A"},
        {"id": "SCR-002", "job_title": "B"},
        {"id": "SCR-003", "job_title": "C"}
    ]
    # Next ID should be SCR-004
    assert app.generate_screening_id(screenings) == "SCR-004"

    # Simulate deletion of SCR-002 and SCR-003
    screenings_after_delete = [
        {"id": "SCR-001", "job_title": "A"}
    ]
    # With only 1 item remaining, len+1 would have yielded SCR-002 (collision with deleted history!)
    # The new function generates SCR-002
    assert app.generate_screening_id(screenings_after_delete) == "SCR-002"

    # If SCR-037 is present, next must be SCR-038
    screenings_with_high = [
        {"id": "SCR-037", "job_title": "Z"},
        {"id": "SCR-010", "job_title": "Y"}
    ]
    assert app.generate_screening_id(screenings_with_high) == "SCR-038"


# ==========================================
# 14. Historical Data Preservation & Persistence
# ==========================================
def test_historical_data_preservation(client, isolated_env):
    """Verify screening records persist in data.json and can be retrieved via /api/screening/<id>."""
    # Create screening session
    client.post('/api/job-description', json={
        "title": "Backend Lead",
        "description": "Python, Flask, microservices.",
        "skills": ["Python"]
    })
    pdf = create_synthetic_pdf("Python backend engineer with Flask.")
    client.post('/api/upload-resumes', data={'resumes': (pdf, 'dev.pdf')}, content_type='multipart/form-data')

    proc = client.post('/api/process')
    screening_id = proc.get_json()['screening_id']

    # Retrieve specific historical screening
    hist_res = client.get(f'/api/screening/{screening_id}')
    assert hist_res.status_code == 200
    hist_data = hist_res.get_json()
    assert hist_data['id'] == screening_id
    assert hist_data['job_title'] == "Backend Lead"
    assert len(hist_data['results']) == 1

    # Verify physical file persistence on disk
    with open(isolated_env['data_file'], 'r', encoding='utf-8') as f:
        disk_data = json.load(f)
    assert any(s['id'] == screening_id for s in disk_data['recent_screenings'])


# ==========================================
# 15. Prevention of Redundant Processing
# ==========================================
def test_prevent_redundant_processing_when_data_missing(client):
    """Verify /api/process returns 400 with meaningful error when prerequisites are missing."""
    # Reset data
    client.post('/api/screening/new')

    # Calling process without JD and without Resumes
    res1 = client.post('/api/process')
    assert res1.status_code == 400
    assert "No job description found" in res1.get_json()['error']

    # Add JD only
    client.post('/api/job-description', json={"title": "Test Role", "description": "desc"})
    res2 = client.post('/api/process')
    assert res2.status_code == 400
    assert "No resumes found" in res2.get_json()['error']


# ==========================================
# 16. Existing API Response Compatibility
# ==========================================
def test_api_response_compatibility(client):
    """Verify dashboard and stats responses adhere strictly to the existing schema."""
    dash_res = client.get('/api/dashboard')
    assert dash_res.status_code == 200
    dash = dash_res.get_json()

    # Required top-level keys
    for key in ['stats', 'current_screening', 'workflow', 'recent_screenings', 'top_skills']:
        assert key in dash, f"Missing key in /api/dashboard: {key}"

    # Required stats subkeys
    for sk in ['total_screenings', 'resumes_uploaded', 'avg_match_score', 'top_candidate_score']:
        assert sk in dash['stats']

    stats_res = client.get('/api/stats')
    assert stats_res.status_code == 200
    stats = stats_res.get_json()
    assert 'total_screenings' in stats
    assert 'resumes_uploaded' in stats

