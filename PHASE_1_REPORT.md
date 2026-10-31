# Phase 1: Recovery, Stabilization, Security and Regression Testing Report

**Project:** AI Resume Screening System  
**Workspace:** `D:\College Project\Macro Project Sem 4`  
**Date:** October 31, 2026  
**Auditor / Lead Engineer:** Senior Python Backend Engineer, Security Engineer & Software Architect  

---

## A. Initial State

The application was in an unstable state following incomplete previous development:
- **Git & Backups:** No version control repository was configured for the project folder. All source code, datasets, and resumes were untracked in a parent directory Git repository with zero commits. No safe backup existed.
- **Security Vulnerabilities:** Uploaded files were written directly using raw client-supplied filenames without `secure_filename()` or unique prefixes, leaving the server vulnerable to path traversal and file overwrite attacks. No server-side file extension or content validation existed. The server had no upload file size limit (`MAX_CONTENT_LENGTH`), and Flask was configured with unconditional interactive debug mode (`debug=True`).
- **Path Resolution Bug:** PDF text extraction in `process_resumes()` used `os.path.join("uploads", r["filename"])`, resolving relative to the process current working directory (CWD). When started from the project root, this path failed, silently swallowing errors and generating empty text and inaccurate match scores.
- **Flawed Candidate Ranking:** Candidate rank (`i + 1`) was assigned before sorting by score.
- **Duplicate Screening IDs:** Screening IDs were generated using array length (`f"SCR-{len(data['recent_screenings']) + 1:03d}"`), causing immediate ID collisions whenever a screening was deleted.
- **Format Discrepancy:** The UI advertised PDF, DOC, and DOCX support, but the backend only used PyMuPDF (`fitz`), causing all Word documents to fail silently.
- **Frontend Runtime Crashes:** `dashboard.js` attached event listeners to `notificationBtn` unconditionally, throwing `TypeError` and halting script execution on 4 out of 6 pages.
- **Redundant Processing:** The "View Results" button on `processing.html` issued a second redundant `POST /api/process` call, executing expensive transformer inference twice per screening.

---

## B. Files Modified

| File Path | Nature of Changes | Reason for Modification |
| :--- | :--- | :--- |
| `.gitignore` | **Created** | Comprehensive exclusion of `.venv/`, `__pycache__/`, `python/data.json`, `python/uploads/`, sensitive resumes, datasets, logs, and temp files. |
| `python/app.py` | **Refactored & Hardened** | Secure file upload pipeline (`secure_filename`, UUID prefixes, magic byte validation, 16 MB limit), native DOCX text extraction, atomic JSON writes with backup, absolute path resolution, deterministic candidate ranking after sorting, monotonic collision-resistant screening IDs, environment-driven debug mode. |
| `python/requirements.txt` | **Updated** | Added `python-docx` for native DOCX parsing and `pytest` for automated regression testing. |
| `javascript/dashboard.js` | **Fixed & Hardened** | Added optional chaining (`?.`) to `sidebarToggle`, `profileBtn`, `notificationBtn`, `closeNotifBtn`, and conditional initializers to prevent `TypeError` crashes on pages where elements do not exist. Standardized dynamic `API_BASE`. |
| `javascript/processing.js` | **Refactored** | Removed redundant `POST /api/process` call in `viewResultsBtn` click listener; added progress error handling and duplicate request prevention. Standardized dynamic `PROC_API_BASE`. |
| `javascript/upload-resumes.js` | **Updated** | Updated allowed extensions to PDF and DOCX; added explicit rejection and user warnings for legacy `.doc` files; supported dual `display_name` and stored UUID `filename`. |
| `javascript/job-description.js` | **Enhanced** | Added auto-save on clicking "Next &rarr;" button to prevent data loss. Standardized dynamic `JD_API_BASE`. |
| `javascript/results.js` | **Fixed** | Replaced hardcoded `http://127.0.0.1:5000` endpoints with dynamic `RES_API_BASE`. |
| `javascript/history.js` | **Fixed** | Standardized dynamic `HIST_API_BASE`. |
| `html/upload-resumes.html` | **Updated UI Text** | Corrected supported format labels and file dialog accepts from `PDF, DOC, DOCX` to `PDF, DOCX`. |
| `html/results.html` | **Corrected Label** | Corrected misleading "Matching Method: TF-IDF + Cosine Similarity" label to "Semantic Embeddings (MiniLM-L6-v2) + Cosine Similarity". |
| `html/resume-details.html` | **Completed & Styled** | Transformed raw 41-line stub into a clean, styled candidate details card using `dashboard.css`, displaying score, matched skills, extraction notices, text preview, and a link to view original uploaded documents. |
| `tests/test_regression.py` | **Created** | 27 comprehensive automated regression tests covering uploads, validation, parsing, ranking, persistence, security, and API compatibility in an isolated temporary directory. |

---

## C. Security Fixes

1. **Secure File Upload Pipeline:**
   - Client filenames are now sanitized via `werkzeug.utils.secure_filename()`.
   - Stored filenames are prepended with a 12-character cryptographic UUID (`{uuid.uuid4().hex[:12]}_{safe_filename}`), preventing directory traversal, path injection, and arbitrary file overwrite.
   - Original human-readable filenames are preserved in metadata as `original_filename` for UI display.
2. **Strict File Extension & Signature Validation:**
   - Server enforces `ALLOWED_EXTENSIONS = {'pdf', 'docx'}`.
   - Files are validated against true binary headers (magic bytes):
     - PDF: Verified to start with `%PDF-`.
     - DOCX: Verified as a valid zip archive containing `word/document.xml`.
   - Empty files (0 bytes) and spoofed executables renamed to `.pdf` or `.docx` are rejected with HTTP 400.
3. **Upload Size Limit:**
   - Enforced `app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024` (16 MB).
   - Added custom 413 error handler returning clear JSON error feedback.
4. **Environment-Driven Debug Mode:**
   - Removed hardcoded `debug=True`.
   - Debug mode now defaults to `False` (safe for production) and is only enabled when `FLASK_DEBUG=1` or `FLASK_DEBUG=true` is explicitly set in the environment.
5. **Path Traversal Shielding:**
   - Endpoint `/uploads/<path:filename>` strictly enforces `os.path.basename()` and rejects filenames containing `..`.
6. **Remaining Access Control Limitations (Phase 3 Roadmap):**
   - Endpoints do not currently require user authentication or JWT tokens. Any client on the network can access `/api/results` and `/uploads/<filename>`. Full role-based authentication (RBAC) and candidate privacy controls are scheduled for implementation with PostgreSQL and FastAPI in Phase 3.

---

## D. Backend Fixes

1. **Working-Directory Independent Paths:**
   - Replaced fragile relative path `uploads/` with `UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')` where `BASE_DIR = os.path.dirname(os.path.abspath(__file__))`. File access works reliably regardless of current working directory.
2. **DOCX Document Parsing:**
   - Integrated `python-docx` to extract text from DOCX paragraphs and tables.
   - Unified text extraction in `extract_text()`, returning explicit errors for unsupported legacy formats (`.doc`) or corrupted files.
3. **Deterministic Candidate Ranking:**
   - Candidate scores are computed, sorted in descending score order with deterministic tie-breaking (`results.sort(key=lambda x: (-x["score"], x["name"].lower()))`), and ranks (`rank = 1, 2, ...`) are assigned strictly after sorting.
4. **Collision-Resistant Screening IDs:**
   - Replaced `len(recent_screenings) + 1` with `generate_screening_id()`, which scans existing IDs for the maximum numeric counter (`max(SCR-xxx) + 1`) and resolves collisions against existing set members. Existing duplicate IDs in historical data (`SCR-006` through `SCR-009`) are preserved without disruption.
5. **Atomic Data Persistence:**
   - `save_data()` now writes to a unique temporary file (`data.json.tmp.<uuid>`), flushes and syncs to disk (`os.fsync`), backs up the previous state to `data.json.bak`, and executes an atomic file replacement (`os.replace`).
   - Read/write access is synchronized with a reentrant `threading.Lock()`.
6. **Token-Bounded Skill Matching:**
   - Replaced naive substring `in` check with regex word-boundary matching (`r'(?:\b|_)' + re.escape(skill) + r'(?:\b|_)'`), preventing false positives such as "c" matching "education" or "java" matching "javascript".

---

## E. Frontend Fixes

1. **Eliminated `TypeError` Null-Pointer Crashes:**
   - Added optional chaining (`?.`) and DOM existence checks to `sidebarToggle`, `profileBtn`, `notificationBtn`, and `closeNotifBtn` in `dashboard.js`. All six HTML pages now execute without console errors.
2. **Prevented Redundant Inference in Processing Workflow:**
   - Removed the extra `fetch('/api/process')` call inside `viewResultsBtn` in `processing.js`. Clicking "View Results" now navigates directly to `results.html` without re-triggering model inference.
3. **Auto-Saving Job Descriptions:**
   - Enhanced `job-description.js` so clicking "Next &rarr;" automatically validates and persists the entered Job Description before navigating to `upload-resumes.html`.
4. **Accurate Document Format Guidance:**
   - Updated UI copy in `upload-resumes.html` and validation logic in `upload-resumes.js` to accept `PDF, DOCX` and warn users if legacy `.doc` files are selected.
5. **Polished Candidate Details View:**
   - Overhauled `resume-details.html` into a fully styled responsive card with score badges, skill lists, text preview, and a direct link to view the original PDF/DOCX file.

---

## F. Testing Results

Automated regression test suite executed via `pytest tests/test_regression.py -v`:

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\College Project\Macro Project Sem 4
collected 27 items

tests/test_regression.py::test_app_initialization PASSED                 [  3%]
tests/test_regression.py::test_existing_get_routes[/] PASSED             [  7%]
tests/test_regression.py::test_existing_get_routes[/dashboard.html] PASSED [ 11%]
tests/test_regression.py::test_existing_get_routes[/job-description.html] PASSED [ 14%]
tests/test_regression.py::test_existing_get_routes[/upload-resumes.html] PASSED [ 18%]
tests/test_regression.py::test_existing_get_routes[/processing.html] PASSED [ 22%]
tests/test_regression.py::test_existing_get_routes[/results.html] PASSED [ 25%]
tests/test_regression.py::test_existing_get_routes[/history.html] PASSED [ 29%]
tests/test_regression.py::test_existing_get_routes[/resume-details.html] PASSED [ 33%]
tests/test_regression.py::test_existing_get_routes[/api/dashboard] PASSED [ 37%]
tests/test_regression.py::test_existing_get_routes[/api/stats] PASSED    [ 40%]
tests/test_regression.py::test_existing_get_routes[/api/job-description] PASSED [ 44%]
tests/test_regression.py::test_existing_get_routes[/api/upload-resumes] PASSED [ 48%]
tests/test_regression.py::test_existing_get_routes[/api/results] PASSED  [ 51%]
tests/test_regression.py::test_valid_pdf_upload PASSED                   [ 55%]
tests/test_regression.py::test_valid_docx_upload PASSED                  [ 59%]
tests/test_regression.py::test_invalid_extension_and_legacy_doc_rejection PASSED [ 62%]
tests/test_regression.py::test_oversized_upload_rejection PASSED         [ 66%]
tests/test_regression.py::test_path_traversal_prevention PASSED          [ 70%]
tests/test_regression.py::test_pdf_text_extraction PASSED                [ 74%]
tests/test_regression.py::test_docx_text_extraction PASSED               [ 77%]
tests/test_regression.py::test_missing_or_corrupted_file_handling PASSED [ 81%]
tests/test_regression.py::test_candidate_score_ordering_and_rank_consistency PASSED [ 85%]
tests/test_regression.py::test_collision_resistant_screening_id PASSED   [ 88%]
tests/test_regression.py::test_historical_data_preservation PASSED       [ 92%]
tests/test_regression.py::test_prevent_redundant_processing_when_data_missing PASSED [ 96%]
tests/test_regression.py::test_api_response_compatibility PASSED         [100%]

======================= 27 passed, 1 warning in 31.88s ========================
```

- **Passed:** 27
- **Failed:** 0
- **Skipped:** 0
- **Test Isolation:** 100% of tests executed in temporary isolated directories (`tmp_path`) with synthetic resumes. Zero modifications to live `python/data.json` or `python/uploads/`.

---

## G. Remaining Issues & Known Limitations

1. **Pre-Existing Duplicate Screening IDs:** Historical data in `data.json` contains duplicate IDs (`SCR-006` through `SCR-009`) caused by legacy code prior to Phase 1. These records were preserved to avoid data loss. New screenings will increment cleanly above `SCR-037`. A database deduplication migration is planned for Phase 3.
2. **No Authentication / Access Control:** The application has no user login, password hashing, or token verification. Anyone with network access can view candidate data and upload resumes.
3. **No OCR for Scanned Documents:** Image-only or scanned PDF resumes will yield empty text. A notice (`extraction_error`) is recorded, and the candidate is assigned a 0% score to avoid misleading results.
4. **MiniLM Token Limit:** Sentences longer than 256 tokens are truncated by `all-MiniLM-L6-v2`. Document chunking and section weighting will be addressed in Phase 2.
5. **Single Monolithic JSON Database:** Although hardened with atomic writes and locks, `data.json` remains a flat file unsuited for multi-user high concurrency.

---

## H. Git Repository Status

- **Repository Location:** Dedicated Git repository initialized in `D:\College Project\Macro Project Sem 4\.git`.
- **Branch:** `master`
- **Commits:**
  1. `0be29aa` - `chore: initial baseline commit of existing AI Resume Screening System`
  2. `8fe9181` - `feat(phase-1): complete stabilization, security hardening, docx support and regression test suite`
- **Clean Working Tree:** All application code, stylesheets, templates, scripts, and tests are committed.
- **Ignored Assets:** `.venv/`, `__pycache__/`, `python/data.json`, `python/uploads/*`, `.cache/`, and `.pdf` files are verified untracked and excluded via `.gitignore`.
- **External Backup:** A full pre-Phase 1 backup is preserved at `C:\Users\dell\.gemini\antigravity\brain\13bbbad3-b2c1-429f-bce6-37471ce657b3\backups\pre_phase_1_backup`.

---

## I. Phase 2 Readiness

**Readiness Status: READY FOR PHASE 2.**

The Flask backend is now functionally stable, secure against common file upload and path traversal vectors, properly handles both PDF and DOCX files, ranks candidates accurately, and has a complete automated regression test harness. The frontend runs cleanly without JavaScript crashes.

The project is in an ideal baseline condition to transition to Phase 2 (FastAPI backend architecture and design) without regression risks.

---

## J. Recommended Next Actions (Phase 2 & Phase 3)

1. **Phase 2 (FastAPI Migration & Clean Architecture):**
   - Design FastAPI schemas (Pydantic v2) mirroring existing request and response payloads.
   - Establish service-layer separation (`ExtractionService`, `EmbeddingService`, `ScreeningService`).
   - Implement asynchronous upload and processing endpoints (`async def`) for improved throughput.
2. **Phase 3 (PostgreSQL Database & Authentication):**
   - Introduce SQLAlchemy models and Alembic migrations.
   - Migrate historical records from `data.json` into relational tables (`jobs`, `resumes`, `screenings`, `screening_results`).
   - Implement recruiter authentication (JWT, Argon2/Bcrypt password hashing).
3. **Phase 4 (React + TypeScript Frontend):**
   - Rebuild the dashboard, job definition, and ranking views as modular React components with TailwindCSS / Shadcn UI.
4. **Phase 5 (Advanced AI & Hybrid Matching):**
   - Implement text chunking with sliding-window pooling and hybrid lexical (BM25 / TF-IDF) + semantic scoring.

