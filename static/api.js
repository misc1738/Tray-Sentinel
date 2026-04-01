/**
 * Shared API and Utility Functions
 * Replaces duplicated code across static/app.js, static/case.js, static/auth.js, etc.
 */

// ===== API CONFIGURATION =====
const API_BASE_URL = window.location.origin;
const API_TIMEOUT = 30000; // 30 seconds

// ===== JWT TOKEN MANAGEMENT =====
class TokenManager {
    constructor() {
        this.accessToken = localStorage.getItem('access_token');
        this.refreshToken = localStorage.getItem('refresh_token');
        this.tokenExpiry = parseInt(localStorage.getItem('token_expiry') || '0', 10);
    }

    setTokens(accessToken, refreshToken, expiresIn) {
        this.accessToken = accessToken;
        this.refreshToken = refreshToken;
        // Store expiry time (current + expiresIn seconds, minus 1 minute buffer)
        this.tokenExpiry = Date.now() + (expiresIn * 1000) - (60 * 1000);
        
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        localStorage.setItem('token_expiry', this.tokenExpiry.toString());
    }

    clearTokens() {
        this.accessToken = null;
        this.refreshToken = null;
        this.tokenExpiry = 0;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('token_expiry');
    }

    getAccessToken() {
        // Refresh if token is about to expire
        if (this.tokenExpiry && Date.now() > this.tokenExpiry && this.refreshToken) {
            this.refreshAccessToken();
        }
        return this.accessToken;
    }

    async refreshAccessToken() {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    refresh_token: this.refreshToken
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access_token, data.refresh_token, data.expires_in);
                return this.accessToken;
            } else {
                this.clearTokens();
                return null;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
            this.clearTokens();
            return null;
        }
    }

    isAuthenticated() {
        return !!this.accessToken;
    }
}

// Global token manager instance
const tokenManager = new TokenManager();


// ===== FETCH UTILITIES =====

/**
 * Fetch with authentication and error handling
 */
async function fetchAPI(endpoint, options = {}) {
    const {
        method = 'GET',
        body = null,
        headers = {},
        timeout = API_TIMEOUT,
    } = options;

    // Add authorization header if authenticated
    const finalHeaders = {
        'Content-Type': 'application/json',
        ...headers,
    };

    const token = tokenManager.getAccessToken();
    if (token) {
        finalHeaders['Authorization'] = `Bearer ${token}`;
    }

    // Create fetch with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method,
            headers: finalHeaders,
            body: body ? JSON.stringify(body) : null,
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // Handle 401 - unauthorized
        if (response.status === 401) {
            tokenManager.clearTokens();
            window.location.href = '/static/auth.html';
            throw new Error('Session expired. Please login again.');
        }

        // Handle network errors
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new APIError(
                response.status,
                errorData.detail || `HTTP ${response.status}`,
                errorData
            );
        }

        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error instanceof APIError) {
            throw error;
        }
        throw new APIError(0, error.message, null);
    }
}

/**
 * Make GET request
 */
async function apiGet(endpoint, options = {}) {
    return fetchAPI(endpoint, { method: 'GET', ...options });
}

/**
 * Make POST request
 */
async function apiPost(endpoint, body, options = {}) {
    return fetchAPI(endpoint, { method: 'POST', body, ...options });
}

/**
 * Make PUT request
 */
async function apiPut(endpoint, body, options = {}) {
    return fetchAPI(endpoint, { method: 'PUT', body, ...options });
}

/**
 * Make DELETE request
 */
async function apiDelete(endpoint, options = {}) {
    return fetchAPI(endpoint, { method: 'DELETE', ...options });
}


// ===== ERROR HANDLING =====

class APIError extends Error {
    constructor(status, message, details) {
        super(message);
        this.status = status;
        this.details = details;
    }
}

/**
 * Display error message to user
 */
function showError(message, duration = 5000) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 20px;">❌</span>
            <span>${escapeHtml(message)}</span>
            <button style="margin-left: auto; background: none; border: none; cursor: pointer; color: inherit;" onclick="this.parentElement.parentElement.remove()">✕</button>
        </div>
    `;
    
    container.appendChild(notification);
    
    if (duration > 0) {
        setTimeout(() => notification.remove(), duration);
    }
    
    return notification;
}

/**
 * Display success message to user
 */
function showSuccess(message, duration = 3000) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = 'notification success';
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 20px;">✓</span>
            <span>${escapeHtml(message)}</span>
            <button style="margin-left: auto; background: none; border: none; cursor: pointer; color: inherit;" onclick="this.parentElement.parentElement.remove()">✕</button>
        </div>
    `;
    
    container.appendChild(notification);
    
    if (duration > 0) {
        setTimeout(() => notification.remove(), duration);
    }
    
    return notification;
}

/**
 * Display info message to user
 */
function showInfo(message, duration = 0) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = 'notification info';
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 20px;">ℹ️</span>
            <span>${escapeHtml(message)}</span>
            <button style="margin-left: auto; background: none; border: none; cursor: pointer; color: inherit;" onclick="this.parentElement.parentElement.remove()">✕</button>
        </div>
    `;
    
    container.appendChild(notification);
    
    if (duration > 0) {
        setTimeout(() => notification.remove(), duration);
    }
    
    return notification;
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 10000; max-width: 500px;';
    document.body.appendChild(container);
    return container;
}

/**
 * Clear all notifications
 */
function clearNotifications() {
    const container = document.getElementById('notification-container');
    if (container) {
        container.innerHTML = '';
    }
}


// ===== UTILITY FUNCTIONS =====

/**
 * Escape HTML special characters to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format date to readable format
 */
function formatDate(dateStr, includeTime = true) {
    try {
        const date = new Date(dateStr);
        if (includeTime) {
            return date.toLocaleString();
        } else {
            return date.toLocaleDateString();
        }
    } catch {
        return dateStr;
    }
}

/**
 * Format bytes to readable format
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showSuccess('Copied to clipboard');
        return true;
    } catch (error) {
        showError('Failed to copy to clipboard');
        return false;
    }
}

/**
 * Download file from blob
 */
function downloadFile(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

/**
 * Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

/**
 * Throttle function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
