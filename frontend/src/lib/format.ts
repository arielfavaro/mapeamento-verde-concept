export const formatPct = (fraction: number | null | undefined, digits = 0) =>
  fraction == null ? "—" : `${(fraction * 100).toFixed(digits)}%`;

export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/** "2024-03-05" → "05/03/2024" (sem passar por Date, evitando deslocamento de fuso). */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function formatNumber(value: number | null | undefined, digits = 3): string {
  return value == null ? "—" : value.toLocaleString("pt-BR", { maximumFractionDigits: digits });
}

const pad = (n: number) => String(n).padStart(2, "0");

export const toIsoDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** Primeiro e último dia do mês (mês 1–12). */
export function monthRange(year: number, month: number): { start: string; end: string } {
  const last = new Date(year, month, 0).getDate();
  return { start: `${year}-${pad(month)}-01`, end: `${year}-${pad(month)}-${pad(last)}` };
}

export type PeriodPreset = { label: string; hint: string; start: string; end: string };

/** Períodos típicos para o interior paulista: estação seca e chuvosa do mesmo ciclo. */
export function seasonPresets(year: number): PeriodPreset[] {
  return [
    { label: `Seca ${year}`, hint: "jun–ago: céu limpo, cana em colheita", start: `${year}-06-01`, end: `${year}-08-31` },
    {
      label: `Chuvas ${year}/${String(year + 1).slice(2)}`,
      hint: "dez–fev: muita nuvem, vegetação no pico",
      start: `${year}-12-01`,
      end: `${year + 1}-02-${new Date(year + 1, 2, 0).getDate()}`,
    },
    { label: `Ano ${year}`, hint: "mediana anual", start: `${year}-01-01`, end: `${year}-12-31` },
  ];
}

export function daysBetween(start: string, end: string): number {
  const ms = Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`);
  return Math.round(ms / 86_400_000) + 1;
}

/** "sentinel-2c" → "S2C", "landsat-9" → "L9" */
export function shortPlatform(platform: string): string {
  const m = /^(sentinel|landsat)-?(\w+)$/i.exec(platform);
  if (!m) return platform;
  return `${m[1]![0]!.toUpperCase()}${m[2]!.toUpperCase()}`;
}
