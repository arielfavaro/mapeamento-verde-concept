import type {
  AoiPreset,
  AppConfig,
  Colormap,
  Job,
  JobRequest,
  JobSummary,
  SceneSearchRequest,
  SceneSearchResponse,
  Sensor,
  SpectralIndex,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ValidationDetail = { loc?: (string | number)[]; msg: string };

/** Converte o `detail` do FastAPI (texto ou lista de erros de validação) em mensagem legível. */
export function formatErrorDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationDetail[])
      .map((d) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return "Erro desconhecido";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      message = formatErrorDetail(body.detail);
    } catch {
      // corpo não-JSON: mantém o status HTTP como mensagem
    }
    throw new ApiError(message, res.status);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  config: () => request<AppConfig>("/config"),
  colormap: (name: string) => request<Colormap>(`/colormaps/${name}`),
  sensors: () => request<Sensor[]>("/sensors"),
  indices: () => request<SpectralIndex[]>("/indices"),
  presets: () => request<AoiPreset[]>("/aoi-presets"),
  searchScenes: (body: SceneSearchRequest) =>
    request<SceneSearchResponse>("/scenes/search", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<JobSummary[]>("/jobs"),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  createJob: (body: JobRequest) => request<Job>("/jobs", { method: "POST", body: JSON.stringify(body) }),
  deleteJob: (id: string) => request<void>(`/jobs/${id}`, { method: "DELETE" }),
};

export const urls = {
  tile: (jobId: string, layerId: string) => `/api/jobs/${jobId}/tiles/${layerId}/{z}/{x}/{y}.png`,
  file: (jobId: string, name: string) => `/api/jobs/${jobId}/files/${encodeURIComponent(name)}`,
  archive: (jobId: string) => `/api/jobs/${jobId}/archive.zip`,
};
