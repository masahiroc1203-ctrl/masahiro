import { test } from 'node:test';
import assert from 'node:assert/strict';
import { weekKey, addDays, dayKey, formatWeekRange, suggestParts, partBalance, logsInWeek, beepGain, voiceGain, DEFAULT_SETTINGS } from '../js/store.js';
import { parseVideo, youtubeEmbedUrl } from '../js/video.js';

test('週は月曜はじまり', () => {
  assert.equal(weekKey(new Date(2026, 8, 28)), '2026-09-28'); // 月
  assert.equal(weekKey(new Date(2026, 9, 4)), '2026-09-28'); // 日
  assert.equal(weekKey(new Date(2026, 9, 5)), '2026-10-05'); // 翌月曜
  assert.equal(weekKey(new Date(2027, 0, 1)), '2026-12-28'); // 年またぎ
  assert.equal(addDays('2026-09-28', 6), '2026-10-04');
  assert.equal(addDays('2026-03-01', -1), '2026-02-28');
  assert.equal(dayKey(new Date(2026, 0, 5)), '2026-01-05');
  assert.equal(formatWeekRange('2026-09-28'), '9/28(月)〜10/4(日)');
});

test('しばらくやっていない部位をおすすめする', () => {
  const state = {
    weeks: {
      '2026-09-07': { parts: ['lower'] },
      '2026-09-14': { parts: ['core'] },
      '2026-09-21': { parts: ['upper'] },
    },
    logs: [{ week: '2026-09-21', parts: ['full'] }],
  };
  const order = suggestParts(state, '2026-09-28');
  assert.equal(order[0], 'back'); // 一度もやっていない
  assert.deepEqual(order.slice(1, 3), ['lower', 'core']);
  // 今週以降の記録は判断に使わない
  state.weeks['2026-09-28'] = { parts: ['back'] };
  assert.equal(suggestParts(state, '2026-09-28')[0], 'back');
});

test('部位バランスは直近の週だけ数える', () => {
  const logs = [
    { week: '2026-09-28', parts: ['lower'] },
    { week: '2026-09-21', parts: ['lower'] },
    { week: '2026-09-07', parts: ['core'] },
    { week: '2026-08-24', parts: ['core'] }, // 5週前なので対象外
  ];
  const b = partBalance(logs, '2026-09-28', 4);
  assert.equal(b.lower, 2);
  assert.equal(b.core, 1);
  assert.equal(logsInWeek(logs, '2026-09-28').length, 1);
});

test('動画URLの解釈', () => {
  assert.deepEqual(parseVideo('https://youtu.be/dQw4w9WgXcQ?t=42'), { type: 'youtube', id: 'dQw4w9WgXcQ', start: 42 });
  assert.equal(parseVideo('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m5s').start, 65);
  assert.equal(parseVideo('https://m.youtube.com/shorts/dQw4w9WgXcQ').id, 'dQw4w9WgXcQ');
  assert.equal(parseVideo('https://www.youtube.com/embed/dQw4w9WgXcQ').id, 'dQw4w9WgXcQ');
  assert.deepEqual(parseVideo('https://example.com/squat.mp4'), { type: 'file', src: 'https://example.com/squat.mp4' });
  assert.equal(parseVideo('https://example.com/page'), null);
  assert.equal(parseVideo('javascript:alert(1)'), null);
  assert.equal(parseVideo('スクワット'), null);
  const url = youtubeEmbedUrl({ id: 'dQw4w9WgXcQ', start: 0 });
  assert.match(url, /^https:\/\/www\.youtube-nocookie\.com\/embed\/dQw4w9WgXcQ\?/);
  assert.match(url, /mute=1/);
  assert.match(url, /playlist=dQw4w9WgXcQ/);
});

test('音量の段階（1〜5）が倍率になる', () => {
  // ビープ音：3 が最初の版と同じ、段階を上げるほど大きく、5 でも一番大きい音（振幅 0.35）が 1 を超えない
  assert.equal(beepGain(3), 1);
  for (let v = 1; v < 5; v++) assert.ok(beepGain(v + 1) > beepGain(v), `beep ${v}`);
  assert.ok(0.35 * beepGain(5) <= 1 && 0.35 * beepGain(5) > 0.95);
  // 音声：5 が端末の音量いっぱい
  assert.equal(voiceGain(5), 1);
  for (let v = 1; v < 5; v++) assert.ok(voiceGain(v + 1) > voiceGain(v), `voice ${v}`);
  // 範囲外・未設定（古い保存データ）は既定値や端の値になる
  assert.equal(beepGain(undefined), beepGain(DEFAULT_SETTINGS.soundVol));
  assert.equal(voiceGain(undefined), voiceGain(DEFAULT_SETTINGS.voiceVol));
  assert.equal(beepGain(9), beepGain(5));
  assert.equal(beepGain(-3), beepGain(1));
  assert.ok(DEFAULT_SETTINGS.soundVol > 3, '初期値は最初の版より大きい');
});
