// 種目ライブラリと種目詳細
import { EXERCISES, EXERCISE_BY_ID, LR_LABEL, youtubeSearchUrl } from '../data/exercises.js';
import { PARTS, LEVELS } from '../data/parts.js';
import { allMenus, videoFor, setVideo } from '../store.js';
import { parseVideo } from '../video.js';
import { $, $$, esc, icon, partTag, levelDots, figSlot, mountFigures, videoEmbedHtml, toast } from '../ui.js';

let filter = 'all';

export function exercisesView() {
  const list = EXERCISES.filter((ex) => filter === 'all' || ex.parts.includes(filter));
  return {
    title: '種目',
    sub: `${EXERCISES.length}種目のお手本`,
    html: `
      <div class="chip-row" role="toolbar" aria-label="部位で絞り込み">
        <button class="chip" data-filter="all" aria-pressed="${filter === 'all'}">すべて</button>
        ${PARTS.map((p) => `<button class="chip" data-filter="${p.id}" aria-pressed="${filter === p.id}"><span class="dot" style="--c:${p.color}"></span>${esc(p.short)}</button>`).join('')}
      </div>
      <div class="ex-grid section">
        ${list
          .map(
            (ex) => `<a class="card ex-card" href="#/exercise/${ex.id}">
              ${figSlot(ex.id, 'anim', 'fig-box')}
              <h3>${esc(ex.name)}</h3>
              <div class="meta">${levelDots(ex.level)}${ex.parts.map(partTag).join('')}${videoFor(ex.id) ? icon('video') : ''}</div>
            </a>`,
          )
          .join('')}
      </div>`,
    mount(root, ctx) {
      mountFigures(root);
      for (const b of $$('[data-filter]', root)) {
        b.addEventListener('click', () => {
          filter = b.dataset.filter;
          ctx.rerender();
        });
      }
    },
  };
}

export function exerciseView({ id }) {
  const ex = EXERCISE_BY_ID[id];
  if (!ex) return { title: '種目', back: '#/exercises', html: '<div class="empty">種目が見つかりません</div>' };
  const url = videoFor(id);
  const inMenus = allMenus().filter((m) => m.exercises.includes(id));
  return {
    title: ex.name,
    back: '#/exercises',
    html: `
      <div class="demo">
        ${figSlot(ex.id, 'anim', 'fig-fill')}
        <div class="speed" role="group" aria-label="再生速度">
          <button data-speed="0.5" aria-pressed="false">0.5x</button>
          <button data-speed="1" aria-pressed="true">1x</button>
        </div>
      </div>
      <div class="section" style="margin-top:14px">
        <div class="meta">${ex.parts.map(partTag).join('')}${levelDots(ex.level)}<span>${LEVELS[ex.level].label}</span>${ex.lr ? `<span class="tag">${LR_LABEL[ex.lr]}</span>` : ''}</div>
        <h2 style="font-size:24px;font-weight:800;margin:6px 0 2px">${esc(ex.name)}</h2>
        <p style="margin:0;font-weight:700">${esc(ex.cue)}</p>
      </div>

      <div class="card section">
        <h2 style="font-size:16px">やり方</h2>
        <ol class="steps">${ex.steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
        <h2 style="font-size:16px;margin-top:14px">ポイント</h2>
        <ul class="tips">${ex.tips.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
        <h2 style="font-size:16px;margin-top:14px">きついときは</h2>
        <p style="margin:6px 0 0">${esc(ex.easy)}</p>
      </div>

      <div class="card section">
        <div class="section-head"><h2>${icon('video')} 動画でも確認</h2></div>
        ${
          url
            ? `${videoEmbedHtml(url, { autoplay: false, mute: false })}
               <p class="muted small" style="margin:8px 0 10px">この動画はワークアウト中にも表示されます（アニメと切り替え可）。</p>`
            : `<p class="muted small" style="margin:0 0 10px">YouTube などで気に入った解説動画のURLを登録すると、ワークアウト中にお手本アニメの代わりにその動画を流せます。</p>`
        }
        <a class="btn btn-block" href="${esc(youtubeSearchUrl(ex))}" target="_blank" rel="noopener">${icon('external')}YouTubeで「${esc(ex.name.replace(/（.*?）/g, ''))} やり方」を探す</a>
        <form data-video-form style="margin-top:12px">
          <label class="field" style="margin-bottom:8px"><span>動画のURL（YouTube / mp4）</span>
            <input class="input" name="url" type="url" inputmode="url" placeholder="https://youtu.be/..." value="${esc(url)}">
          </label>
          <div class="btn-row">
            <button class="btn btn-primary" type="submit">${url ? '更新' : '登録'}</button>
            ${url ? '<button class="btn btn-danger" type="button" data-act="remove-video">削除</button>' : ''}
          </div>
        </form>
      </div>

      ${
        inMenus.length
          ? `<div class="section">
              <div class="section-head"><h2>この種目を使うメニュー</h2></div>
              <div class="card" style="padding:4px 14px">
                ${inMenus.map((m) => `<a class="ex-row" href="#/menu/${esc(m.id)}"><div class="body"><h4>${esc(m.name)}</h4></div>${partTag(m.part)}</a>`).join('')}
              </div>
            </div>`
          : ''
      }`,
    mount(root, ctx) {
      const [fig] = mountFigures($('.demo', root));
      for (const b of $$('[data-speed]', root)) {
        b.addEventListener('click', () => {
          fig.speed = Number(b.dataset.speed);
          for (const x of $$('[data-speed]', root)) x.setAttribute('aria-pressed', String(x === b));
        });
      }
      $('[data-video-form]', root).addEventListener('submit', (e) => {
        e.preventDefault();
        const value = e.target.url.value.trim();
        if (!value) {
          setVideo(id, '');
          ctx.rerender();
          return;
        }
        if (!parseVideo(value)) {
          toast('YouTube の動画URL か mp4 などの動画ファイルURLを入力してください');
          return;
        }
        setVideo(id, value);
        toast('動画を登録しました');
        ctx.rerender();
      });
      $('[data-act="remove-video"]', root)?.addEventListener('click', () => {
        setVideo(id, '');
        toast('動画を削除しました');
        ctx.rerender();
      });
    },
  };
}
