import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseHeartRate, receive, hr, currentBpm, onHr } from '../js/hr.js';

test('心拍の通知から 拍/分 を取り出す（1バイト・2バイト・不正な値）', () => {
  assert.equal(parseHeartRate('0048'), 72); // 値は1バイト
  assert.equal(parseHeartRate('16a5e803'), 165); // 接触検出つき・RR間隔つきでも2バイト目が値
  assert.equal(parseHeartRate('012c01'), 300); // bit0 = 1 なら2バイト（下位が先）
  assert.equal(parseHeartRate('0000'), null); // 0 は測れていない
  assert.equal(parseHeartRate('01ff'), null); // 2バイトのはずが足りない
  for (const bad of ['', '00', '0g48', '048', null, undefined, 72]) assert.equal(parseHeartRate(bad), null);
});

test('受け取った値は接続中だけ使い、5秒届かなければ出さない', () => {
  receive('status', { status: 'on' });
  receive('data', { hex: '0096' });
  assert.equal(hr.bpm, 150);
  assert.equal(currentBpm(hr.at + 1000), 150);
  assert.equal(currentBpm(hr.at + 6000), null);
  receive('data', { hex: '0000' }); // 測れていない通知では前の値を消さない
  assert.equal(hr.bpm, 150);
  receive('status', { status: 'connecting' }); // 切れてつなぎ直している間
  assert.equal(currentBpm(hr.at), null);
});

test('見つかった機器は重ねて出さず、心拍計だと名乗るものを上に並べる', () => {
  const seen = [];
  const off = onHr((_, type) => seen.push(type));
  hr.devices = [];
  receive('device', { id: 'A', name: 'イヤホン', hr: false });
  receive('device', { id: 'B', name: 'Band', hr: false });
  receive('device', { id: 'A', name: 'イヤホン', hr: false }); // 同じものは知らせない
  receive('device', { id: 'B', name: 'Band', hr: true }); // あとから心拍計だと分かった
  off();
  receive('device', { id: 'C', name: '解除後', hr: false });
  assert.deepEqual(hr.devices.slice(0, 2), [
    { id: 'B', name: 'Band', hr: true },
    { id: 'A', name: 'イヤホン', hr: false },
  ]);
  assert.equal(seen.length, 3);
});
