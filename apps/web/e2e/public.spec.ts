import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("navega desde la portada hasta el mapa", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Entiende cómo se organiza");
  await page.getByRole("link", { name: /Abrir el mapa/ }).click();
  await expect(page).toHaveURL(/\/mapa$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Una vista para la estructura");
});

test("ofrece una alternativa tabular al grafo", async ({ page }) => {
  await page.goto("/mapa");
  await page.getByRole("button", { name: "Vista en tabla" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Fundamento" })).toBeVisible();
});

test("cada ficha de relación muestra evidencia", async ({ page }) => {
  await page.goto("/relaciones/rel-asf-ejecutivo");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ASF fiscaliza Ejecutivo");
  await expect(page.getByText("CPEUM, artículo 79")).toBeVisible();
  await expect(page.getByRole("link", { name: /Abrir fuente/ })).toHaveAttribute("href", /diputados\.gob\.mx/);
});

test("la portada no contiene violaciones críticas de accesibilidad", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter((violation) => violation.impact === "critical");
  expect(critical).toEqual([]);
});
