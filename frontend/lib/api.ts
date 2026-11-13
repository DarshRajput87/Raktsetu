/** Typed fetch wrapper for the RaktSetu API, with JWT handling. */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "raktsetu.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode): the session lasts until reload */
  }
}

type Params = Record<string, string | number | boolean | undefined | null>;

interface Options {
  method?: "GET" | "POST" | "PATCH";
  params?: Params;
  body?: unknown;
  signal?: AbortSignal;
}

export async function api<T>(path: string, { method = "GET", params, body, signal }: Options = {}): Promise<T> {
  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
  }
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(url, { method, headers, signal, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network", "Cannot reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    let code = "error";
    let message = `Something went wrong (${response.status}).`;
    try {
      const data = await response.json();
      code = data.error?.code ?? code;
      message = data.error?.message ?? message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}
