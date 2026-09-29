// ルーター・画面の組み立て
import { homeView } from './views/home.js';
import { menusView, menuView, editView, clearDraft } from './views/menus.js';
import { exercisesView, exerciseView } from './views/exercises.js';
import { historyView, settingsView } from './views/history.js';
import { openPlayer } from './player.js';
import { unlockAudio } from './audio.js';
import { $, esc, icon, toast } from './ui.js';

const ROUTES = [
  { re: /^\/?$/, tab: 'home', view: () => homeView() },
  { re: /^\/menus$/, tab: 'menus', view: () => menusView() },
  { re: /^\/menu\/([^/]+)$/, tab: 'menus', view: (m) => menuView({ id: m[1] }) },
  { re: /^\/edit\/([^/]+)$/, tab: 'menus', name: 'edit', view: (m, q) => editView({ id: m[1] }, q) },
  { re: /^\/exercises$/, tab: 'exercises', view: () => exercisesView() },
  { re: /^\/exercise\/([^/]+)$/, tab: 'exercises', view: (m) => exerciseView({ id: m[1] }) },
  { re: /^\/history$/, tab: 'history', view: () => historyView() },
  { re: /^\/settings$/, tab: 'home', view: () => settingsView() },
];

const topbar = $('#topbar');
const main = $('#view');
const stack = []; // アプリ内で辿った画面（戻るボタン用）
let lastPath = null;

function parseHash() {
  const raw = decodeURIComponent(location.hash.replace(/^#/, '')) || '/';
  const [path, qs = ''] = raw.split('?');
  return { path, query: new URLSearchParams(qs), key: raw };
}

function render() {
  const { path, query } = parseHash();
  let route = ROUTES.find((r) => r.re.test(path));
  let match = route?.re.exec(path);
  if (!route) {
    route = ROUTES[0];
    match = [];
  }
  if (route.name !== 'edit') clearDraft();
  const view = route.view(match, query);

  topbar.innerHTML = `
    ${view.back ? `<button class="icon-btn" data-back="${esc(view.back)}" aria-label="戻る">${icon('back')}</button>` : ''}
    <h1>${esc(view.title)}${view.sub ? `<span class="sub">${esc(view.sub)}</span>` : ''}</h1>
    ${view.actions || ''}`;

  // 画面ごとに新しい要素を作る（イベントの二重登録を防ぐ）
  const root = document.createElement('div');
  root.innerHTML = view.html;
  main.className = `view ${view.cls || ''}`;
  main.replaceChildren(root);
  view.mount?.(root, ctx);

  for (const tab of document.querySelectorAll('.tab')) {
    if (tab.dataset.tab === route.tab) tab.setAttribute('aria-current', 'page');
    else tab.removeAttribute('aria-current');
  }
  document.title = route.tab === 'home' && !view.back ? 'HIIT Weekly' : `${view.title} | HIIT Weekly`;
  if (path !== lastPath) window.scrollTo(0, 0);
  lastPath = path;
}

function onHashChange() {
  const { key } = parseHash();
  if (stack.length > 1 && stack[stack.length - 2] === key) stack.pop();
  else if (stack[stack.length - 1] !== key) stack.push(key);
  render();
}

function navigate(hash, { replace = false } = {}) {
  if (replace) {
    stack.pop();
    location.replace(hash);
  } else {
    location.hash = hash;
  }
}

function goBack(fallback) {
  if (stack.length > 1) history.back();
  else navigate(fallback, { replace: true });
}

const ctx = {
  navigate,
  rerender: render,
  startWorkout(menu) {
    if (!menu?.exercises.length) {
      toast('種目が入っていません');
      return;
    }
    unlockAudio();
    openPlayer(menu, {
      onClose(result) {
        if (result === 'history') navigate('#/history');
        else render();
        if (result === 'saved') toast('途中までの運動を記録しました');
      },
    });
  },
};

topbar.addEventListener('click', (e) => {
  const back = e.target.closest('[data-back]');
  if (back) goBack(back.dataset.back);
});

window.addEventListener('hashchange', onHashChange);
stack.push(parseHash().key);
render();

// オフライン対応（http(s) で開いたときだけ）
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  });
}
