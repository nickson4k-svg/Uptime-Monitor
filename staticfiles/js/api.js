/**
 * API client — thin wrapper around fetch() with JWT token management.
 *
 * Features:
 * - Auto-attach Authorization header
 * - Auto-refresh access token on 401
 * - Redirect to login on refresh failure
 */

const API = (() => {
  const BASE = '/api/v1';

  function getTokens() {
    return {
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token'),
    };
  }

  function setTokens({ access, refresh }) {
    localStorage.setItem('access_token', access);
    if (refresh) localStorage.setItem('refresh_token', refresh);
  }

  function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  function isLoggedIn() {
    return !!getTokens().access;
  }

  async function refreshAccessToken() {
    const { refresh } = getTokens();
    if (!refresh) return false;

    const resp = await fetch(`${BASE}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });

    if (resp.ok) {
      const data = await resp.json();
      setTokens({ access: data.access, refresh: data.refresh });
      return true;
    }
    return false;
  }

  async function request(method, path, body = null, retry = true) {
    const { access } = getTokens();
    const headers = { 'Content-Type': 'application/json' };
    if (access) headers['Authorization'] = `Bearer ${access}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(`${BASE}${path}`, opts);

    if (resp.status === 401 && retry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) return request(method, path, body, false);
      clearTokens();
      window.location.href = '/login/';
      return;
    }

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: { message: resp.statusText } }));
      throw new APIError(resp.status, err?.error?.message || 'Request failed', err);
    }

    if (resp.status === 204) return null;
    return resp.json();
  }

  // ── Auth ──────────────────────────────────────────────────────────────────

  async function login(email, password) {
    const data = await request('POST', '/auth/token/', { email, password });
    setTokens({ access: data.access, refresh: data.refresh });
    return data.user;
  }

  async function register(email, password, passwordConfirm, fullName) {
    const data = await request('POST', '/auth/register/', {
      email, password, password_confirm: passwordConfirm, full_name: fullName
    });
    setTokens({ access: data.access, refresh: data.refresh });
    return data.user;
  }

  function logout() {
    clearTokens();
    window.location.href = '/login/';
  }

  // ── Monitors ──────────────────────────────────────────────────────────────

  const monitors = {
    list: () => request('GET', '/monitors/'),
    get: (id) => request('GET', `/monitors/${id}/`),
    create: (data) => request('POST', '/monitors/', data),
    update: (id, data) => request('PATCH', `/monitors/${id}/`, data),
    delete: (id) => request('DELETE', `/monitors/${id}/`),
    pause: (id) => request('POST', `/monitors/${id}/pause/`),
    resume: (id) => request('POST', `/monitors/${id}/resume/`),
    stats: (id, period = '24h') => request('GET', `/monitors/${id}/stats/?period=${period}`),
  };

  // ── Checks ────────────────────────────────────────────────────────────────

  const checks = {
    list: (monitorId) => request('GET', `/monitors/${monitorId}/checks/`),
  };

  // ── Incidents ─────────────────────────────────────────────────────────────

  const incidents = {
    list: (monitorId, onlyOpen = false) => {
      const q = onlyOpen ? '?is_resolved=false' : '';
      return request('GET', `/monitors/${monitorId}/incidents/${q}`);
    },
  };

  // ── Alert Channels ────────────────────────────────────────────────────────

  const alertChannels = {
    list: () => request('GET', '/alert-channels/'),
    create: (data) => request('POST', '/alert-channels/', data),
    update: (id, data) => request('PATCH', `/alert-channels/${id}/`, data),
    delete: (id) => request('DELETE', `/alert-channels/${id}/`),
  };

  return { isLoggedIn, login, register, logout, monitors, checks, incidents, alertChannels };
})();

// ── Error class ───────────────────────────────────────────────────────────────

class APIError extends Error {
  constructor(status, message, raw) {
    super(message);
    this.status = status;
    this.raw = raw;
  }
}

// ── Toast utility ─────────────────────────────────────────────────────────────

const Toast = {
  _container: null,

  _init() {
    if (!this._container) {
      this._container = document.createElement('div');
      this._container.id = 'toast-container';
      document.body.appendChild(this._container);
    }
  },

  show(message, type = 'info', duration = 4000) {
    this._init();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    this._container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  success: (msg) => Toast.show(msg, 'success'),
  error: (msg) => Toast.show(msg, 'error'),
  info: (msg) => Toast.show(msg, 'info'),
};
