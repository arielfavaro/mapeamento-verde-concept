import type { SceneSearchResponse, Sensor } from "../api/types";
import { formatDate, formatPct, shortPlatform } from "../lib/format";

type Props = {
  sensor: Sensor;
  maxSceneCloud: number;
  estimateAoiCloud: boolean;
  result: SceneSearchResponse | undefined;
  loading: boolean;
  error: string | null;
  selected: ReadonlySet<string>;
  onMaxSceneCloudChange: (v: number) => void;
  onEstimateChange: (v: boolean) => void;
  onSearch: () => void;
  onToggleDate: (date: string) => void;
  onSelectDates: (dates: string[]) => void;
  onHoverDate: (date: string | null) => void;
};

const CLEAN_THRESHOLD = 0.9;

export function SceneSearch(props: Props) {
  const { sensor, result } = props;
  const cleanDates = result?.dates.filter((d) => (d.aoi_valid_fraction ?? 0) >= CLEAN_THRESHOLD).map((d) => d.date);

  return (
    <div className="form-grid">
      {sensor.cloud_filterable ? (
        <>
          <label className="field">
            <span>
              Nuvem máxima por cena: <strong>{props.maxSceneCloud}%</strong>
            </span>
            <input
              type="range"
              min={5}
              max={100}
              step={5}
              value={props.maxSceneCloud}
              onChange={(e) => props.onMaxSceneCloudChange(Number(e.target.value))}
            />
            <small className="muted">
              Filtro frouxo de propósito: a nuvem é removida pixel a pixel. Uma cena com 60% de nuvem no tile
              pode estar limpa justamente sobre a sua área.
            </small>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={props.estimateAoiCloud}
              onChange={(e) => props.onEstimateChange(e.target.checked)}
            />
            Medir a fração limpa <em>dentro da área</em> (lê a máscara de cada cena, mais lento)
          </label>
        </>
      ) : (
        <p className="muted small">Radar não é afetado por nuvens: todas as passagens são úteis.</p>
      )}

      <button type="button" className="primary" onClick={props.onSearch} disabled={props.loading}>
        {props.loading ? "Buscando…" : "Buscar cenas"}
      </button>
      {props.error && <p className="error-text">{props.error}</p>}

      {result && (
        <div>
          <p className="small">
            <strong>{result.total_scenes}</strong> cenas em <strong>{result.dates.length}</strong> datas.
            {result.dates.length > 0 && " Marque datas para processar só elas, ou deixe em branco para usar todas."}
          </p>
          {cleanDates && cleanDates.length > 0 && (
            <button type="button" className="link" onClick={() => props.onSelectDates(cleanDates)}>
              Selecionar as {cleanDates.length} datas com ≥ {formatPct(CLEAN_THRESHOLD)} da área limpa
            </button>
          )}
          {props.selected.size > 0 && (
            <button type="button" className="link" onClick={() => props.onSelectDates([])}>
              Limpar seleção ({props.selected.size})
            </button>
          )}
          <div className="table-scroll">
            <table className="table compact">
              <thead>
                <tr>
                  <th />
                  <th>Data</th>
                  <th>Satélite</th>
                  {sensor.cloud_filterable && <th title="Maior nuvem entre os tiles do dia">Nuvem tile</th>}
                  {sensor.cloud_filterable && <th title="Fração da área sem nuvem/sombra">Área limpa</th>}
                  <th />
                </tr>
              </thead>
              <tbody>
                {result.dates.map((d) => (
                  <tr
                    key={d.date}
                    className={props.selected.has(d.date) ? "selected" : ""}
                    onMouseEnter={() => props.onHoverDate(d.date)}
                    onMouseLeave={() => props.onHoverDate(null)}
                  >
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Selecionar ${formatDate(d.date)}`}
                        checked={props.selected.has(d.date)}
                        onChange={() => props.onToggleDate(d.date)}
                      />
                    </td>
                    <td title={`${d.scenes.length} cena(s): ${d.scenes.map((s) => s.tile).join(", ")}`}>
                      {formatDate(d.date)}
                    </td>
                    <td>{[...new Set(d.scenes.map((s) => shortPlatform(s.platform)))].join(", ")}</td>
                    {sensor.cloud_filterable && (
                      <td>{d.scene_cloud_max == null ? "—" : `${d.scene_cloud_max.toFixed(0)}%`}</td>
                    )}
                    {sensor.cloud_filterable && (
                      <td>
                        <CleanBar fraction={d.aoi_valid_fraction} />
                      </td>
                    )}
                    <td>
                      {d.scenes[0]?.preview_url && (
                        <a href={d.scenes[0].preview_url} target="_blank" rel="noreferrer" title="Prévia da cena">
                          ver
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function CleanBar({ fraction }: { fraction: number | null }) {
  if (fraction == null) return <span className="muted">—</span>;
  return (
    <span className="clean" title={formatPct(fraction, 1)}>
      <span className="clean-bar">
        <span style={{ width: `${fraction * 100}%` }} />
      </span>
      {formatPct(fraction)}
    </span>
  );
}
