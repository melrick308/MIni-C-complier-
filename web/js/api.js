async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Server not reachable — is uvicorn running?");
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join("; ");
    } catch { /* not JSON */ }
    throw new Error(`Request rejected: ${detail}`);
  }
  return response.json();
}

export const api = {
  compile(payload) {
    return request("/api/compile", { method: "POST", body: JSON.stringify(payload) });
  },
  examples() {
    return request("/api/examples");
  },
  grammar(profile) {
    return request(`/api/grammar?profile=${encodeURIComponent(profile)}`);
  },
};
