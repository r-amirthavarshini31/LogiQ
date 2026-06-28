/**
 * LogiQ — Dashboard Page JavaScript
 * Fetches anomaly data, renders stats, Chart.js charts, and the anomaly table.
 * @module dashboard
 */

/** @const {object} Dashboard configuration */
const DASHBOARD_CONFIG = {
    CHART_COLORS: {
        'Database': '#6366F1',
        'Network': '#8B5CF6',
        'Auth': '#EC4899',
        'Memory': '#F43F5E',
        'File System': '#F97316',
        'Timeout': '#EAB308',
        'Application': '#22C55E',
        'Unknown': '#94A3B8',
    },
    LEVEL_COLORS: {
        'critical': { bg: 'var(--color-peach-deep)', text: 'var(--color-error-dark)' },
        'error': { bg: 'var(--color-peach)', text: 'var(--color-error-dark)' },
        'warning': { bg: 'var(--color-sky)', text: 'var(--color-warning-dark)' },
        'info': { bg: 'var(--color-sky)', text: 'var(--color-warning-dark)' },
    },
};

/** @type {Array<object>} Current anomalies data */
let currentAnomalies = [];

/** @type {object|null} Current session data */
let currentSession = null;

/** @type {Chart|null} Timeline chart instance */
let timelineChart = null;

/** @type {Chart|null} Category chart instance */
let categoryChart = null;

/** @type {string} Current sort field */
let sortField = 'severity_score';

/** @type {boolean} Sort ascending */
let sortAsc = false;

/**
 * Initialize the dashboard page.
 */
async function initDashboard() {
    /* Try to load from session storage first (from upload redirect) */
    const uploadResult = LogiQ.retrieve('upload_result');
    const sessionId = LogiQ.retrieve('session_id');

    if (uploadResult && uploadResult.anomalies) {
        currentAnomalies = uploadResult.anomalies;
        currentSession = {
            id: uploadResult.session_id,
            filename: uploadResult.filename,
            total_lines: uploadResult.total_lines,
            anomaly_count: uploadResult.anomaly_count,
            critical_count: uploadResult.critical_count,
            resolved_count: 0,
            created_at: new Date().toISOString(),
        };
        renderDashboard();
    } else if (sessionId) {
        /* Fetch the specific active session from the server */
        await fetchSession(sessionId);
    } else {
        /* No session active — show clear empty dashboard */
        showEmptyState();
    }

    /* Set up event listeners */
    setupEventListeners();
}

/**
 * Fetch specific session data from the API.
 * @param {string} id - Session UUID
 */
async function fetchSession(id) {
    try {
        const data = await LogiQ.apiCall(`/api/session/${id}`);

        if (!data.session) {
            showEmptyState();
            return;
        }

        currentSession = data.session;
        currentAnomalies = data.anomalies;
        renderDashboard();
    } catch (error) {
        showError('Failed to load dashboard data: ' + error.message);
        showEmptyState();
    }
}

/**
 * Show the empty state when no data is available.
 */
function showEmptyState() {
    document.getElementById('dashboard-empty').style.display = '';
    document.getElementById('dashboard-content').style.display = 'none';
}

/**
 * Show error banner.
 * @param {string} msg - Error message
 */
function showError(msg) {
    const banner = document.getElementById('dashboard-error');
    document.getElementById('dashboard-error-message').textContent = msg;
    banner.classList.add('visible');
}

/**
 * Render the full dashboard with stats, charts, and table.
 */
function renderDashboard() {
    document.getElementById('dashboard-empty').style.display = 'none';
    document.getElementById('dashboard-content').style.display = '';

    /* Session info */
    if (currentSession) {
        const sessionInfo = document.getElementById('session-info');
        sessionInfo.style.display = '';
        document.getElementById('session-filename').textContent = currentSession.filename || 'Unknown';
        document.getElementById('session-date').textContent = LogiQ.formatTimestamp(currentSession.created_at);
        
        const exportBtn = document.getElementById('btn-export-dropdown');
        if (exportBtn) exportBtn.style.display = '';
    }

    renderStats();
    renderTimelineChart();
    renderCategoryChart();
    renderAnomalyTable();

    /* Re-initialize Lucide icons */
    lucide.createIcons();
}

/**
 * Render stat cards with current data.
 */
function renderStats() {
    const totalLines = currentSession ? currentSession.total_lines : 0;
    const anomalyCount = currentAnomalies.length;
    const criticalCount = currentAnomalies.filter(a => a.level === 'critical').length;
    const resolvedCount = currentAnomalies.filter(a => a.status === 'resolved').length;

    animateCounter('stat-total-lines-value', totalLines);
    animateCounter('stat-anomalies-value', anomalyCount);
    animateCounter('stat-critical-value', criticalCount);
    animateCounter('stat-resolved-value', resolvedCount);
}

/**
 * Animate a counter from 0 to target value.
 * @param {string} elementId - DOM element ID
 * @param {number} target - Target number
 */
function animateCounter(elementId, target) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const duration = 800;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * eased);

        el.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

/**
 * Render the anomaly timeline line chart.
 */
function renderTimelineChart() {
    const ctx = document.getElementById('timeline-chart');
    if (!ctx) return;

    /* Group anomalies by timestamp (rounded to hour) */
    const timeBuckets = {};
    currentAnomalies.forEach(anomaly => {
        const ts = anomaly.timestamp;
        if (!ts) return;

        let bucketKey;
        try {
            const date = new Date(ts);
            date.setMinutes(0, 0, 0);
            bucketKey = date.toISOString();
        } catch {
            return;
        }

        if (!timeBuckets[bucketKey]) {
            timeBuckets[bucketKey] = { error: 0, warning: 0, critical: 0 };
        }

        const level = anomaly.level || 'error';
        if (timeBuckets[bucketKey][level] !== undefined) {
            timeBuckets[bucketKey][level]++;
        } else {
            timeBuckets[bucketKey].error++;
        }
    });

    const sortedKeys = Object.keys(timeBuckets).sort();
    const labels = sortedKeys.map(k => {
        const d = new Date(k);
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    });

    if (timelineChart) {
        timelineChart.destroy();
    }

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
    const textColor = isDark ? '#A9A6C4' : '#6B6890';

    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Critical',
                    data: sortedKeys.map(k => timeBuckets[k].critical),
                    borderColor: '#DC2626',
                    backgroundColor: 'rgba(220, 38, 38, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#DC2626',
                },
                {
                    label: 'Error',
                    data: sortedKeys.map(k => timeBuckets[k].error),
                    borderColor: '#6366F1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#6366F1',
                },
                {
                    label: 'Warning',
                    data: sortedKeys.map(k => timeBuckets[k].warning),
                    borderColor: '#EAB308',
                    backgroundColor: 'rgba(234, 179, 8, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#EAB308',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: textColor, usePointStyle: true, padding: 16, font: { family: "'Plus Jakarta Sans'", size: 12 } },
                },
            },
            scales: {
                x: {
                    grid: { color: gridColor },
                    ticks: { color: textColor, font: { family: "'Plus Jakarta Sans'", size: 11 } },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: gridColor },
                    ticks: { color: textColor, font: { family: "'Plus Jakarta Sans'", size: 11 }, stepSize: 1 },
                },
            },
            interaction: { intersect: false, mode: 'index' },
        },
    });
}

/**
 * Render the category breakdown donut chart.
 */
function renderCategoryChart() {
    const ctx = document.getElementById('category-chart');
    if (!ctx) return;

    /* Count anomalies per category */
    const categoryCounts = {};
    currentAnomalies.forEach(a => {
        const cat = a.category || 'Unknown';
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
    });

    const categories = Object.keys(categoryCounts);
    const counts = categories.map(c => categoryCounts[c]);
    const colors = categories.map(c => DASHBOARD_CONFIG.CHART_COLORS[c] || '#94A3B8');

    if (categoryChart) {
        categoryChart.destroy();
    }

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#A9A6C4' : '#6B6890';

    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories,
            datasets: [{
                data: counts,
                backgroundColor: colors,
                borderWidth: 3,
                borderColor: isDark ? '#1E1B32' : '#FFFFFF',
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: textColor, usePointStyle: true, padding: 12, font: { family: "'Plus Jakarta Sans'", size: 11 } },
                },
            },
        },
    });
}

/**
 * Render the anomaly table with sortable columns.
 */
function renderAnomalyTable() {
    const tbody = document.getElementById('anomaly-table-body');
    const tableEmpty = document.getElementById('table-empty');

    if (currentAnomalies.length === 0) {
        tbody.innerHTML = '';
        tableEmpty.style.display = '';
        return;
    }

    tableEmpty.style.display = 'none';

    /* Sort anomalies */
    const sorted = [...currentAnomalies].sort((a, b) => {
        let aVal = a[sortField] || '';
        let bVal = b[sortField] || '';

        if (sortField === 'severity_score') {
            aVal = a.severity_score || 0;
            bVal = b.severity_score || 0;
        }

        if (typeof aVal === 'string') aVal = aVal.toLowerCase();
        if (typeof bVal === 'string') bVal = bVal.toLowerCase();

        if (aVal < bVal) return sortAsc ? -1 : 1;
        if (aVal > bVal) return sortAsc ? 1 : -1;
        return 0;
    });

    tbody.innerHTML = sorted.map(anomaly => {
        const levelClass = `badge-${anomaly.level || 'error'}`;
        const statusClass = anomaly.status === 'resolved' ? 'resolved' : 'open';

        return `
            <tr data-id="${anomaly.id}">
                <td>${LogiQ.formatTimestamp(anomaly.timestamp)}</td>
                <td><span class="badge ${levelClass}">${(anomaly.level || 'error').toUpperCase()}</span></td>
                <td><span class="badge badge-category">${anomaly.category || 'Unknown'}</span></td>
                <td class="message-preview" title="${(anomaly.message || '').replace(/"/g, '&quot;')}">${anomaly.message || 'No message'}</td>
                <td>
                    <span class="status-dot ${statusClass}"></span>
                    <span class="status-text ${statusClass}">${statusClass === 'resolved' ? 'Resolved' : 'Open'}</span>
                </td>
                <td>
                    <div class="row-actions">
                        <button class="row-action-btn" onclick="openDrawer(${anomaly.id})" title="View details and AI explanation">
                            <i data-lucide="sparkles" width="14" height="14"></i>
                            Explain
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    lucide.createIcons();
}

/**
 * Set up event listeners for sorting and refresh.
 */
function setupEventListeners() {
    /* Sortable table headers */
    document.querySelectorAll('.clay-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.getAttribute('data-sort');
            if (sortField === field) {
                sortAsc = !sortAsc;
            } else {
                sortField = field;
                sortAsc = true;
            }

            /* Update sort indicators */
            document.querySelectorAll('.clay-table th').forEach(h => h.classList.remove('sorted'));
            th.classList.add('sorted');

            renderAnomalyTable();
        });
    });

    /* Refresh button */
    const refreshBtn = document.getElementById('btn-refresh-table');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            if (currentSession && currentSession.id) {
                await fetchSession(currentSession.id);
            }
            LogiQ.showToast('Refreshed', 'Dashboard data updated', 'success');
        });
    }

    /* Export Dropdown Toggle */
    const exportBtn = document.getElementById('btn-export-dropdown');
    const exportMenu = document.getElementById('export-dropdown-menu');
    
    if (exportBtn && exportMenu) {
        exportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const visible = exportMenu.style.display === 'block';
            exportMenu.style.display = visible ? 'none' : 'block';
        });

        // Close on document click
        document.addEventListener('click', () => {
            exportMenu.style.display = 'none';
        });
        
        // Export JSON
        document.getElementById('export-json-btn').addEventListener('click', () => {
            if (!currentSession) return;
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
                session: currentSession,
                anomalies: currentAnomalies
            }, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `logiq-session-${currentSession.id}.json`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            LogiQ.showToast("Export Completed", "JSON data downloaded successfully.", "success");
        });

        // Export CSV
        document.getElementById('export-csv-btn').addEventListener('click', () => {
            if (!currentSession || currentAnomalies.length === 0) return;
            
            const headers = ['Line', 'Timestamp', 'Level', 'Category', 'Message', 'Severity Score', 'Status'];
            const rows = currentAnomalies.map(a => [
                a.line_number || '',
                a.timestamp || '',
                a.level || '',
                a.category || '',
                `"${(a.message || '').replace(/"/g, '""')}"`,
                a.severity_score || 0,
                a.status || 'open'
            ]);
            
            const csvContent = "data:text/csv;charset=utf-8," 
                + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
                
            const encodedUri = encodeURI(csvContent);
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", encodedUri);
            downloadAnchor.setAttribute("download", `logiq-anomalies-${currentSession.id}.csv`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            LogiQ.showToast("Export Completed", "CSV dataset downloaded successfully.", "success");
        });

        // Export Markdown Incident Report
        document.getElementById('export-md-btn').addEventListener('click', () => {
            if (!currentSession) return;
            
            let md = `# Incident Diagnosis Report — LogiQ\n\n`;
            md += `## Session Summary\n`;
            md += `- **Log File Name:** ${currentSession.filename}\n`;
            md += `- **Session ID:** ${currentSession.id}\n`;
            md += `- **Total Lines Processed:** ${currentSession.total_lines.toLocaleString()}\n`;
            md += `- **Anomalies Detected:** ${currentAnomalies.length}\n`;
            md += `- **Critical Failures:** ${currentAnomalies.filter(a => a.level === 'critical').length}\n`;
            md += `- **Resolved Count:** ${currentAnomalies.filter(a => a.status === 'resolved').length}\n`;
            md += `- **Generated At:** ${new Date().toLocaleString()}\n\n`;
            
            md += `## Detected Anomalies Checklist\n\n`;
            currentAnomalies.forEach((a, i) => {
                const statusChar = a.status === 'resolved' ? '[x]' : '[ ]';
                md += `### ${i + 1}. ${a.level ? a.level.toUpperCase() : 'ERROR'} [${a.category || 'General'}] — Line ${a.line_number}\n`;
                md += `- **Status:** ${statusChar} ${a.status || 'open'}\n`;
                md += `- **Timestamp:** ${a.timestamp || 'N/A'}\n`;
                md += `- **Raw Log Message:** \`${a.message}\`\n`;
                if (a.explanation) {
                    md += `- **AI Explanation:** ${a.explanation}\n`;
                }
                if (a.suggested_fix) {
                    md += `- **Suggested Fix:** ${a.suggested_fix}\n`;
                }
                md += `\n---\n\n`;
            });
            
            md += `\n*Report compiled automatically by LogiQ — From chaos to clarity in seconds.*\n`;
            
            const dataStr = "data:text/markdown;charset=utf-8," + encodeURIComponent(md);
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `logiq-report-${currentSession.id}.md`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            LogiQ.showToast("Export Completed", "Incident Markdown report generated and downloaded.", "success");
        });
    }
}

/**
 * Find an anomaly by ID in the current data.
 * @param {number} id - Anomaly ID
 * @returns {object|undefined} The anomaly object
 */
function findAnomaly(id) {
    return currentAnomalies.find(a => a.id === id);
}

/* ── Initialize on DOM Ready ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initDashboard);
