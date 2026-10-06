// Playwright acceptance for the Super Admin console. Run: BASE=http://localhost:8011 SA_EMAIL=... SA_PASSWORD=... npx playwright test tests/e2e/superadmin
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE ?? 'http://localhost:8000';
const sections: [string, string, string][] = [
  ['/platform/', 'Platform overview', 'Organization health'],
  ['/platform/organizations/', 'Organizations', 'Name'],
  ['/platform/sites/', 'Sites & Locations', 'Site'],
  ['/platform/users/', 'Users', 'Last login'],
  ['/platform/roles/', 'Roles & Permissions', 'Permission matrix'],
  ['/platform/assets/', 'Assets', 'Total assets'],
  ['/platform/service-operations/', 'Service Operations', 'Service requests'],
  ['/platform/work-orders/', 'Work Orders', 'Work orders'],
  ['/platform/maintenance/', 'Maintenance', 'Schedules'],
  ['/platform/inventory/', 'Inventory', 'Stock movements'],
  ['/platform/sla/', 'SLA & Policies', 'Organizations'],
  ['/platform/dashboards/', 'Operational Dashboards', 'Organization comparison'],
  ['/platform/audit/', 'Audit & Compliance', 'Action'],
  ['/platform/settings/', 'System Settings', 'System health'],
  ['/platform/security/', 'Security', 'Security events'],
  ['/platform/profile/', 'Profile', 'Account'],
];

test.beforeEach(async ({ page }) => {
  await page.goto(`${BASE}/accounts/login/`);
  await page.getByLabel(/email/i).fill(process.env.SA_EMAIL!);
  await page.getByLabel(/password/i).fill(process.env.SA_PASSWORD!);
  await page.getByRole('button', { name: /sign in|log in/i }).click();
});

for (const [path, heading, marker] of sections) {
  test(`superadmin ${path}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
    page.on('response', (r) => r.status() >= 400 && errors.push(`${r.status()} ${r.url()}`));
    await page.goto(`${BASE}${path}`);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.getByText(marker).first()).toBeVisible();
    await page.screenshot({ path: `test-results/superadmin${path.replace(/\//g, '_')}.png`, fullPage: true });
    expect(errors).toEqual([]);
  });
}
