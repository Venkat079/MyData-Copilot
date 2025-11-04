const TOKEN_KEY = "jwtToken";

export function saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function isAuthenticated() {
  return !!localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// Optional helper (already present)
export function getAuthHeader() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}
