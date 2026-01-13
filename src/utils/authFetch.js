import { getAccessToken, refreshAccessToken, clearTokens } from "./authService";

/**
 * ✅ authFetch:
 * - sends access token
 * - if 401 -> refresh -> retry
 * - if refresh fails -> logout by clearing tokens
 */
export async function authFetch(url, options = {}, onLogout) {
  let accessToken = getAccessToken();

  const doFetch = async (token) => {
    const headers = {
      ...(options.headers || {}),
      "Content-Type": "application/json",
    };

    if (token) headers.Authorization = `Bearer ${token}`;

    return fetch(url, {
      ...options,
      headers,
    });
  };

  // 1️⃣ attempt with current access token
  let res = await doFetch(accessToken);

  // 2️⃣ if access token expired -> refresh and retry
  if (res.status === 401) {
    const newToken = await refreshAccessToken();

    // refresh token expired -> logout
    if (!newToken) {
      clearTokens();
      if (onLogout) onLogout();
      return res; // return old 401 response
    }

    // retry request with new access token
    res = await doFetch(newToken);
  }

  return res;
}
