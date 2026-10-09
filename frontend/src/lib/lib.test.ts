import { describe, expect, it } from "vitest";

import { formatErrorDetail } from "../api/client";
import { colorAt } from "./colors";
import { daysBetween, formatBytes, formatDate, monthRange, seasonPresets, shortPlatform } from "./format";
import { bboxAreaKm2, bboxFromCorners, isValidBBox } from "./geo";

describe("geo", () => {
  it("calcula a área do retângulo de Porto Ferreira igual ao backend", () => {
    const area = bboxAreaKm2({ west: -47.5546664, south: -21.935324, east: -47.3343908, north: -21.7547284 });
    expect(area).toBeGreaterThan(445);
    expect(area).toBeLessThan(475);
  });

  it("ordena cantos desenhados em qualquer direção", () => {
    const b = bboxFromCorners({ lat: -21.7, lng: -47.3 }, { lat: -21.9, lng: -47.5 });
    expect(b).toEqual({ west: -47.5, south: -21.9, east: -47.3, north: -21.7 });
    expect(isValidBBox(b)).toBe(true);
  });
});

describe("format", () => {
  it("formata datas ISO sem deslocamento de fuso", () => {
    expect(formatDate("2024-03-01")).toBe("01/03/2024");
  });

  it("calcula o intervalo do mês considerando ano bissexto", () => {
    expect(monthRange(2024, 2)).toEqual({ start: "2024-02-01", end: "2024-02-29" });
    expect(monthRange(2025, 2).end).toBe("2025-02-28");
  });

  it("estação chuvosa atravessa o ano", () => {
    const chuvas = seasonPresets(2024)[1]!;
    expect(chuvas.start).toBe("2024-12-01");
    expect(chuvas.end).toBe("2025-02-28");
  });

  it("conta dias inclusivos", () => {
    expect(daysBetween("2024-03-01", "2024-03-31")).toBe(31);
  });

  it("formata bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(19_756_925)).toBe("18.8 MB");
  });
});

describe("colors", () => {
  it("interpola nas extremidades e no meio", () => {
    expect(colorAt(["#000000", "#ffffff"], 0)).toBe("rgb(0,0,0)");
    expect(colorAt(["#000000", "#ffffff"], 1)).toBe("rgb(255,255,255)");
    expect(colorAt(["#000000", "#ffffff"], 0.5)).toBe("rgb(128,128,128)");
  });
});

describe("api", () => {
  it("transforma erros de validação do FastAPI em texto", () => {
    const detail = [{ loc: ["body", "aoi", "west"], msg: "valor inválido" }];
    expect(formatErrorDetail(detail)).toBe("aoi.west: valor inválido");
    expect(formatErrorDetail("falhou")).toBe("falhou");
  });
});

describe("plataformas", () => {
  it("abrevia nomes de satélites", () => {
    expect(shortPlatform("sentinel-2c")).toBe("S2C");
    expect(shortPlatform("landsat-9")).toBe("L9");
    expect(shortPlatform("Sentinel-2B")).toBe("S2B");
    expect(shortPlatform("outro")).toBe("outro");
  });
});
