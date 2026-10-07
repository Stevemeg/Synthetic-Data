import axios from "axios";

export const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || "http://127.0.0.1:5000").replace(
    /\/$/,
    "",
  ),
  timeout: 30000,
  withCredentials: true,
});
let currentOrganization: string | null = null;
let csrfToken: string | null = null;
export function configureIdentity(organization: string | null, csrf: string | null) {
  currentOrganization = organization;
  csrfToken = csrf;
}
api.interceptors.request.use((request) => {
  if (currentOrganization) request.headers.set("X-Organization-ID", currentOrganization);
  if (csrfToken && request.method !== "get") request.headers.set("X-CSRF-Token", csrfToken);
  return request;
});
api.interceptors.response.use((response) => {
  const organization = response.config.headers.get("X-Organization-ID");
  if (organization && organization !== currentOrganization) throw new axios.CanceledError("Organization changed");
  return response;
}, (error: unknown) => {
  if (axios.isAxiosError(error) && error.response?.status === 401 && !error.config?.url?.endsWith("/auth/me")) {
    window.dispatchEvent(new Event("medsynth-session-expired"));
  }
  return Promise.reject(error);
});
export function errorMessage(error: unknown): string {
  if (
    axios.isAxiosError<{
      error?: { code: string; message: string; request_id: string };
    }>(error)
  ) {
    const detail = error.response?.data?.error;
    const category =
      error.response?.status === 422
        ? "Validation problem"
        : error.response?.status === 403
          ? "Security restriction"
          : detail?.code.includes("INTEGRITY")
            ? "Artifact integrity error"
            : error.response?.status === 404
              ? "Resource not found"
              : "Operation unavailable";
    return detail
      ? `${category}: ${detail.message} · Request ${detail.request_id}`
      : "Platform unavailable. Check the API connection and retry.";
  }
  return error instanceof Error
    ? error.message
    : "The operation could not be completed.";
}
export async function downloadArtifact(id: string, filename: string) {
  const response = await api
    .get<Blob>(`/api/v1/artifacts/${id}/download`, { responseType: "blob" })
    .catch(async (error: unknown) => {
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        try {
          error.response.data = JSON.parse(await error.response.data.text());
        } catch {
          /* Transport fallback. */
        }
      }
      throw error;
    });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.replace(/[^A-Za-z0-9._-]/g, "_");
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
