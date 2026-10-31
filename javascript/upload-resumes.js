// Upload Resumes page JS

const UP_API_BASE = (window.location.origin && window.location.origin.startsWith('http'))
    ? window.location.origin + '/api'
    : 'http://127.0.0.1:5000/api';

let selectedFiles = [];
let uploadedFiles = [];

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const startProcessingBtn = document.getElementById('startProcessingFromUpload');
    const backToDashboardBtn = document.getElementById('backToDashboard');

    browseBtn?.addEventListener('click', () => fileInput?.click());

    fileInput?.addEventListener('change', (e) => {
        addSelectedFiles(Array.from(e.target.files || []));
    });

    if (dropZone) {
        ['dragenter', 'dragover'].forEach(evt => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('drag-over');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            const files = Array.from(e.dataTransfer?.files || []);
            addSelectedFiles(files);
        });
    }

    uploadBtn?.addEventListener('click', () => {
        if (!selectedFiles.length) {
            showToast('Please select at least one PDF or DOCX resume file', 'warning');
            return;
        }
        uploadSelectedFiles();
    });

    startProcessingBtn?.addEventListener('click', () => {
        window.location.href = 'processing.html';
    });

    backToDashboardBtn?.addEventListener('click', () => {
        window.location.href = 'dashboard.html';
    });

    // Load existing uploaded files
    loadExistingUploads();
});

function addSelectedFiles(files) {
    const allowed = ['pdf', 'docx'];
    let rejectedDocCount = 0;

    files.forEach(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext === 'doc') {
            rejectedDocCount++;
            return;
        }
        if (!allowed.includes(ext)) {
            return;
        }

        if (!selectedFiles.find(f => f.name === file.name && f.size === file.size)) {
            selectedFiles.push(file);
        }
    });

    if (rejectedDocCount > 0) {
        showToast('Legacy .doc format is not supported. Please convert to .docx or .pdf.', 'warning');
    }

    updateSelectedCount();
}

function updateSelectedCount() {
    const label = document.getElementById('selectedCount');
    if (!label) return;
    if (!selectedFiles.length) {
        label.textContent = 'No files selected';
    } else {
        label.textContent = `${selectedFiles.length} file(s) selected`;
    }
}

async function uploadSelectedFiles() {
    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('resumes', file));

    try {
        const res = await fetch(`${UP_API_BASE}/upload-resumes`, {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || 'Upload failed');
        }

        showToast(data.message || 'Resumes uploaded successfully', 'success');
        if (data.warnings && data.warnings.length) {
            data.warnings.forEach(w => showToast(w, 'warning'));
        }

        await loadExistingUploads();
        selectedFiles = [];
        updateSelectedCount();
    } catch (err) {
        showToast(err.message || 'Error uploading files', 'error');
    }
}

async function loadExistingUploads() {
    try {
        const res = await fetch(`${UP_API_BASE}/upload-resumes`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        uploadedFiles = Array.isArray(data.resumes) ? data.resumes : [];
    } catch {
        // backend may be starting up
    }
    renderUploadedTable();
}

function renderUploadedTable() {
    const tbody = document.getElementById('uploadedTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    uploadedFiles.forEach((file) => {
        const sizeKB = Math.max(1, Math.round((file.size || 0) / 1024));
        const displayName = file.display_name || file.filename;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${displayName}</td>
            <td>${sizeKB} KB</td>
            <td>${file.status || 'Uploaded'}</td>
            <td>
                <a class="btn btn-sm btn-view" href="${file.url || '#'}" target="_blank" rel="noopener noreferrer">
                    <i class="fas fa-eye"></i> View
                </a>
            </td>
        `;
        tbody.appendChild(tr);
    });

    const countEl = document.getElementById('totalUploadedText');
    if (countEl) {
        countEl.textContent = `Total Resumes Uploaded: ${uploadedFiles.length}`;
    }
}
