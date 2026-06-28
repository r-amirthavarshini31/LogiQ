/**
 * LogiQ — User Profile & History Dashboard JS
 * Manages tab views, aggregates lifetime metrics, initializes metrics charts,
 * updates user preferences, and manages past session deletion.
 */
document.addEventListener('DOMContentLoaded', () => {
    // ─── Setup Defaults / Verify Session ──────────────────────────────────
    let user = JSON.parse(localStorage.getItem('logiq_user'));
    
    // If not logged in, load defaults but prompt them to log in for full persistence
    if (!user) {
        user = {
            name: "DevOps Dan",
            email: "dan@company.com",
            role: "SRE Analyst",
            apiKey: "lq_live_samplekey123456789",
            slackWebhook: "",
            discordWebhook: ""
        };
        // Do not force redirect so they can play around, but show a toast
        if (window.LogiQ && typeof window.LogiQ.showToast === 'function') {
            window.LogiQ.showToast("Demo Mode", "Log in to create and save custom profile credentials.", "info");
        }
    }

    // Populate UI Text fields
    updateProfileUIDisplay(user);

    // ─── Tab Controls ──────────────────────────────────────────────────────
    const tabButtons = document.querySelectorAll('.profile-tab-btn');
    const tabContents = document.querySelectorAll('.profile-tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
        });
    });

    // ─── Logout handler ────────────────────────────────────────────────────
    const logoutBtn = document.getElementById('btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('logiq_user');
            if (window.LogiQ && typeof window.LogiQ.showToast === 'function') {
                window.LogiQ.showToast("Signed Out", "Redirecting...", "success");
            }
            setTimeout(() => {
                window.location.href = '/';
            }, 800);
        });
    }

    // ─── Initialize Settings Form ──────────────────────────────────────────
    const settingsForm = document.getElementById('settings-profile-form');
    const inputUsername = document.getElementById('settings-username');
    const inputEmail = document.getElementById('settings-email');
    const inputRole = document.getElementById('settings-role');
    const inputApiKey = document.getElementById('settings-apikey');
    const inputSlack = document.getElementById('settings-slack');
    const inputDiscord = document.getElementById('settings-discord');

    // Bind values from localStorage to form inputs
    if (settingsForm) {
        inputUsername.value = user.name || "";
        inputEmail.value = user.email || "";
        inputRole.value = user.role || "DevOps Engineer";
        inputApiKey.value = user.apiKey || "";
        inputSlack.value = user.slackWebhook || "";
        inputDiscord.value = user.discordWebhook || "";

        // Rotate key handler
        document.getElementById('btn-rotate-key').addEventListener('click', () => {
            const newKey = 'lq_live_' + Math.random().toString(36).substring(2, 18) + Math.random().toString(36).substring(2, 10);
            inputApiKey.value = newKey;
            LogiQ.showToast("API Key Rotated", "Remember to save settings to apply changes.", "warning");
        });

        // Submit form
        settingsForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            user.name = inputUsername.value.trim();
            user.email = inputEmail.value.trim();
            user.role = inputRole.value;
            user.apiKey = inputApiKey.value;
            user.slackWebhook = inputSlack.value.trim();
            user.discordWebhook = inputDiscord.value.trim();

            localStorage.setItem('logiq_user', JSON.stringify(user));
            updateProfileUIDisplay(user);

            // Sync with base navbar elements
            const navAvatar = document.getElementById('nav-avatar');
            if (navAvatar && user.name) {
                const initials = user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                navAvatar.textContent = initials;
            }

            LogiQ.showToast("Settings Saved", "Profile configs updated successfully.", "success");
            
            // Switch back to dashboard overview tab
            setTimeout(() => {
                document.querySelector('[data-tab="tab-dashboard"]').click();
            }, 500);
        });

        // Purge DB handler
        document.getElementById('btn-purge-db').addEventListener('click', async () => {
            if (confirm("Are you sure you want to delete all historical analysis sessions? This action is permanent!")) {
                try {
                    await LogiQ.apiCall('/api/history', { method: 'DELETE' });
                    sessionStorage.removeItem('logiq_session_id');
                    sessionStorage.removeItem('logiq_upload_result');
                    LogiQ.showToast("Database Purged", "Cleaned up all history sessions.", "success");
                    loadLifetimeDashboard();
                } catch (err) {
                    console.error("Purging error:", err);
                    LogiQ.showToast("Error", "Failed to purge database sessions.", "error");
                }
            }
        });
    }

    // ─── Fetch Stats & Load Charts ─────────────────────────────────────────
    let categoryChart = null;

    async function loadLifetimeDashboard() {
        try {
            const stats = await LogiQ.apiCall('/api/profile/stats');
            const history = await LogiQ.apiCall('/api/profile/sessions');

            // Render top cards
            document.getElementById('stat-lines').textContent = Number(stats.total_lines).toLocaleString();
            document.getElementById('stat-anomalies').textContent = Number(stats.total_anomalies).toLocaleString();
            
            const resolvedRate = stats.total_anomalies > 0 
                ? Math.round((stats.total_resolved / stats.total_anomalies) * 100) 
                : 100;
            document.getElementById('stat-resolved').textContent = resolvedRate + '%';

            // Populate categories chart
            renderChart(stats.categories || {});

            // Populate recent sessions table
            renderSessionsTable(history.sessions || []);

        } catch (err) {
            console.error("Failed to load dashboard metrics", err);
            LogiQ.showToast("Dashboard Error", "Could not load profile dashboard telemetry.", "error");
        }
    }

    /**
     * Update UI Display strings
     */
    function updateProfileUIDisplay(userData) {
        document.getElementById('profile-name-display').textContent = userData.name;
        document.getElementById('profile-role-display').textContent = userData.role;
        document.getElementById('profile-email-display').textContent = userData.email;
        
        const avatarBox = document.getElementById('profile-avatar');
        if (userData.name) {
            const initials = userData.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            avatarBox.textContent = initials || 'U';
        }
    }

    /**
     * Setup & draw the category distribution chart
     */
    function renderChart(categories) {
        const ctx = document.getElementById('categoryChart').getContext('2d');
        
        const keys = Object.keys(categories);
        const values = Object.values(categories);

        // Fallback placeholder data if database is empty
        const finalKeys = keys.length > 0 ? keys : ['Database', 'Network', 'Auth', 'Memory', 'Timeout'];
        const finalValues = values.length > 0 ? values : [5, 4, 3, 2, 1];

        if (categoryChart) {
            categoryChart.destroy();
        }

        categoryChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: finalKeys,
                datasets: [{
                    data: finalValues,
                    backgroundColor: [
                        '#818CF8', // Lavender primary
                        '#6EE7B7', // Mint
                        '#FCA5A5', // Peach
                        '#BAE6FD', // Sky
                        '#FEF3C7', // Cream
                        '#F472B6', // Rose
                        '#C084FC'  // Purple
                    ],
                    borderWidth: 2,
                    borderColor: 'rgba(255, 255, 255, 0.4)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            font: {
                                family: 'Plus Jakarta Sans',
                                size: 11
                            },
                            color: '#6B6890'
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }

    /**
     * Populate the sessions history table
     */
    function renderSessionsTable(sessions) {
        const tbody = document.getElementById('sessions-table-body');
        tbody.innerHTML = '';

        if (sessions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; color: var(--color-text-muted); padding: var(--space-xl);">
                        <i data-lucide="folder-open" width="32" height="32" style="margin-bottom: var(--space-xs); opacity: 0.5;"></i>
                        <p>No historical analysis sessions found. Ingest logs to populate.</p>
                    </td>
                </tr>
            `;
            lucide.createIcons({ nodes: [tbody] });
            return;
        }

        sessions.forEach(session => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight: 600;">${session.filename}</td>
                <td>
                    <span class="badge" style="background: var(--color-peach); color: var(--color-error-dark); font-weight:700; padding: 2px 6px; border-radius: 6px;">
                        ${session.anomaly_count}
                    </span>
                </td>
                <td>
                    <span class="badge" style="background: var(--color-mint); color: var(--color-success-dark); font-weight:700; padding: 2px 6px; border-radius: 6px;">
                        ${session.resolved_count} / ${session.anomaly_count}
                    </span>
                </td>
                <td style="color: var(--color-text-muted); font-size: var(--font-size-xs);">
                    ${LogiQ.formatTimestamp(session.created_at)}
                </td>
                <td>
                    <div class="flex gap-xs">
                        <button class="clay-btn clay-btn-ghost clay-btn-sm btn-view-session" data-id="${session.id}" title="Virtualize on Dashboard" style="padding: 6px; border-radius: 6px;">
                            <i data-lucide="eye" width="16" height="16"></i>
                        </button>
                        <button class="clay-btn clay-btn-error clay-btn-sm btn-delete-session" data-id="${session.id}" title="Delete session" style="padding: 6px; border-radius: 6px; background: rgba(220, 38, 38, 0.1);">
                            <i data-lucide="trash-2" width="16" height="16"></i>
                        </button>
                    </div>
                </td>
            `;

            // View button handler
            tr.querySelector('.btn-view-session').addEventListener('click', () => {
                LogiQ.store('session_id', session.id);
                window.location.href = '/dashboard';
            });

            // Delete button handler
            tr.querySelector('.btn-delete-session').addEventListener('click', async () => {
                if (confirm(`Delete session "${session.filename}" and its anomalies?`)) {
                    try {
                        const response = await fetch(`/api/session/${session.id}`, { method: 'DELETE' });
                        if (response.ok) {
                            LogiQ.showToast("Session Deleted", "Successfully removed log history.", "success");
                            loadLifetimeDashboard();
                        } else {
                            throw new Error("Deletion failed");
                        }
                    } catch (err) {
                        LogiQ.showToast("Delete Failed", err.message, "error");
                    }
                }
            });

            tbody.appendChild(tr);
        });

        // Initialize icons inside the table
        lucide.createIcons({ nodes: [tbody] });
    }

    // Drive initial fetch
    loadLifetimeDashboard();
});
