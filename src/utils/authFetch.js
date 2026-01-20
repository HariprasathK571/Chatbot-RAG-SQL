import { getAccessToken, refreshAccessToken, clearTokens } from "./authService";

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

  // 1️⃣ try with current access token
  let res = await doFetch(accessToken);

  // 2️⃣ if 401 -> refresh -> retry
  if (res.status === 401) {
    const newToken = await refreshAccessToken();

    // refresh failed => logout
    if (!newToken) {
      clearTokens();
      if (onLogout) onLogout();
      return res;
    }

    // retry with new access token
    res = await doFetch(newToken);
  }

  return res;
}
