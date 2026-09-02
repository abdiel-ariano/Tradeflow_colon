#!/usr/bin/env node
/** Graba verificación del menú móvil (invitado + comprador). */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const BASE = 'http://127.0.0.1:8000';
const OUT = '/opt/cursor/artifacts/video_mobile_menu_android_fix.mp4';

async function login(page) {
  await page.goto(`${BASE}/login/`, { waitUntil: 'networkidle2', timeout: 60000 });
  if (await page.$('#id_username')) {
    await page.type('#id_username', 'demo_buyer');
    await page.type('#id_password', 'Demo1234!');
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }),
      page.click('button[type="submit"]'),
    ]);
  }
}

async function tap(page, selector) {
  const el = await page.$(selector);
  const box = await el.boundingBox();
  await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: '/usr/local/bin/google-chrome',
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      `--window-size=390,844`,
    ],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
  const recorder = await page.screencast({ path: OUT });
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle2' });
  await new Promise((r) => setTimeout(r, 800));
  await tap(page, '#cat-nav-hamburger');
  await new Promise((r) => setTimeout(r, 1200));
  await tap(page, '#cat-nav-hamburger');
  await new Promise((r) => setTimeout(r, 600));
  await page.goto(`${BASE}/catalogo/`, { waitUntil: 'networkidle2' });
  await new Promise((r) => setTimeout(r, 800));
  await tap(page, '#cat-nav-hamburger');
  await new Promise((r) => setTimeout(r, 1200));
  await tap(page, '#cat-nav-hamburger');
  await new Promise((r) => setTimeout(r, 600));
  await login(page);
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle2' });
  await new Promise((r) => setTimeout(r, 800));
  await tap(page, '#bn-mobile-toggle');
  await new Promise((r) => setTimeout(r, 1200));
  await tap(page, '#bn-mobile-toggle');
  await new Promise((r) => setTimeout(r, 600));
  await page.goto(`${BASE}/catalogo/`, { waitUntil: 'networkidle2' });
  await new Promise((r) => setTimeout(r, 800));
  await tap(page, '#bn-mobile-toggle');
  await new Promise((r) => setTimeout(r, 1200));
  await recorder.stop();
  await browser.close();
  if (!fs.existsSync(OUT)) {
    throw new Error('Video not created');
  }
  console.log(OUT);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
