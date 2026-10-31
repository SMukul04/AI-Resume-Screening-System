// Job Description page JS

const JD_API_BASE = (window.location.origin && window.location.origin.startsWith('http'))
    ? window.location.origin + '/api'
    : 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('jobDescriptionForm');
    const addSkillBtn = document.getElementById('addSkillBtn');
    const customSkillInput = document.getElementById('customSkill');
    const nextBtn = document.getElementById('nextBtn');

    // Load any existing JD data
    fetch(`${JD_API_BASE}/job-description`)
        .then(res => res.json())
        .then(data => {
            if (data.current) {
                const c = data.current;
                if (c.job_title && document.getElementById('jobTitle')) {
                    document.getElementById('jobTitle').value = c.job_title;
                }
            }
        })
        .catch(() => {
            // Ignore if backend not running
        });

    // Add custom skill chips
    addSkillBtn?.addEventListener('click', () => {
        const value = customSkillInput.value.trim();
        if (!value) return;

        const container = document.querySelector('.jd-skills');
        if (!container) return;

        const label = document.createElement('label');
        label.className = 'jd-chip';
        label.innerHTML = `
            <input type="checkbox" value="${value}" checked>
            <span>${value}</span>
        `;
        container.appendChild(label);
        customSkillInput.value = '';
    });

    // Save JD to backend helper
    async function saveJobDescription() {
        const jobTitle = document.getElementById('jobTitle').value.trim();
        const jobDescription = document.getElementById('jobDescription').value.trim();
        const selectedSkills = Array.from(document.querySelectorAll('.jd-chip input:checked'))
            .map(i => i.value);

        if (!jobTitle) {
            showToast('Please enter a Job Title before proceeding.', 'warning');
            return false;
        }

        const res = await fetch(`${JD_API_BASE}/job-description`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: jobTitle,
                description: jobDescription,
                skills: selectedSkills
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.error || 'Failed to save job description');
        }
        return true;
    }

    // Form submit button
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const saved = await saveJobDescription();
            if (saved) {
                showToast('Job description saved successfully', 'success');
            }
        } catch (err) {
            showToast(err.message || 'Error saving job description', 'error');
        }
    });

    // Next button: auto-saves before navigating
    nextBtn?.addEventListener('click', async () => {
        const jobTitle = document.getElementById('jobTitle')?.value.trim();
        if (jobTitle) {
            try {
                await saveJobDescription();
            } catch (err) {
                showToast(err.message || 'Could not auto-save job description', 'warning');
            }
        }
        window.location.href = 'upload-resumes.html';
    });
});
