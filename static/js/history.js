/**
 * LogiQ — History Page JavaScript
 * Fetches and displays historical anomalies with filtering, sorting, and CSV export.
 * @module history
 */

/** @const {object} History configuration */
const HISTORY_CONFIG = {
    API_ENDPOINT: '/api/history',
    CSV_FILENAME: 'logiq-anomaly-history.csv',
    CSV_HEADERS: ['ID', 'Timestamp', 'Level', 'Category', 'Message', 'Status', 'Cache Hit', 'Created At'],
};

/** @type {Array<object>} Current history data */
let historyData = [];

/**
 * Initialize the history page.
 */
async function initHistory() {
    await fetchHistory();
    setupHistoryEventListeners();
}

/**
 * Fetch anomaly history from the API with optional filters.
 * @param {object} [filters] - Filter parameters
 */
async function fetchHistory(filters) {
    const loading = document.getElementById('history-loading');
    const tableBody = document.getElementById('history-table-body');
    const emptyState = document.getElementById('history-empty');
    const errorBanner = document.getElementById('history-error');
    const filtersBar = document.getElementById('history-filters');
    const tableCard = document.getElementById('history-table-card');
    const clearHistoryBtn = document.getElementById('btn-clear-history');
    const exportCsvBtn = document.getElementById('btn-export-csv');

    // Make history only appear when a sample data or log file is selected/uploaded
    const activeSession = LogiQ.retrieve('session_id');
    if (!activeSession) {
        loading.style.display = 'none';
        tableBody.innerHTML = '';
        emptyState.style.display = '';
        errorBanner.classList.remove('visible');
        if (filtersBar) filtersBar.style.display = 'none';
        if (tableCard) tableCard.style.boxShadow = 'none';
        if (clearHistoryBtn) clearHistoryBtn.style.display = 'none';
        if (exportCsvBtn) exportCsvBtn.style.display = 'none';
        return;
    }

    // Restore UI visibility
    if (filtersBar) filtersBar.style.display = '';
    if (tableCard) tableCard.style.boxShadow = '';
    if (clearHistoryBtn) clearHistoryBtn.style.display = '';
    if (exportCsvBtn) exportCsvBtn.style.display = '';

    loading.style.display = '';
    tableBody.innerHTML = '';
    emptyState.style.display = 'none';
    errorBanner.classList.remove('visible');

    try {
        /* Build query string from filters */
        const params = new URLSearchParams();
        if (filters) {
            Object.entries(filters).forEach(([key, val]) => {
                if (val) params.append(key, val);
            });
        }

        const queryString = params.toString();
        const url = queryString ? `${HISTORY_CONFIG.API_ENDPOINT}?${queryString}` : HISTORY_CONFIG.API_ENDPOINT;

        const data = await LogiQ.apiCall(url);
        historyData = data.anomalies || [];

        loading.style.display = 'none';

        if (historyData.length === 0) {
            emptyState.style.display = '';
        } else {
            renderHistoryTable();
        }

    } catch (error) {
        loading.style.display = 'none';
        document.getElementById('history-error-message').textContent = 'Failed to load history: ' + error.message;
        errorBanner.classList.add('visible');
    }
}

/**
 * Render the history table with current data.
 */
function renderHistoryTable() {
    const tbody = document.getElementById('history-table-body');

    tbody.innerHTML = historyData.map(anomaly => {
        const levelClass = `badge-${anomaly.level || 'error'}`;
        const statusClass = anomaly.status === 'resolved' ? 'resolved' : 'open';
        const cacheLabel = anomaly.cache_hit ? 'Cached' : 'Live';
        const cacheBadgeClass = anomaly.cache_hit ? 'badge-cache' : 'badge-info';

        return `
            <tr data-id="${anomaly.id}">
                <td style="color: var(--color-text-muted); font-size: var(--font-size-xs);">#${anomaly.id}</td>
                <td>${LogiQ.formatTimestamp(anomaly.timestamp)}</td>
                <td><span class="badge ${levelClass}">${(anomaly.level || 'error').toUpperCase()}</span></td>
                <td><span class="badge badge-category">${anomaly.category || 'Unknown'}</span></td>
                <td class="message-preview" title="${(anomaly.message || '').replace(/"/g, '&quot;')}">${anomaly.message || 'No message'}</td>
                <td><span class="badge ${cacheBadgeClass}">${cacheLabel}</span></td>
                <td>
                    <span class="status-dot ${statusClass}"></span>
                    <span class="status-text ${statusClass}">${statusClass === 'resolved' ? 'Resolved' : 'Open'}</span>
                </td>
                <td>
                    <div class="row-actions">
                        <button class="row-action-btn" onclick="openDrawer(${anomaly.id})" title="View details">
                            <i data-lucide="eye" width="14" height="14"></i>
                            View
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    lucide.createIcons();
}

/**
 * Get current filter values from the filter bar.
 * @returns {object} Filter parameters
 */
function getFilterValues() {
    return {
        date_from: document.getElementById('filter-date-from').value || undefined,
        date_to: document.getElementById('filter-date-to').value || undefined,
        level: document.getElementById('filter-severity').value || undefined,
        category: document.getElementById('filter-category').value || undefined,
        status: document.getElementById('filter-status').value || undefined,
    };
}

/**
 * Clear all filter inputs.
 */
function clearFilters() {
    document.getElementById('filter-date-from').value = '';
    document.getElementById('filter-date-to').value = '';
    document.getElementById('filter-severity').value = '';
    document.getElementById('filter-category').value = '';
    document.getElementById('filter-status').value = '';
}

/**
 * Export current history data as a CSV file.
 */
function exportCSV() {
    if (historyData.length === 0) {
        LogiQ.showToast('No Data', 'No history data to export', 'warning');
        return;
    }

    const rows = [HISTORY_CONFIG.CSV_HEADERS.join(',')];

    historyData.forEach(anomaly => {
        const row = [
            anomaly.id,
            `"${(anomaly.timestamp || '').replace(/"/g, '""')}"`,
            anomaly.level || '',
            anomaly.category || '',
            `"${(anomaly.message || '').replace(/"/g, '""')}"`,
            anomaly.status || '',
            anomaly.cache_hit ? 'Yes' : 'No',
            `"${(anomaly.created_at || '').replace(/"/g, '""')}"`,
        ];
        rows.push(row.join(','));
    });

    const csvContent = rows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = HISTORY_CONFIG.CSV_FILENAME;
    link.click();

    URL.revokeObjectURL(url);

    LogiQ.showToast('Exported', `${historyData.length} anomalies exported to CSV`, 'success');
}

/**
 * Set up event listeners for the history page.
 */
function setupHistoryEventListeners() {
    /* Apply filters */
    document.getElementById('btn-apply-filters').addEventListener('click', () => {
        const filters = getFilterValues();
        fetchHistory(filters);
    });

    /* Clear filters */
    document.getElementById('btn-clear-filters').addEventListener('click', () => {
        clearFilters();
        fetchHistory();
    });

    /* Export CSV */
    document.getElementById('btn-export-csv').addEventListener('click', exportCSV);

    /* Clear History */
    const clearBtn = document.getElementById('btn-clear-history');
    if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
            if (confirm("Are you sure you want to clear all history records from the database? This action is permanent.")) {
                try {
                    await LogiQ.apiCall('/api/history', { method: 'DELETE' });
                    sessionStorage.removeItem('logiq_session_id');
                    sessionStorage.removeItem('logiq_upload_result');
                    LogiQ.showToast('History Cleared', 'All stored sessions and anomalies have been deleted.', 'success');
                    await fetchHistory();
                } catch (error) {
                    LogiQ.showToast('Error', 'Failed to clear history: ' + error.message, 'error');
                }
            }
        });
    }
}

/**
 * Find an anomaly by ID in history data (used by drawer).
 * @param {number} id - Anomaly ID
 * @returns {object|undefined}
 */
function findAnomaly(id) {
    return historyData.find(a => a.id === id);
}

/* ── Initialize on DOM Ready ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initHistory);
