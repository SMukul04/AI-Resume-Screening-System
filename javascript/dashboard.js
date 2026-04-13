// ============================
// DOM Elements
// ============================
const sidebar = document.getElementById('sidebar');
const mainWrapper = document.getElementById('mainWrapper');
const sidebarToggle = document.getElementById('sidebarToggle');
const profileDropdown = document.getElementById('profileDropdown');
const profileBtn = document.getElementById('profileBtn');
const notificationBtn = document.getElementById('notificationBtn');
const notificationPanel = document.getElementById('notificationPanel');
const closeNotifBtn = document.getElementById('closeNotifBtn');
const startNewBtn = document.getElementById('startNewBtn');
const viewHistoryBtn = document.getElementById('viewHistoryBtn');
const startProcessingBtn = document.getElementById('startProcessingBtn');
const continueScreeningBtn = document.getElementById('continueScreeningBtn');
const logoutBtn = document.getElementById('logoutBtn');

// ============================
// Sidebar Toggle
// ============================
sidebarToggle.addEventListener('click', () => {
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        sidebar.classList.toggle('mobile-open');
        toggleOverlay();
    } else {
        sidebar.classList.toggle('collapsed');
        mainWrapper.classList.toggle('expanded');
    }
});

function toggleOverlay() {
    let overlay = document.querySelector('.overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.classList.add('overlay');
        document.body.appendChild(overlay);
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('mobile-open');
            overlay.classList.remove('active');
        });
    }
    overlay.classList.toggle('active');
}

// ============================
// Profile Dropdown
// ============================
profileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    profileDropdown.classList.toggle('open');
    notificationPanel.classList.remove('open');
});

document.addEventListener('click', (e) => {
    if (!profileDropdown.contains(e.target)) {
        profileDropdown.classList.remove('open');
    }
});

// ============================
// Notification Panel
// ============================
notificationBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    notificationPanel.classList.toggle('open');
    profileDropdown.classList.remove('open');
});

closeNotifBtn.addEventListener('click', () => {
    notificationPanel.classList.remove('open');
});

document.addEventListener('click', (e) => {
    if (!notificationPanel.contains(e.target) && !notificationBtn.contains(e.target)) {
        notificationPanel.classList.remove('open');
    }
});

// ============================
// API Base URL
// ============================
const API_BASE = 'http://127.0.0.1:5000/api';

// ============================
// Dashboard Data Loader
// ============================
async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE}/dashboard`);
        if (!response.ok) throw new Error('Failed to fetch dashboard data');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.warn('Backend not available, using static data:', error.message);
    }
}

function capitalize(str) {
    return str.replace(/\b\w/g, c => c.toUpperCase());
}

function updateDashboard(data) {
    if (data.stats) {
        document.getElementById('totalScreenings').textContent = data.stats.total_screenings;
        document.getElementById('resumesUploaded').textContent = data.stats.resumes_uploaded;
        document.getElementById('avgMatchScore').textContent = data.stats.avg_match_score + '%';
        document.getElementById('topCandidateScore').textContent = data.stats.top_candidate_score + '%';
    }

    if (data.current_screening) {
        const cs = data.current_screening;
        document.getElementById('currentJob').textContent = cs.job_title || 'Not set';
        document.getElementById('currentResumes').textContent = cs.resumes_uploaded || 0;

        const jdStatusEl = document.getElementById('currentJDStatus');
        jdStatusEl.textContent = cs.jd_added ? 'Added' : 'Not Added';
        jdStatusEl.className = 'summary-value ' + (cs.jd_added ? 'badge-success' : 'badge-danger');

        const procStatusEl = document.getElementById('currentProcessing');
        procStatusEl.textContent = cs.processing_status || 'Pending';
        const statusClass = {
            'Completed': 'badge-success',
            'In Progress': 'badge-warning',
            'Pending': 'badge-warning',
            'Not Started': 'badge-danger'
        };
        procStatusEl.className = 'summary-value ' + (statusClass[cs.processing_status] || 'badge-warning');
    }

    if (data.workflow) {
        updateWorkflowCards(data.workflow);
    }

    if (data.recent_screenings) {
        updateScreeningsTable(data.recent_screenings);
    }

    if (data.top_skills && data.top_skills.length > 0) {
        const list = document.getElementById('topSkillsList');
        list.innerHTML = data.top_skills
            .map(t => `<li class="top-skill-item">${capitalize(t.skill)} (${t.count} candidate${t.count !== 1 ? 's' : ''})</li>`)
            .join('');
    } else if (data.top_skills && data.top_skills.length === 0) {
        document.getElementById('topSkillsList').innerHTML =
            '<li class="top-skill-item">No skills found — run processing first</li>';
    }

    if (data.current_screening) {
        const total = data.current_screening.resumes_uploaded || 15;
        const qualified = data.current_screening.qualified || Math.round(total * 0.6);
        renderPieChart(qualified, total - qualified);
    }
}

function updateWorkflowCards(workflow) {
    const jdStatus = document.getElementById('jdStatus');
    if (workflow.jd_added) {
        jdStatus.innerHTML = '<i class="fas fa-check-circle"></i> Added';
        jdStatus.className = 'card-status status-success';
    } else {
        jdStatus.innerHTML = '<i class="fas fa-times-circle"></i> Not Added';
        jdStatus.className = 'card-status status-danger';
    }

    const uploadStatus = document.getElementById('uploadStatus');
    const count = workflow.resumes_count || 0;
    uploadStatus.innerHTML = `<i class="fas fa-info-circle"></i> ${count} resume${count !== 1 ? 's' : ''} uploaded`;
    uploadStatus.className = count > 0 ? 'card-status status-success' : 'card-status status-neutral';

    const processingStatus = document.getElementById('processingStatus');
    const pStatus = workflow.processing_status || 'Not started';
    if (pStatus === 'Completed') {
        processingStatus.innerHTML = '<i class="fas fa-check-circle"></i> Completed';
        processingStatus.className = 'card-status status-success';
    } else if (pStatus === 'In Progress') {
        processingStatus.innerHTML = '<span class="spinner"></span> In progress';
        processingStatus.className = 'card-status status-warning';
    } else {
        processingStatus.innerHTML = '<i class="fas fa-info-circle"></i> Not started';
        processingStatus.className = 'card-status status-neutral';
    }

    const resultsStatus = document.getElementById('resultsStatus');
    if (workflow.results_ready) {
        resultsStatus.innerHTML = '<i class="fas fa-check-circle"></i> Results ready';
        resultsStatus.className = 'card-status status-success';
    } else {
        resultsStatus.innerHTML = '<i class="fas fa-info-circle"></i> Not generated';
        resultsStatus.className = 'card-status status-neutral';
    }
}

function updateScreeningsTable(screenings) {
    const tbody = document.getElementById('screeningsTableBody');
    tbody.innerHTML = '';

    // Show only the latest 5 in dashboard; full list is in History page.
    screenings.slice(0, 5).forEach(s => {
        let scoreClass = 'medium';
        const score = parseInt(s.top_score);
        if (score >= 85) scoreClass = 'high';
        else if (score < 60) scoreClass = 'low';

        const row = document.createElement('tr');
        row.innerHTML = `
            <td><span class="screening-id">${s.id}</span></td>
            <td>${s.job_title}</td>
            <td>${s.resumes}</td>
            <td>${s.date}</td>
            <td><span class="score-badge ${scoreClass}">${s.top_score}%</span></td>
            <td>
                <button class="btn btn-sm btn-view" onclick="viewScreening('${s.id}')">
                    <i class="fas fa-eye"></i> View
                </button>
                <button class="btn btn-sm btn-delete" onclick="deleteScreening('${s.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// ============================
// Actions
// ============================
function viewScreening(id) {
    window.location.href = `results.html?screening=${id}`;
}

function deleteScreening(id) {
    if (!confirm(`Are you sure you want to delete screening ${id}?`)) return;

    fetch(`${API_BASE}/screening/${id}`, { method: 'DELETE' })
        .then(res => {
            if (res.ok) {
                loadDashboardData();
                showToast('Screening deleted successfully', 'success');
            }
        })
        .catch(() => {
            const row = document.querySelector(`[onclick="viewScreening('${id}')"]`)?.closest('tr');
            if (row) row.remove();
            showToast('Screening removed from view', 'success');
        });
}

startNewBtn?.addEventListener('click', async () => {
    try {
        await fetch(`${API_BASE}/screening/new`, { method: 'POST' });
    } catch (e) {
        console.error("Failed to reset screening state", e);
    }
    window.location.href = 'job-description.html';
});

viewHistoryBtn?.addEventListener('click', () => {
    window.location.href = 'history.html';
});

startProcessingBtn?.addEventListener('click', () => {
    window.location.href = 'processing.html';
});

continueScreeningBtn?.addEventListener('click', () => {
    window.location.href = 'job-description.html';
});

logoutBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = 'dashboard.html';
    }
});

// ============================
// Toast Notifications
// ============================
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        padding: 14px 24px;
        border-radius: 8px;
        color: white;
        font-size: 14px;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        z-index: 9999;
        animation: fadeInUp 0.3s ease;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    `;

    const colors = {
        success: '#2e7d32',
        error: '#c62828',
        warning: '#ef6c00',
        info: '#1a73e8'
    };
    toast.style.background = colors[type] || colors.info;
    toast.textContent = message;

    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================
// Responsive Handling
// ============================
window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
        sidebar.classList.remove('mobile-open');
        const overlay = document.querySelector('.overlay');
        if (overlay) overlay.classList.remove('active');
    }
});

// ============================
// Pie Chart
// ============================
let pieChart = null;

function renderPieChart(qualified, notQualified) {
    const ctx = document.getElementById('resumePieChart');
    if (!ctx) return;

    document.getElementById('qualifiedCount').textContent = qualified;
    document.getElementById('notQualifiedCount').textContent = notQualified;

    if (pieChart) pieChart.destroy();

    pieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Qualified', 'Not Qualified'],
            datasets: [{
                data: [qualified, notQualified],
                backgroundColor: ['#2e7d32', '#c62828'],
                borderColor: ['#ffffff', '#ffffff'],
                borderWidth: 3,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '60%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a202c',
                    padding: 10,
                    cornerRadius: 8,
                    titleFont: { family: 'Inter', size: 13 },
                    bodyFont: { family: 'Inter', size: 13 },
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = Math.round((context.raw / total) * 100);
                            return ` ${context.label}: ${context.raw} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

// ============================
// Initialize
// ============================
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    renderPieChart(9, 6);
});
