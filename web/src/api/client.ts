import type { ApiErrorBody } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiClientError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error || `HTTP ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, init);
  if (!response.ok) {
    const text = await response.text();
    let body: ApiErrorBody;
    try {
      body = text
        ? (JSON.parse(text) as ApiErrorBody)
        : { error: `HTTP ${response.status}` };
    } catch {
      body = { error: text || `HTTP ${response.status}` };
    }
    throw new ApiClientError(response.status, body);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return response as unknown as T;
  }
  return parseJson<T>(response);
}

export function pageRenderUrl(
  documentId: string,
  pageNumber: number,
  options?: { dpi?: number; pdfPath?: string | null },
): string {
  const params = new URLSearchParams();
  if (options?.dpi) {
    params.set("dpi", String(options.dpi));
  }
  if (options?.pdfPath) {
    params.set("pdf_path", options.pdfPath);
  }
  const query = params.toString();
  const base = `${API_BASE}/documents/${documentId}/pages/${pageNumber}/render`;
  return query ? `${base}?${query}` : base;
}
