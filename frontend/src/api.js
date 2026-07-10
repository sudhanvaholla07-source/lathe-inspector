// Every backend call funnels through here. The point of a single
// api.js instead of scattering `fetch()` calls across pages: one place
// to (a) know the backend's base URL, (b) attach the JWT to every
// request automatically, and (c) turn non-2xx responses into thrown
// errors so pages can just `try/catch` instead of checking
// `res.ok` everywhere.

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:4000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// `body` is JSON by default (login, signup, creating a machine). File
// uploads (part type + inspection creation) pass a FormData instance
// instead -- when they do, we must NOT set Content-Type ourselves;
// the browser sets it (including the multipart boundary) automatically.
async function request(path, { method = "GET", body, isFormData = false } = {}) {
  const headers = { ...authHeaders() };
  if (!isFormData && body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
  });

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const message = (data && data.error) || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

export const api = {
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  signup: (email, password, name, role) =>
    request("/auth/signup", { method: "POST", body: { email, password, name, role } }),

  getMachines: () => request("/machines"),
  createMachine: (name, location) => request("/machines", { method: "POST", body: { name, location } }),

  getPartTypes: (machineId) =>
    request(machineId ? `/part-types?machineId=${machineId}` : "/part-types"),
  createPartType: (formData) => request("/part-types", { method: "POST", body: formData, isFormData: true }),

  getInspections: (filters = {}) => {
    const params = new URLSearchParams(filters).toString();
    return request(params ? `/inspections?${params}` : "/inspections");
  },
  confirmInspection: (id, confirmedResult) =>
    request(`/inspections/${id}/confirm`, { method: "PATCH", body: { confirmedResult } }),

  getBatches: () => request("/batches"),
  getBatch: (id) => request(`/batches/${id}`),
  createBatch: (label) => request("/batches", { method: "POST", body: { label } }),
  closeBatch: (id) => request(`/batches/${id}/close`, { method: "PATCH" }),

  getStats: (filters = {}) => {
    const params = new URLSearchParams(filters).toString();
    return request(params ? `/inspections/stats?${params}` : "/inspections/stats");
  },
};

export { BASE_URL };
