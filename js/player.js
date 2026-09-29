// ワークアウト画面（タバタ式タイマー＋お手本デモ）
import { EXERCISE_BY_ID, LR_LABEL } from './data/exercises.js';
import { buildTimeline, Session, PHASE_LABEL, formatClock, formatMinutes } from './engine.js';
import { createFigure } from './figure.js';
import { play, speak, stopSpeech, buzz, keepAwake } from './audio.js';
import { state, addLog, dayKey, weekKey, logsInWeek, uid, videoFor, setSetting } from './store.js';
import { $, esc, icon, partTag, spokenName, videoEmbedHtml, confirmSheet } from './ui.js';

let current = null; // 開いているプレイヤー（同時に1つだけ）

export function openPlayer(menu, { onClose } = {}) {
  if (current) current.destroy();
  const settings = state.settings;
  const segs = buildTimeline(menu, { prep: settings.prep });
  const session = new Session(segs);
  const works = segs.filter((s) => s.type === 'work');
  const multiLap = menu.laps > 1;
  // 各セグメントから見た「次（または現在）のワーク」
  const workAt = [];
  for (let i = segs.length - 1, w = null; i >= 0; i--) {
    if (segs[i].type === 'work') w = segs[i];
    workAt[i] = w;
  }

  const root = document.createElement('div');
  root.className = 'player';
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-label', `${menu.name} ワークアウト`);
  root.innerHTML = `
    <div class="player-inner">
      <div class="p-top">
        <button class="icon-btn" data-act="close" aria-label="終了">${icon('close')}</button>
        <div class="title">${esc(menu.name)}</div>
        <div class="remain" aria-live="off"></div>
      </div>
      <div class="p-progress">${works.map(() => '<i><b></b></i>').join('')}</div>
      <div class="p-main">
        <div class="p-phase"><span class="label"></span><span class="round"></span></div>
        <div class="p-clock" aria-live="off"></div>
        <div class="p-stage">
          <div class="p-demo">
            <span class="badge"></span>
            <button class="src-toggle hidden" data-act="src"></button>
            <div class="demo-body"></div>
            <div class="paused-overlay hidden">一時停止中</div>
          </div>
          <div class="p-ex"><h2></h2><p class="cue"></p></div>
          <div class="p-next"></div>
        </div>
        <div class="p-controls">
          <button data-act="prev" aria-label="前へ">${icon('prev')}</button>
          <button class="main" data-act="toggle" aria-label="一時停止">${icon('pause')}</button>
          <button data-act="next" aria-label="次へ">${icon('next')}</button>
        </div>
      </div>
    </div>`;
  document.body.append(root);
  document.body.style.overflow = 'hidden';

  const ui = {
    remain: $('.remain', root),
    bars: [...root.querySelectorAll('.p-progress i')],
    label: $('.p-phase .label', root),
    round: $('.p-phase .round', root),
    clock: $('.p-clock', root),
    badge: $('.p-demo .badge', root),
    body: $('.demo-body', root),
    paused: $('.paused-overlay', root),
    src: $('.src-toggle', root),
    exName: $('.p-ex h2', root),
    cue: $('.p-ex .cue', root),
    next: $('.p-next', root),
    toggle: $('[data-act="toggle"]', root),
    main: $('.p-main', root),
  };

  let fig = null;
  let shownEx = null;
  let shownSrc = null;
  let lastSec = null;
  let halfDone = false;
  let timer = 0;
  let closed = false;

  const exOf = (seg) => EXERCISE_BY_ID[seg.ex];

  function showDemo(ex, force = false) {
    const url = videoFor(ex.id);
    const src = url && settings.videoFirst ? 'video' : 'anim';
    ui.src.classList.toggle('hidden', !url);
    ui.src.innerHTML = src === 'video' ? `${icon('figure')}アニメ` : `${icon('video')}動画`;
    if (!force && ex === shownEx && src === shownSrc) return;
    shownEx = ex;
    shownSrc = src;
    fig?.destroy();
    fig = null;
    if (src === 'video') {
      ui.body.innerHTML = videoEmbedHtml(url);
      const frame = $('.video-frame', ui.body);
      if (frame) frame.style.width = '100%';
    } else {
      ui.body.replaceChildren();
      fig = createFigure(ex);
      fig.setPaused(session.paused);
      ui.body.append(fig.el);
    }
  }

  function enter(seg, { announce = true } = {}) {
    lastSec = null;
    halfDone = false;
    root.dataset.phase = seg.type;
    ui.label.textContent = PHASE_LABEL[seg.type];
    if (seg.type === 'done') return finish();
    const ex = exOf(seg);
    const w = workAt[session.i];
    showDemo(ex);
    ui.badge.textContent = seg.type === 'work' ? 'いまの種目' : '次の種目';
    ui.exName.innerHTML = `${esc(ex.name)}${ex.lr ? `<span class="lr">${LR_LABEL[ex.lr]}</span>` : ''}`;
    ui.cue.textContent = ex.cue;
    const lap = multiLap ? `${w.lap + 1}周目・` : '';
    ui.round.textContent = `${lap}${w.index} / ${w.total}`;
    const upcoming = segs.slice(session.i + 1).find((s) => s.type === 'work');
    ui.next.textContent = seg.type === 'work' && upcoming ? `次：${exOf(upcoming).name}` : seg.type === 'work' ? 'ラスト！' : '';
    if (!announce) return;
    const name = spokenName(ex);
    if (seg.type === 'prep') {
      speak(`準備してください。最初は、${name}`, settings.voice);
    } else if (seg.type === 'work') {
      play('go', settings.sound);
      buzz(250, settings.vibrate);
      speak(w.index === w.total ? 'ラスト、スタート' : 'スタート', settings.voice);
    } else if (seg.type === 'rest') {
      play('rest', settings.sound);
      buzz([100, 80, 100], settings.vibrate);
      speak(`レスト。次は、${name}`, settings.voice);
    } else if (seg.type === 'lapRest') {
      play('rest', settings.sound);
      buzz([100, 80, 100], settings.vibrate);
      speak(`${seg.lap + 1}周目おわり。${seg.dur}秒休憩。次は、${name}`, settings.voice);
    }
  }

  function render(now) {
    const seg = session.seg;
    if (seg.type === 'done') return;
    const remain = session.remaining(now);
    const sec = Math.ceil(remain - 1e-6);
    ui.clock.textContent = seg.dur >= 60 && sec >= 60 ? formatClock(sec) : String(sec);
    ui.remain.textContent = `残り ${formatClock(session.totalDuration - session.totalElapsed(now))}`;
    // カウントダウン音 3・2・1
    if (sec !== lastSec) {
      if (lastSec !== null && sec <= 3 && sec >= 1 && !session.paused) play('tick', settings.sound);
      lastSec = sec;
    }
    // 左右入れ替え種目は半分でお知らせ
    if (seg.type === 'work' && exOf(seg).lr === 'switch' && !halfDone && remain <= seg.dur / 2) {
      halfDone = true;
      play('half', settings.sound);
      buzz([60, 60, 60], settings.vibrate);
      speak('反対側', settings.voice);
    }
    // 進捗バー
    const w = workAt[session.i];
    const idx = w ? w.index - 1 : works.length;
    ui.bars.forEach((b, i) => {
      b.classList.toggle('done', i < idx);
      const fill = b.firstChild;
      fill.style.width = i === idx && seg.type === 'work' ? `${Math.min(100, (1 - remain / seg.dur) * 100)}%` : '0';
    });
  }

  function tick() {
    const now = performance.now();
    const passed = session.advance(now);
    if (passed.length) enter(session.seg);
    render(now);
  }

  function setPaused(p) {
    const now = performance.now();
    if (p) session.pause(now);
    else session.resume(now);
    fig?.setPaused(p);
    ui.paused.classList.toggle('hidden', !p);
    ui.toggle.innerHTML = icon(p ? 'play' : 'pause');
    ui.toggle.setAttribute('aria-label', p ? '再開' : '一時停止');
    if (p) stopSpeech();
    render(now);
  }

  function jump(i) {
    const now = performance.now();
    session.jump(i, now);
    enter(session.seg, { announce: session.seg.type !== 'done' && !session.paused });
    render(now);
  }

  function prev() {
    const now = performance.now();
    if (session.elapsed(now) > 2) return jump(session.i);
    for (let k = session.i - 1; k >= 0; k--) {
      if (segs[k].type === 'work' || segs[k].type === 'prep') return jump(k);
    }
    jump(0);
  }

  function next() {
    if (!session.finished) jump(session.i + 1);
  }

  function saveLog(completed) {
    const now = performance.now();
    const { count, sec } = session.workDone(now);
    if (!completed && sec < 10) return null;
    const entry = {
      id: uid('log-'),
      at: new Date().toISOString(),
      day: dayKey(),
      week: weekKey(),
      menuId: menu.id,
      menuName: menu.name,
      parts: [menu.part],
      sec: Math.round(sec),
      total: Math.round(session.totalElapsed(now)),
      count: Math.min(count, works.length),
      of: works.length,
      completed,
    };
    addLog(entry);
    return entry;
  }

  function finish() {
    clearInterval(timer);
    fig?.destroy();
    fig = null;
    const entry = saveLog(true);
    play('done', settings.sound);
    buzz([200, 100, 200, 100, 400], settings.vibrate);
    speak('おつかれさまでした！', settings.voice);
    keepAwake(false);
    const weekCount = logsInWeek(state.logs, weekKey()).length;
    ui.bars.forEach((b) => b.classList.add('done'));
    ui.remain.textContent = '';
    ui.main.innerHTML = `
      <div class="p-done">
        <div class="big" aria-hidden="true">🎉</div>
        <h2>おつかれさま！</h2>
        <div>${partTag(menu.part)} <b>${esc(menu.name)}</b> を完走しました</div>
        <div class="sum">
          <div><b class="num">${formatClock(entry.total)}</b><span>トータル</span></div>
          <div><b class="num">${formatMinutes(entry.sec)}</b><span>運動時間</span></div>
          <div><b class="num">${weekCount}回目</b><span>今週</span></div>
        </div>
        <div class="btn-row">
          <button class="btn" data-act="again">もう一度</button>
          <button class="btn btn-primary" data-act="exit">記録を見る</button>
        </div>
      </div>`;
  }

  function destroy() {
    if (closed) return;
    closed = true;
    clearInterval(timer);
    fig?.destroy();
    stopSpeech();
    keepAwake(false);
    document.removeEventListener('visibilitychange', onVisible);
    window.removeEventListener('popstate', onPop);
    root.remove();
    document.body.style.overflow = '';
    if (current === api) current = null;
  }

  // 閉じる前の確認。途中まででも10秒以上やっていれば記録する
  let confirming = false;
  async function requestClose() {
    if (session.finished) return close();
    if (confirming) return;
    confirming = true;
    const wasPaused = session.paused;
    setPaused(true);
    const ok = await confirmSheet('ワークアウトを終了しますか？', {
      detail: 'ここまでの運動は記録されます。',
      ok: '終了する',
      cancel: '続ける',
    });
    confirming = false;
    if (closed) return;
    if (ok) {
      const entry = saveLog(false);
      close(entry ? 'saved' : null);
    } else if (!wasPaused) {
      setPaused(false);
    }
  }

  function close(result) {
    const popped = history.state?.player;
    destroy();
    if (!popped) return onClose?.(result);
    // 積んだ履歴を戻してから次の画面へ（順番が逆だと遷移が打ち消される）
    window.addEventListener('popstate', () => onClose?.(result), { once: true });
    history.back();
  }

  // Android の戻るボタンで閉じられるように履歴を1つ積む（「もう一度」のときは積み直さない）
  if (!history.state?.player) history.pushState({ player: true }, '');
  function onPop() {
    if (closed) return;
    if (session.finished) {
      destroy();
      onClose?.('done');
      return;
    }
    history.pushState({ player: true }, '');
    requestClose();
  }
  window.addEventListener('popstate', onPop);

  function onVisible() {
    if (document.visibilityState === 'visible' && !session.finished) {
      keepAwake(true);
      tick();
    }
  }
  document.addEventListener('visibilitychange', onVisible);

  root.addEventListener('click', (e) => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    if (act === 'close') requestClose();
    else if (act === 'toggle') setPaused(!session.paused);
    else if (act === 'prev') prev();
    else if (act === 'next') next();
    else if (act === 'src') {
      setSetting('videoFirst', !settings.videoFirst);
      showDemo(exOf(session.seg), true);
    } else if (act === 'again') {
      destroy();
      openPlayer(menu, { onClose });
    } else if (act === 'exit') {
      close('history');
    }
  });

  const api = { destroy, root };
  current = api;
  keepAwake(true);
  session.start(performance.now());
  enter(session.seg);
  render(performance.now());
  timer = setInterval(tick, 100);
  return api;
}
