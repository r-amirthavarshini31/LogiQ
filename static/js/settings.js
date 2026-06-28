/**
 * LogiQ — Settings Page JavaScript
 * Handles loading, saving, and toggling of application settings.
 * @module settings
 */

/** @const {object} Settings configuration */
const SETTINGS_CONFIG = {
    API_ENDPOINT: '/api/settings',
    /** Map of setting keys to their input element IDs */
    FIELDS: {
        openai_api_key: 'setting-openai-key',
        openai_enabled: 'setting-openai-enabled',
        ollama_endpoint: 'setting-ollama-endpoint',
        ollama_enabled: 'setting-ollama-enabled',
        slack_webhook_url: 'setting-slack-webhook',
        slack_enabled: 'setting-slack-enabled',
        discord_webhook_url: 'setting-discord-webhook',
        discord_enabled: 'setting-discord-enabled',
        github_token: 'setting-github-token',
        github_enabled: 'setting-github-enabled',
        github_repo: 'setting-github-repo',
        twilio_account_sid: 'setting-twilio-sid',
        twilio_enabled: 'setting-twilio-enabled',
        twilio_auth_token: 'setting-twilio-token',
        twilio_from_number: 'setting-twilio-from',
        twilio_to_number: 'setting-twilio-to',
    },
};

/**
 * Initialize the settings page.
 */
async function initSettings() {
    await loadSettings();
    setupSettingsEventListeners();
}

/**
 * Load current settings from the API and populate form fields.
 */
async function loadSettings() {
    try {
        const data = await LogiQ.apiCall(SETTINGS_CONFIG.API_ENDPOINT);
        const settings = data.settings || {};

        /* Populate input fields */
        Object.entries(SETTINGS_CONFIG.FIELDS).forEach(([key, elementId]) => {
            const element = document.getElementById(elementId);
            if (!element) return;

            const value = settings[key];
            if (value === undefined || value === null) return;

            if (element.type === 'checkbox') {
                element.checked = value === 'true' || value === true;
            } else {
                element.value = value;
            }
        });

    } catch (error) {
        /* Settings may not exist yet, that's fine */
        console.log('No saved settings found, using defaults');
    }
}

/**
 * Collect all setting values from the form.
 * @returns {object} Key-value pairs of settings
 */
function collectSettings() {
    const settings = {};

    Object.entries(SETTINGS_CONFIG.FIELDS).forEach(([key, elementId]) => {
        const element = document.getElementById(elementId);
        if (!element) return;

        if (element.type === 'checkbox') {
            settings[key] = element.checked.toString();
        } else {
            settings[key] = element.value;
        }
    });

    return settings;
}

/**
 * Save settings to the API.
 */
async function saveSettings() {
    const btn = document.getElementById('btn-save-settings');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" width="20" height="20"></i> Saving...';

    try {
        const settings = collectSettings();

        await LogiQ.apiCall(SETTINGS_CONFIG.API_ENDPOINT, {
            method: 'POST',
            body: JSON.stringify(settings),
        });

        LogiQ.showToast('Settings Saved', 'Your configuration has been saved successfully', 'success');

    } catch (error) {
        LogiQ.showToast('Save Failed', error.message, 'error');
        const errorBanner = document.getElementById('settings-error');
        document.getElementById('settings-error-message').textContent = 'Failed to save: ' + error.message;
        errorBanner.classList.add('visible');
    }

    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="save" width="20" height="20"></i> Save Settings';
    lucide.createIcons({ nodes: [btn] });
}

/**
 * Set up event listeners for the settings page.
 */
function setupSettingsEventListeners() {
    /* Save button */
    document.getElementById('btn-save-settings').addEventListener('click', saveSettings);

    /* Toggle switches — visual feedback */
    document.querySelectorAll('.clay-toggle input[type="checkbox"]').forEach(toggle => {
        toggle.addEventListener('change', () => {
            const section = toggle.closest('.settings-section');
            if (section) {
                const inputs = section.querySelectorAll('.clay-input:not([type="checkbox"])');
                inputs.forEach(input => {
                    input.style.opacity = toggle.checked ? '1' : '0.5';
                });
            }
        });
    });

    /* Enter key to save */
    document.querySelectorAll('.clay-input').forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                saveSettings();
            }
        });
    });
}

/* ── Initialize on DOM Ready ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initSettings);
