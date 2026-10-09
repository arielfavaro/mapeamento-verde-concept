/** Cor interpolada em uma lista de cores hex, com t entre 0 e 1. */
export function colorAt(colors: readonly string[], t: number): string {
  if (colors.length === 0) return "#888888";
  const clamped = Math.min(1, Math.max(0, t));
  const pos = clamped * (colors.length - 1);
  const i = Math.floor(pos);
  const a = hexToRgb(colors[i] as string);
  const b = hexToRgb(colors[Math.min(i + 1, colors.length - 1)] as string);
  const f = pos - i;
  const mix = a.map((v, k) => Math.round(v + ((b[k] as number) - v) * f));
  return `rgb(${mix.join(",")})`;
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export const gradientCss = (colors: readonly string[]) => `linear-gradient(to right, ${colors.join(", ")})`;
