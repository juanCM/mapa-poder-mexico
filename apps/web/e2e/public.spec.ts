import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("navega desde la portada hasta el mapa", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Entiende cómo se organiza");
  await page.getByRole("link", { name: /Abrir el mapa/ }).click();
  await expect(page).toHaveURL(/\/mapa$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("El poder público federal");
});

test("expande un poder y conserva la ruta compartible", async ({ page }) => {
  await page.goto("/mapa");
  await page.getByRole("button", { name: /^Poder Legislativo Federal\./ }).click();
  await page.getByRole("button", { name: /Explorar .* elementos/ }).click();
  await expect(page).toHaveURL(/root=/);
  await expect(page.getByRole("button", { name: /^Cámara de Diputados\./ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mapa general" })).toBeVisible();
  await page.getByRole("button", { name: "Mapa general" }).click();
  await expect(page).not.toHaveURL(/root=/);
});

test("ofrece una vista parlamentaria específica para las cámaras", async ({ page }) => {
  await page.goto("/mapa");
  await page.getByRole("button", { name: /^Poder Legislativo Federal\./ }).click();
  await page.getByRole("button", { name: /Explorar .* elementos/ }).click();
  await page.getByRole("button", { name: /^Cámara de Diputados\./ }).click();
  await page.getByRole("button", { name: /Explorar .* elementos/ }).click();
  await expect(page.getByRole("button", { name: "Hemiciclo" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Composición parlamentaria")).toBeVisible();
  await page.getByRole("button", { name: "Estructura" }).click();
  await expect(page.getByRole("img", { name: "Detalle radial del grupo seleccionado" })).toBeVisible();
});

test("busca, selecciona y presenta relaciones con evidencia", async ({ page }) => {
  await page.goto("/mapa");
  await page.getByRole("textbox", { name: "Buscar en el mapa" }).fill("Auditoría Superior");
  await page.getByRole("option").first().click();
  await expect(page.getByRole("heading", { level: 2 })).toContainText("Auditoría Superior");
  await expect(page.getByRole("heading", { name: "Relaciones documentadas" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Cámara de Diputados|Constitución|CPEUM/ }).first()).toBeVisible({ timeout: 15_000 });
});

test("restaura fecha en URL y permite selección por teclado", async ({ page }) => {
  await page.goto("/mapa");
  const executive = page.getByRole("button", { name: /^Poder Ejecutivo Federal\./ });
  await executive.focus();
  await executive.press("Enter");
  await expect(page.getByRole("heading", { level: 2 })).toContainText("Poder Ejecutivo");
  await page.locator('input[type="date"]').fill("2025-09-01");
  await expect(page).toHaveURL(/asOf=2025-09-01/);
});

test("resalta el cargo de la Presidencia con identidad visual propia", async ({ page }) => {
  await page.goto("/mapa");
  const presidency = page.getByRole("button", { name: /^Presidencia de los Estados Unidos Mexicanos\./ });
  await expect(presidency).toHaveClass(/nodePresidency/);
  await expect(presidency).toContainText("Presidencia");
});

test("usa hoja móvil y fallback cuando no existe retrato oficial", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/mapa");
  await page.getByRole("textbox", { name: "Buscar en el mapa" }).fill("Claudia Sheinbaum");
  await page.getByRole("option").first().click();
  await expect(page.getByRole("heading", { level: 2 })).toContainText("Claudia Sheinbaum");
  await expect(page.getByRole("img", { name: "Retrato oficial no disponible" })).toBeVisible();
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
