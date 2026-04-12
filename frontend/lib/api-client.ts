import type { Job, JobOverallStatus, JobStepKey, StepState } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const AUTH_TOKEN_KEY = "shotcut_ai_auth_token_v1";

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export type CreateJobResponse = {
  jobId: string;
};

/** FastAPI/Pydantic JSON uses snake_case for top-level job fields. */
interface JobApiPayload {
  job_id: string;
  created_at: string;
  overall_status: JobOverallStatus;
  steps: Record<JobStepKey, StepState>;
  outputs?: Record<string, unknown>;
}

function mapJobPayload(data: JobApiPayload): Job {
  return {
    id: data.job_id,
    createdAt: data.created_at,
    overallStatus: data.overall_status,
    steps: data.steps,
    outputs: data.outputs as Job["outputs"] | undefined,
  };
}

/** Use when logging `unknown` / Error inside plain objects (avoids `[object Error]`). */
export function serializeUnknownError(e: unknown): {
  errorMessage: string;
  errorName?: string;
  errorStack?: string;
} {
  if (e instanceof Error) {
    return {
      errorMessage: e.message,
      errorName: e.name,
      errorStack: e.stack,
    };
  }
  return { errorMessage: String(e) };
}

/** True when the API returned 404 for this job (e.g. server restarted; jobs are in-memory). */
export function isJobNotFoundError(e: unknown): boolean {
  const m = serializeUnknownError(e).errorMessage;
  return (
    m.includes("404") &&
    (m.includes("Job not found") || m.includes('"detail":"Job not found"'))
  );
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Request failed (${res.status}): ${text || res.statusText}`,
    );
  }
  return (text ? JSON.parse(text) : ({} as T)) as T;
}

let authTokenCache: string | null | undefined = undefined;
let authTokenPromise: Promise<string | null> | null = null;

async function ensureAuthToken(): Promise<string | null> {
  if (authTokenCache !== undefined) return authTokenCache;
  if (authTokenPromise) return authTokenPromise;

  authTokenPromise = (async () => {
    if (typeof window === "undefined") return null;

    const existing = window.localStorage.getItem(AUTH_TOKEN_KEY);
    if (existing) {
      authTokenCache = existing;
      return existing;
    }

    const res = await fetch(`${API_BASE_URL}/auth/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await parseJson<{ token: string }>(res);
    window.localStorage.setItem(AUTH_TOKEN_KEY, data.token);
    authTokenCache = data.token;
    return data.token;
  })();

  try {
    return await authTokenPromise;
  } finally {
    authTokenPromise = null;
  }
}

async function authedFetch(
  url: string,
  init: RequestInit,
): Promise<Response> {
  const token = await ensureAuthToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...init, headers });
}

export async function createJob(): Promise<CreateJobResponse> {
  const res = await authedFetch(`${API_BASE_URL}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await parseJson<{ job_id: string }>(res);
  return { jobId: data.job_id };
}

export async function uploadVideo(jobId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);

  const res = await authedFetch(`${API_BASE_URL}/jobs/${jobId}/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }
}

export async function getJobStatus(jobId: string): Promise<Job> {
  const url = `${API_BASE_URL}/jobs/${jobId}`;
  const res = await authedFetch(url, { method: "GET" });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Request failed (${res.status} ${res.statusText}): ${text.slice(0, 500) || "(empty body)"}`,
    );
  }
  let data: JobApiPayload;
  try {
    data = (text ? JSON.parse(text) : {}) as JobApiPayload;
  } catch (parseErr) {
    const hint =
      parseErr instanceof Error ? parseErr.message : String(parseErr);
    throw new Error(
      `Invalid JSON from GET /jobs/${jobId}: ${hint}; body preview: ${text.slice(0, 240)}`,
    );
  }
  return mapJobPayload(data);
}

/**
 * Load a job-scoped media URL with Bearer auth and return a `blob:` URL for `<video src>`.
 * Browser media elements do not send `Authorization`; without this, `/jobs/.../rough-cut` 404s.
 */
export async function fetchAuthenticatedMediaObjectUrl(
  mediaPathOrUrl: string,
  options?: { cacheBust?: string | number },
): Promise<string> {
  let absolute =
    mediaPathOrUrl.startsWith("http://") ||
    mediaPathOrUrl.startsWith("https://")
      ? mediaPathOrUrl
      : `${API_BASE_URL}${
          mediaPathOrUrl.startsWith("/") ? "" : "/"
        }${mediaPathOrUrl}`;

  if (options?.cacheBust != null && String(options.cacheBust) !== "") {
    const sep = absolute.includes("?") ? "&" : "?";
    absolute = `${absolute}${sep}v=${encodeURIComponent(String(options.cacheBust))}`;
  }

  const res = await authedFetch(absolute, { method: "GET" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `Media fetch failed (${res.status}): ${text.slice(0, 400) || res.statusText}`,
    );
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

