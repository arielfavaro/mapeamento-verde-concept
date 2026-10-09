import type { Sensor, SpectralIndex } from "../api/types";
import { colorAt, gradientCss } from "../lib/colors";
import { formatNumber } from "../lib/format";
import { SensorDetails } from "./SensorPicker";

type Props = { sensors: Sensor[]; indices: SpectralIndex[] };

export function Guide({ sensors, indices }: Props) {
  const categories = [...new Set(indices.map((i) => i.category))];
  return (
    <div className="guide">
      <section>
        <h3>Qual satélite usar?</h3>
        <table className="table compact">
          <thead>
            <tr>
              <th>Satélite</th>
              <th>Resolução</th>
              <th>Revisita</th>
              <th>Nuvem</th>
            </tr>
          </thead>
          <tbody>
            {sensors.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.resolution_m} m</td>
                <td>{s.revisit.split(";")[0]}</td>
                <td>{s.kind === "radar" ? "Atravessa" : "Bloqueia"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="small">
          Regra prática: <strong>Sentinel-2</strong> como padrão; <strong>HLS</strong> quando faltar imagem limpa
          (dezembro a fevereiro); <strong>Landsat</strong> para comparar vários anos; <strong>Sentinel-1</strong> para
          água e para acompanhar a vegetação sob nuvem.
        </p>
        {sensors.map((s) => (
          <details key={s.id} className="guide-sensor">
            <summary>{s.name}</summary>
            <SensorDetails sensor={s} open />
          </details>
        ))}
      </section>

      <section>
        <h3>Por que a janela de 30 dias falhava</h3>
        <p className="small">
          O filtro antigo descartava a cena inteira quando o tile (110 × 110 km) tinha mais de 10% de nuvem. Em
          Porto Ferreira, que fica na divisa de 4 tiles, isso deixava dezembro, janeiro e fevereiro sem nenhuma
          imagem. Agora a nuvem é removida pixel a pixel, e a janela é ampliada só quando ainda sobram buracos. Cada
          processamento registra as datas usadas e a cobertura obtida.
        </p>
      </section>

      {categories.map((cat) => (
        <section key={cat}>
          <h3>{cat}</h3>
          {indices
            .filter((i) => i.category === cat)
            .map((i) => (
              <article key={i.id} className="index-card">
                <header>
                  <strong>{i.name}</strong> <code>{i.formula}</code>
                </header>
                <p className="small">{i.description}</p>
                <div className="gradient" style={{ background: gradientCss(i.colors) }} />
                <div className="gradient-labels">
                  <span>{formatNumber(i.vmin, 2)}</span>
                  <span>{formatNumber(i.vmax, 2)}</span>
                </div>
                <ul className="classes">
                  {i.classes.map((c) => (
                    <li key={c.label}>
                      <span
                        className="swatch"
                        style={{ background: colorAt(i.colors, ((c.min + c.max) / 2 - i.vmin) / (i.vmax - i.vmin)) }}
                      />
                      <span className="nowrap">
                        {formatNumber(c.min, 2)} a {formatNumber(c.max, 2)}
                      </span>
                      <span>{c.label}</span>
                    </li>
                  ))}
                </ul>
                <p className="muted small">Referência: {i.reference}</p>
              </article>
            ))}
        </section>
      ))}
    </div>
  );
}
