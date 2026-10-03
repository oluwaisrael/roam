import { expect, test, type Page } from "@playwright/test";

const response = {
  search_id: "browser-test",
  engine: "ai", engine_status: "AI understanding", data_status: "live", clarification: null, locality_note: "Showing places within about 7 km of your current location",
  intent: { activity: "work", area: "Yaba", place_types: ["cafe"], budget_max: 10000, duration_hours: 3, max_minutes: null, quiet: true, wifi: true, power: true, open_now: false, romantic: false, cheap: false, must_have: ["quiet", "wifi", "power"], avoid: [], priority: [], interpretation: "Work in Yaba, under NGN 10,000" },
  intelligence: { headline: "Start with Test Cafe", summary: "Start with Test Cafe for working: estimated spend fits your budget. Test Coffee is a close alternative.", confidence: "low", primary_tradeoff: "Amenities need confirmation", next_best_action: "Confirm power access before going.", caveats: ["Place names and locations come from OpenStreetMap. Spend and suitability are estimates."] },
  suggestions: ["Find somewhere closer"],
  results: ["Test Cafe", "Test Coffee", "Test Library"].map((name, index) => ({
    place_id: `test-${index}`, name, category: index === 2 ? "Library" : "Cafe", area: "Yaba", score: 85 - index * 6,
    rating: null, typical_spend: 8000 - index * 1000, distance_km: 1.2 + index, travel_minutes: 5 + index,
    open_now: null, match_reasons: ["Cafe matches your plans", "Estimated spend fits your budget"], tradeoffs: ["Prices, noise and amenities need confirmation"],
    tags: ["details limited"], data_source: "OpenStreetMap", photo_url: null, photo_page_url: null,
    maps_url: "https://www.google.com/maps/search/?api=1&query=6.5,3.3", photos_url: "https://www.google.com/search?tbm=isch&q=test+cafe",
    evidence: [{ label: "Wi-Fi", value: "Listed by the map contributor", status: "listed" }, { label: "Power", value: "Not confirmed", status: "unknown" }],
  })),
};

async function assertFits(page: Page) {
  const overflowing = await page.evaluate(() => [...document.querySelectorAll("main *, header *, nav *")].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1);
  }).map(el => `${el.tagName}.${el.className}`));
  expect(overflowing).toEqual([]);
}

async function search(page: Page) {
  await page.getByRole("textbox", { name: "What are you looking for?" }).fill("quiet cafe in Yaba with Wi-Fi under 10k");
  await page.getByRole("button", { name: "Find my place" }).click();
  await expect(page.getByRole("heading", { name: "3 places, picked for you." })).toBeVisible();
}

test("discovery images, responsive layout and persistent dark mode", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What’s the plan?" })).toBeVisible();
  await expect(page.locator(".mood-card img")).toHaveCount(3);
  await expect.poll(() => page.locator(".mood-card img").evaluateAll(images => images.every(image => (image as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await assertFits(page);
  await page.screenshot({ path: info.outputPath("home-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Switch to dark mode", exact: true }).filter({ visible: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({ path: info.outputPath("home-dark.png"), fullPage: true });
  await page.setViewportSize({ width: 320, height: 740 });
  await assertFits(page);
});

test("search, save, compare, details and contextual refinements", async ({ page }, info) => {
  let lastRequest: Record<string, unknown> = {};
  await page.route("**/api/search**", async route => {
    lastRequest = route.request().postDataJSON();
    await route.fulfill({ json: response });
  });
  await page.goto("/");
  await search(page);
  await expect(page.getByText("AI understanding", { exact: true })).toBeVisible();
  await assertFits(page);
  await page.screenshot({ path: info.outputPath("results-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Save Test Cafe", exact: true }).click();
  await page.getByRole("button", { name: "Compare Test Cafe", exact: true }).click();
  await page.getByRole("button", { name: "Compare Test Coffee", exact: true }).click();
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Not verified", exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByText("Why this place", { exact: true }).first().click();
  await expect(page.getByText("Listed by the map contributor").first()).toBeVisible();
  await page.getByRole("button", { name: "Find somewhere closer", exact: true }).click();
  await expect.poll(() => lastRequest.query).toBe("Find somewhere closer");
  expect(lastRequest.search_id).toBe("browser-test");
  await expect(page.getByRole("button", { name: "Find my place" })).toBeEnabled();
  await page.getByRole("button", { name: "Adjust preferences" }).click();
  await page.getByLabel("Budget per person").fill("20000");
  await page.getByRole("button", { name: "Update my places" }).click();
  await expect.poll(() => (lastRequest.change as { budget_max: number })?.budget_max).toBe(20000);
  await page.getByRole("button", { name: "Switch to dark mode", exact: true }).filter({ visible: true }).click();
  await page.screenshot({ path: info.outputPath("results-dark.png"), fullPage: true });
  await page.reload();
  await page.getByRole("button", { name: /Saved/ }).filter({ visible: true }).click();
  await expect(page.getByRole("heading", { name: "Test Cafe", exact: true })).toBeVisible();
  await assertFits(page);
  await page.getByRole("button", { name: "Unsave Test Cafe", exact: true }).click();
  await expect(page.getByRole("heading", { name: "A few favourites in the making." })).toBeVisible();
});

test("current location is sent to the decision engine and keeps the local boundary visible", async ({ page }) => {
  let requestBody: Record<string, unknown> = {};
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation({ latitude: 6.52, longitude: 3.37 });
  await page.route("**/api/search", async route => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({ json: response });
  });
  await page.goto("/");
  await page.getByRole("textbox", { name: "What are you looking for?" }).fill("quiet cafe to work");
  await page.getByRole("button", { name: "Use my location" }).click();
  await expect(page.getByText("Showing places within about 7 km of your current location", { exact: true })).toBeVisible();
  expect(requestBody.location).toEqual({ lat: 6.52, lng: 3.37 });
});

test("empty results and network errors are recoverable", async ({ page }) => {
  await page.route("**/api/search", route => route.fulfill({ json: { ...response, results: [], data_status: "unavailable" } }));
  await page.goto("/");
  await page.getByRole("textbox", { name: "What are you looking for?" }).fill("coffee around Yaba");
  await page.getByRole("button", { name: "Find my place" }).click();
  await expect(page.getByRole("heading", { name: "No live places found this time." })).toBeVisible();
  await page.unroute("**/api/search");
  await page.route("**/api/search", route => route.abort());
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("alert")).toContainText("Couldn't reach Roam");
  await expect(page.getByRole("button", { name: "Find my place" })).toBeEnabled();
});

test("cancelling a search does not replace the page with stale results", async ({ page }) => {
  await page.route("**/api/search", async route => { await new Promise(resolve => setTimeout(resolve, 1000)); await route.fulfill({ json: response }).catch(() => {}); });
  await page.goto("/");
  await page.getByRole("textbox", { name: "What are you looking for?" }).fill("coffee near me");
  await page.getByRole("button", { name: "Find my place" }).click();
  await page.getByRole("button", { name: "Cancel search" }).click();
  await expect(page.getByRole("heading", { name: "A change of scene." })).toBeVisible();
  await page.waitForTimeout(1200);
  await expect(page.getByRole("heading", { name: "Your shortlist" })).toHaveCount(0);
});
