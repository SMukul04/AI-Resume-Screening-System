// Upload Resumes page JS

const UP_API_BASE = 'http://127.0.0.1:5000/api';

let selectedFiles = [];
let uploadedFiles = [];

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const startProcessingBtn = document.getElementById('startProcessingFromUpload');
    const backToDashboardBtn = document.getElementById('backToDashboard');

    browseBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        addSelectedFiles(Array.from(e.target.files));
    });

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
        const files = Array.from(e.dataTransfer.files || []);
        addSelectedFiles(files);
    });

    uploadBtn.addEventListener('click', () => {
        if (!selectedFiles.length) {
            showToast('Please select at least one resume file', 'warning');
            return;
        }
        uploadSelectedFiles();
    });

    startProcessingBtn.addEventListener('click', () => {
        window.location.href = 'processing.html';
    });

    backToDashboardBtn.addEventListener('click', () => {
        window.location.href = 'dashboard.html';
    });

    // Try to load existing uploaded info
    loadExistingUploads();
});

function addSelectedFiles(files) {
    const allowed = ['pdf', 'doc', 'docx'];
    files.forEach(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!allowed.includes(ext)) return;

        if (!selectedFiles.find(f => f.name === file.name && f.size === file.size)) {
            selectedFiles.push(file);
        }
    });
    updateSelectedCount();
}

function updateSelectedCount() {
    const label = document.getElementById('selectedCount');
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

        if (!res.ok) throw new Error('Upload failed');

        const data = await res.json();
        showToast(data.message || 'Resumes uploaded', 'success');
        await loadExistingUploads();
        selectedFiles = [];
        updateSelectedCount();
    } catch (err) {
        // Fallback: just show them in the local table
        uploadedFiles = uploadedFiles.concat(selectedFiles.map(f => ({
            filename: f.name,
            size: f.size,
            status: 'Uploaded'
        })));
        renderUploadedTable();
        selectedFiles = [];
        updateSelectedCount();
        showToast('Files added locally (backend not running)', 'warning');
    }
}

async function loadExistingUploads() {
    try {
        const res = await fetch(`${UP_API_BASE}/upload-resumes`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        uploadedFiles = Array.isArray(data.resumes) ? data.resumes : [];
    } catch {
        // ignore, backend may not be running
    }
    renderUploadedTable();
}

function renderUploadedTable() {
    const tbody = document.getElementById('uploadedTableBody');
    tbody.innerHTML = '';

    uploadedFiles.forEach((file) => {
        const sizeKB = Math.max(1, Math.round((file.size || 0) / 1024));
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${file.filename}</td>
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

    document.getElementById('totalUploadedText').textContent =
        `Total Resumes Uploaded: ${uploadedFiles.length}`;
}

