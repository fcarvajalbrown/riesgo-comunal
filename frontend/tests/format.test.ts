import assert from "node:assert/strict";
import { test } from "node:test";
import { DATA_CLASS_STYLE, LEVEL_ICON, LEVEL_STYLE, formatTime } from "../lib/format.ts";

test("every level has a colour, a text label and an icon", () => {
  for (const level of ["SIN_DATOS", "INFORMATIVO", "BAJO", "MODERADO", "ALTO", "CRITICO"] as const) {
    assert.ok(LEVEL_STYLE[level].label.length > 0);
    assert.match(LEVEL_STYLE[level].hex, /^#[0-9a-f]{6}$/);
    assert.ok(LEVEL_ICON[level]);
  }
});

test("missing data is never styled as low risk", () => {
  assert.notEqual(LEVEL_STYLE.SIN_DATOS.hex, LEVEL_STYLE.BAJO.hex);
  assert.equal(LEVEL_STYLE.SIN_DATOS.label, "Sin datos");
});

test("every data class has a distinct Spanish label", () => {
  const labels = Object.values(DATA_CLASS_STYLE).map((s) => s.label);
  assert.equal(new Set(labels).size, labels.length);
  assert.equal(DATA_CLASS_STYLE.derived.label, "Cálculo de la plataforma");
  assert.equal(DATA_CLASS_STYLE.forecast.label, "Pronóstico");
  assert.equal(DATA_CLASS_STYLE.observed.label, "Observado");
});

test("times are shown in Chile local time with UTC in parentheses", () => {
  const text = formatTime("2026-07-15T06:13:00Z");
  assert.match(text, /02:13/);
  assert.match(text, /hora de Chile/);
  assert.match(text, /\(06:13 UTC\)/);
});

test("missing timestamps say so instead of inventing one", () => {
  assert.equal(formatTime(null), "sin fecha");
});
