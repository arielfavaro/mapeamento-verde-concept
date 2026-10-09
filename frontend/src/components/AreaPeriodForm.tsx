import type { AoiPreset, BBox } from "../api/types";
import { daysBetween, monthRange, seasonPresets } from "../lib/format";
import { bboxAreaKm2, bboxFromTuple, isValidBBox } from "../lib/geo";

type Props = {
  presets: AoiPreset[];
  maxAreaKm2: number;
  aoi: BBox;
  aoiName: string;
  start: string;
  end: string;
  drawing: boolean;
  onAoiChange: (aoi: BBox, name?: string) => void;
  onAoiNameChange: (name: string) => void;
  onPeriodChange: (start: string, end: string) => void;
  onToggleDrawing: () => void;
  onUseVisibleExtent: () => void;
};

const FIELDS: { key: keyof BBox; label: string }[] = [
  { key: "west", label: "Oeste" },
  { key: "east", label: "Leste" },
  { key: "south", label: "Sul" },
  { key: "north", label: "Norte" },
];

export function AreaPeriodForm(props: Props) {
  const { aoi, start, end } = props;
  const area = isValidBBox(aoi) ? bboxAreaKm2(aoi) : NaN;
  const today = new Date();
  const lastMonth = monthRange(
    today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear(),
    today.getMonth() === 0 ? 12 : today.getMonth(),
  );
  const quick = [
    { label: "Mês passado", hint: "janela base de 30 dias", ...lastMonth },
    ...seasonPresets(today.getFullYear() - 1),
  ];

  return (
    <div className="form-grid">
      <label className="field">
        <span>Área pronta</span>
        <select
          value=""
          onChange={(e) => {
            const p = props.presets.find((x) => x.id === e.target.value);
            if (p) props.onAoiChange(bboxFromTuple(p.bbox), p.name);
          }}
        >
          <option value="">Escolher…</option>
          {props.presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.area_km2} km²)
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Nome da área (usado nos arquivos)</span>
        <input value={props.aoiName} maxLength={60} onChange={(e) => props.onAoiNameChange(e.target.value)} />
      </label>

      <div className="bbox-inputs">
        {FIELDS.map((f) => (
          <label key={f.key} className="field">
            <span>{f.label}</span>
            <input
              type="number"
              step="0.0001"
              value={aoi[f.key]}
              onChange={(e) => props.onAoiChange({ ...aoi, [f.key]: Number(e.target.value) })}
            />
          </label>
        ))}
      </div>
      <div className="row">
        <button type="button" className={props.drawing ? "primary" : ""} onClick={props.onToggleDrawing}>
          {props.drawing ? "Arraste no mapa…" : "Desenhar retângulo"}
        </button>
        <button type="button" onClick={props.onUseVisibleExtent}>
          Usar área visível
        </button>
        <span className={`muted small ${area > props.maxAreaKm2 ? "error-text" : ""}`}>
          {Number.isFinite(area) ? `${area.toFixed(0)} km²` : "bbox inválido"}
          {area > props.maxAreaKm2 && ` (máx. ${props.maxAreaKm2})`}
        </span>
      </div>

      <div className="row">
        <label className="field">
          <span>Início</span>
          <input type="date" value={start} max={end} onChange={(e) => props.onPeriodChange(e.target.value, end)} />
        </label>
        <label className="field">
          <span>Fim</span>
          <input type="date" value={end} min={start} onChange={(e) => props.onPeriodChange(start, e.target.value)} />
        </label>
        <span className="muted small">{daysBetween(start, end)} dias</span>
      </div>
      <div className="chips">
        {quick.map((q) => (
          <button
            key={q.label}
            type="button"
            className={`chip ${q.start === start && q.end === end ? "active" : ""}`}
            title={q.hint}
            onClick={() => props.onPeriodChange(q.start, q.end)}
          >
            {q.label}
          </button>
        ))}
      </div>
    </div>
  );
}
