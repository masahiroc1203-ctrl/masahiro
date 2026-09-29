// タバタ式タイマーのタイムライン生成（DOM非依存）
//
// menu: { work, rest, laps, lapRest, exercises: [id...] }
//   work    … 1種目の運動時間(秒)
//   rest    … 種目間の休憩(秒)
//   laps    … 何周するか
//   lapRest … 周と周の間の休憩(秒)。0 のときは通常の rest を使う

export const PHASE_LABEL = {
  prep: '準備',
  work: 'ワーク',
  rest: 'レスト',
  lapRest: '周間休憩',
  done: '完了',
};

export function buildTimeline(menu, { prep = 10 } = {}) {
  const ex = menu.exercises;
  if (!ex.length) return [{ type: 'done', dur: 0, start: 0 }];
  const laps = Math.max(1, menu.laps | 0);
  const total = ex.length * laps;
  const segs = [];
  if (prep > 0) segs.push({ type: 'prep', dur: prep, ex: ex[0] });
  let n = 0;
  for (let lap = 0; lap < laps; lap++) {
    for (let i = 0; i < ex.length; i++) {
      n++;
      segs.push({ type: 'work', dur: menu.work, ex: ex[i], lap, pos: i, index: n, total });
      const lastInLap = i === ex.length - 1;
      if (lastInLap && lap === laps - 1) continue;
      const next = lastInLap ? ex[0] : ex[i + 1];
      if (lastInLap && menu.lapRest > 0) segs.push({ type: 'lapRest', dur: menu.lapRest, ex: next, lap });
      else if (menu.rest > 0) segs.push({ type: 'rest', dur: menu.rest, ex: next, lap });
    }
  }
  segs.push({ type: 'done', dur: 0 });
  let t = 0;
  for (const s of segs) {
    s.start = t;
    t += s.dur;
  }
  return segs;
}

// 準備時間を除いたメニューの所要時間(秒)
export function menuSeconds(menu) {
  const n = menu.exercises.length;
  if (!n) return 0;
  const laps = Math.max(1, menu.laps | 0);
  const works = n * laps * menu.work;
  const restsInLap = (n - 1) * menu.rest;
  const between = menu.lapRest > 0 ? menu.lapRest : menu.rest;
  return works + restsInLap * laps + between * (laps - 1);
}

export function formatClock(sec) {
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

export function formatMinutes(sec) {
  const m = sec / 60;
  if (!sec) return '0分';
  if (m < 1) return `${Math.round(sec)}秒`;
  const r = Math.round(m * 2) / 2;
  return `${r % 1 ? r.toFixed(1) : r}分`;
}

// 再生中の状態を扱う小さなクラス（時刻は外から渡す＝テストしやすい）
export class Session {
  constructor(segs) {
    this.segs = segs;
    this.i = 0;
    this.segStart = null; // 現在セグメント開始時刻(ms)
    this.pausedAt = null;
    this.doneCount = 0; // 実際にこなしたワーク区間
    this.doneSec = 0;
  }
  get seg() {
    return this.segs[this.i];
  }
  get finished() {
    return this.seg.type === 'done';
  }
  start(now) {
    this.segStart = now;
    this.pausedAt = null;
  }
  get paused() {
    return this.pausedAt != null;
  }
  pause(now) {
    if (!this.paused) this.pausedAt = now;
  }
  resume(now) {
    if (this.paused) {
      this.segStart += now - this.pausedAt;
      this.pausedAt = null;
    }
  }
  elapsed(now) {
    return ((this.paused ? this.pausedAt : now) - this.segStart) / 1000;
  }
  remaining(now) {
    return Math.max(0, this.seg.dur - this.elapsed(now));
  }
  // 時間経過で次へ進める。進んだセグメントの配列を返す
  advance(now) {
    const passed = [];
    while (!this.finished && !this.paused && this.elapsed(now) >= this.seg.dur) {
      if (this.seg.type === 'work') {
        this.doneCount++;
        this.doneSec += this.seg.dur;
      }
      this.segStart += this.seg.dur * 1000;
      this.i++;
      passed.push(this.seg);
    }
    return passed;
  }
  // スキップ／戻る。途中までのワークは実施分だけ記録する
  jump(i, now) {
    if (this.seg.type === 'work') {
      const sec = Math.min(this.seg.dur, this.elapsed(now));
      this.doneSec += sec;
      if (sec >= this.seg.dur / 2) this.doneCount++;
    }
    this.i = Math.min(Math.max(0, i), this.segs.length - 1);
    this.segStart = now;
    if (this.paused) this.pausedAt = now;
  }
  // 全体の経過(秒)
  totalElapsed(now) {
    return this.seg.start + Math.min(this.seg.dur, this.elapsed(now));
  }
  get totalDuration() {
    return this.segs[this.segs.length - 1].start;
  }
  // 実施したワーク区間の数と合計秒
  workDone(now) {
    let { doneCount: count, doneSec: sec } = this;
    if (this.seg.type === 'work') {
      const cur = Math.min(this.seg.dur, this.elapsed(now));
      sec += cur;
      if (cur >= this.seg.dur / 2) count++;
    }
    return { count, sec };
  }
}
