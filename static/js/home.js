'use strict';

const TOKEN_KEY = 'db_token';

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

document.addEventListener('DOMContentLoaded', async () => {
    // Already authenticated → go straight to the board
    const token = getToken();
    if (token) {
        try {
            const res = await fetch('/api/auth/me', {
                headers: { 'Authorization': 'Bearer ' + token }
            });
            if (res.ok) {
                window.location.href = '/board';
                return;
            }
        } catch (_) {}
        clearToken();
    }

    document.body.addEventListener('auth-success', event => {
        setToken(event.detail.token);
        window.location.href = '/board';
    });

    // ESC closes modals
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') { closeLoginModal(); closeRegisterModal(); }
    });

    // Click backdrop to close
    document.getElementById('login-modal-overlay').addEventListener('click', e => {
        if (e.target === e.currentTarget) closeLoginModal();
    });
    document.getElementById('register-modal-overlay').addEventListener('click', e => {
        if (e.target === e.currentTarget) closeRegisterModal();
    });
});

function openLoginModal() {
    document.getElementById('login-modal-overlay').classList.add('open');
    document.getElementById('login-form').reset();
    document.getElementById('login-error').textContent = '';
    setTimeout(() => document.getElementById('login-username').focus(), 50);
}

function closeLoginModal() {
    document.getElementById('login-modal-overlay').classList.remove('open');
}

function openRegisterModal() {
    document.getElementById('register-modal-overlay').classList.add('open');
    document.getElementById('register-form').reset();
    document.getElementById('register-error').textContent = '';
    setTimeout(() => document.getElementById('register-username').focus(), 50);
}

function closeRegisterModal() {
    document.getElementById('register-modal-overlay').classList.remove('open');
}
