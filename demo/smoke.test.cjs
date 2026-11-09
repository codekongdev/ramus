const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { createServer } = require('node:net');
const { once } = require('node:events');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('@playwright/test');

let browser, server, url;
before(async () => {
  const listener = createServer();
  listener.listen(0, '127.0.0.1');
  await once(listener, 'listening');
  const port = listener.address().port;
  await new Promise((resolve) => listener.close(resolve));
  url = `http://127.0.0.1:${port}`;
  server = spawn('python3', [path.join(__dirname, 'serve.py'), '--port', String(port)], { stdio: ['ignore', 'pipe', 'pipe'] });
  await once(server.stdout, 'data');
  browser = await chromium.launch({ headless: true });
});
after(async () => { await browser?.close(); server?.kill('SIGTERM'); });

const state = (page) => page.evaluate(() => RamusDemo.getState());
async function close(page) {
  if (await page.getByRole('dialog').count()) await page.getByRole('dialog').getByRole('button', { name: /^(Close|Close task)$/ }).first().click();
}

test('all nine guided scenes work through visible controls, including open modals', async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(url);
  for (let index = 1; index <= 8; index++) {
    await page.getByRole('button', { name: 'Next scene', exact: true }).click();
    assert.equal((await state(page)).scene, index);
  }
  const final = await state(page);
  assert.equal(final.goalComplete, true);
  assert.equal(final.conversations.cart.appliedVersion, 2);
  assert.equal(final.conversations.coupons.appliedVersion, 1);
  assert.deepEqual(final.conversations.checkout.inputs.map((input) => input.sourceId), ['coupons', 'cart']);
  assert.equal(await page.locator('.graph-svg path[stroke-dasharray]').count(), 3);
  assert.equal(await page.evaluate(() => /[가-힣]/.test(document.body.innerText)), false);
  assert.deepEqual(errors, []);
  await page.getByRole('button', { name: 'Replay story', exact: true }).click();
  assert.equal((await state(page)).scene, 0);
  await page.close();
});

test('manual review and selected-destination sharing preserve drafts and input snapshots', async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(url);
  await page.locator('[data-action="suggest"]').first().click();
  await page.waitForFunction(() => RamusDemo.getState().conversations.planning.messages.some((message) => message.author === 'ai'));
  await page.getByRole('button', { name: 'Save as shared convention', exact: true }).click();
  await page.getByRole('button', { name: 'Save v1', exact: true }).click();
  await close(page);
  await page.getByRole('button', { name: 'Branch work', exact: true }).click();
  await page.waitForFunction(() => RamusDemo.getState().tasks.every((task) => task.status === 'ready'));
  await page.locator('#composer-planning').fill('Keep this parent draft.');
  await page.locator('.task-card[data-id="coupons"]').click();
  await page.getByRole('dialog').getByRole('button', { name: 'Review & save result', exact: true }).last().click();
  await page.getByRole('button', { name: 'Save conclusion', exact: true }).click();
  const count = (await state(page)).conversations.checkout.messages.length;
  await page.getByRole('button', { name: 'Send to conversation', exact: true }).click();
  await page.locator('input[name="share-target"][value="checkout"]').check();
  await page.getByRole('button', { name: 'Send conclusion', exact: true }).click();
  assert.equal((await state(page)).conversations.checkout.inputs[0].sourceId, 'coupons');
  assert.equal((await state(page)).conversations.checkout.messages.length, count);
  assert.equal((await state(page)).conversations.cart.inputs.length, 0);
  await close(page);
  assert.equal(await page.locator('#composer-planning').inputValue(), 'Keep this parent draft.');
  await page.reload();
  assert.equal(await page.locator('#composer-planning').inputValue(), 'Keep this parent draft.');
  assert.equal((await state(page)).results.coupons.version, 1);
  await page.getByRole('button', { name: 'Reset demo', exact: true }).click();
  assert.equal((await state(page)).branched, false);
  await page.close();
});

test('mobile stays within the viewport and standalone HTML runs without a server', async () => {
  const page = await browser.newPage({ viewport: { width: 375, height: 812 }, reducedMotion: 'reduce' });
  await page.goto(url);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.ok(await page.getByRole('button', { name: 'Next scene', exact: true }).isVisible());
  await page.getByRole('button', { name: 'Next scene', exact: true }).click();
  await page.getByRole('button', { name: 'Next scene', exact: true }).click();
  assert.equal((await state(page)).scene, 2);
  const requests = [];
  page.on('request', (request) => requests.push(request.url()));
  await page.goto(pathToFileURL(path.join(__dirname, 'ramus-demo.html')).href);
  await page.getByRole('button', { name: 'Next scene', exact: true }).click();
  assert.ok((await state(page)).scene >= 1);
  assert.ok(requests.every((request) => !/^https?:/.test(request)));
  await page.close();
});
