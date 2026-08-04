import { getDeviceId } from "./deviceId.js";

export async function apiFetch(path, options = {}) {
  const headers = {
    "X-Device-Id": getDeviceId(),
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };

  const res = await fetch(path, { ...options, headers });

  if (res.status === 204) {
    return null;
  }

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}
