#!/usr/bin/env node
/**
 * Matriz de verificación del menú compacto — múltiples viewports y roles.
 * Uso: node scripts/test_mobile_menu_matrix.js [baseUrl]
 */
const puppeteer = require('puppeteer-core');

const BASE = process.argv[2] || 'http://127.0.0.1:8000';
const DEMO_PASSWORD = process.env.DEMO_USER_PASSWORD || '';
const VIEWPORTS = [
  { width: 360, height: 740, label: '360x740' },
  { width: 390, height: 844, label: '390x844' },
  { width: 412, height: 915, label: '412x915' },
  { width: 768, height: 1024, label: '768x1024' },
];

const SCENARIOS = [
  {
    name: 'guest-home',
    path: '/',
    button: '#cat-nav-hamburger',
    menu: '#cat-nav-secondary',
    login: null,
  },
  {
    name: 'guest-catalog',
    path: '/catalogo/',
    button: '#cat-nav-hamburger',
    menu: '#cat-nav-secondary',
    login: null,
  },
  {
    name: 'buyer-home',
    path: '/',
    button: '#bn-mobile-toggle',
    menu: '#bn-l2',
    login: { user: 'demo_buyer', pass: DEMO_PASSWORD },
  },
  {
    name: 'buyer-catalog',
    path: '/catalogo/',
    button: '#bn-mobile-toggle',
    menu: '#bn-l2',
    login: { user: 'demo_buyer', pass: DEMO_PASSWORD },
  },
];

async function login(page, creds) {
  await page.goto(`${BASE}/login/`, { waitUntil: 'networkidle2', timeout: 60000 });
  const hasForm = await page.$('#id_username');
  if (!hasForm) {
    return;
  }
  await page.type('#id_username', creds.user);
  await page.type('#id_password', creds.pass);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }),
    page.click('button[type="submit"]'),
  ]);
}

async function tapMenu(page, selector) {
  const box = await page.$(selector);
  if (!box) {
    throw new Error(`Missing button: ${selector}`);
  }
  const rect = await box.boundingBox();
  if (!rect) {
    throw new Error(`Button not visible: ${selector}`);
  }
  await page.touchscreen.tap(rect.x + rect.width / 2, rect.y + rect.height / 2);
}

async function readMenuState(page, menuSelector) {
  return page.evaluate((sel) => {
    const menu = document.querySelector(sel);
    const style = menu ? window.getComputedStyle(menu) : null;
    const rect = menu ? menu.getBoundingClientRect() : null;
    return {
      exists: Boolean(menu),
      isOpen: menu && menu.classList.contains('is-open'),
      bodyOpen: document.body.classList.contains('tf-market-menu-open'),
      display: style && style.display,
      position: style && style.position,
      height: rect && rect.height,
      visible: rect && rect.height > 40 && style && style.display !== 'none',
      docOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    };
  }, menuSelector);
}

async function runScenario(browser, scenario, viewport) {
  const context = await browser.createBrowserContext();
  const page = await context.newPage();
  const label = `${scenario.name}@${viewport.label}`;
  try {
    await page.setViewport({
      width: viewport.width,
      height: viewport.height,
      isMobile: viewport.width < 900,
      hasTouch: true,
    });
    if (scenario.login) {
      await login(page, scenario.login);
    }
    await page.goto(`${BASE}${scenario.path}`, {
      waitUntil: 'networkidle2',
      timeout: 60000,
    });
    await tapMenu(page, scenario.button);
    await new Promise((r) => setTimeout(r, 250));
    const afterOpen = await readMenuState(page, scenario.menu);
    if (!afterOpen.isOpen || !afterOpen.bodyOpen || !afterOpen.visible) {
      return { label, ok: false, afterOpen };
    }
    await tapMenu(page, scenario.button);
    await new Promise((r) => setTimeout(r, 200));
    const afterClose = await readMenuState(page, scenario.menu);
    if (afterClose.isOpen || afterClose.bodyOpen) {
      return { label, ok: false, afterClose, phase: 'close' };
    }
    return { label, ok: true, afterOpen, afterClose };
  } catch (error) {
    return { label, ok: false, error: String(error) };
  } finally {
    await page.close();
    await context.close();
  }
}

async function main() {
  if (!DEMO_PASSWORD) {
    console.error('Define DEMO_USER_PASSWORD antes de ejecutar escenarios de comprador.');
    process.exit(1);
  }
  const browser = await puppeteer.launch({
    executablePath: '/usr/local/bin/google-chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const results = [];
  for (const scenario of SCENARIOS) {
    for (const viewport of VIEWPORTS) {
      results.push(await runScenario(browser, scenario, viewport));
    }
  }
  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(JSON.stringify({ total: results.length, failed: failed.length, results }, null, 2));
  if (failed.length) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
