// 保存データ（localStorage）と週の計算
import { PRESET_MENUS } from './data/menus.js';
import { PARTS } from './data/parts.js';

const KEY = 'hiit-weekly:v1';

export const DEFAULT_SETTINGS = {
  prep: 10, // 開始前の準備秒数
  sound: true, // ビープ音
  soundVol: 4, // ビープ音の音量（1〜5）
  voice: true, // 音声ガイド
  voiceVol: 5, // 音声ガイドの音量（1〜5）
  vibrate: true, // バイブ（対応端末のみ）
  goal: 3, // 週の目標回数
  videoFirst: true, // 動画を登録した種目は動画で表示
};

// 音量（1〜5）→ 倍率。ビープ音は 3 が最初の版の大きさで、5 が歪まない上限（一番大きい音の振幅が 1 になる）。
// 音声は端末のメディア音量に対する割合なので、5 より大きくはできない
const BEEP_GAIN = [0.35, 0.6, 1, 1.7, 2.85];
const VOICE_GAIN = [0.25, 0.4, 0.6, 0.8, 1];
const levelOf = (v, fallback) => Math.min(5, Math.max(1, Math.round(Number(v)) || fallback));
export const beepGain = (v) => BEEP_GAIN[levelOf(v, DEFAULT_SETTINGS.soundVol) - 1];
export const voiceGain = (v) => VOICE_GAIN[levelOf(v, DEFAULT_SETTINGS.voiceVol) - 1];

const blank = () => ({
  settings: { ...DEFAULT_SETTINGS },
  weeks: {}, // { '2026-09-28': { parts: ['lower'] } }
  logs: [], // 実施記録
  custom: [], // 自作メニュー
  overrides: {}, // プリセットの時間設定の上書き { menuId: { work, rest, laps, lapRest } }
  videos: {}, // 種目ごとの動画URL { exerciseId: url }
});

// ───── 日付ユーティリティ（ローカル時刻・月曜はじまり） ─────
const pad = (n) => String(n).padStart(2, '0');
export const dayKey = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const parseDay = (key) => {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d);
};
export function weekKey(date = new Date()) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const offset = (d.getDay() + 6) % 7; // 月=0 … 日=6
  d.setDate(d.getDate() - offset);
  return dayKey(d);
}
export function addDays(key, n) {
  const d = parseDay(key);
  d.setDate(d.getDate() + n);
  return dayKey(d);
}
export const WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日'];
const WD = ['日', '月', '火', '水', '木', '金', '土'];
export const shortDate = (key) => {
  const d = parseDay(key);
  return `${d.getMonth() + 1}/${d.getDate()}(${WD[d.getDay()]})`;
};
export const formatWeekRange = (wk) => `${shortDate(wk)}〜${shortDate(addDays(wk, 6))}`;

// ───── 集計（純粋関数） ─────
export function logsInWeek(logs, wk) {
  return logs.filter((l) => l.week === wk);
}

// しばらく強化していない部位ほど前に並べる（週の強化部位と実施記録の両方を見る）
export function suggestParts(state, currentWeek) {
  const last = Object.fromEntries(PARTS.map((p) => [p.id, '']));
  for (const [wk, w] of Object.entries(state.weeks)) {
    if (wk >= currentWeek) continue;
    for (const id of w.parts || []) if (wk > last[id]) last[id] = wk;
  }
  for (const l of state.logs) {
    if (l.week >= currentWeek) continue;
    for (const id of l.parts || []) if (l.week > (last[id] ?? '')) last[id] = l.week;
  }
  return PARTS.map((p) => p.id).sort((a, b) => (last[a] < last[b] ? -1 : last[a] > last[b] ? 1 : 0));
}

// 直近 n 週の部位ごとの実施回数
export function partBalance(logs, currentWeek, weeks = 4) {
  const from = addDays(currentWeek, -7 * (weeks - 1));
  const count = Object.fromEntries(PARTS.map((p) => [p.id, 0]));
  for (const l of logs) {
    if (l.week < from || l.week > currentWeek) continue;
    for (const id of l.parts || []) if (id in count) count[id]++;
  }
  return count;
}

// ───── 永続化 ─────
function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return blank();
    const data = JSON.parse(raw);
    const b = blank();
    return { ...b, ...data, settings: { ...b.settings, ...(data.settings || {}) } };
  } catch {
    return blank();
  }
}

export const state = typeof localStorage === 'undefined' ? blank() : load();

export function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // 保存できない環境（プライベートモード等）では何もしない
  }
}

export function setSetting(key, value) {
  state.settings[key] = value;
  save();
}

export function weekParts(wk) {
  return state.weeks[wk]?.parts || [];
}
export function setWeekParts(wk, parts) {
  state.weeks[wk] = { ...(state.weeks[wk] || {}), parts };
  save();
}

export function addLog(entry) {
  state.logs.push(entry);
  save();
}
export function deleteLog(id) {
  state.logs = state.logs.filter((l) => l.id !== id);
  save();
}

export function videoFor(exId) {
  return state.videos[exId] || '';
}
export function setVideo(exId, url) {
  if (url) state.videos[exId] = url;
  else delete state.videos[exId];
  save();
}

// ───── メニュー ─────
const TIMING = ['work', 'rest', 'laps', 'lapRest'];

export function allMenus() {
  return [...PRESET_MENUS.map(withOverride), ...state.custom];
}
export function getMenu(id) {
  const preset = PRESET_MENUS.find((m) => m.id === id);
  if (preset) return withOverride(preset);
  return state.custom.find((m) => m.id === id) || null;
}
export const isCustom = (id) => state.custom.some((m) => m.id === id);

function withOverride(menu) {
  const o = state.overrides[menu.id];
  return o ? { ...menu, ...o, edited: true } : menu;
}

export function setTiming(id, timing) {
  const custom = state.custom.find((m) => m.id === id);
  const pick = Object.fromEntries(TIMING.map((k) => [k, timing[k]]));
  if (custom) Object.assign(custom, pick);
  else state.overrides[id] = pick;
  save();
}
export function resetTiming(id) {
  delete state.overrides[id];
  save();
}

export function saveCustomMenu(menu) {
  const i = state.custom.findIndex((m) => m.id === menu.id);
  if (i >= 0) state.custom[i] = menu;
  else state.custom.push(menu);
  save();
}
export function deleteCustomMenu(id) {
  state.custom = state.custom.filter((m) => m.id !== id);
  save();
}

export function resetAll() {
  Object.assign(state, blank());
  save();
}

export const uid = (prefix = '') => `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
