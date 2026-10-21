const TOKEN_KEY = "documind_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// Turns DRF error responses into one readable sentence
function formatError(data) {
  if (!data || typeof data !== "object") return "Something went wrong. Please try again.";
  if (data.detail) return data.detail;
  if (data.non_field_errors) return data.non_field_errors.join(" ");
  return Object.entries(data)
    .map(([field, messages]) => `${field}: ${[].concat(messages).join(" ")}`)
    .join(" ");
}

async function request(path, { method = "GET", body } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Token ${token}`;

  let payload;
  if (body instanceof FormData) {
    payload = body; // the browser sets the multipart Content-Type itself
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError("Can't reach the server. Is Django running?", 0);
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401) {
      // Token is missing or no longer valid: log the user out everywhere
      clearToken();
      window.dispatchEvent(new Event("auth:logout"));
    }
    throw new ApiError(formatError(data), response.status);
  }
  return data;
}

export const api = {
  register: (username, email, password) =>
    request("/auth/register/", { method: "POST", body: { username, email, password } }),
  login: (username, password) =>
    request("/auth/login/", { method: "POST", body: { username, password } }),
  logout: () => request("/auth/logout/", { method: "POST" }),
  me: () => request("/auth/me/"),

  listDocuments: () => request("/documents/"),
  uploadDocument: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/documents/", { method: "POST", body: form });
  },
  deleteDocument: (id) => request(`/documents/${id}/`, { method: "DELETE" }),
  reprocessDocument: (id) => request(`/documents/${id}/reprocess/`, { method: "POST" }),

  listConversations: () => request("/conversations/"),
  getConversation: (id) => request(`/conversations/${id}/`),
  deleteConversation: (id) => request(`/conversations/${id}/`, { method: "DELETE" }),

  ask: (question, documentIds, conversationId) =>
    request("/ask/", {
      method: "POST",
      body: {
        question,
        document_ids: documentIds,
        conversation_id: conversationId ?? null,
      },
    }),
};
