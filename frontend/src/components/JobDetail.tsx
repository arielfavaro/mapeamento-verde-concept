import { urls } from "../api/client";
import type { Job, SpectralIndex } from "../api/types";
import { formatBytes, formatDate, formatNumber, formatPct } from "../lib/format";
import { Histogram } from "./Histogram";

type Props = {
  job: Job;
  indices: SpectralIndex[];
  activeLayerId: string | null;
  opacity: number;
  deleting: boolean;
  onLayerChange: (id: string) => void;
  onOpacityChange: (v: number) => void;
  onDelete: () => void;
};

export function JobDetail({ job, indices, activeLayerId, opacity, deleting, ...handlers }: Props) {
  const { result } = job;
  const active = job.state === "queued" || job.state === "running";
  const index = indices.find((i) => i.id === activeLayerId);
  const stats = activeLayerId ? result?.stats[activeLayerId] : undefined;

  return (
    <div className="job-detail">
      <div className="row space-between">
        <h3>
          {job.request.aoi_name} · {formatDate(job.request.start)} → {formatDate(job.request.end)}
        </h3>
        {!active && (
          <button type="button" className="danger small" onClick={handlers.onDelete} disabled={deleting}>
            Excluir
          </button>
        )}
      </div>

      {active && (
        <div className="status-box">
          <progress value={job.progress} max={1} />
          <span>{job.message}</span>
        </div>
      )}
      {job.state === "failed" && <p className="error-box">{job.error}</p>}

      {result && (
        <>
          <section>
            <h4>Resumo</h4>
            <dl className="facts">
              <dt>Janela usada</dt>
              <dd>
                {formatDate(result.window_start)} → {formatDate(result.window_end)}
              </dd>
              <dt>Datas usadas</dt>
              <dd>{result.acquisitions.length}</dd>
              <dt>Cobertura</dt>
              <dd>{formatPct(result.coverage, 1)} da área com observação válida</dd>
              <dt>Grade</dt>
              <dd>
                {result.crs}, {result.resolution_m} m ({result.width} × {result.height} px)
              </dd>
            </dl>
            {result.warnings.map((w) => (
              <p key={w} className="warning-box">
                {w}
              </p>
            ))}
            {result.window_attempts.length > 1 && (
              <details>
                <summary>Como a janela foi escolhida</summary>
                <table className="table compact">
                  <thead>
                    <tr>
                      <th>Janela</th>
                      <th>Cenas</th>
                      <th>Cobertura estimada</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.window_attempts.map((a) => (
                      <tr key={a.start}>
                        <td>
                          {formatDate(a.start)} → {formatDate(a.end)}
                        </td>
                        <td>{a.scenes}</td>
                        <td>{formatPct(a.coverage, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </section>

          <section>
            <h4>Camadas no mapa</h4>
            <div className="layer-list" role="radiogroup">
              {result.layers.map((layer) => (
                <label key={layer.id} className={`chip ${layer.id === activeLayerId ? "active" : ""}`}>
                  <input
                    type="radio"
                    name="layer"
                    checked={layer.id === activeLayerId}
                    onChange={() => handlers.onLayerChange(layer.id)}
                  />
                  {layer.name}
                </label>
              ))}
            </div>
            <label className="field">
              <span>Opacidade: {Math.round(opacity * 100)}%</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={opacity}
                onChange={(e) => handlers.onOpacityChange(Number(e.target.value))}
              />
            </label>
          </section>

          {index && stats && (
            <section>
              <h4>
                {index.name}: {index.formula}
              </h4>
              <p className="small">{index.description}</p>
              <dl className="facts">
                <dt>Média ± desvio</dt>
                <dd>
                  {formatNumber(stats.mean)} ± {formatNumber(stats.std)}
                </dd>
                <dt>Mediana (p25–p75)</dt>
                <dd>
                  {formatNumber(stats.percentiles.p50)} ({formatNumber(stats.percentiles.p25)} –{" "}
                  {formatNumber(stats.percentiles.p75)})
                </dd>
              </dl>
              <Histogram stats={stats} colors={index.colors} />
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Faixa</th>
                    <th>Interpretação</th>
                    <th>Área</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.classes.map((c) => (
                    <tr key={c.label}>
                      <td className="nowrap">
                        {formatNumber(c.min, 2)} a {formatNumber(c.max, 2)}
                      </td>
                      <td>{c.label}</td>
                      <td className="nowrap">
                        {formatNumber(c.area_km2, 2)} km² ({formatPct(c.fraction, 1)})
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section>
            <h4>Downloads</h4>
            <a className="button primary" href={urls.archive(job.id)}>
              Baixar tudo (.zip)
            </a>
            <ul className="file-list">
              {result.files.map((f) => (
                <li key={f.name}>
                  <a href={urls.file(job.id, f.name)} download>
                    {f.name}
                  </a>
                  <span className="muted small">
                    {f.description} · {formatBytes(f.size_bytes)}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <details>
              <summary>Datas usadas ({result.acquisitions.length})</summary>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Plataforma</th>
                    <th>Cenas</th>
                    <th>Área limpa</th>
                  </tr>
                </thead>
                <tbody>
                  {result.acquisitions.map((a) => (
                    <tr key={`${a.date}-${a.scene_ids[0]}`}>
                      <td>{formatDate(a.date)}</td>
                      <td>{a.platforms.join(", ")}</td>
                      <td title={a.scene_ids.join("\n")}>{a.scene_ids.length}</td>
                      <td>{formatPct(a.valid_fraction)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </section>
        </>
      )}

      {job.log.length > 0 && (
        <details>
          <summary>Log</summary>
          <pre className="log">{job.log.join("\n")}</pre>
        </details>
      )}
    </div>
  );
}
