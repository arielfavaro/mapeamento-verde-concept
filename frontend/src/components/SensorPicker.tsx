import type { Sensor } from "../api/types";

type Props = {
  sensors: Sensor[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export function SensorPicker({ sensors, selectedId, onSelect }: Props) {
  const selected = sensors.find((s) => s.id === selectedId);
  return (
    <div>
      <div className="sensor-grid" role="radiogroup" aria-label="Satélite">
        {sensors.map((s) => (
          <button
            key={s.id}
            type="button"
            role="radio"
            aria-checked={s.id === selectedId}
            className={`sensor-card ${s.id === selectedId ? "selected" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <span className="sensor-name">{s.name}</span>
            <span className="sensor-meta">
              <span className={`badge ${s.kind}`}>{s.kind === "radar" ? "Radar" : "Óptico"}</span>
              {s.resolution_m} m
            </span>
          </button>
        ))}
      </div>
      {selected && <SensorDetails sensor={selected} />}
    </div>
  );
}

export function SensorDetails({ sensor, open = false }: { sensor: Sensor; open?: boolean }) {
  const { info } = sensor;
  return (
    <div className="sensor-details">
      <p>{info.summary}</p>
      <dl className="facts">
        <dt>Missão</dt>
        <dd>{info.mission}</dd>
        <dt>Revisita</dt>
        <dd>{sensor.revisit}</dd>
        <dt>Em órbita desde</dt>
        <dd>{sensor.since}</dd>
        <dt>Índices</dt>
        <dd>{sensor.indices.join(", ")}</dd>
      </dl>
      <details open={open}>
        <summary>Como funciona, pontos fortes e limitações</summary>
        <h4>Como funciona</h4>
        <p>{info.how_it_works}</p>
        <h4>Como processamos</h4>
        <p>{info.processing}</p>
        <div className="pros-cons">
          <div>
            <h4>Pontos fortes</h4>
            <ul className="pros">
              {info.strengths.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4>Limitações</h4>
            <ul className="cons">
              {info.limitations.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        </div>
        <h4>Indicado para</h4>
        <div className="chips">
          {info.best_for.map((t) => (
            <span key={t} className="chip static">
              {t}
            </span>
          ))}
        </div>
        <h4>Bandas usadas</h4>
        <table className="table compact">
          <thead>
            <tr>
              <th>Banda</th>
              <th>Comprimento de onda</th>
              <th>Resolução</th>
            </tr>
          </thead>
          <tbody>
            {sensor.bands.map((b) => (
              <tr key={b.common}>
                <td>{b.label}</td>
                <td>{b.wavelength}</td>
                <td>{b.resolution_m} m</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted small">Coleções STAC: {sensor.collections.join(", ")}</p>
      </details>
    </div>
  );
}
