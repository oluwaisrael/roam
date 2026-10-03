import type { SearchResponse } from "./types";

export async function searchApi(path: string, body: unknown, signal: AbortSignal): Promise<SearchResponse> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ""}/api/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error("This search has expired. Start a new search to continue.");
    throw new Error("Roam couldn't complete your search. Please try again.");
  }
  return response.json();
}
