import { describe, expect, it } from "vitest";
import { dataset, getNodeById } from "./data";

describe("curated dataset", () => {
  it("backs every relationship with evidence", () => {
    expect(dataset.edges.every((edge) => edge.evidence.length > 0)).toBe(true);
  });

  it("does not leave dangling graph endpoints", () => {
    expect(dataset.edges.every((edge) => getNodeById(edge.source) && getNodeById(edge.target))).toBe(true);
  });

  it("keeps automatic review items out of published graph records", () => {
    expect(dataset.reviewTasks.some((task) => task.status === "needs_review")).toBe(true);
    expect(dataset.edges.every((edge) => !edge.id.startsWith("review-"))).toBe(true);
  });
});
