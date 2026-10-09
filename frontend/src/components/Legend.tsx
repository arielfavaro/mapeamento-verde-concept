import type { Layer, SpectralIndex } from "../api/types";
import { gradientCss } from "../lib/colors";
import { formatNumber } from "../lib/format";

type Props = {
  layer: Layer;
  index: SpectralIndex | undefined;
  colors: string[] | undefined;
};

export function Legend({ layer, index, colors }: Props) {
  if (layer.kind === "composite") {
    return (
      <div className="legend">
        <strong>{layer.name}</strong>
        <span className="muted small">
          Reflectância {layer.vmin}–{layer.vmax} esticada em cada canal
        </span>
      </div>
    );
  }
  return (
    <div className="legend">
      <strong>
        {layer.name}
        {layer.unit && ` (${layer.unit})`}
      </strong>
      {colors && <div className="gradient" style={{ background: gradientCss(colors) }} />}
      <div className="gradient-labels">
        <span>{formatNumber(layer.vmin, 2)}</span>
        <span>{formatNumber((layer.vmin + layer.vmax) / 2, 2)}</span>
        <span>{formatNumber(layer.vmax, 2)}</span>
      </div>
      {layer.kind === "count" && <span className="muted small">Transparente = nenhuma observação válida</span>}
      {index && <span className="muted small">{index.formula}</span>}
    </div>
  );
}
