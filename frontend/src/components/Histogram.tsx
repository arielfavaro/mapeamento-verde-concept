import type { IndexStats } from "../api/types";
import { colorAt } from "../lib/colors";
import { formatNumber } from "../lib/format";

type Props = { stats: IndexStats; colors: string[] };

const W = 360;
const H = 90;

export function Histogram({ stats, colors }: Props) {
  const max = Math.max(1, ...stats.histogram);
  const n = stats.histogram.length;
  const barW = W / n;
  const first = stats.histogram_edges[0] ?? 0;
  const last = stats.histogram_edges[n] ?? 1;
  return (
    <figure className="histogram">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Histograma dos valores do índice">
        {stats.histogram.map((count, i) => {
          const h = (count / max) * (H - 4);
          return (
            <rect
              key={i}
              x={i * barW + 0.5}
              y={H - h}
              width={barW - 1}
              height={h}
              fill={colorAt(colors, (i + 0.5) / n)}
            >
              <title>
                {formatNumber(stats.histogram_edges[i], 2)} a {formatNumber(stats.histogram_edges[i + 1], 2)}:{" "}
                {count.toLocaleString("pt-BR")} pixels
              </title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="gradient-labels">
        <span>≤ {formatNumber(first, 2)}</span>
        <span>≥ {formatNumber(last, 2)}</span>
      </figcaption>
    </figure>
  );
}
