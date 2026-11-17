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
  const usernameField = page.locator('input[name="username"]');
  await expect(usernameField).toBeVisible({ timeout: 45_000 });
  await usernameField.fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.locator("#kc-login").click();

  const dashboard = page.getByRole("heading", { name: "Command centre", level: 1 });
  try {
    await expect(dashboard).toBeVisible({ timeout: 45_000 });
  } catch {
    const visibleErrors = await page.locator("#input-error:visible, .alert-error:visible, [role='alert']:visible")
      .allTextContents().catch(() => []);
    const errorText = visibleErrors.map((value) => value.trim()).filter(Boolean).join(" | ");
    throw new Error(
      "Keycloak OIDC login did not reach the workspace for " + username +
      "; current URL: " + page.url() + "; Keycloak message: " + (errorText || "not shown"),
    );
  }
}

test("clinician can use the patient twin workflows and is kept out of admin governance", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await signInAsDemoUser(page, "demo.clinician", clinicianPassword);
  await expect(page.getByText("Alex Morgan").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Governance & audit" })).toHaveCount(0);

  await page.getByRole("button", { name: "Clinical timeline" }).click();
  await expect(page.getByRole("heading", { name: "Clinical timeline", level: 1 })).toBeVisible();

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
  await expect(page.getByRole("heading", { name: /^Answer · (?:[\w-]+\/)?qwen2\.5:3b$/ })).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.getByText(/Prompt twinfixeno-evidence-assistant v1\.0\.0/)).toBeVisible();
  await expect(page.getByText(/Answer SHA-256/)).toBeVisible();

  expect(pageErrors, "browser should not report uncaught JavaScript errors").toEqual([]);
});


test("administrator can search the 10,000-patient registry and manage access grants", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsDemoUser(page, "demo.admin", adminPassword);
  await page.getByRole("button", { name: "Patient registry" }).click();
  await expect(page.getByText("10,000 patients in registry")).toBeVisible({ timeout: 30_000 });
  await page.getByPlaceholder("Search patient ID, given name or family name…").fill("SYN-10000");
  await expect(page.getByText("SYN-10000")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /Open twin/ }).click();
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
  test.setTimeout(180_000);
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
