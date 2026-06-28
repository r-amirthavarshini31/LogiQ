/**
 * LogiQ — Drawer (Slide-in Panel) JavaScript
 * Handles the anomaly detail drawer with AI explanation, runbook, alerts, PR, and resolve.
 * @module drawer
 */

/** @const {object} Drawer configuration */
const DRAWER_CONFIG = {
    ENDPOINTS: {
        EXPLAIN: '/api/explain',
        RUNBOOK: '/api/runbook',
        ALERT: '/api/alert',
        PR: '/api/pr',
        RESOLVE: '/api/anomaly',
    },
};

/** @type {number|null} Currently open anomaly ID */
let currentDrawerAnomalyId = null;

/** @type {object|null} Currently displayed anomaly data */
let currentDrawerAnomaly = null;

/**
 * Open the anomaly detail drawer for a given anomaly ID.
 * @param {number} anomalyId - The anomaly ID to display
 */
async function openDrawer(anomalyId) {
    const overlay = document.getElementById('drawer-overlay');
    const drawer = document.getElementById('anomaly-drawer');
    const drawerBody = document.getElementById('drawer-body');
    const drawerActions = document.getElementById('drawer-actions');

    currentDrawerAnomalyId = anomalyId;

    /* Show loading state */
    drawerBody.innerHTML = `
        <div class="flex-center" style="padding: var(--space-3xl);">
            <div class="chart-loading-spinner"></div>
            <span style="color: var(--color-text-muted); margin-left: var(--space-sm);">Loading anomaly details...</span>
        </div>
    `;
    drawerActions.innerHTML = '';

    overlay.classList.add('open');
    drawer.classList.add('open');

    /* Try to find the anomaly locally first */
    let anomaly = null;
    if (typeof findAnomaly === 'function') {
        anomaly = findAnomaly(anomalyId);
    }

    if (!anomaly) {
        /* Fetch from API if not found locally */
        try {
            const data = await LogiQ.apiCall(`/api/history?id=${anomalyId}`);
            anomaly = data.anomalies?.find(a => a.id === anomalyId);
        } catch (error) {
            drawerBody.innerHTML = `
                <div class="error-banner visible">
                    <i data-lucide="alert-circle" width="20" height="20"></i>
                    <span>Failed to load anomaly: ${error.message}</span>
                </div>
            `;
            lucide.createIcons({ nodes: [drawerBody] });
            return;
        }
    }

    if (!anomaly) {
        drawerBody.innerHTML = `
            <div class="empty-state">
                <h3 class="empty-state-title">Anomaly Not Found</h3>
                <p class="empty-state-text">The requested anomaly could not be loaded.</p>
            </div>
        `;
        return;
    }

    currentDrawerAnomaly = anomaly;

    /* Fetch AI explanation */
    let explanation = anomaly.explanation;
    let fix = anomaly.suggested_fix;
    let cacheHit = anomaly.cache_hit;

    if (!explanation) {
        try {
            const explainData = await LogiQ.apiCall(DRAWER_CONFIG.ENDPOINTS.EXPLAIN, {
                method: 'POST',
                body: JSON.stringify({ anomaly_id: anomalyId }),
            });
            explanation = explainData.explanation;
            fix = explainData.fix;
            cacheHit = explainData.cache_hit;

            /* Update local data */
            anomaly.explanation = explanation;
            anomaly.suggested_fix = fix;
            anomaly.cache_hit = cacheHit;
        } catch (error) {
            explanation = 'Failed to generate explanation: ' + error.message;
            fix = '';
        }
    }

    /* Render the drawer content */
    renderDrawerContent(anomaly, explanation, fix, cacheHit);
    renderDrawerActions(anomaly);

    /* Initialize icons */
    lucide.createIcons({ nodes: [drawerBody, drawerActions] });
}

/**
 * Render the drawer body content.
 * @param {object} anomaly - Anomaly data
 * @param {string} explanation - AI explanation text
 * @param {string} fix - Suggested fix text
 * @param {boolean} cacheHit - Whether the explanation was from cache
 */
function renderDrawerContent(anomaly, explanation, fix, cacheHit) {
    const drawerBody = document.getElementById('drawer-body');
    const levelClass = `badge-${anomaly.level || 'error'}`;

    drawerBody.innerHTML = `
        <!-- Badges -->
        <div class="flex gap-sm" style="margin-bottom: var(--space-lg); flex-wrap: wrap;">
            <span class="badge ${levelClass}">${(anomaly.level || 'error').toUpperCase()}</span>
            <span class="badge badge-category">${anomaly.category || 'Unknown'}</span>
            ${anomaly.timestamp ? `<span class="badge badge-info">${LogiQ.formatTimestamp(anomaly.timestamp)}</span>` : ''}
            ${cacheHit ? '<span class="badge badge-cache"><i data-lucide="zap" width="12" height="12"></i> Cache Hit</span>' : ''}
        </div>

        <!-- Full Log Entry -->
        <div class="drawer-section">
            <h4 class="drawer-section-title">
                <i data-lucide="terminal" width="16" height="16"></i>
                Full Log Entry
            </h4>
            <div class="drawer-log-entry">${escapeHtml(anomaly.raw_line || anomaly.message || 'No log entry')}</div>
        </div>

        <!-- AI Explanation -->
        <div class="drawer-section" style="position: relative;">
            <div class="illustration-corner">
                <img src="/static/illustrations/robot-wrench.svg" alt="" width="80" height="80">
            </div>
            <h4 class="drawer-section-title">
                <i data-lucide="sparkles" width="16" height="16"></i>
                AI Explanation
            </h4>
            <div class="clay-card-flat" style="padding: var(--space-md);">
                <p style="font-size: var(--font-size-sm); line-height: 1.7; color: var(--color-text-secondary);">
                    ${escapeHtml(explanation || 'No explanation available')}
                </p>
            </div>
        </div>

        <!-- Suggested Fix (Accordion) -->
        <div class="drawer-section">
            <div class="accordion">
                <button class="accordion-trigger" id="fix-accordion-trigger">
                    <span class="flex gap-sm">
                        <i data-lucide="wrench" width="16" height="16"></i>
                        Suggested Fix
                    </span>
                    <i data-lucide="chevron-down" width="16" height="16" class="accordion-icon"></i>
                </button>
                <div class="accordion-content" id="fix-accordion-content">
                    <div class="accordion-inner">
                        ${fix ? formatFix(fix) : '<p style="color: var(--color-text-muted);">No fix suggestion available</p>'}
                    </div>
                </div>
            </div>
        </div>

        <!-- Runbook Section -->
        <div class="drawer-section" id="runbook-section" style="display: none;">
            <h4 class="drawer-section-title">
                <i data-lucide="book-open" width="16" height="16"></i>
                Generated Runbook
            </h4>
            <div class="runbook-content" id="runbook-content"></div>
        </div>
    `;

    /* Accordion toggle */
    const trigger = document.getElementById('fix-accordion-trigger');
    const content = document.getElementById('fix-accordion-content');
    if (trigger && content) {
        trigger.addEventListener('click', () => {
            trigger.classList.toggle('open');
            content.classList.toggle('open');
        });
    }
}

/**
 * Render the drawer action buttons.
 * @param {object} anomaly - Anomaly data
 */
function renderDrawerActions(anomaly) {
    const drawerActions = document.getElementById('drawer-actions');
    const isResolved = anomaly.status === 'resolved';

    drawerActions.innerHTML = `
        <button class="clay-btn clay-btn-sm clay-btn-outline" id="btn-generate-runbook" title="Generate operational runbook">
            <i data-lucide="book-open" width="14" height="14"></i>
            Generate Runbook
        </button>
        <button class="clay-btn clay-btn-sm clay-btn-outline" id="btn-create-pr" title="Create GitHub pull request">
            <i data-lucide="git-pull-request" width="14" height="14"></i>
            Create PR
        </button>
        <button class="clay-btn clay-btn-sm clay-btn-outline" id="btn-send-alert" title="Send alert notification">
            <i data-lucide="bell" width="14" height="14"></i>
            Send Alert
        </button>
        <button class="clay-btn clay-btn-sm ${isResolved ? 'clay-btn-ghost' : 'clay-btn-success'}" id="btn-mark-resolved" ${isResolved ? 'disabled' : ''}>
            <i data-lucide="${isResolved ? 'check-circle' : 'check'}" width="14" height="14"></i>
            ${isResolved ? 'Resolved' : 'Mark as Resolved'}
        </button>
    `;

    /* Event listeners */
    document.getElementById('btn-generate-runbook').addEventListener('click', handleGenerateRunbook);
    document.getElementById('btn-create-pr').addEventListener('click', handleCreatePR);
    document.getElementById('btn-send-alert').addEventListener('click', handleSendAlert);

    if (!isResolved) {
        document.getElementById('btn-mark-resolved').addEventListener('click', handleMarkResolved);
    }
}

/**
 * Handle Generate Runbook button click.
 */
async function handleGenerateRunbook() {
    const btn = document.getElementById('btn-generate-runbook');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" width="14" height="14" class="animate-spin"></i> Generating...';

    try {
        const data = await LogiQ.apiCall(DRAWER_CONFIG.ENDPOINTS.RUNBOOK, {
            method: 'POST',
            body: JSON.stringify({ anomaly_id: currentDrawerAnomalyId }),
        });

        const section = document.getElementById('runbook-section');
        const content = document.getElementById('runbook-content');
        section.style.display = '';
        content.innerHTML = LogiQ.renderMarkdown(data.runbook);

        LogiQ.showToast('Runbook Generated', 'Operational runbook is ready below', 'success');
    } catch (error) {
        LogiQ.showToast('Runbook Failed', error.message, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="book-open" width="14" height="14"></i> Generate Runbook';
    lucide.createIcons({ nodes: [btn] });
}

/**
 * Handle Create PR button click.
 */
async function handleCreatePR() {
    const btn = document.getElementById('btn-create-pr');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" width="14" height="14"></i> Creating...';

    try {
        const data = await LogiQ.apiCall(DRAWER_CONFIG.ENDPOINTS.PR, {
            method: 'POST',
            body: JSON.stringify({ anomaly_id: currentDrawerAnomalyId }),
        });

        if (data.success) {
            LogiQ.showToast('PR Created', `Pull request opened successfully`, 'success');
            if (data.pr_url) {
                window.open(data.pr_url, '_blank');
            }
        } else {
            LogiQ.showToast('PR Failed', data.message, 'warning');
        }
    } catch (error) {
        LogiQ.showToast('PR Failed', error.message, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="git-pull-request" width="14" height="14"></i> Create PR';
    lucide.createIcons({ nodes: [btn] });
}

/**
 * Handle Send Alert button click.
 */
async function handleSendAlert() {
    const btn = document.getElementById('btn-send-alert');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" width="14" height="14"></i> Sending...';

    try {
        const data = await LogiQ.apiCall(DRAWER_CONFIG.ENDPOINTS.ALERT, {
            method: 'POST',
            body: JSON.stringify({ anomaly_id: currentDrawerAnomalyId }),
        });

        if (data.success) {
            LogiQ.showToast('Alert Sent', data.message, 'success');
        } else {
            LogiQ.showToast('Alert Notice', data.message, 'warning');
        }
    } catch (error) {
        LogiQ.showToast('Alert Failed', error.message, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="bell" width="14" height="14"></i> Send Alert';
    lucide.createIcons({ nodes: [btn] });
}

/**
 * Handle Mark as Resolved button click.
 */
async function handleMarkResolved() {
    const btn = document.getElementById('btn-mark-resolved');
    btn.disabled = true;

    try {
        await LogiQ.apiCall(`${DRAWER_CONFIG.ENDPOINTS.RESOLVE}/${currentDrawerAnomalyId}/resolve`, {
            method: 'PATCH',
        });

        /* Update local data */
        if (currentDrawerAnomaly) {
            currentDrawerAnomaly.status = 'resolved';
        }

        btn.innerHTML = '<i data-lucide="check-circle" width="14" height="14"></i> Resolved';
        btn.classList.remove('clay-btn-success');
        btn.classList.add('clay-btn-ghost');

        LogiQ.showToast('Resolved', 'Anomaly marked as resolved', 'success');

        /* Refresh dashboard stats if on dashboard page */
        if (typeof renderStats === 'function') {
            renderStats();
        }
        if (typeof renderAnomalyTable === 'function') {
            renderAnomalyTable();
        }

    } catch (error) {
        btn.disabled = false;
        LogiQ.showToast('Error', error.message, 'error');
    }

    lucide.createIcons({ nodes: [btn] });
}

/**
 * Close the drawer panel.
 */
function closeDrawer() {
    document.getElementById('drawer-overlay').classList.remove('open');
    document.getElementById('anomaly-drawer').classList.remove('open');
    currentDrawerAnomalyId = null;
    currentDrawerAnomaly = null;
}

/**
 * Escape HTML special characters for safe rendering.
 * @param {string} str - Raw string
 * @returns {string} Escaped string
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Format a fix string with line breaks and code formatting.
 * @param {string} fix - Fix text
 * @returns {string} Formatted HTML
 */
function formatFix(fix) {
    return fix
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>')
        .replace(/(\d+\.\s)/g, '<br><strong>$1</strong>');
}

/* ── Event Listeners ────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    /* Close drawer */
    document.getElementById('drawer-close').addEventListener('click', closeDrawer);
    document.getElementById('drawer-overlay').addEventListener('click', closeDrawer);

    /* Close on Escape key */
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDrawer();
    });
});
