// 記録と設定
import { PARTS } from '../data/parts.js';
import { formatMinutes } from '../engine.js';
import {
  state,
  save,
  weekKey,
  dayKey,
  formatWeekRange,
  logsInWeek,
  partBalance,
  deleteLog,
  setSetting,
  resetAll,
} from '../store.js';
import { play, speak, unlockAudio, buzz } from '../audio.js';
import { hr, hrAvailable, hrScan, hrStopScan, hrConnect, hrDisconnect, currentBpm, onHr } from '../hr.js';
import { $, $$, esc, icon, partTag, stepperHtml, bindSteppers, toast, confirmSheet, openSheet } from '../ui.js';

export function historyView() {
  const wk = weekKey();
  const month = dayKey().slice(0, 7);
  const logs = state.logs;
  const totalSec = logs.reduce((s, l) => s + (l.sec || 0), 0);
  const balance = partBalance(logs, wk, 4);
  const maxBal = Math.max(1, ...Object.values(balance));
  const weeks = [...new Set([...logs.map((l) => l.week), ...Object.keys(state.weeks).filter((k) => state.weeks[k].parts?.length)])]
    .filter((k) => k <= wk)
    .sort()
    .reverse();

  return {
    title: '記録',
    actions: `<a class="icon-btn" href="#/settings" aria-label="設定">${icon('sliders')}</a>`,
    html: `
      <div class="stats">
        <div class="card stat"><b>${logsInWeek(logs, wk).length}</b><span>今週（回）</span></div>
        <div class="card stat"><b>${logs.filter((l) => l.day.startsWith(month)).length}</b><span>今月（回）</span></div>
        <div class="card stat"><b>${Math.round(totalSec / 60)}</b><span>累計（分）</span></div>
      </div>

      <section class="section card">
        <div class="section-head"><h2>部位バランス</h2><span class="muted small">直近4週の回数</span></div>
        <div class="balance">
          ${PARTS.map(
            (p) => `<div class="balance-row" style="--c:${p.color}">
              <span>${p.icon} ${esc(p.short)}</span>
              <div class="bar"><i style="width:${(balance[p.id] / maxBal) * 100}%"></i></div>
              <span class="num" style="text-align:right">${balance[p.id]}回</span>
            </div>`,
          ).join('')}
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h2>週ごとの記録</h2></div>
        ${
          weeks.length
            ? `<div class="card" style="padding:4px 16px">${weeks
                .map((k) => {
                  const wl = logsInWeek(logs, k);
                  const parts = state.weeks[k]?.parts || [];
                  const sec = wl.reduce((s, l) => s + (l.sec || 0), 0);
                  return `<div class="week-item">
                    <div class="head">
                      <b class="small">${k === wk ? '今週　' : ''}${esc(formatWeekRange(k))}</b>
                      <span class="small muted num">${wl.length}回・${formatMinutes(sec)}</span>
                    </div>
                    <div class="meta" style="margin-top:4px">${parts.length ? `強化部位 ${parts.map(partTag).join('')}` : '<span>強化部位：未設定</span>'}</div>
                    ${
                      wl.length
                        ? `<ul class="log-list">${wl
                            .slice()
                            .reverse()
                            .map(
                              (l) => `<li>
                                <span>${esc(l.day.slice(5).replace('-', '/'))}　<b>${esc(l.menuName)}</b>${l.completed ? '' : ' <span class="muted">（途中まで）</span>'}</span>
                                <span class="num">${formatMinutes(l.sec)}
                                  <button class="icon-btn" style="width:28px;height:28px" data-del="${esc(l.id)}" aria-label="この記録を削除">${icon('close')}</button>
                                </span>
                              </li>`,
                            )
                            .join('')}</ul>`
                        : ''
                    }
                  </div>`;
                })
                .join('')}</div>`
            : `<div class="card empty">まだ記録がありません。<br>メニューを1つやってみましょう！<br><br><a class="btn btn-primary" href="#/">ホームへ</a></div>`
        }
      </section>`,
    mount(root, ctx) {
      for (const b of $$('[data-del]', root)) {
        b.addEventListener('click', async () => {
          if (!(await confirmSheet('この記録を削除しますか？', { ok: '削除する', danger: true }))) return;
          deleteLog(b.dataset.del);
          ctx.rerender();
        });
      }
    },
  };
}

const SETTING_SPEC = {
  prep: { min: 0, max: 30, step: 5, fmt: (v) => (v ? `${v}秒` : 'なし') },
  goal: { min: 1, max: 7, step: 1, fmt: (v) => `${v}回` },
  soundVol: { min: 1, max: 5, step: 1, fmt: (v) => `${v} / 5` },
  voiceVol: { min: 1, max: 5, step: 1, fmt: (v) => `${v} / 5` },
};

const sw = (key, label, note) => `
  <div class="setting">
    <div class="label"><b>${label}</b>${note ? `<small>${note}</small>` : ''}</div>
    <label class="switch"><input type="checkbox" data-switch="${key}" ${state.settings[key] ? 'checked' : ''} aria-label="${label}"><span></span></label>
  </div>`;

// 近くの機器の一覧から心拍計を選ぶ
function openHrSheet(onPick) {
  let off = () => {};
  openSheet(
    `<h2>心拍計をさがす</h2>
     <p class="muted small" style="margin:4px 0 0">出てこないときは、バンドの「心拍数を共有」がオンになっているか確かめてください。</p>
     <div class="part-options" data-list></div>
     <div class="btn-row">
       <button class="btn" data-rescan>もう一度さがす</button>
       <button class="btn" data-cancel>閉じる</button>
     </div>`,
    (sheet, close) => {
      const list = $('[data-list]', sheet);
      let ran = false; // 実際にさがし始めたか（Bluetooth の許可を待っている間は「見つかりません」と出さない）
      const paint = () => {
        ran ||= hr.scanning;
        const note = hr.scanning ? 'さがしています…' : ran && !hr.devices.length ? '見つかりませんでした' : '';
        list.innerHTML =
          hr.devices
            .map((d) => `<button class="part-option" data-id="${esc(d.id)}"><span class="txt"><b>${esc(d.name)}</b>${d.hr ? '<small>心拍計</small>' : ''}</span></button>`)
            .join('') + (note ? `<p class="muted small" style="margin:0;text-align:center">${note}</p>` : '');
      };
      off = onHr(paint);
      list.addEventListener('click', (e) => {
        const dev = hr.devices.find((d) => d.id === e.target.closest('[data-id]')?.dataset.id);
        if (!dev) return;
        close();
        onPick(dev);
      });
      $('[data-rescan]', sheet).addEventListener('click', hrScan);
      $('[data-cancel]', sheet).addEventListener('click', close);
      hrScan();
      paint();
    },
    () => {
      off();
      hrStopScan();
    },
  );
}

// 設定画面の「心拍計」。さがす → 選ぶ → 心拍数が届いたら登録する
function mountHr(root) {
  const box = $('[data-hr-status]', root);
  const forget = $('[data-act="hr-forget"]', root);
  let picked = null; // 選んだが、まだ心拍数が届いていない機器
  const paint = () => {
    const saved = state.settings.hrDevice;
    forget.classList.toggle('hidden', !saved && hr.status === 'off');
    forget.textContent = saved ? '登録を外す' : 'やめる';
    if (hr.status === 'on') {
      box.innerHTML = `<b>${esc(hr.name)}</b><span class="hr-now">${icon('heart')}<b class="num">${currentBpm() ?? '--'}</b>拍/分</span>`;
    } else if (hr.status === 'connecting') {
      box.innerHTML = `<b>${esc(hr.name)}</b><span class="muted small">つないでいます…</span>`;
    } else if (saved) {
      box.innerHTML = `<b>${esc(saved.name)}</b><button class="btn" data-act="hr-test">つないで確かめる</button>`;
    } else {
      box.innerHTML = '<span class="muted small">まだ登録していません</span>';
    }
  };
  // この画面が描き直されて root が外れたら、登録したものを片づける
  function stop() {
    window.removeEventListener('hashchange', leave);
    clearInterval(timer);
    off();
  }
  // 画面を離れたら切る（ワークアウトでは player.js がつなぎ直す）
  function leave() {
    stop();
    hrDisconnect();
  }
  const off = onHr((_, type) => {
    if (!root.isConnected) return stop();
    if (type === 'error') {
      picked = null;
      toast(hr.error);
    } else if (type === 'data' && picked) {
      setSetting('hrDevice', { id: picked.id, name: picked.name });
      picked = null;
      toast('心拍計を登録しました');
    }
    paint();
  });
  // 値が届かなくなったときに古い数字を出したままにしない
  const timer = setInterval(() => {
    if (!root.isConnected) stop();
    else if (hr.status === 'on') paint();
  }, 1000);
  window.addEventListener('hashchange', leave);
  root.addEventListener('click', (e) => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'hr-scan') {
      openHrSheet((dev) => {
        picked = dev;
        hrConnect(dev);
      });
    } else if (act === 'hr-test') {
      hrConnect(state.settings.hrDevice);
    } else if (act === 'hr-forget') {
      picked = null;
      setSetting('hrDevice', null);
      hrDisconnect();
      paint();
    }
  });
  paint();
}

export function settingsView() {
  const s = state.settings;
  // すでにアプリとして開いている（ホーム画面から起動・Android アプリ版）なら、追加のしかたの案内は出さない
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone || window.HiitNative;
  return {
    title: '設定',
    back: '#/',
    html: `
      <div class="card">
        <div class="settings-list">
          <div class="setting"><div class="label"><b>準備時間</b><small>スタート前のカウントダウン</small></div>${stepperHtml('prep', s.prep, SETTING_SPEC.prep.fmt)}</div>
          <div class="setting"><div class="label"><b>週の目標</b><small>ホームの進み具合に使います</small></div>${stepperHtml('goal', s.goal, SETTING_SPEC.goal.fmt)}</div>
          ${sw('sound', 'ビープ音', '3・2・1 のカウントと切り替え音')}
          <div class="setting"><div class="label"><b>ビープ音の音量</b><small>変えると試しに鳴ります</small></div>${stepperHtml('soundVol', s.soundVol, SETTING_SPEC.soundVol.fmt)}</div>
          ${sw('voice', '音声ガイド', '「レスト。次は〇〇」などを読み上げ')}
          <div class="setting"><div class="label"><b>音声ガイドの音量</b><small>5 が端末の音量いっぱい</small></div>${stepperHtml('voiceVol', s.voiceVol, SETTING_SPEC.voiceVol.fmt)}</div>
          ${sw('vibrate', 'バイブレーション', '対応している端末のみ（Androidなど）')}
          ${sw('videoFirst', '登録した動画を優先', '動画URLを登録した種目は、ワークアウト中に動画を表示')}
        </div>
        <button class="btn btn-block" style="margin-top:12px" data-act="test">${icon('sound')}音と声をテスト</button>
      </div>

      ${
        hrAvailable()
          ? `<div class="card section">
              <h2 style="font-size:16px;margin-bottom:6px">心拍計</h2>
              <p class="small muted" style="margin:0 0 10px">Bluetooth の心拍計を登録すると、ワークアウト中に今の心拍数が出ます。Xiaomi Smart Band は、バンドの「設定 → 心拍数を共有」をオンにしてからさがしてください。</p>
              <div class="hr-status" data-hr-status></div>
              <div class="btn-row" style="margin-top:10px">
                <button class="btn" data-act="hr-scan">${icon('heart')}心拍計をさがす</button>
                <button class="btn" data-act="hr-forget"></button>
              </div>
            </div>`
          : ''
      }

      ${
        standalone
          ? ''
          : `<div class="card section">
              <h2 style="font-size:16px">ホーム画面に追加するとアプリのように使えます</h2>
              <p class="small muted" style="margin:6px 0 0"><b>iPhone（Safari）</b>：共有ボタン → 「ホーム画面に追加」<br><b>Android（Chrome）</b>：メニュー（︙） → 「ホーム画面に追加」<br>追加するとオフラインでも使えます。</p>
            </div>`
      }

      <div class="card section">
        <h2 style="font-size:16px;margin-bottom:10px">データ</h2>
        <p class="small muted" style="margin:0 0 10px">記録・自作メニュー・動画URLはこの端末に保存されます。機種変更のときはバックアップを使ってください。</p>
        <div class="btn-row">
          <button class="btn" data-act="export">バックアップを保存</button>
          <label class="btn">読み込む<input type="file" accept="application/json,.json" data-import hidden></label>
        </div>
        <button class="btn btn-danger btn-block" style="margin-top:10px" data-act="reset">すべてのデータを消去</button>
      </div>
      <p class="small muted" style="text-align:center;margin-top:18px">HIIT Weekly</p>`,
    mount(root, ctx) {
      if (hrAvailable()) mountHr(root);
      const values = { prep: s.prep, goal: s.goal, soundVol: s.soundVol, voiceVol: s.voiceVol };
      bindSteppers(root, values, SETTING_SPEC, (name, v) => {
        setSetting(name, v);
        // 音量は変えたその場で鳴らして確かめられるようにする（スイッチがオフでも鳴らす）
        if (name === 'soundVol') {
          unlockAudio();
          play('go', true, v);
        } else if (name === 'voiceVol') {
          unlockAudio();
          speak('スタート', true, v);
        }
      });
      for (const input of $$('[data-switch]', root)) {
        input.addEventListener('change', () => setSetting(input.dataset.switch, input.checked));
      }
      root.addEventListener('click', async (e) => {
        const act = e.target.closest('[data-act]')?.dataset.act;
        if (act === 'test') {
          unlockAudio();
          play('tick', state.settings.sound, state.settings.soundVol);
          setTimeout(() => play('go', state.settings.sound, state.settings.soundVol), 400);
          buzz(200, state.settings.vibrate);
          speak('レスト。次は、スクワット', state.settings.voice, state.settings.voiceVol);
          if (!state.settings.sound && !state.settings.voice) toast('ビープ音と音声ガイドがオフになっています');
        } else if (act === 'export') {
          const json = JSON.stringify(state, null, 2);
          const name = `hiit-weekly-${dayKey()}.json`;
          // Android アプリ版はダウンロードが使えないので、保存先を選ぶ画面を出す
          if (window.HiitNative) return window.HiitNative.saveFile(name, json);
          const blob = new Blob([json], { type: 'application/json' });
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = name;
          a.click();
          setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        } else if (act === 'reset') {
          const ok = await confirmSheet('すべてのデータを消去しますか？', {
            detail: '記録・自作メニュー・動画URL・設定が消えます。元に戻せません。',
            ok: '消去する',
            danger: true,
          });
          if (ok) {
            resetAll();
            toast('消去しました');
            ctx.rerender();
          }
        }
      });
      $('[data-import]', root).addEventListener('change', async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        try {
          const data = JSON.parse(await file.text());
          if (!data || typeof data !== 'object' || !Array.isArray(data.logs)) throw new Error('format');
          const ok = await confirmSheet('バックアップを読み込みますか？', { detail: '今のデータは置き換わります。', ok: '読み込む' });
          if (!ok) return;
          for (const key of ['weeks', 'logs', 'custom', 'overrides', 'videos']) if (data[key]) state[key] = data[key];
          if (data.settings) Object.assign(state.settings, data.settings);
          save();
          toast('読み込みました');
          ctx.rerender();
        } catch {
          toast('読み込めませんでした（形式が違います）');
        }
      });
    },
  };
}

