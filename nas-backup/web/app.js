'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const el = {
    owner: $('owner'),
    dest: $('dest-preview'),
    input: $('file-input'),
    inputAny: $('file-input-any'),
    pick: $('pick'),
    pickAlt: $('pick-alt'),
    summary: $('summary'),
    total: $('c-total'),
    size: $('c-size'),
    done: $('c-done'),
    skip: $('c-skip'),
    err: $('c-err'),
    overall: $('overall'),
    overallBar: $('overall-bar'),
    overallText: $('overall-text'),
    speed: $('speed'),
    retry: $('retry-btn'),
    clear: $('clear-btn'),
    notice: $('notice'),
    list: $('list'),
    start: $('start-btn'),
    disk: $('disk'),
    diskFree: $('disk-free'),
    diskUsed: $('disk-used'),
  };

  const WORKERS = 2;          // 同時に送るファイル数
  const MAX_RETRY = 8;        // 通信エラー時の再試行回数
  const STALL_MS = 30000;     // この時間進まなければ通信をやり直す
  const MAX_THUMBS = 300;     // サムネイルを表示する最大枚数 (メモリ節約)

  const state = {
    items: [],
    running: false,
    stopRequested: false,
    chunkSize: 8 * 1024 * 1024,
    layout: 'date',
    thumbs: 0,
    samples: [],
    wakeLock: null,
    checkedOwner: '',      // 「バックアップ済み」を確認したときの保存先フォルダ名
    startAfterCheck: false, // 確認中に開始ボタンが押された
  };

  // ------------------------------------------------------------ util

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function fmtBytes(n) {
    if (!Number.isFinite(n)) return '';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(n < 10 ? 1 : 0)) + ' ' + u[i];
  }

  function fmtDuration(sec) {
    if (!Number.isFinite(sec) || sec <= 0) return '';
    if (sec < 60) return `残り約${Math.ceil(sec)}秒`;
    if (sec < 3600) return `残り約${Math.ceil(sec / 60)}分`;
    return `残り約${(sec / 3600).toFixed(1)}時間`;
  }

  function storageGet(key) {
    try { return localStorage.getItem(key) || ''; } catch { return ''; }
  }
  function storageSet(key, value) {
    try { localStorage.setItem(key, value); } catch { /* プライベートモード等 */ }
  }

  class HttpError extends Error {
    constructor(status, body, message) {
      super(message || (body && body.error) || `HTTP ${status}`);
      this.status = status;
      this.body = body;
    }
    // 再試行しても直らないエラーか
    get fatal() {
      return this.status === 507 || (this.status >= 400 && this.status < 500 && ![404, 408, 409, 429].includes(this.status));
    }
  }

  async function api(method, url, body) {
    let res;
    try {
      res = await fetch(url, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
        cache: 'no-store',
        credentials: 'same-origin',
      });
    } catch (e) {
      throw new HttpError(0, null, 'NASに接続できません');
    }
    let data = null;
    try { data = await res.json(); } catch { /* 空レスポンス */ }
    if (!res.ok) throw new HttpError(res.status, data);
    return data;
  }

  function showNotice(text, kind) {
    el.notice.textContent = text;
    el.notice.className = 'notice' + (kind ? ' ' + kind : '');
    el.notice.hidden = !text;
  }

  // ------------------------------------------------------------ status / 設定

  function owner() {
    return el.owner.value.trim();
  }

  function updateDest() {
    const o = owner().replace(/[\\/:*?"<>|]/g, '_').replace(/^[.\s]+|[.\s]+$/g, '');
    let p = '/' + (o ? o + '/' : '');
    if (state.layout === 'date') {
      const d = new Date();
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      p += `${y}/${y}-${m}/`;
    }
    el.dest.textContent = p + 'IMG_0001.JPG' + (state.layout === 'date' ? '（撮影年月ごと）' : '');
  }

  async function loadStatus() {
    try {
      const s = await api('GET', 'api/status');
      if (s.chunkSize) state.chunkSize = s.chunkSize;
      if (s.layout) state.layout = s.layout;
      if (s.totalBytes) {
        el.disk.hidden = false;
        el.diskFree.textContent = `空き ${fmtBytes(s.freeBytes)} / ${fmtBytes(s.totalBytes)}`;
        el.diskUsed.style.width = ((1 - s.freeBytes / s.totalBytes) * 100).toFixed(1) + '%';
      }
      if (el.notice.dataset.offline) {
        delete el.notice.dataset.offline;
        showNotice('');
      }
    } catch (e) {
      el.notice.dataset.offline = '1';
      showNotice('NASに接続できません。スマホが家のWi-Fiにつながっているか確認してください。', 'error');
    }
    updateDest();
  }

  // ------------------------------------------------------------ ファイル一覧

  const STATUS_TEXT = {
    waiting: '待機中',
    checking: '確認中…',
    uploading: '送信中',
    done: '完了',
    exists: 'バックアップ済み',
    error: '失敗',
  };

  function isVideo(file) {
    return file.type.startsWith('video/') || /\.(mov|mp4|m4v|3gp|avi|mkv|webm)$/i.test(file.name);
  }

  function addFiles(files) {
    const known = new Set(state.items.map((i) => i.key));
    const added = [];
    for (const file of files) {
      const key = `${file.name}\u0000${file.size}\u0000${file.lastModified}`;
      if (known.has(key)) continue;
      known.add(key);
      const item = {
        key,
        file,
        status: 'checking',
        uploadId: null,
        offset: 0,
        sent: 0,
        path: '',
        error: '',
        note: '',
        thumbUrl: null,
        xhr: null,
        lastProgress: 0,
      };
      item.row = renderRow(item);
      state.items.push(item);
      added.push(item);
    }
    if (added.length) {
      el.list.prepend(...added.map((i) => i.row.li).reverse());
      checkExisting(added);
    }
    refresh();
  }

  function renderRow(item) {
    const li = document.createElement('li');
    li.className = 'item';
    const thumb = document.createElement('div');
    thumb.className = 'thumb';
    if (isVideo(item.file)) {
      thumb.textContent = '🎬';
    } else if (state.thumbs < MAX_THUMBS) {
      state.thumbs++;
      item.thumbUrl = URL.createObjectURL(item.file);
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.decoding = 'async';
      img.alt = '';
      img.src = item.thumbUrl;
      img.onerror = () => { thumb.textContent = '🖼️'; };
      thumb.append(img);
    } else {
      thumb.textContent = '🖼️';
    }
    const meta = document.createElement('div');
    meta.className = 'meta';
    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = item.file.name;
    const sub = document.createElement('div');
    sub.className = 'sub';
    const st = document.createElement('span');
    st.className = 'state';
    const size = document.createElement('span');
    size.textContent = fmtBytes(item.file.size);
    sub.append(st, size);
    const bar = document.createElement('div');
    bar.className = 'bar';
    const fill = document.createElement('div');
    bar.append(fill);
    meta.append(name, sub, bar);
    li.append(thumb, meta);
    return { li, st, fill };
  }

  function updateRow(item) {
    const { li, st, fill } = item.row;
    li.className = 'item ' + item.status;
    const size = item.file.size;
    let text = STATUS_TEXT[item.status];
    let pct = 0;
    switch (item.status) {
      case 'uploading':
        pct = size ? (item.sent / size) * 100 : 100;
        text = item.note || `${text} ${Math.floor(pct)}%`;
        break;
      case 'done':
        pct = 100;
        if (item.path) text += ' → ' + item.path;
        break;
      case 'exists':
        pct = 100;
        break;
      case 'error':
        pct = size ? (item.sent / size) * 100 : 0;
        text += ': ' + item.error;
        break;
      case 'waiting':
        pct = size ? (item.offset / size) * 100 : 0;
        if (item.offset > 0) text = `一時停止中 ${Math.floor(pct)}%`;
        break;
    }
    st.textContent = text;
    fill.style.width = Math.min(100, pct).toFixed(1) + '%';
  }

  async function checkExisting(items) {
    const o = owner();
    state.checkedOwner = o;
    for (let i = 0; i < items.length; i += 1000) {
      const batch = items.slice(i, i + 1000);
      try {
        const res = await api('POST', 'api/check', {
          owner: o,
          files: batch.map((it) => ({ name: it.file.name, size: it.file.size })),
        });
        res.files.forEach((r, j) => {
          const it = batch[j];
          if (it.status !== 'checking') return;
          it.status = r.exists ? 'exists' : 'waiting';
          it.path = r.path || '';
        });
      } catch (e) {
        // 確認できなくても送信時にもう一度確認されるので待機扱いにする
        batch.forEach((it) => { if (it.status === 'checking') it.status = 'waiting'; });
      }
      refresh();
    }
    if (state.startAfterCheck && !state.items.some((i) => i.status === 'checking')) {
      state.startAfterCheck = false;
      run();
    }
  }

  function pending() {
    return state.items.filter((i) => i.status === 'waiting' || i.status === 'error');
  }

  // ------------------------------------------------------------ 表示の更新

  let rafQueued = false;
  function refresh() {
    if (rafQueued) return;
    rafQueued = true;
    requestAnimationFrame(() => {
      rafQueued = false;
      render();
    });
  }

  function render() {
    const items = state.items;
    items.forEach(updateRow);

    el.summary.hidden = items.length === 0;
    const count = (s) => items.filter((i) => i.status === s).length;
    el.total.textContent = items.length;
    el.size.textContent = fmtBytes(items.reduce((a, i) => a + i.file.size, 0));
    el.done.textContent = count('done');
    el.skip.textContent = count('exists');
    const errors = count('error');
    el.err.textContent = errors;

    // 全体の進捗 (バックアップ済みを除いた分)
    const target = items.filter((i) => i.status !== 'exists' && i.status !== 'checking');
    const totalBytes = target.reduce((a, i) => a + i.file.size, 0);
    const sentBytes = target.reduce((a, i) => a + (i.status === 'done' ? i.file.size : i.sent), 0);
    const pct = totalBytes ? (sentBytes / totalBytes) * 100 : 100;
    el.overall.hidden = target.length === 0;
    el.overallBar.style.width = pct.toFixed(1) + '%';
    el.overallText.textContent = totalBytes ? `${fmtBytes(sentBytes)} / ${fmtBytes(totalBytes)}` : '';

    if (state.running) {
      const now = performance.now();
      state.samples.push({ t: now, b: sentBytes });
      while (state.samples.length > 2 && now - state.samples[0].t > 8000) state.samples.shift();
      const first = state.samples[0];
      const dt = (now - first.t) / 1000;
      const rate = dt > 1 ? (sentBytes - first.b) / dt : 0;
      el.speed.textContent = rate > 0
        ? `${fmtBytes(rate)}/s · ${fmtDuration((totalBytes - sentBytes) / rate)}`
        : '';
    } else {
      el.speed.textContent = '';
    }

    el.retry.hidden = state.running || errors === 0;
    el.clear.disabled = state.running;
    el.owner.disabled = state.running;
    el.pick.classList.toggle('disabled', state.running);
    el.pickAlt.classList.toggle('disabled', state.running);

    const p = pending();
    const btn = el.start;
    btn.classList.toggle('stop', state.running);
    if (state.running) {
      btn.disabled = state.stopRequested;
      btn.textContent = state.stopRequested ? '停止しています…' : '停止する';
    } else if (items.some((i) => i.status === 'checking')) {
      btn.disabled = state.startAfterCheck;
      btn.textContent = state.startAfterCheck ? 'まもなく開始します…' : 'NASを確認しています…';
    } else if (p.length) {
      btn.disabled = false;
      const bytes = p.reduce((a, i) => a + i.file.size - i.offset, 0);
      btn.textContent = `バックアップ開始（${p.length}件・${fmtBytes(bytes)}）`;
    } else {
      btn.disabled = true;
      btn.textContent = items.length ? 'すべてバックアップ済みです' : '写真・動画を選んでください';
    }
  }

  // ------------------------------------------------------------ アップロード

  function putChunk(item, start, end) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      item.xhr = xhr;
      item.lastProgress = Date.now();
      xhr.open('PUT', `api/uploads/${encodeURIComponent(item.uploadId)}`);
      xhr.setRequestHeader('Upload-Offset', String(start));
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.upload.onprogress = (ev) => {
        item.lastProgress = Date.now();
        item.sent = start + ev.loaded;
        refresh();
      };
      xhr.onload = () => {
        item.xhr = null;
        let body = null;
        try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
        if (xhr.status >= 200 && xhr.status < 300 && body) resolve(body);
        else reject(new HttpError(xhr.status, body));
      };
      xhr.onerror = xhr.onabort = () => {
        item.xhr = null;
        reject(new HttpError(0, null, '通信が中断されました'));
      };
      xhr.send(item.file.slice(start, end));
    });
  }

  async function uploadItem(item) {
    const file = item.file;
    item.status = 'uploading';
    item.error = '';
    item.note = '';
    item.sent = item.offset;
    let attempt = 0;
    refresh();

    for (;;) {
      if (state.stopRequested) {
        item.status = 'waiting';
        return;
      }
      try {
        if (!item.uploadId) {
          const r = await api('POST', 'api/uploads', {
            name: file.name,
            size: file.size,
            lastModified: file.lastModified,
            owner: owner(),
          });
          if (r.status === 'exists' || r.status === 'done') {
            item.status = r.status;
            item.path = r.path || '';
            item.sent = item.offset = file.size;
            return;
          }
          item.uploadId = r.id;
          item.offset = item.sent = r.offset;
        }
        const end = Math.min(item.offset + state.chunkSize, file.size);
        const r = await putChunk(item, item.offset, end);
        attempt = 0;
        item.note = '';
        item.offset = item.sent = r.offset;
        if (r.status === 'done') {
          item.status = 'done';
          item.path = r.path || '';
          return;
        }
        if (r.offset >= file.size) item.uploadId = null; // 念のため状態を取り直す
      } catch (e) {
        if (e.status === 409 && e.body && typeof e.body.offset === 'number') {
          // サーバーが受け取り済みの位置から続ける
          item.offset = item.sent = e.body.offset;
          continue;
        }
        if (e.fatal) {
          item.status = 'error';
          item.error = e.message;
          return;
        }
        attempt++;
        if (attempt > MAX_RETRY) {
          item.status = 'error';
          item.error = e.message + '（再試行してください）';
          return;
        }
        item.note = `再接続を待っています… (${attempt}/${MAX_RETRY})`;
        refresh();
        await sleep(Math.min(30000, 1000 * 2 ** (attempt - 1)));
        item.uploadId = null; // 再開位置をサーバーに問い合わせる
      } finally {
        refresh();
      }
    }
  }

  async function run() {
    if (state.running) return;
    if (state.items.some((i) => i.status === 'checking')) {
      // 確認が終わったら自動で開始する
      state.startAfterCheck = true;
      refresh();
      return;
    }
    const queue = pending();
    if (!queue.length) return;
    queue.forEach((i) => { if (i.status === 'error') i.status = 'waiting'; });
    state.running = true;
    state.stopRequested = false;
    state.samples = [];
    showNotice('送信中は画面を開いたままにしてください。');
    acquireWakeLock();
    refresh();

    const worker = async () => {
      while (!state.stopRequested) {
        const item = queue.shift();
        if (!item) return;
        if (item.status !== 'waiting') continue;
        await uploadItem(item);
      }
    };
    await Promise.all(Array.from({ length: WORKERS }, worker));

    const stopped = state.stopRequested;
    state.running = false;
    state.stopRequested = false;
    releaseWakeLock();
    loadStatus();

    const items = state.items;
    const done = items.filter((i) => i.status === 'done').length;
    const errors = items.filter((i) => i.status === 'error').length;
    if (stopped) {
      showNotice('停止しました。「バックアップ開始」で続きから再開できます。');
    } else if (errors) {
      showNotice(`${errors}件のファイルが失敗しました。「失敗したファイルを再試行」を押してください。`, 'error');
    } else {
      showNotice(`バックアップが完了しました（新規 ${done}件）。`, 'ok');
      if (navigator.vibrate) navigator.vibrate(200);
    }
    refresh();
  }

  function stop() {
    state.stopRequested = true;
    refresh();
  }

  // 通信が止まったまま進まない場合 (スリープ復帰後など) はやり直す
  setInterval(() => {
    if (!state.running) return;
    const now = Date.now();
    for (const item of state.items) {
      if (item.xhr && now - item.lastProgress > STALL_MS) item.xhr.abort();
    }
  }, 5000);

  // ------------------------------------------------------------ スリープ防止 (HTTPS 環境のみ有効)

  async function acquireWakeLock() {
    try {
      if ('wakeLock' in navigator && document.visibilityState === 'visible') {
        state.wakeLock = await navigator.wakeLock.request('screen');
      }
    } catch { /* 非対応 */ }
  }

  function releaseWakeLock() {
    if (state.wakeLock) {
      state.wakeLock.release().catch(() => {});
      state.wakeLock = null;
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (state.running) {
      acquireWakeLock();
      // バックグラウンド中に止まった通信をすぐやり直す
      for (const item of state.items) if (item.xhr && Date.now() - item.lastProgress > 5000) item.xhr.abort();
    } else {
      loadStatus();
    }
  });

  // ------------------------------------------------------------ イベント

  for (const input of [el.input, el.inputAny]) {
    input.addEventListener('change', () => {
      if (input.files && input.files.length) addFiles(Array.from(input.files));
      input.value = ''; // 同じファイルを選び直せるようにする
    });
  }

  el.start.addEventListener('click', () => (state.running ? stop() : run()));

  el.retry.addEventListener('click', () => run());

  el.clear.addEventListener('click', () => {
    if (state.running) return;
    for (const i of state.items) if (i.thumbUrl) URL.revokeObjectURL(i.thumbUrl);
    state.items = [];
    state.thumbs = 0;
    state.startAfterCheck = false;
    el.list.textContent = '';
    showNotice('');
    refresh();
  });

  el.owner.value = storageGet('owner');
  el.owner.addEventListener('input', () => {
    storageSet('owner', owner());
    updateDest();
  });
  el.owner.addEventListener('change', () => {
    if (owner() === state.checkedOwner) return;
    // 保存先が変わったので、未送信のファイルを確認し直す
    const targets = state.items.filter((i) => i.status === 'waiting' || i.status === 'exists' || i.status === 'error');
    targets.forEach((i) => { i.status = 'checking'; i.uploadId = null; i.offset = i.sent = 0; });
    if (targets.length) checkExisting(targets);
    refresh();
  });

  window.addEventListener('beforeunload', (e) => {
    if (state.running) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

  loadStatus();
  refresh();
})();
