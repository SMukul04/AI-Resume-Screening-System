// history.js - Logic for the full Screening History page

const HIST_API_BASE = 'http://127.0.0.1:5000/api';

let allHistory = [];

document.addEventListener('DOMContentLoaded', () => {
    loadHistoryData();

    const searchInput = document.getElementById('historySearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filtered = allHistory.filter(s => 
                s.job_title.toLowerCase().includes(query) || 
                s.id.toLowerCase().includes(query)
            );
            renderHistoryTable(filtered);
        });
    }
});

async function loadHistoryData() {
    try {
        const response = await fetch(`${HIST_API_BASE}/dashboard`);
        if (!response.ok) throw new Error('Failed to load history');
        const data = await response.json();
        
        allHistory = data.recent_screenings || [];
        renderHistoryTable(allHistory);
    } catch (err) {
        console.error("Error loading history:", err);
        const tbody = document.getElementById('historyTableBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-history">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Error loading history data</p>
                    </td>
                </tr>
            `;
        }
    }
}

function renderHistoryTable(screenings) {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;

    if (screenings.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-history">
                    <i class="fas fa-inbox"></i>
                    <p>No screenings found</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = '';
    
    screenings.forEach(s => {
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
                <button class="btn btn-sm btn-view" onclick="viewHistoryItem('${s.id}')">
                    <i class="fas fa-eye"></i> View
                </button>
                <button class="btn btn-sm btn-delete" onclick="deleteHistoryItem('${s.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function viewHistoryItem(id) {
    window.location.href = `results.html?screening=${id}`;
}

async function deleteHistoryItem(id) {
    if (!confirm(`Are you sure you want to permanently delete screening ${id}?`)) return;

    try {
        const res = await fetch(`${HIST_API_BASE}/screening/${id}`, { method: 'DELETE' });
        if (res.ok) {
            // Remove from local array
            allHistory = allHistory.filter(s => s.id !== id);
            // Re-render
            const searchInput = document.getElementById('historySearchInput');
            if (searchInput && searchInput.value) {
                const query = searchInput.value.toLowerCase();
                renderHistoryTable(allHistory.filter(s => 
                    s.job_title.toLowerCase().includes(query) || 
                    s.id.toLowerCase().includes(query)
                ));
            } else {
                renderHistoryTable(allHistory);
            }
            
            // Show toast from dashboard.js if available
            if (typeof showToast !== 'undefined') {
                showToast('Screening deleted successfully', 'success');
            }
        } else {
            alert("Failed to delete the screening");
        }
    } catch (err) {
        console.error("Failed to delete", err);
    }
}
