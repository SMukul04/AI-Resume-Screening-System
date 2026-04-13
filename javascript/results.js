// Results page JS

const RES_API_BASE = (window.location.origin && window.location.origin.startsWith('http'))
  ? window.location.origin + '/api'
  : 'http://127.0.0.1:5000/api';

let allCandidates = [];
let currentScreeningId = null;

async function loadResults(screeningId) {
  try {
    currentScreeningId = screeningId || null;

    let data;
    if (screeningId) {
      const res = await fetch(`http://127.0.0.1:5000/api/screening/${encodeURIComponent(screeningId)}`);
      if (!res.ok) throw new Error('Failed to fetch screening');
      data = await res.json();
      allCandidates = Array.isArray(data.results) ? data.results : [];
      const roleEl = document.getElementById('resultsJobRole');
      if (roleEl) roleEl.textContent = data.job_title || roleEl.textContent;
    } else {
      const res = await fetch('http://127.0.0.1:5000/api/results');
      data = await res.json();
      allCandidates = data.results || [];
    }

    renderTable(allCandidates);
    updateTopCandidate();
    if (allCandidates.length === 0) {
      showEmptyState();
    }
  } catch (err) {
    console.error("Failed to load results", err);
    showEmptyState();
  }
}

function showEmptyState() {
  const tbody = document.getElementById('resultsTableBody');
  if (tbody && allCandidates.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="empty-state">
          <i class="fas fa-inbox"></i>
          <p>No results yet. Run processing to rank your uploaded resumes.</p>
          <button id="runProcessingBtn" class="btn btn-primary btn-sm">
            <i class="fas fa-cog"></i> Run Processing Now
          </button>
          <p class="empty-state-hint">Or <a href="processing.html">go to Processing page</a></p>
        </td>
      </tr>
    `;
    document.getElementById('runProcessingBtn')?.addEventListener('click', runProcessing);
  }
}

async function runProcessing() {
  const btn = document.getElementById('runProcessingBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
  }
  try {
    const res = await fetch(`${RES_API_BASE}/process`, { method: 'POST' });
    const data = await res.json();
    if (data.error) {
      alert(data.error + '\n\nMake sure you have added a job description and uploaded at least one resume.');
      return;
    }
    await loadResults();
    if (allCandidates.length > 0) {
      showToast('Results loaded successfully!', 'success');
    }
  } catch (err) {
    alert('Failed to run processing. Is the backend running on http://127.0.0.1:5000 ?');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-cog"></i> Run Processing Now';
    }
  }
}

function showToast(message, type) {
  const toast = document.createElement('div');
  toast.style.cssText = 'position:fixed;bottom:24px;right:24px;padding:14px 24px;border-radius:8px;color:white;z-index:9999;font-family:Inter,sans-serif;';
  toast.style.background = type === 'success' ? '#2e7d32' : '#1a73e8';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  const screeningId = params.get('screening');

  loadResults(screeningId);

  document.getElementById('searchBtn').addEventListener('click', () => applyFilters());
  document.getElementById('candidateSearch').addEventListener('keyup', (e) => {
    if (e.key === 'Enter') applyFilters();
  });
  document.getElementById('topFilter').addEventListener('change', applyFilters);
  document.getElementById('scoreFilter').addEventListener('change', applyFilters);

  document.getElementById('downloadReportBtn').addEventListener('click', downloadReport);
  document.getElementById('newScreeningBtn').addEventListener('click', async () => {
    try {
      await fetch(`${RES_API_BASE}/screening/new`, { method: 'POST' });
    } catch(e) {
      console.error(e);
    }
    window.location.href = 'job-description.html';
  });
  document.getElementById('backDashboardBtn').addEventListener('click', () => {
    window.location.href = 'dashboard.html';
  });

  // Try to pull real data from backend, if you later add such endpoint
  tryLoadFromBackend();
});

function applyFilters() {
  const query = document.getElementById('candidateSearch').value.toLowerCase().trim();
  const topVal = document.getElementById('topFilter').value;
  const minScore = parseInt(document.getElementById('scoreFilter').value, 10);

  let filtered = allCandidates.filter(c => (c.score || 0) >= minScore);

  if (query) {
    filtered = filtered.filter(c =>
      (c.name || '').toLowerCase().includes(query) ||
      (c.skills || []).some(s => String(s).toLowerCase().includes(query))
    );
  }

  if (topVal !== 'all') {
    const limit = parseInt(topVal, 10);
    filtered = filtered.slice(0, limit);
  }

  renderTable(filtered);
}

function renderTable(list = allCandidates) {
  const tbody = document.getElementById('resultsTableBody');
  tbody.innerHTML = '';

  list.forEach(c => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${c.rank}</td>
      <td>${c.name}</td>
      <td><span class="score-badge ${c.score >= 80 ? 'high' : c.score >= 60 ? 'medium' : 'low'}">${c.score}%</span></td>
      <td>${(c.skills || []).join(', ') || '-'}</td>
      <td>
        <button class="btn btn-sm btn-view" onclick="viewDetails('${String(c.name).replace(/'/g, "\\'")}')">
          <i class="fas fa-eye"></i> View Details
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('resultsTotalResumes').textContent = list.length.toString();
}

function viewDetails(filename) {
  const qs = currentScreeningId
    ? `&screening=${encodeURIComponent(currentScreeningId)}`
    : '';
  window.location.href = `resume-details.html?file=${encodeURIComponent(filename)}${qs}`;
}

function updateTopCandidate() {
  const nameEl = document.getElementById('topCandidateName');
  const scoreEl = document.getElementById('topCandidateScoreDetail');
  const skillsEl = document.getElementById('topCandidateSkills');
  if (!allCandidates.length) {
    if (nameEl) nameEl.textContent = 'No results yet';
    if (scoreEl) scoreEl.textContent = '-';
    if (skillsEl) skillsEl.textContent = 'Run processing to see top candidate';
    return;
  }
  const top = allCandidates[0];
  nameEl.textContent = top.name;
  scoreEl.textContent = `${top.score}%`;
  skillsEl.textContent = (top.skills || []).join(', ') || '-';
}

function downloadReport() {
  const lines = [
    'Candidate Ranking Report',
    '=========================',
    '',
    ...allCandidates.map(c => `${c.rank}. ${c.name} - ${c.score}% - ${(c.skills || []).join(', ')}`)
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'candidate_ranking_report.txt';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function tryLoadFromBackend() {
  try {
    const res = await fetch(`${RES_API_BASE}/dashboard`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.current_screening?.job_title) {
      document.getElementById('resultsJobRole').textContent = data.current_screening.job_title;
    }
    // you could later add real ranking data here
  } catch {
    // ignore if backend not available
  }
}

