// Processing page JS

const PROC_API_BASE = (window.location.origin && window.location.origin.startsWith('http'))
    ? window.location.origin + '/api'
    : 'http://127.0.0.1:5000/api';

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
    let isProcessing = false;
    let progressInterval = null;

    // Get current resume count
    fetch(`${PROC_API_BASE}/dashboard`)
        .then(res => res.json())
        .then(data => {
            totalResumes = data.workflow?.resumes_count || data.current_screening?.resumes_uploaded || 0;
            if (!totalResumes) totalResumes = 1;
            processedCount.textContent = `Processed: 0 / ${totalResumes} resumes`;
        })
        .catch(() => {
            totalResumes = 1;
            processedCount.textContent = `Processed: 0 / ${totalResumes} resumes`;
        })
        .finally(() => {
            startFakeProgress();
            triggerBackendProcessing();
        });

    function updateProgress(pct) {
        if (progressFill) progressFill.style.width = `${pct}%`;
        if (progressPercent) progressPercent.textContent = `${pct}% Completed`;
    }

    function markStepDone(index) {
        const items = stepsList?.querySelectorAll('li') || [];
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
        progressInterval = setInterval(() => {
            if (pct >= 90) {
                return;
            }
            pct += 5;
            if (pct > 90) pct = 90;
            updateProgress(pct);

            if (totalResumes && processedCount) {
                currentProcessed = Math.min(totalResumes, Math.max(1, Math.round((pct / 100) * totalResumes)));
                processedCount.textContent = `Processed: ${currentProcessed} / ${totalResumes} resumes`;
            }

            if (pct % 15 === 0 && currentStepIndex < steps.length + 1) {
                markStepDone(currentStepIndex);
                if (loaderText) loaderText.textContent = steps[currentStepIndex - 1];
                currentStepIndex++;
            }
        }, 500);
    }

    async function triggerBackendProcessing() {
        if (isProcessing) return;
        isProcessing = true;

        try {
            const res = await fetch(`${PROC_API_BASE}/process`, {
                method: 'POST'
            });
            const data = await res.json();
            if (!res.ok) {
                if (progressInterval) clearInterval(progressInterval);
                const errMsg = data.error || 'Processing failed on the server.';
                if (loaderText) loaderText.textContent = `Error: ${errMsg}`;
                showToast(errMsg, 'error');
                return;
            }
            finishProgressUI();
        } catch (err) {
            if (progressInterval) clearInterval(progressInterval);
            if (loaderText) loaderText.textContent = 'Network or server error during processing.';
            showToast('Failed to connect to screening server.', 'error');
        } finally {
            isProcessing = false;
        }
    }

    function finishProgressUI() {
        if (progressInterval) clearInterval(progressInterval);
        updateProgress(100);
        currentProcessed = totalResumes;
        if (processedCount) processedCount.textContent = `Processed: ${currentProcessed} / ${totalResumes} resumes`;

        const items = stepsList?.querySelectorAll('li') || [];
        items.forEach((_, idx) => markStepDone(idx));

        if (loaderText) loaderText.textContent = 'Processing completed.';
        if (afterCompletion) afterCompletion.style.display = 'block';

        showToast('Processing completed. Results are ready.', 'success');
    }

    // Step 3.4 Fix: View Results button simply navigates to results.html without duplicate POST /api/process
    viewResultsBtn?.addEventListener('click', () => {
        window.location.href = 'results.html';
    });
});
