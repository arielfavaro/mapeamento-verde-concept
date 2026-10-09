import type { CompositeMethod, Sensor, SpectralIndex } from "../api/types";

export type ProcessOptions = {
  method: CompositeMethod;
  adaptiveWindow: boolean;
  targetCoverage: number;
  maxWindowDays: number;
  cloudBufferPx: number;
  indices: string[];
  resolutionM: number;
  onlySelected: boolean;
};

type Props = {
  sensor: Sensor;
  indices: SpectralIndex[];
  options: ProcessOptions;
  selectedDates: number;
  submitting: boolean;
  error: string | null;
  onChange: (patch: Partial<ProcessOptions>) => void;
  onSubmit: () => void;
};

export function ProcessForm({ sensor, indices, options, selectedDates, submitting, error, onChange, onSubmit }: Props) {
  const manual = options.onlySelected && selectedDates > 0;
  const available = indices.filter((i) => sensor.indices.includes(i.id));

  const toggleIndex = (id: string) =>
    onChange({
      indices: options.indices.includes(id) ? options.indices.filter((x) => x !== id) : [...options.indices, id],
    });

  return (
    <form
      className="form-grid"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <fieldset>
        <legend>Composição</legend>
        <label className="check">
          <input
            type="radio"
            name="method"
            checked={options.method === "median"}
            onChange={() => onChange({ method: "median" })}
          />
          <span>
            <strong>Mediana</strong>: para cada pixel, a mediana das observações sem nuvem. Remove nuvens
            residuais e ruído. Indicada para retratar o período.
          </span>
        </label>
        <label className="check">
          <input
            type="radio"
            name="method"
            checked={options.method === "best_date"}
            onChange={() => onChange({ method: "best_date" })}
          />
          <span>
            <strong>Melhor data</strong>: usa só o dia com a maior área limpa. Preserva eventos pontuais (colheita,
            queimada) que a mediana apaga. Indicada para ΔNBR e antes/depois.
          </span>
        </label>
      </fieldset>

      {selectedDates > 0 && (
        <label className="check">
          <input type="checkbox" checked={options.onlySelected} onChange={(e) => onChange({ onlySelected: e.target.checked })} />
          Usar só as {selectedDates} data(s) selecionada(s)
        </label>
      )}

      <fieldset disabled={manual}>
        <legend>Janela adaptativa</legend>
        <label className="check">
          <input
            type="checkbox"
            checked={options.adaptiveWindow}
            onChange={(e) => onChange({ adaptiveWindow: e.target.checked })}
          />
          <span>
            Ampliar o período (±15 dias por vez) até que a área tenha observação válida. Evita buracos nos meses
            chuvosos.
          </span>
        </label>
        <div className="row">
          <label className="field">
            <span>Cobertura alvo</span>
            <select
              value={options.targetCoverage}
              disabled={!options.adaptiveWindow}
              onChange={(e) => onChange({ targetCoverage: Number(e.target.value) })}
            >
              {[0.9, 0.95, 0.98, 0.995].map((v) => (
                <option key={v} value={v}>
                  {(v * 100).toFixed(1).replace(".0", "")}%
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Janela máxima (dias)</span>
            <input
              type="number"
              min={30}
              max={366}
              step={15}
              value={options.maxWindowDays}
              disabled={!options.adaptiveWindow}
              onChange={(e) => onChange({ maxWindowDays: Number(e.target.value) })}
            />
          </label>
        </div>
      </fieldset>

      <div className="row">
        {sensor.cloud_filterable && (
          <label className="field" title="Pixels ao redor de nuvens também são descartados (bordas mal classificadas)">
            <span>Margem de nuvem (pixels)</span>
            <input
              type="number"
              min={0}
              max={10}
              value={options.cloudBufferPx}
              onChange={(e) => onChange({ cloudBufferPx: Number(e.target.value) })}
            />
          </label>
        )}
        <label className="field">
          <span>Resolução (m)</span>
          <input
            type="number"
            min={sensor.resolution_m}
            max={1000}
            step={sensor.resolution_m}
            value={options.resolutionM}
            onChange={(e) => onChange({ resolutionM: Number(e.target.value) })}
          />
        </label>
      </div>

      <fieldset>
        <legend>Índices</legend>
        <div className="chips">
          {available.map((i) => (
            <label key={i.id} className={`chip ${options.indices.includes(i.id) ? "active" : ""}`} title={i.description}>
              <input type="checkbox" checked={options.indices.includes(i.id)} onChange={() => toggleIndex(i.id)} />
              {i.name}
            </label>
          ))}
        </div>
      </fieldset>

      <button type="submit" className="primary" disabled={submitting || options.indices.length === 0}>
        {submitting ? "Enviando…" : "Baixar e processar"}
      </button>
      {error && <p className="error-text">{error}</p>}
    </form>
  );
}
