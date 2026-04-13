// Processing page JS

const PROC_API_BASE = 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', () => {
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const processedCount = document.getElementById('processedCount');
    const stepsList = document.getElementById('processingSteps');
    const loaderText = document.getElementById('loaderText');
    const afterCompletion = document.getElementById('afterCompletion');
    const viewResultsBtn = document.getElementById('viewResultsBtn');

    let totalResumes = 0;
    let currentProcessed = 0;
    let currentStepIndex = 1; // 0 is already "uploaded"

    // Get current resume count
    fetch(`${PROC_API_BASE}/dashboard`)
        .then(res => res.json())
        .then(data => {
            totalResumes = data.workflow?.resumes_count || data.current_screening?.resumes_uploaded || 0;
            if (!totalResumes) totalResumes = 10;
            processedCount.textContent = `Processed: 0 / ${totalResumes} resumes`;
        })
        .catch(() => {
            totalResumes = 10;
            processedCount.textContent = `Processed: 0 / ${totalResumes} resumes`;
        })
        .finally(() => {
            startFakeProgress();
            triggerBackendProcessing();
        });

    function updateProgress(pct) {
        progressFill.style.width = `${pct}%`;
        progressPercent.textContent = `${pct}% Completed`;
    }

    function markStepDone(index) {
        const items = stepsList.querySelectorAll('li');
        if (!items[index]) return;
        items[index].classList.add('done');
        items[index].textContent = items[index].textContent.replace('⟳', '✔');
    }

    function startFakeProgress() {
        const steps = [
            'Extracting text from resumes...',
            'Cleaning & preprocessing text...',
            'Extracting skills & keywords...',
            'Matching with job description...',
            'Calculating similarity scores...',
            'Ranking candidates...'
        ];

        let pct = 0;
        const interval = setInterval(() => {
            if (pct >= 90) {
                clearInterval(interval);
                return;
            }
            pct += 5;
            if (pct > 90) pct = 90;
            updateProgress(pct);

            // Simulate processed count
            if (totalResumes) {
                currentProcessed = Math.min(totalResumes, Math.round((pct / 100) * totalResumes));
                processedCount.textContent = `Processed: ${currentProcessed} / ${totalResumes} resumes`;
            }

            // Advance steps text
            if (pct % 15 === 0 && currentStepIndex < steps.length + 1) {
                markStepDone(currentStepIndex);
                loaderText.textContent = steps[currentStepIndex - 1];
                currentStepIndex++;
            }
        }, 500);
    }

    async function triggerBackendProcessing() {
        await fetch('http://127.0.0.1:5000/api/process', {
            method: 'POST'
        });
        finishProgressUI();
    }

    function finishProgressUI() {
        updateProgress(100);
        currentProcessed = totalResumes;
        processedCount.textContent = `Processed: ${currentProcessed} / ${totalResumes} resumes`;

        const items = stepsList.querySelectorAll('li');
        items.forEach((_, idx) => markStepDone(idx));

        loaderText.textContent = 'Processing completed.';
        afterCompletion.style.display = 'block';

        showToast('Processing completed. Results are ready.', 'success');
    }

    viewResultsBtn.addEventListener('click', async () => {
        await fetch('http://127.0.0.1:5000/api/process', {
            method: 'POST'
        });
        window.location.href = 'results.html';
    });
});

