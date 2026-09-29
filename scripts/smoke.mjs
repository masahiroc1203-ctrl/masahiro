// ブラウザでの通し確認（スマホサイズ・ライト/ダーク）
//
// 事前準備（初回のみ）:
//   npm i -D playwright && npx playwright install chromium
// 実行:
//   npm run smoke
// 画面のスクリーンショットは .screenshots/ に保存される（git管理外）
import { mkdir } from 'node:fs/promises';
import { startServer } from './serve.mjs';

async function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright', '@playwright/test'].filter(Boolean);
  for (const name of candidates) {
    try {
      const mod = await import(name);
      return mod.chromium ? mod : mod.default;
    } catch {
      // 次の候補へ
    }
  }
  console.error('Playwright が見つかりません。次を実行してください:\n  npm i -D playwright && npx playwright install chromium');
  process.exit(1);
}

const { chromium } = await loadPlaywright();
const OUT = '.screenshots';
await mkdir(OUT, { recursive: true });
const server = await startServer(0);
const base = `http://localhost:${server.address().port}/index.html`;
const failures = [];
const check = (ok, msg) => {
  console.log(`${ok ? '✓' : '✗'} ${msg}`);
  if (!ok) failures.push(msg);
};

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });

async function newPage(colorScheme) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  page.errors = [];
  page.on('pageerror', (e) => page.errors.push(e.message));
  page.on('console', (m) => {
    // YouTube など外部への通信失敗はオフライン環境では起こりうるので除外
    if (m.type() === 'error' && !/youtube|net::|Failed to load resource/i.test(m.text())) page.errors.push(m.text());
  });
  return page;
}
const seed = (page, data) =>
  page.evaluate((d) => localStorage.setItem('hiit-weekly:v1', JSON.stringify(d)), {
    settings: { prep: 3 },
    weeks: {},
    logs: [],
    custom: [],
    overrides: {},
    videos: {},
    ...data,
  });
const state = (page) => page.evaluate(() => JSON.parse(localStorage.getItem('hiit-weekly:v1') || '{}'));
const phase = (page) => page.evaluate(() => document.querySelector('.player')?.dataset.phase);

// ── 1. 全画面をライト/ダークで表示 ──
for (const scheme of ['light', 'dark']) {
  const page = await newPage(scheme);
  await page.goto(base);
  await seed(page, {});
  await page.reload();
  const shot = async (name) => {
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/${scheme}-${name}.png` });
  };
  await shot('home');
  await page.click('[data-quick="lower"]');
  check((await page.$$('.menu-card')).length > 0, `[${scheme}] 部位を選ぶと今週のメニューが出る`);
  await shot('home-lower');
  for (const [hash, name] of [
    ['#/menus', 'menus'],
    ['#/menu/lower-tabata', 'menu'],
    ['#/exercises', 'exercises'],
    ['#/exercise/burpee', 'exercise'],
    ['#/edit/new', 'edit'],
    ['#/history', 'history'],
    ['#/settings', 'settings'],
  ]) {
    await page.goto(base + hash);
    await shot(name);
  }
  await page.goto(base + '#/exercises');
  check((await page.$$('.ex-card svg.fig')).length >= 35, `[${scheme}] 35種目のお手本アニメが表示される`);
  check(page.errors.length === 0, `[${scheme}] コンソールエラーなし ${page.errors.join(' / ')}`);
  await page.context().close();
}

// ── 2. ワークアウト（短い時間で通し） ──
{
  const page = await newPage('light');
  await page.goto(base);
  await seed(page, { overrides: { 'lower-tabata': { work: 5, rest: 3, laps: 2, lapRest: 4 } } });
  await page.goto(base + '#/menu/lower-tabata');
  await page.reload();
  await page.click('[data-act="start"]');
  await page.waitForTimeout(500);
  check((await phase(page)) === 'prep', 'スタート直後は「準備」');
  await page.waitForTimeout(3000);
  check((await phase(page)) === 'work', '準備のあと「ワーク」になる');
  await page.screenshot({ path: `${OUT}/player-work.png` });
  await page.waitForTimeout(5000);
  check((await phase(page)) === 'rest', 'ワークのあと「レスト」になる');
  await page.click('[data-act="toggle"]');
  const c1 = await page.textContent('.p-clock');
  await page.waitForTimeout(1500);
  check(c1 === (await page.textContent('.p-clock')), '一時停止中はカウントが止まる');
  await page.click('[data-act="toggle"]');
  for (let i = 0; i < 30 && (await phase(page)) !== 'done'; i++) {
    await page.click('[data-act="next"]');
    await page.waitForTimeout(80);
  }
  check((await phase(page)) === 'done', 'スキップで最後まで進むと完了画面');
  await page.screenshot({ path: `${OUT}/player-done.png` });
  await page.click('[data-act="exit"]');
  await page.waitForTimeout(400);
  check((await page.evaluate(() => location.hash)) === '#/history', '「記録を見る」で記録画面へ');
  check((await state(page)).logs?.length === 1, '完了した運動が記録される');
  check(page.errors.length === 0, `ワークアウト中のエラーなし ${page.errors.join(' / ')}`);
  await page.context().close();
}

// ── 3. メニュー作成・動画登録・途中終了・削除 ──
{
  const page = await newPage('light');
  await page.goto(base);
  await seed(page, {});
  await page.goto(base + '#/edit/new');
  await page.reload();
  await page.fill('[data-name]', 'テスト用メニュー');
  await page.click('[data-part="core"]');
  await page.click('[data-add="plank"]');
  await page.click('[data-add="crunch"]');
  await page.click('[data-move="1:-1"]');
  const order = await page.$$eval('.picked-item .name', (els) => els.map((e) => e.textContent));
  check(order.join(',') === 'クランチ,プランク', '種目の追加と並べ替え');
  await page.click('[data-act="save"]');
  await page.waitForTimeout(300);
  const id = (await page.evaluate(() => location.hash)).split('/').pop();
  check(id.startsWith('my-'), '保存すると自作メニューの詳細へ');

  // 並べ替え後の1種目目（クランチ）に動画を登録する
  await page.goto(base + '#/exercise/crunch');
  await page.fill('input[name="url"]', 'https://youtu.be/dQw4w9WgXcQ');
  await page.click('[data-video-form] button[type="submit"]');
  await page.waitForTimeout(200);
  check(!!(await page.$('.video-frame iframe')), '動画URLを登録すると埋め込み表示');

  await page.goto(base + `#/menu/${id}`);
  await page.click('[data-act="start"]');
  await page.waitForTimeout(300);
  check(!!(await page.$('.p-demo iframe')), '動画を登録した種目はワークアウト中に動画表示');
  await page.click('[data-act="src"]');
  check(!!(await page.$('.p-demo svg.fig')) && !(await page.$('.p-demo iframe')), 'アニメに切り替えられる');
  await page.click('[data-act="close"]');
  await page.click('.sheet [data-cancel]');
  check(!!(await page.$('.player')), '終了確認で「続ける」を選ぶと続行');
  await page.click('[data-act="close"]');
  await page.click('.sheet [data-ok]');
  await page.waitForTimeout(300);
  check(!(await page.$('.player')), '終了確認で「終了する」を選ぶと閉じる');

  await page.click('[data-act="start"]');
  await page.waitForTimeout(300);
  await page.goBack();
  await page.waitForTimeout(200);
  await page.click('.sheet [data-ok]');
  await page.waitForTimeout(300);
  check(!(await page.$('.player')), '端末の戻るボタンでも終了確認が出て閉じられる');

  await page.click('[data-act="delete"]');
  await page.click('.sheet [data-ok]');
  await page.waitForTimeout(300);
  check((await state(page)).custom.length === 0, '自作メニューを削除できる');
  check(page.errors.length === 0, `操作中のエラーなし ${page.errors.join(' / ')}`);
  await page.context().close();
}

await browser.close();
server.close();
console.log(failures.length ? `\n${failures.length} 件失敗` : `\nすべてOK（スクリーンショット: ${OUT}/）`);
process.exit(failures.length ? 1 : 0);
