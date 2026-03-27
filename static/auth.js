// Tracey's Sentinel Authentication System

const API_BASE = '';

// Show/hide alert message
function showAlert(message, type = 'info') {
    const alert = document.getElementById('alert');
    alert.textContent = message;
    alert.className = `alert show alert-${type}`;
    setTimeout(() => {
        alert.classList.remove('show');
    }, 5000);
}

// Switch between login and signup forms
function switchAuthMode(mode) {
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');

    if (mode === 'signup') {
        loginForm.style.display = 'none';
        signupForm.style.display = 'block';
    } else {
        loginForm.style.display = 'block';
        signupForm.style.display = 'none';
    }

    // Clear alert when switching
    document.getElementById('alert').classList.remove('show');
}

// Clear form errors
function clearFormErrors(prefix) {
    const inputs = document.querySelectorAll(`[id^="${prefix}"]`);
    inputs.forEach(input => {
        const errorEl = document.getElementById(`${input.id}-error`);
        if (errorEl) {
            errorEl.classList.remove('show');
            errorEl.textContent = '';
        }
    });
}

// Show form error
function showFormError(fieldId, message) {
    const errorEl = document.getElementById(`${fieldId}-error`);
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.add('show');
    }
}

// Demo user quick login
function setDemoUser(userId) {
    document.getElementById('login-user').value = userId;
    document.getElementById('login-password').value = 'demo123'; // Demo password
    showAlert(`🔑 Demo user "${userId}" loaded. Password auto-filled.`, 'info');
    setTimeout(() => {
        document.getElementById('login-password').focus();
    }, 100);
}

// Handle login
async function handleLogin(event) {
    event.preventDefault();
    clearFormErrors('login');

    const userId = document.getElementById('login-user').value.trim();
    const password = document.getElementById('login-password').value;

    if (!userId) {
        showFormError('login-user', 'User ID is required');
        return;
    }

    if (!password) {
        showFormError('login-password', 'Password is required');
        return;
    }

    const btn = document.getElementById('login-btn');
    const btnText = document.getElementById('login-btn-text');
    const originalText = btnText.textContent;

    try {
        btn.disabled = true;
        btnText.innerHTML = '<span class="loading-spinner"></span>Logging in...';

        // Call backend login endpoint
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                password: password,
            }),
        });

        const data = await response.json();

        if (response.ok && data.token) {
            // Store authentication token
            localStorage.setItem('auth_token', data.token);
            localStorage.setItem('user_id', userId);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('org_id', data.org_id);

            showAlert(`✅ Login successful! Welcome, ${userId}.`, 'success');

            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        } else {
            showFormError(
                'login-user',
                data.detail || 'Invalid credentials'
            );
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert('❌ Login failed. Please try again.', 'error');
    } finally {
        btn.disabled = false;
        btnText.textContent = originalText;
    }
}

// Handle signup
async function handleSignup(event) {
    event.preventDefault();
    clearFormErrors('signup');

    const userId = document.getElementById('signup-user').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const role = document.getElementById('signup-role').value;
    const orgId = document.getElementById('signup-org').value.trim();
    const password = document.getElementById('signup-password').value;
    const confirm = document.getElementById('signup-confirm').value;

    // Validation
    if (!userId || userId.length < 3) {
        showFormError('signup-user', 'User ID must be at least 3 characters');
        return;
    }

    if (!email) {
        showFormError('signup-email', 'Email is required');
        return;
    }

    if (!role) {
        showFormError('signup-role', 'Please select a role');
        return;
    }

    if (!orgId) {
        showFormError('signup-org', 'Organization ID is required');
        return;
    }

    if (password.length < 8) {
        showFormError('signup-password', 'Password must be at least 8 characters');
        return;
    }

    if (password !== confirm) {
        showFormError('signup-confirm', 'Passwords do not match');
        return;
    }

    const btn = document.getElementById('signup-btn');
    const btnText = document.getElementById('signup-btn-text');
    const originalText = btnText.textContent;

    try {
        btn.disabled = true;
        btnText.innerHTML = '<span class="loading-spinner"></span>Creating account...';

        // Call backend signup endpoint
        const response = await fetch(`${API_BASE}/auth/signup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                email: email,
                role: role,
                org_id: orgId,
                password: password,
            }),
        });

        const data = await response.json();

        if (response.ok && data.token) {
            // Store authentication token
            localStorage.setItem('auth_token', data.token);
            localStorage.setItem('user_id', userId);
            localStorage.setItem('user_role', role);
            localStorage.setItem('org_id', orgId);

            showAlert(`✅ Account created successfully! Welcome, ${userId}.`, 'success');

            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        } else {
            if (data.detail) {
                if (data.detail.includes('already exists')) {
                    showFormError('signup-user', 'User ID already exists');
                } else {
                    showAlert(`❌ ${data.detail}`, 'error');
                }
            } else {
                showAlert('❌ Signup failed. Please try again.', 'error');
            }
        }
    } catch (error) {
        console.error('Signup error:', error);
        showAlert('❌ Signup failed. Please try again.', 'error');
    } finally {
        btn.disabled = false;
        btnText.textContent = originalText;
    }
}

// Check authentication on page load
function checkAuthentication() {
    const token = localStorage.getItem('auth_token');
    if (token) {
        // User is already authenticated, redirect to dashboard
        window.location.href = '/';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuthentication();

    // Set up enter key handling
    const loginForm = document.querySelector('#login-form form');
    const signupForm = document.querySelector('#signup-form form');

    if (loginForm) {
        loginForm.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleLogin(e);
            }
        });
    }

    if (signupForm) {
        signupForm.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                handleSignup(e);
            }
        });
    }

    // Default focus
    setTimeout(() => {
        document.getElementById('login-user').focus();
    }, 100);
});
