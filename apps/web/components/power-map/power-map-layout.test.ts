import { describe, expect, it } from "vitest";
import type { PowerMapNode } from "@mapa/contracts";
import { annularSector, positionNodes, sectors, uniqueNodes } from "./power-map-layout";

function node(id: string, branch: string, category = "federal_entity"): PowerMapNode {
  return {
    id,
    slug: id,
    kind: "organization",
    label: id,
    shortLabel: id,
    description: "",
    category,
    branch,
    jurisdiction: "Federal",
    validFrom: "2024-01-01",
    validTo: null,
    sourceIds: [],
    parentId: null,
    hierarchyDepth: category === "branch" ? 0 : 1,
    expandable: category === "branch",
    counts: { children: 1, positions: 0, people: 0, relationships: 0 },
    occupancy: null,
    portrait: null,
    metadata: {}
  };
}

describe("power map geometry", () => {
  it("defines three powers and an autonomous sector without creating a fourth power", () => {
    expect(sectors.map((sector) => sector.branch)).toEqual(["executive", "legislative", "judicial", "independent"]);
    expect(sectors.find((sector) => sector.branch === "independent")?.label).toBe("Órganos autónomos");
  });

  it("is deterministic and places the expanded root at the center", () => {
    const nodes = [node("child-b", "legislative"), node("root", "legislative", "branch"), node("child-a", "legislative")];
    const first = positionNodes(nodes, "root");
    const second = positionNodes(nodes, "root");
    expect(first).toEqual(second);
    expect(first.find((item) => item.id === "root")).toMatchObject({ x: 460, y: 460, radius: 0 });
  });

  it("creates closed annular SVG paths", () => {
    expect(annularSector(-70, 20, 100, 200)).toMatch(/^M .+ Z$/);
  });

  it("deduplicates repeated nodes before rendering", () => {
    const repeated = [node("same", "executive"), node("same", "executive"), node("other", "judicial")];
    expect(uniqueNodes(repeated).map((item) => item.id)).toEqual(["same", "other"]);
    expect(positionNodes(repeated, null).map((item) => item.id)).toEqual(["same", "other"]);
  });

  it("keeps ciudadanía in the centre when a legacy record has a power branch", () => {
    const citizen = { ...node("ciudadania-id", "executive"), slug: "ciudadania" };
    const positioned = positionNodes([citizen, node("presidencia", "executive")], null);
    expect(positioned.filter((item) => item.id === citizen.id)).toHaveLength(1);
    expect(positioned.find((item) => item.id === citizen.id)).toMatchObject({ x: 460, y: 460 });
  });
});
