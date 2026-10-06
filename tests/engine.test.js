import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildTimeline, menuSeconds, formatClock, formatMinutes, Session } from '../js/engine.js';

const tabata = { work: 20, rest: 10, laps: 2, lapRest: 0, exercises: ['a', 'b', 'c', 'd'] };

test('タバタ（4種目×2周）は ワーク8本・レスト7本 になる', () => {
  const segs = buildTimeline(tabata, { prep: 10 });
  const types = segs.map((s) => s.type);
  assert.equal(types[0], 'prep');
  assert.equal(types.at(-1), 'done');
  assert.equal(types.filter((t) => t === 'work').length, 8);
  assert.equal(types.filter((t) => t === 'rest').length, 7);
  assert.equal(types.filter((t) => t === 'lapRest').length, 0);
  assert.deepEqual(
    segs.filter((s) => s.type === 'work').map((s) => s.ex),
    ['a', 'b', 'c', 'd', 'a', 'b', 'c', 'd'],
  );
  // 最後のワークの後に休憩は入らない
  assert.equal(segs.at(-2).type, 'work');
});

test('休憩中は次の種目を指す', () => {
  const segs = buildTimeline(tabata, { prep: 5 });
  assert.equal(segs[0].ex, 'a');
  const firstRest = segs.find((s) => s.type === 'rest');
  assert.equal(firstRest.ex, 'b');
});

test('周間休憩を指定すると周の切れ目だけ置き換わる', () => {
  const segs = buildTimeline({ ...tabata, lapRest: 60 }, { prep: 0 });
  const lapRests = segs.filter((s) => s.type === 'lapRest');
  assert.equal(lapRests.length, 1);
  assert.equal(lapRests[0].dur, 60);
  assert.equal(lapRests[0].ex, 'a');
  assert.equal(segs[0].type, 'work');
});

test('開始時刻と合計時間が一致する', () => {
  const segs = buildTimeline({ ...tabata, lapRest: 30 }, { prep: 10 });
  const total = segs.reduce((s, x) => s + x.dur, 0);
  assert.equal(segs.at(-1).start, total);
  assert.equal(total - 10, menuSeconds({ ...tabata, lapRest: 30 }));
  assert.equal(menuSeconds(tabata), 8 * 20 + 7 * 10);
});

test('休憩0秒ならレストを挟まない', () => {
  const segs = buildTimeline({ ...tabata, rest: 0, laps: 1 }, { prep: 0 });
  assert.deepEqual(
    segs.map((s) => s.type),
    ['work', 'work', 'work', 'work', 'done'],
  );
});

test('種目なしは即完了', () => {
  assert.deepEqual(buildTimeline({ ...tabata, exercises: [] }).map((s) => s.type), ['done']);
  assert.equal(menuSeconds({ ...tabata, exercises: [] }), 0);
});

test('時間の表示', () => {
  assert.equal(formatClock(0), '0:00');
  assert.equal(formatClock(65), '1:05');
  assert.equal(formatClock(-3), '0:00');
  assert.equal(formatMinutes(0), '0分');
  assert.equal(formatMinutes(45), '45秒');
  assert.equal(formatMinutes(240), '4分');
  assert.equal(formatMinutes(270), '4.5分');
});

test('Session: 時間経過で進み、一時停止中は止まる', () => {
  const segs = buildTimeline({ work: 20, rest: 10, laps: 1, lapRest: 0, exercises: ['a', 'b'] }, { prep: 5 });
  const s = new Session(segs);
  s.start(0);
  assert.equal(s.seg.type, 'prep');
  s.advance(4000);
  assert.equal(s.seg.type, 'prep');
  assert.equal(Math.ceil(s.remaining(4000)), 1);
  s.advance(5000);
  assert.equal(s.seg.type, 'work');
  s.pause(10000);
  s.advance(60000);
  assert.equal(s.seg.type, 'work');
  assert.equal(s.remaining(60000), 15);
  s.resume(60000);
  s.advance(75000); // ワーク(20秒)終了 → レスト
  assert.equal(s.seg.type, 'rest');
  // バックグラウンドから戻ったときなど、まとめて進める
  const passed = s.advance(200000);
  assert.equal(s.finished, true);
  assert.deepEqual(passed.map((x) => x.type), ['work', 'done']);
  assert.deepEqual(s.workDone(200000), { count: 2, sec: 40 });
});

test('Session: スキップしたワークは実施分だけ記録する', () => {
  const segs = buildTimeline({ work: 20, rest: 10, laps: 1, lapRest: 0, exercises: ['a', 'b'] }, { prep: 0 });
  const s = new Session(segs);
  s.start(0);
  s.jump(s.i + 1, 5000); // 5秒で次へ
  assert.equal(s.seg.type, 'rest');
  assert.deepEqual(s.workDone(5000), { count: 0, sec: 5 });
  s.jump(s.i + 1, 6000);
  s.advance(26000);
  assert.equal(s.finished, true);
  assert.deepEqual(s.workDone(26000), { count: 1, sec: 25 });
  assert.equal(s.totalDuration, 50);
});
