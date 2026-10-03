export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const body = text ? safeJson(text) : null;
  if (!response.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, `${response.status} ${detail}`, body);
  }
  return body;
}

function queryString(params) {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return entries.length ? `?${new URLSearchParams(entries).toString()}` : "";
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  systemStatus: () => request("/system/status"),
  runQuery: (payload) => post("/query", payload),
  listQueries: (limit = 20, experimentRun) =>
    request(`/query${queryString({ limit, experiment_run: experimentRun })}`),
  getQuery: (id) => request(`/query/${id}`),
  retrieve: (payload) => post("/retrieve", payload),
  paper: (id, includeChunks = false) => request(`/papers/${id}${queryString({ include_chunks: includeChunks })}`),
  sendFeedback: (feedback) => post("/feedback", feedback),
  metrics: (experimentRun) => request(`/metrics${queryString({ experiment_run: experimentRun })}`),
  improvementHistory: (experimentRun, limit = 500) =>
    request(`/improvement/history${queryString({ experiment_run: experimentRun, limit })}`),
  experiments: () => request("/experiments"),
  experimentCycles: (run) => request(`/experiments/${encodeURIComponent(run)}/cycles`),
};
