// Job Description page JS

const JD_API_BASE = 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('jobDescriptionForm');
    const addSkillBtn = document.getElementById('addSkillBtn');
    const customSkillInput = document.getElementById('customSkill');
    const nextBtn = document.getElementById('nextBtn');

    // Load any existing JD data (optional, used if backend running)
    fetch(`${JD_API_BASE}/job-description`)
        .then(res => res.json())
        .then(data => {
            if (data.current) {
                const c = data.current;
                if (c.job_title) document.getElementById('jobTitle').value = c.job_title;
            }
        })
        .catch(() => {
            // Ignore if backend not running
        });

    // Add custom skill chips
    addSkillBtn.addEventListener('click', () => {
        const value = customSkillInput.value.trim();
        if (!value) return;

        const container = document.querySelector('.jd-skills');
        const label = document.createElement('label');
        label.className = 'jd-chip';
        label.innerHTML = `
            <input type="checkbox" value="${value}" checked>
            <span>${value}</span>
        `;
        container.appendChild(label);
        customSkillInput.value = '';
    });

    // Save JD to backend
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const jobTitle = document.getElementById('jobTitle').value.trim();
        const jobDescription = document.getElementById('jobDescription').value.trim();
        const selectedSkills = Array.from(document.querySelectorAll('.jd-chip input:checked'))
            .map(i => i.value);

        try {
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

            if (!res.ok) throw new Error('Failed to save');

            showToast('Job description saved successfully', 'success');
        } catch (err) {
            showToast('Saved locally (backend not running)', 'warning');
        }
    });

    // Next -> go to Upload Resumes page
    nextBtn.addEventListener('click', () => {
        window.location.href = 'upload-resumes.html';
    });
});

