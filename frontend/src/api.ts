const TOKEN_KEY = "rag_admin_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${getToken()}`,
      ...(init?.headers || {}),
    },
  });
  if (res.status === 401) {
    throw new Error("Unauthorized — set your admin token");
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export const API = {
  // metrics
  overview: (hours = 24) =>
    api<any>(`/api/admin/metrics/overview?hours=${hours}`),
  timeseries: (hours = 24, bucket = "hour") =>
    api<any>(`/api/admin/metrics/timeseries?hours=${hours}&bucket=${bucket}`),
  latency: (hours = 24) =>
    api<any>(`/api/admin/metrics/latency?hours=${hours}`),
  topQuestions: () =>
    api<any>(`/api/admin/metrics/top-questions?limit=20`),
  unanswered: () =>
    api<any>(`/api/admin/metrics/unanswered?limit=50`),

  // documents
  documents: () => api<any[]>("/api/admin/documents"),
  chunkingStrategies: () => api<any>("/api/admin/chunking/strategies"),
  uploadDocuments: async (files: File[], chunkStrategy = "auto", chunkParams: Record<string, string | number> = {}) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("tenant_id", "default");
    fd.append("chunk_strategy", chunkStrategy);
    fd.append("chunk_params", JSON.stringify(chunkParams));
    const res = await fetch("/api/admin/documents/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    return res.json();
  },
  createTextDocument: async (title: string, text: string, chunkStrategy = "auto", chunkParams: Record<string, string | number> = {}) => {
    const fd = new FormData();
    fd.append("title", title);
    fd.append("text", text);
    fd.append("tenant_id", "default");
    fd.append("chunk_strategy", chunkStrategy);
    fd.append("chunk_params", JSON.stringify(chunkParams));
    const res = await fetch("/api/admin/documents/create-text", {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    return res.json();
  },
  deleteDocument: (id: string) =>
    api<any>(`/api/admin/documents/${id}`, { method: "DELETE" }),
  docChunks: (id: string) =>
    api<any[]>(`/api/admin/documents/${id}/chunks`),
  reembed: (id: string) =>
    api<any>(`/api/admin/documents/${id}/reembed`, { method: "POST" }),
  
  // chunks
  updateChunk: async (chunkId: string, text: string) => {
    const fd = new FormData();
    fd.append("text", text);
    const res = await fetch(`/api/admin/chunks/${chunkId}`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    return res.json();
  },
  deleteChunk: (chunkId: string) =>
    api<any>(`/api/admin/chunks/${chunkId}`, { method: "DELETE" }),

  // conversations
  conversations: () => api<any[]>("/api/admin/conversations"),
  conversation: (id: string) =>
    api<any>(`/api/admin/conversations/${id}`),
  feedbackRecent: () => api<any[]>("/api/admin/feedback/recent"),

  // cost & health
  cost: (days = 30) => api<any>(`/api/admin/cost?days=${days}`),
  health: () => api<any>("/api/admin/health"),
  storage: () => api<any>("/api/admin/storage"),
  users: () => api<any[]>(`/api/admin/users?tenant_id=default&limit=500`),

  // system prompt
  getPrompt: () => api<any>("/api/admin/prompt"),
  updatePrompt: async (prompt: string) => {
    const fd = new FormData();
    fd.append("prompt", prompt);
    const res = await fetch("/api/admin/prompt", {
      method: "PUT",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    return res.json();
  },
  resetPrompt: () =>
    api<any>("/api/admin/prompt/reset", { method: "POST" }),

  // eval
  goldenList: () => api<any[]>("/api/admin/eval/golden"),
  goldenAdd: (data: any) =>
    api<any>("/api/admin/eval/golden", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  goldenDelete: (id: string) =>
    api<any>(`/api/admin/eval/golden/${id}`, { method: "DELETE" }),
  evalRuns: () => api<any[]>("/api/admin/eval/runs"),
  evalRun: (id: string) => api<any>(`/api/admin/eval/runs/${id}`),
  evalStart: (data: any) =>
    api<any>("/api/admin/eval/run", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};