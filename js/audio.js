// 効果音・音声ガイド・バイブ
import { beepGain, voiceGain } from './store.js';

let ctx = null;
let scale = 1; // いま鳴らす音の音量倍率（play() が設定する）
let voice = null;
// Android アプリ版（android/）では WebView に無い読み上げ・スリープ防止をアプリ側の機能で行う
const native = window.HiitNative;

// iOS では最初のタップ中に音声系を有効化しておく必要がある
export function unlockAudio() {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC && !ctx) ctx = new AC();
    if (ctx && ctx.state === 'suspended') ctx.resume();
    if (ctx) tone(0, 0.01, 0); // 無音を一度鳴らしてロック解除
  } catch {
    ctx = null;
  }
  if ('speechSynthesis' in window) {
    pickVoice();
    window.speechSynthesis.onvoiceschanged = pickVoice;
    const u = new SpeechSynthesisUtterance('');
    u.volume = 0;
    window.speechSynthesis.speak(u);
  }
}

function pickVoice() {
  const voices = window.speechSynthesis.getVoices();
  voice = voices.find((v) => v.lang === 'ja-JP' && /Kyoko|O-ren|Google/.test(v.name)) || voices.find((v) => v.lang?.startsWith('ja')) || null;
}

function tone(freq, dur, vol = 0.25, at = 0) {
  if (!ctx) return;
  const t0 = ctx.currentTime + at;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq || 440;
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(Math.min(1, Math.max(vol * scale, 0.0001)), t0 + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.05);
}

export const SOUNDS = {
  tick: () => tone(880, 0.12, 0.25), // 3・2・1
  go: () => tone(1320, 0.45, 0.35), // ワーク開始
  rest: () => {
    tone(660, 0.18, 0.3);
    tone(520, 0.3, 0.3, 0.2);
  },
  half: () => {
    tone(990, 0.1, 0.25);
    tone(990, 0.1, 0.25, 0.15);
  },
  done: () => {
    [784, 988, 1175, 1568].forEach((f, i) => tone(f, i === 3 ? 0.6 : 0.16, 0.3, i * 0.16));
  },
};

export function play(name, enabled = true, level) {
  if (!enabled) return;
  try {
    if (ctx?.state === 'suspended') ctx.resume();
    scale = beepGain(level);
    SOUNDS[name]?.();
  } catch {
    // 再生失敗は無視
  }
}

export function speak(text, enabled = true, level) {
  if (enabled && native) return native.speak(text, voiceGain(level));
  if (!enabled || !('speechSynthesis' in window)) return;
  try {
    const s = window.speechSynthesis;
    s.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'ja-JP';
    if (voice) u.voice = voice;
    u.rate = 1.05;
    u.volume = voiceGain(level);
    s.speak(u);
  } catch {
    // 読み上げ非対応
  }
}

export function stopSpeech() {
  try {
    native?.stopSpeaking();
    window.speechSynthesis?.cancel();
  } catch {
    // noop
  }
}

export function buzz(pattern, enabled = true) {
  if (enabled && native) return native.vibrate(JSON.stringify(pattern));
  if (enabled && navigator.vibrate) {
    try {
      navigator.vibrate(pattern);
    } catch {
      // noop
    }
  }
}

// 画面スリープ防止
let lock = null;
export async function keepAwake(on) {
  if (native) return native.keepScreenOn(!!on);
  try {
    if (on && 'wakeLock' in navigator) {
      if (!lock || lock.released) lock = await navigator.wakeLock.request('screen');
    } else if (!on && lock) {
      await lock.release();
      lock = null;
    }
  } catch {
    lock = null;
  }
}
