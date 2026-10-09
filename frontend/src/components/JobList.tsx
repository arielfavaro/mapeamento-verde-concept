import type { JobSummary, Sensor } from "../api/types";
import { formatDate } from "../lib/format";

const STATE_LABEL: Record<JobSummary["state"], string> = {
  queued: "Na fila",
  running: "Processando",
  succeeded: "Concluído",
  failed: "Falhou",
};

type Props = {
  jobs: JobSummary[];
  sensors: Sensor[];
  activeId: string | null;
  onSelect: (id: string) => void;
};

export function JobList({ jobs, sensors, activeId, onSelect }: Props) {
  if (jobs.length === 0) {
    return <p className="muted">Nenhum processamento ainda. Configure e envie um na aba “Processar”.</p>;
  }
  const sensorName = (id: string) => sensors.find((s) => s.id === id)?.name.split(" (")[0] ?? id;
  return (
    <ul className="job-list">
      {jobs.map((job) => (
        <li key={job.id}>
          <button
            type="button"
            className={`job-item ${job.id === activeId ? "selected" : ""}`}
            onClick={() => onSelect(job.id)}
          >
            <span className="job-title">
              {job.request.aoi_name} · {sensorName(job.request.sensor)}
            </span>
            <span className="muted small">
              {formatDate(job.request.start)} → {formatDate(job.request.end)}
            </span>
            <span className={`state ${job.state}`}>
              {STATE_LABEL[job.state]}
              {job.state === "running" && ` ${Math.round(job.progress * 100)}%`}
            </span>
            {job.state === "running" && <progress value={job.progress} max={1} />}
          </button>
        </li>
      ))}
    </ul>
  );
}
