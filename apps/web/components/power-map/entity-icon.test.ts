import { describe, expect, it } from "vitest";
import { isFederalPresidency } from "./entity-icon";

describe("entity icon identity", () => {
  it("distinguishes the federal presidency from other presidencies", () => {
    expect(isFederalPresidency({
      slug: "presidencia-de-mexico",
      label: "Presidencia de los Estados Unidos Mexicanos",
      kind: "position",
      branch: "executive"
    })).toBe(true);
    expect(isFederalPresidency({
      slug: "presidencia-scjn",
      label: "Presidencia de la Suprema Corte de Justicia de la Nación",
      kind: "position",
      branch: "judicial"
    })).toBe(false);
  });
});
