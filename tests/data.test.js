import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EXERCISES, EXERCISE_BY_ID } from '../js/data/exercises.js';
import { PRESET_MENUS } from '../js/data/menus.js';
import { PARTS, LEVELS } from '../js/data/parts.js';
import { frameAt, computeJoints, solveIK, LIMB_KEYS, VIEW, BODY } from '../js/pose.js';

const partIds = new Set(PARTS.map((p) => p.id));

test('種目データがそろっている', () => {
  assert.equal(new Set(EXERCISES.map((e) => e.id)).size, EXERCISES.length, 'IDが重複していない');
  for (const ex of EXERCISES) {
    assert.ok(ex.name && ex.cue && ex.easy, ex.id);
    assert.ok(ex.steps.length >= 2 && ex.tips.length >= 1, ex.id);
    assert.ok(ex.parts.length && ex.parts.every((p) => partIds.has(p)), `${ex.id} の部位`);
    assert.ok(LEVELS[ex.level], `${ex.id} のレベル`);
    assert.ok(['side', 'front'].includes(ex.anim.view), ex.id);
    assert.ok(ex.anim.k.length >= 1 && ex.anim.ms > 0, ex.id);
  }
});

test('どの部位にも種目とメニューがある', () => {
  for (const p of PARTS) {
    assert.ok(EXERCISES.filter((e) => e.parts.includes(p.id)).length >= 5, `${p.id} の種目`);
    assert.ok(PRESET_MENUS.filter((m) => m.part === p.id).length >= 2, `${p.id} のメニュー`);
  }
});

test('プリセットメニューは存在する種目だけを使う', () => {
  assert.equal(new Set(PRESET_MENUS.map((m) => m.id)).size, PRESET_MENUS.length);
  for (const m of PRESET_MENUS) {
    assert.ok(partIds.has(m.part), m.id);
    assert.ok(m.exercises.length >= 3, m.id);
    for (const id of m.exercises) assert.ok(EXERCISE_BY_ID[id], `${m.id}: ${id}`);
    for (const k of ['work', 'rest', 'laps', 'lapRest']) assert.ok(Number.isInteger(m[k]) && m[k] >= 0, `${m.id}.${k}`);
    assert.ok(m.work > 0 && m.laps > 0, m.id);
  }
});

test('すべての種目のアニメが破綻しない（NaNなし・枠内・床にめり込まない）', () => {
  for (const ex of EXERCISES) {
    for (let i = 0; i < 60; i++) {
      const j = frameAt(ex.anim, (ex.anim.ms * i) / 60);
      const pts = [j.hip, j.shoulder, j.head, ...LIMB_KEYS.flatMap((k) => j[k])];
      for (const [x, y] of pts) {
        assert.ok(Number.isFinite(x) && Number.isFinite(y), `${ex.id} NaN`);
        assert.ok(x > -2 && x < VIEW.w + 2, `${ex.id} x=${x.toFixed(1)} が枠外`);
        assert.ok(y > -2 && y <= VIEW.ground + 1.5, `${ex.id} y=${y.toFixed(1)} が床より下`);
      }
      assert.ok(j.head[1] + BODY.head <= VIEW.ground + 1.5, `${ex.id} 頭が床にめり込む`);
    }
  }
});

test('IK指定の手足は目標位置に届く（届く距離の場合）', () => {
  const r = solveIK([0, 0], [10, 20], 17, 17, 1);
  assert.ok(Math.hypot(r.end[0] - 10, r.end[1] - 20) < 1e-6);
  assert.ok(Math.abs(Math.hypot(r.mid[0], r.mid[1]) - 17) < 1e-6);
  // 膝は前(右)に出る
  assert.ok(r.mid[0] > 5);
  // 届かない距離なら伸びきる
  const far = solveIK([0, 0], [0, 100], 17, 17, 1);
  assert.ok(Math.abs(far.end[1] - 34) < 0.01);
});

test('キーフレームで床に置いた手足は床に接している', () => {
  for (const ex of EXERCISES) {
    for (const k of ex.anim.k) {
      const j = computeJoints({ ...k, nk: k.nk ?? k.t }, ex.anim.view);
      for (const key of LIMB_KEYS) {
        const spec = k[key];
        if (Array.isArray(spec) || spec.p[1] < 90) continue;
        const end = j[key][2];
        const miss = Math.hypot(end[0] - spec.p[0], end[1] - spec.p[1]);
        assert.ok(miss < 2.5, `${ex.id} ${key} が目標から ${miss.toFixed(1)} 離れている`);
      }
    }
  }
});
