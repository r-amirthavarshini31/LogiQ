/**
 * LogiQ Sign Up Controller
 * Handles input verification, password checks, and mock session storage.
 */
document.addEventListener('DOMContentLoaded', () => {
    // If user already logged in, redirect to profile
    if (localStorage.getItem('logiq_user')) {
        window.location.href = '/profile';
        return;
    }

    const signupForm = document.getElementById('signup-form');
    const errorBanner = document.getElementById('signup-error-banner');
    const errorMessage = document.getElementById('signup-error-message');

    signupForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const role = document.getElementById('role').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;

        // Validation checks
        if (!username || !email || !role || !password || !confirmPassword) {
            showError("Please fill out all fields.");
            return;
        }

        if (password !== confirmPassword) {
            showError("Passwords do not match.");
            return;
        }

        if (password.length < 6) {
            showError("Password must be at least 6 characters.");
            return;
        }

        // Mock registration success - save session payload
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
            window.LogiQ.showToast("Account Created", `Welcome aboard, ${username}!`, "success");
        }

        // Redirect to profile
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
        
        // Shake card feedback
        const card = document.querySelector('.login-card');
        card.style.animation = 'none';
        void card.offsetWidth;
        card.style.animation = 'shake 0.4s ease';
    }
});

// Add keyframes for shake animation dynamically
if (!document.getElementById('shake-keyframes-style')) {
    const styleNode = document.createElement('style');
    styleNode.id = 'shake-keyframes-style';
    styleNode.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20%, 60% { transform: translateX(-6px); }
        40%, 80% { transform: translateX(6px); }
    }
    `;
    document.head.appendChild(styleNode);
}
