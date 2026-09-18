import { describe, expect, it } from "vitest";
import type { PowerMapNode } from "@mapa/contracts";
import { layoutParliamentarySeats, legislativeSeats, parliamentaryColor } from "./parliamentary-chamber-layout";

function seat(id: string, group: string, seatNumber: number): PowerMapNode {
  return {
    id,
    slug: id,
    kind: "position",
    label: `Senaduría ${seatNumber}`,
    shortLabel: `Escaño ${seatNumber}`,
    description: "",
    category: "legislative_seat",
    branch: "legislative",
    jurisdiction: "Federal",
    validFrom: "2024-09-01",
    validTo: null,
    sourceIds: [],
    parentId: "senado",
    hierarchyDepth: 2,
    expandable: false,
    counts: { children: 0, positions: 0, people: 1, relationships: 1 },
    occupancy: null,
    portrait: null,
    metadata: { parliamentaryGroup: group, seatNumber, positionType: "legislative_seat" }
  };
}

describe("parliamentary chamber layout", () => {
  it("keeps one plotted seat per legislative position and groups its totals", () => {
    const nodes = [seat("a", "MORENA", 1), seat("b", "MORENA", 2), seat("c", "PAN", 3)];
    const result = layoutParliamentarySeats(nodes);

    expect(result.seats).toHaveLength(3);
    expect(result.groups).toEqual([
      expect.objectContaining({ label: "MORENA", count: 2 }),
      expect.objectContaining({ label: "PAN", count: 1 })
    ]);
    expect(new Set(result.seats.map((item) => `${item.x}-${item.y}`)).size).toBe(3);
  });

  it("ignores people and ordinary positions", () => {
    const legislative = seat("a", "PAN", 1);
    const ordinary = { ...seat("b", "PAN", 2), category: "public_office", metadata: {} };
    const person = { ...seat("c", "PAN", 3), kind: "person" as const };
    expect(legislativeSeats([legislative, ordinary, person])).toEqual([legislative]);
  });

  it("uses stable colors for known and unknown groups", () => {
    expect(parliamentaryColor("MORENA")).toBe("#a52b43");
    expect(parliamentaryColor("Grupo local")).toBe(parliamentaryColor("Grupo local"));
  });
});
