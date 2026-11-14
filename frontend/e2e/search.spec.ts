import { expect, test, type Page } from "@playwright/test";

/*
 * The search flow (Case 1) in a real browser, on the fixed synthetic city
 * (seed 42, as of 2026-11-13), using the demo cases from the project brief:
 *   B+ red cells at the city centre  -> 22 banks, nearest Hari Nagar Blood Centre at 1.9 km
 *   O- platelets on the outskirts    -> no bank, donors instead (nearest Vikram S. at 8.6 km)
 */

const CENTRE = { latitude: 23.0225, longitude: 72.5714 };
const OUTSKIRTS = { latitude: 22.8021, longitude: 72.3275 };

async function searchFrom(page: Page, where: { latitude: number; longitude: number }, group: string, component: string) {
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation(where);
  await page.goto("/");
  await page.getByRole("radio", { name: group, exact: true }).check();
  await page.getByRole("radio", { name: component, exact: true }).check();
  await page.getByRole("button", { name: "Use my location" }).click();
  await expect(page.getByText(`Location set at ${where.latitude.toFixed(4)}, ${where.longitude.toFixed(4)}`)).toBeVisible();
  await page.getByRole("button", { name: /^Search for/ }).click();
}

test("finds the nearest blood banks with stock and draws the route", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await searchFrom(page, CENTRE, "B+", "Red cells");

  await expect(page.getByText(/^22 blood banks/)).toBeVisible();
  const nearest = page.locator("li", { hasText: "Nearest with stock" });
  await expect(nearest).toContainText("Hari Nagar Blood Centre");
  await expect(nearest).toContainText("1.9");
  await expect(nearest.getByRole("link", { name: /^Call Hari Nagar Blood Centre/ })).toBeVisible();

  // 5 results at a time.
  await expect(page.getByText("Showing 5 of 22 blood banks")).toBeVisible();
  await page.getByRole("button", { name: "Load 5 more blood banks" }).click();
  await expect(page.getByText("Showing 10 of 22 blood banks")).toBeVisible();

  // The route to the nearest bank is on the map, and the search form folded into a summary.
  await expect(page.locator(".leaflet-overlay-pane path").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Change search" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("falls back to donors when no bank has stock, and shows a number only after login", async ({ page }) => {
  await searchFrom(page, OUTSKIRTS, "O-", "Platelets");

  await expect(page.getByText("No blood bank within 25 km has O- platelets.")).toBeVisible();
  const donors = page.locator("main li").filter({ has: page.getByRole("button", { name: /^Show phone number of/ }) });
  await expect(donors.first()).toContainText("Vikram S.");
  await expect(donors.first()).toContainText("8.6 km");
  await expect(page.getByRole("button", { name: "Search wider (50 km)" })).toBeVisible();

  // No phone number is on the page before the contact endpoint is called.
  await expect(page.locator("main")).not.toContainText("+91-00000");

  // Show number -> phone login (the code is filled in automatically in development) -> the number.
  await page.getByRole("button", { name: "Show phone number of Vikram S." }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Phone number").fill(`+91-00000-6${Date.now().toString().slice(-4)}`);
  await dialog.getByRole("button", { name: "Send code" }).click();
  await expect(dialog.getByLabel(/^Code sent to/)).toHaveValue(/^\d{6}$/);
  await dialog.getByRole("button", { name: "Log in" }).click();
  // Once shown, the card has no "Show number" button any more, so find it by name.
  const vikram = page.locator("main li", { hasText: "Vikram S." });
  await expect(vikram).toContainText(/\+91-00000-\d{5}/);
  await expect(vikram.getByRole("link", { name: "Call Vikram S." })).toBeVisible();
});

test("a shared link fills in the search (demo case 2: one far bank)", async ({ page }) => {
  await page.goto("/?group=AB-&component=platelets&lat=23.2021&lng=72.7706");
  await expect(page.getByRole("radio", { name: "AB-", exact: true })).toBeChecked();
  await expect(page.getByRole("radio", { name: "Platelets", exact: true })).toBeChecked();
  await expect(page.getByText("Location set at 23.2021, 72.7706")).toBeVisible();
  await page.getByRole("button", { name: /^Search for/ }).click();
  const nearest = page.locator("li", { hasText: "Nearest with stock" });
  await expect(nearest).toContainText("Gandhi Park Blood Centre");
  await expect(nearest).toContainText("19.9");
});

test("a link with bad values falls back to the defaults", async ({ page }) => {
  await page.goto("/?group=X%2B&component=soup&lat=abc&lng=1");
  await expect(page.getByRole("radio", { name: "B+", exact: true })).toBeChecked();
  await expect(page.getByText("Or tap the map to drop a pin where you are.")).toBeVisible();
});
