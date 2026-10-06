// 画面共通のヘルパー
import { EXERCISE_BY_ID } from './data/exercises.js';
import { PART_BY_ID, LEVELS } from './data/parts.js';
import { createFigure } from './figure.js';
import { prepare } from './pose.js';
import { parseVideo, youtubeEmbedUrl } from './video.js';

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

const ICONS = {
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01" stroke-width="3"/>',
  figure: '<circle cx="12" cy="4.5" r="2"/><path d="M12 7v7M7 10.5l5-2 5 2M8.5 21l3.5-7 3.5 7"/>',
  chart: '<path d="M3 21h18"/><path d="M6 17v-5M11 17V6M16 17v-8M21 17v-3"/>',
  sliders: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  back: '<path d="M15 18l-6-6 6-6"/>',
  close: '<path d="M18 6L6 18M6 6l12 12"/>',
  play: '<path d="M7 4.5v15l12.5-7.5z" fill="currentColor"/>',
  pause: '<path d="M8 5v14M16 5v14" stroke-width="3.2"/>',
  next: '<path d="M5 5.5v13l10-6.5z" fill="currentColor"/><path d="M19 5v14" stroke-width="2.6"/>',
  prev: '<path d="M19 5.5v13L9 12z" fill="currentColor"/><path d="M5 5v14" stroke-width="2.6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  up: '<path d="M6 15l6-6 6 6"/>',
  down: '<path d="M6 9l6 6 6-6"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3z"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  sound: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
  heart: '<path d="M12 20.5S4 15.6 4 9.8A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 8 2.2c0 5.8-8 10.7-8 10.7z" fill="currentColor"/>',
};

export const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;

export const partTag = (id) => {
  const p = PART_BY_ID[id];
  return p ? `<span class="tag" style="--c:${p.color}"><span class="dot"></span>${esc(p.short)}</span>` : '';
};
export const levelDots = (lv) => `<span class="level" title="${LEVELS[lv]?.label || ''}">${LEVELS[lv]?.dots || ''}</span>`;

// 読み上げ用の名前（カッコ書きを除く）
export const spokenName = (ex) => ex.name.replace(/（.*?）/g, '');

// ───── お手本の人物の差し込み ─────
// HTML内に <div data-fig="種目ID" data-mode="anim|thumb"></div> を置き、描画後に mountFigures を呼ぶ
export const figSlot = (exId, mode = 'anim', cls = '') => `<div class="${cls}" data-fig="${esc(exId)}" data-mode="${mode}"></div>`;

export function thumbTime(anim) {
  const { frames, weight } = prepare(anim);
  if (frames.length < 2) return 0;
  const w = frames[0].hold + frames[0].dur + frames[1].hold / 2;
  return (w / weight) * anim.ms;
}

export function mountFigures(root) {
  const figs = [];
  for (const slot of $$('[data-fig]', root)) {
    const ex = EXERCISE_BY_ID[slot.dataset.fig];
    if (!ex) continue;
    const anim = slot.dataset.mode !== 'thumb';
    const fig = createFigure(ex, { animate: anim, at: anim ? 0 : thumbTime(ex.anim) });
    slot.replaceChildren(fig.el);
    figs.push(fig);
  }
  return figs;
}

// ───── 動画の埋め込み ─────
export function videoEmbedHtml(url, { autoplay = true, mute = true } = {}) {
  const v = parseVideo(url);
  if (!v) return '';
  if (v.type === 'youtube') {
    return `<div class="video-frame"><iframe src="${esc(youtubeEmbedUrl(v, { autoplay, mute }))}" title="参考動画" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`;
  }
  return `<div class="video-frame"><video src="${esc(v.src)}" ${autoplay ? 'autoplay' : ''} ${mute ? 'muted' : ''} loop playsinline controls></video></div>`;
}

// ───── ステッパー（− 値 ＋） ─────
export function stepperHtml(name, value, fmt = (v) => v) {
  return `<div class="stepper" data-stepper="${name}">
    <button type="button" data-step="-1" aria-label="減らす">−</button>
    <output>${esc(fmt(value))}</output>
    <button type="button" data-step="1" aria-label="増やす">＋</button>
  </div>`;
}

// root 内の data-stepper をまとめて処理。spec: { name: { min, max, step, fmt } }
export function bindSteppers(root, values, spec, onChange) {
  for (const el of $$('[data-stepper]', root)) {
    const name = el.dataset.stepper;
    const s = spec[name];
    if (!s) continue;
    const out = $('output', el);
    let timer = null;
    let repeated = false;
    const change = (dir) => {
      const v = Math.min(s.max, Math.max(s.min, values[name] + dir * s.step));
      if (v === values[name]) return;
      values[name] = v;
      out.textContent = (s.fmt || String)(v);
      onChange(name, v);
    };
    for (const btn of $$('button', el)) {
      const dir = Number(btn.dataset.step);
      btn.addEventListener('click', () => {
        if (repeated) repeated = false;
        else change(dir);
      });
      // 長押しで連続変更
      btn.addEventListener('pointerdown', () => {
        clearInterval(timer);
        repeated = false;
        timer = setTimeout(() => {
          timer = setInterval(() => {
            repeated = true;
            change(dir);
          }, 90);
        }, 450);
      });
      for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) btn.addEventListener(ev, () => (clearTimeout(timer), clearInterval(timer)));
    }
  }
}

// ───── トースト ─────
let toastTimer = 0;
export function toast(msg) {
  $('.toast')?.remove();
  const el = document.createElement('div');
  el.className = 'toast';
  el.setAttribute('role', 'status');
  el.textContent = msg;
  document.body.append(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 2200);
}

// ───── ボトムシート ─────
export function openSheet(html, onMount, onClose) {
  const backdrop = document.createElement('div');
  backdrop.className = 'sheet-backdrop';
  backdrop.innerHTML = `<div class="sheet" role="dialog" aria-modal="true"><div class="grabber"></div>${html}</div>`;
  let open = true;
  const close = () => {
    if (!open) return;
    open = false;
    backdrop.remove();
    document.removeEventListener('keydown', onKey);
    onClose?.();
  };
  const onKey = (e) => e.key === 'Escape' && close();
  backdrop.addEventListener('click', (e) => e.target === backdrop && close());
  document.addEventListener('keydown', onKey);
  document.body.append(backdrop);
  onMount?.($('.sheet', backdrop), close);
  return close;
}

// 確認ダイアログ（ブラウザ標準の confirm の代わり）。OKなら true を返す
export function confirmSheet(message, { detail = '', ok = 'OK', cancel = 'キャンセル', danger = false } = {}) {
  return new Promise((resolve) => {
    let result = false;
    openSheet(
      `<h2>${esc(message)}</h2>
       ${detail ? `<p class="muted small" style="margin:4px 0 0">${esc(detail)}</p>` : ''}
       <div class="btn-row" style="margin-top:18px">
         <button class="btn" data-cancel>${esc(cancel)}</button>
         <button class="btn ${danger ? 'btn-danger-fill' : 'btn-primary'}" data-ok>${esc(ok)}</button>
       </div>`,
      (sheet, close) => {
        const okBtn = $('[data-ok]', sheet);
        okBtn.addEventListener('click', () => {
          result = true;
          close();
        });
        $('[data-cancel]', sheet).addEventListener('click', close);
        okBtn.focus();
      },
      () => resolve(result),
    );
  });
}
