import { describe, expect, it } from "vitest";
import { createFallbackNodeContext, createFallbackPowerMap } from "./power-map";

describe("local power map fallback", () => {
  it("keeps only active, evidence-backed relationships for the requested date", () => {
    const map = createFallbackPowerMap("2026-09-17");
    expect(map.nodes.length).toBeGreaterThan(0);
    expect(map.relationships.every((relation) => relation.hasEvidence)).toBe(true);
    expect(map.stats.organizations).toBeGreaterThan(0);
  });

  it("expands a known hierarchy and preserves its ancestor route", () => {
    const map = createFallbackPowerMap("2026-09-17", "camara-de-diputados");
    expect(map.root).not.toBeNull();
    expect(map.nodes.some((node) => node.slug === "camara-de-diputados")).toBe(true);
    expect(map.ancestors.some((node) => node.slug === "poder-legislativo-federal")).toBe(true);
  });

  it("treats validTo as the exclusive end of a tenure", () => {
    const beforeEnd = createFallbackNodeContext("claudia-sheinbaum-pardo", "2030-09-29");
    const atEnd = createFallbackNodeContext("claudia-sheinbaum-pardo", "2030-09-30");
    expect(beforeEnd?.relationships.some((relation) => relation.id === "rel-presidenta-cargo")).toBe(true);
    expect(atEnd?.relationships.some((relation) => relation.id === "rel-presidenta-cargo")).toBe(false);
  });
});
