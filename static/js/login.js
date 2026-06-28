/**
 * LogiQ Login Controller
 * Handles mock login authentication, error states, and session initialization.
 */
document.addEventListener('DOMContentLoaded', () => {
    // If user already logged in, redirect to profile
    if (localStorage.getItem('logiq_user')) {
        window.location.href = '/profile';
        return;
    }

    const loginForm = document.getElementById('login-form');
    const errorBanner = document.getElementById('login-error-banner');
    const errorMessage = document.getElementById('login-error-message');

    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const role = document.getElementById('role').value;
        const password = document.getElementById('password').value;

        // Simple validation
        if (!username || !email || !role || !password) {
            showError("Please fill out all fields.");
            return;
        }

        // Mock authentication success
        const userSession = {
            name: username,
            email: email,
            role: role,
            createdAt: new Date().toISOString(),
            apiKey: 'lq_live_' + Math.random().toString(36).substring(2, 18) + Math.random().toString(36).substring(2, 10),
            discordWebhook: 'https://discord.com/api/webhooks/000000000000000000/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
        };

        // Persist session to localStorage
        localStorage.setItem('logiq_user', JSON.stringify(userSession));

        // Display success toast and redirect
        if (window.LogiQ && typeof window.LogiQ.showToast === 'function') {
            window.LogiQ.showToast("Access Granted", `Welcome back, ${username}!`, "success");
        }

        // Redirect to profile after a brief delay for toast visibility
        setTimeout(() => {
            window.location.href = '/profile';
        }, 800);
    });

    /**
     * Helper to show the error banner.
     * @param {string} msg - The error message.
     */
    function showError(msg) {
        errorMessage.textContent = msg;
        errorBanner.style.display = 'flex';
        
        // Add a gentle shake animation to the card
        const card = document.querySelector('.login-card');
        card.style.animation = 'none';
        // Trigger reflow
        void card.offsetWidth;
        card.style.animation = 'shake 0.4s ease';
    }
});

// Add keyframes for shake animation dynamically
const styleNode = document.createElement('style');
styleNode.textContent = `
@keyframes shake {
    0%, 100% { transform: translateX(0); }
    20%, 60% { transform: translateX(-6px); }
    40%, 80% { transform: translateX(6px); }
}
`;
document.head.appendChild(styleNode);
