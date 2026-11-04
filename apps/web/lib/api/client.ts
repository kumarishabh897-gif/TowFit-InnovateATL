import createClient from "openapi-fetch";
import type { paths } from "./schema";

// "same-origin" means the API is served from the same host as the page (the Vercel deployment).
const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
export const API_BASE_URL = configured === "same-origin" ? "" : (configured ?? "http://localhost:8000");

export const api = createClient<paths>({ baseUrl: API_BASE_URL });

/** Thrown for any non-2xx response or a network failure, with a message an operator can act on. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Unwraps an openapi-fetch result, turning FastAPI's `{detail}` bodies into readable errors. */
export function unwrap<T>(result: Result<T>): T {
  if (result.data !== undefined) return result.data;
  const detail = (result.error as { detail?: unknown } | undefined)?.detail;
  let message = `Request failed (${result.response.status})`;
  if (typeof detail === "string") message = detail;
  else if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    message = `${first.loc?.slice(1).join(".") ?? "input"}: ${first.msg ?? "invalid"}`;
  }
  throw new ApiError(message, result.response.status);
}

export function imageUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
