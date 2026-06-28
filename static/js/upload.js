/**
 * LogiQ — Upload Page JavaScript
 * Handles drag-and-drop file upload, progress animation, and auto-redirect.
 * @module upload
 */

/** @const {object} Upload configuration */
const UPLOAD_CONFIG = {
    ALLOWED_EXTENSIONS: ['.log', '.txt', '.csv'],
    MAX_FILE_SIZE_MB: 50,
    API_ENDPOINT: '/api/upload',
    REDIRECT_DELAY_MS: 1500,
    PROGRESS_STEPS: [
        { percent: 15, message: 'Reading file...', icon: 'file-text' },
        { percent: 40, message: 'Parsing log entries...', icon: 'code' },
        { percent: 65, message: 'Running anomaly detection...', icon: 'radar' },
        { percent: 85, message: 'Categorizing anomalies...', icon: 'tags' },
        { percent: 95, message: 'Finalizing results...', icon: 'check-circle' },
    ],
};

/**
 * Initialize the upload page functionality.
 */
function initUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressMessage = document.getElementById('progress-message');
    const errorBanner = document.getElementById('upload-error');
    const errorMessage = document.getElementById('upload-error-message');

    /**
     * Show an error message in the error banner.
     * @param {string} msg - Error message to display
     */
    function showError(msg) {
        errorMessage.textContent = msg;
        errorBanner.classList.add('visible');
        setTimeout(() => errorBanner.classList.remove('visible'), 6000);
    }

    /**
     * Hide the error banner.
     */
    function hideError() {
        errorBanner.classList.remove('visible');
    }

    /**
     * Validate a file before upload.
     * @param {File} file - The file to validate
     * @returns {boolean} True if valid, false otherwise
     */
    function validateFile(file) {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!UPLOAD_CONFIG.ALLOWED_EXTENSIONS.includes(ext)) {
            showError(`Unsupported file format "${ext}". Please use: ${UPLOAD_CONFIG.ALLOWED_EXTENSIONS.join(', ')}`);
            return false;
        }

        const sizeMB = file.size / (1024 * 1024);
        if (sizeMB > UPLOAD_CONFIG.MAX_FILE_SIZE_MB) {
            showError(`File too large (${sizeMB.toFixed(1)} MB). Maximum size is ${UPLOAD_CONFIG.MAX_FILE_SIZE_MB} MB.`);
            return false;
        }

        return true;
    }

    /**
     * Animate the progress bar through defined steps.
     * @returns {Promise<void>}
     */
    async function animateProgress() {
        progressContainer.classList.add('active');

        for (const step of UPLOAD_CONFIG.PROGRESS_STEPS) {
            progressBar.style.width = step.percent + '%';
            progressMessage.textContent = step.message;

            /* Update the icon */
            const iconEl = document.getElementById('progress-icon');
            if (iconEl) {
                iconEl.setAttribute('data-lucide', step.icon);
                lucide.createIcons({ nodes: [iconEl.parentElement] });
            }

            await new Promise(resolve => setTimeout(resolve, 600));
        }
    }

    /**
     * Upload a file to the server and handle the response.
     * @param {File} file - The file to upload
     */
    async function uploadFile(file) {
        if (!validateFile(file)) return;

        hideError();
        dropZone.style.display = 'none';

        /* Start progress animation */
        const progressPromise = animateProgress();

        /* Build form data */
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(UPLOAD_CONFIG.API_ENDPOINT, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            /* Wait for progress animation to finish */
            await progressPromise;

            /* Show completion */
            progressBar.style.width = '100%';
            progressMessage.textContent = `Found ${data.anomaly_count} anomalies! Redirecting to dashboard...`;

            const iconEl = document.getElementById('progress-icon');
            if (iconEl) {
                iconEl.setAttribute('data-lucide', 'check-circle');
                lucide.createIcons({ nodes: [iconEl.parentElement] });
            }

            /* Store session data for the dashboard */
            LogiQ.store('session_id', data.session_id);
            LogiQ.store('upload_result', data);

            LogiQ.showToast('Analysis Complete', `${data.anomaly_count} anomalies detected in ${data.total_lines} log lines`, 'success');

            /* Redirect to dashboard */
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, UPLOAD_CONFIG.REDIRECT_DELAY_MS);

        } catch (error) {
            dropZone.style.display = '';
            progressContainer.classList.remove('active');
            showError(error.message);
            LogiQ.showToast('Upload Failed', error.message, 'error');
        }
    }

    /* ── Drag & Drop Event Handlers ─────────────────────────────── */

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    /* ── Preloaded Scenario Cards Click Listener ─────────────────── */
    const preloadedCards = document.querySelectorAll('.preloaded-card');
    preloadedCards.forEach(card => {
        card.addEventListener('click', async (e) => {
            e.stopPropagation();
            const datasetName = card.getAttribute('data-dataset');
            if (!datasetName) return;

            hideError();
            dropZone.style.display = 'none';

            // Hide the header/title on upload progress to focus layout
            const pageHeader = document.querySelector('.page-header');
            if (pageHeader) pageHeader.style.display = 'none';
            const exploreTitle = card.parentElement.parentElement;
            if (exploreTitle) exploreTitle.style.display = 'none';

            /* Start progress animation */
            const progressPromise = animateProgress();

            try {
                const response = await fetch('/api/upload-preloaded', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset: datasetName }),
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to load preloaded dataset');
                }

                /* Wait for progress animation to finish */
                await progressPromise;

                /* Show completion */
                progressBar.style.width = '100%';
                progressMessage.textContent = `Found ${data.anomaly_count} anomalies! Redirecting to dashboard...`;

                const iconEl = document.getElementById('progress-icon');
                if (iconEl) {
                    iconEl.setAttribute('data-lucide', 'check-circle');
                    lucide.createIcons({ nodes: [iconEl.parentElement] });
                }

                /* Store session data for the dashboard */
                LogiQ.store('session_id', data.session_id);
                LogiQ.store('upload_result', data);

                LogiQ.showToast('Preloaded Log Loaded', `${data.anomaly_count} anomalies detected in ${data.total_lines} lines`, 'success');

                /* Redirect to dashboard */
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, UPLOAD_CONFIG.REDIRECT_DELAY_MS);

            } catch (error) {
                dropZone.style.display = '';
                if (pageHeader) pageHeader.style.display = '';
                if (exploreTitle) exploreTitle.style.display = '';
                progressContainer.classList.remove('active');
                showError(error.message);
                LogiQ.showToast('Load Failed', error.message, 'error');
            }
        });
    });
}

/* ── Initialize on DOM Ready ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initUpload);
