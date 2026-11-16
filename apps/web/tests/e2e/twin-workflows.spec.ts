import { expect, test } from "@playwright/test";

const clinicianPassword = process.env.PW_E2E_CLINICIAN_PASSWORD || "E2E-Clinician-Only-2026!";
const adminPassword = process.env.PW_E2E_ADMIN_PASSWORD || "E2E-Admin-Only-2026!";
const researcherPassword = process.env.PW_E2E_RESEARCHER_PASSWORD || "E2E-Researcher-Only-2026!";

async function signInAsDemoUser(
  page: import("@playwright/test").Page,
  username: string,
  password: string,
) {
  await page.goto("/");
  await expect(page).toHaveURL(/localhost:8081/);
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/localhost:3000/, { timeout: 90_000 });
  await expect(page.getByRole("heading", { name: "Command centre" })).toBeVisible({
    timeout: 90_000,
  });
}

test("clinician can use the patient twin workflows and is kept out of admin governance", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await signInAsDemoUser(page, "demo.clinician", clinicianPassword);
  await expect(page.getByText("Alex Morgan").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Governance & audit" })).toHaveCount(0);

  await page.getByRole("button", { name: "Clinical timeline" }).click();
  await expect(page.getByRole("heading", { name: "Clinical timeline" })).toBeVisible();

  await page.getByRole("button", { name: "Command centre" }).click();
  await page.getByRole("button", { name: "Sync FHIR" }).click();
  await expect(page.getByText(/FHIR sync completed\./)).toBeVisible({ timeout: 90_000 });

  await page.getByRole("button", { name: "Twin snapshots" }).click();
  await page.getByRole("button", { name: "Create new version" }).click();
  await expect(page.getByText(/Snapshot v1 created\./)).toBeVisible();

  await page.getByRole("button", { name: "Simulation studio" }).click();
  await page.getByRole("button", { name: "Save scenario run" }).click();
  await expect(page.getByText(/Hypothetical scenario saved/)).toBeVisible();

  await page.getByRole("button", { name: "Evidence assistant" }).click();
  await expect(page.getByText("AI ready")).toBeVisible({ timeout: 120_000 });
  await page.getByRole("button", { name: "Index this patient's records" }).click();
  await expect(page.getByText(/Indexed \d+ patient evidence records/)).toBeVisible({
    timeout: 120_000,
  });
  await page
    .getByLabel("Ask about the recorded evidence")
    .fill("Summarise the patient's recorded heart rate and cite the source.");
  await page.getByRole("button", { name: "Ask local evidence assistant" }).click();
  await expect(page.getByRole("heading", { name: /Answer · qwen2\.5:3b/ })).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.getByText(/Prompt twinfixeno-evidence-assistant v1\.0\.0/)).toBeVisible();
  await expect(page.getByText(/Answer SHA-256/)).toBeVisible();

  expect(pageErrors, "browser should not report uncaught JavaScript errors").toEqual([]);
});


test("administrator can manage patient access grants and review audit events", async ({ page }) => {
  await signInAsDemoUser(page, "demo.admin", adminPassword);
  await expect(page.getByRole("button", { name: "Governance & audit" })).toBeVisible();
  await page.getByRole("button", { name: "Governance & audit" }).click();
  await expect(page.getByRole("heading", { name: "Patient access grants" })).toBeVisible();

  await page.getByLabel("Keycloak username").fill("qa.clinician");
  await page.getByLabel("Access level").selectOption("write");
  await page.getByRole("button", { name: "Save grant" }).click();
  await expect(page.getByText("Patient access grant saved.")).toBeVisible();
  await expect(page.getByText("qa.clinician")).toBeVisible();

  await page.getByRole("button", { name: "Revoke" }).last().click();
  await expect(page.getByText("Access grant revoked.")).toBeVisible();
  await expect(page.getByText("Recent audit activity")).toBeVisible();
});


test("researcher receives read-only controls in the clinical workspace", async ({ page }) => {
  await signInAsDemoUser(page, "demo.researcher", researcherPassword);
  await expect(page.getByText("Alex Morgan").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Governance & audit" })).toHaveCount(0);

  await expect(page.getByRole("button", { name: "Sync FHIR" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Create snapshot" })).toBeDisabled();

  await page.getByRole("button", { name: "Simulation studio" }).click();
  await expect(page.getByRole("button", { name: "Save scenario run" })).toBeDisabled();

  await page.getByRole("button", { name: "Twin snapshots" }).click();
  await expect(page.getByRole("button", { name: "Create new version" })).toBeDisabled();

  await page.getByRole("button", { name: "Evidence assistant" }).click();
  await expect(page.getByRole("button", { name: "Index this patient's records" })).toBeDisabled();
});
