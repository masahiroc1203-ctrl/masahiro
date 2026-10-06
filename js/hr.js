// 心拍計（Bluetooth の心拍センサー。Xiaomi Smart Band の「心拍数を共有」、胸ベルト型など）
// 受信は Android アプリ版（android/.../HeartRate.kt）が行い、結果を window.__hiitHr(種類, 内容) で受け取る。
// ブラウザ版には受信機能が無い。画面の確認用に、URL に ?hrsim=1 を付けると擬似の心拍計が出る

const g = typeof window === 'undefined' ? null : window;
const native = g?.HiitNative?.hrScan ? g.HiitNative : null;
const sim = !native && !!g && /[?&]hrsim=1(&|$)/.test(g.location.search);

// 値が届かなくなってこの時間がたったら表示しない（バンドを外した・共有を切った）
const STALE_MS = 5000;

export const hr = {
  status: 'off', // off | connecting | on
  bpm: null,
  at: 0, // 最後に値が届いた時刻（performance.now()）
  name: '',
  scanning: false,
  devices: [], // さがして見つかったもの [{ id, name, hr }]（hr = 心拍計だと名乗っている）
  error: '',
};

// Heart Rate Measurement（0x2A37）の中身（16進文字列）から 拍/分 を取り出す。
// 先頭1バイトの bit0 が 1 なら値は2バイト（下位が先）。0 は「測れていない」なので null
export function parseHeartRate(hex) {
  if (typeof hex !== 'string' || hex.length < 4 || hex.length % 2 || /[^0-9a-f]/i.test(hex)) return null;
  const b = hex.match(/../g).map((h) => parseInt(h, 16));
  const wide = b[0] & 1;
  if (wide && b.length < 3) return null;
  return (wide ? b[1] | (b[2] << 8) : b[1]) || null;
}

export const hrAvailable = () => !!(native || sim);
export const currentBpm = (now = performance.now()) => (hr.status === 'on' && hr.bpm && now - hr.at < STALE_MS ? hr.bpm : null);

const subs = new Set();
// fn(hr, 種類) を状態が変わるたびに呼ぶ。戻り値を呼ぶと解除
export function onHr(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function receive(type, d = {}) {
  if (type === 'scan') {
    hr.scanning = !!d.on;
  } else if (type === 'device') {
    const known = hr.devices.find((x) => x.id === d.id);
    if (known && (known.hr || !d.hr)) return;
    if (known) known.hr = true;
    else hr.devices.push({ id: d.id, name: d.name, hr: !!d.hr });
    hr.devices.sort((a, b) => b.hr - a.hr); // 心拍計だと名乗っているものを上に
  } else if (type === 'status') {
    hr.status = d.status;
    if (d.status !== 'on') hr.bpm = null;
  } else if (type === 'data') {
    const bpm = parseHeartRate(d.hex);
    if (!bpm) return;
    hr.bpm = bpm;
    hr.at = performance.now();
  } else if (type === 'error') {
    hr.error = d.message || '';
  }
  for (const fn of [...subs]) fn(hr, type);
}

// 擬似の心拍計（95〜165 をゆっくり上下する）
function simSource() {
  let timer = 0;
  let t = 0;
  const beat = () => receive('data', { hex: `00${Math.round(130 + 35 * Math.sin(t++ / 8)).toString(16)}` });
  const stop = () => clearInterval(timer);
  return {
    hrScan() {
      receive('scan', { on: true });
      setTimeout(() => {
        receive('device', { id: 'sim', name: '擬似バンド', hr: true });
        receive('scan', { on: false });
      }, 300);
    },
    hrStopScan: () => receive('scan', { on: false }),
    hrConnect() {
      stop();
      receive('status', { status: 'connecting' });
      setTimeout(() => {
        receive('status', { status: 'on' });
        beat();
        timer = setInterval(beat, 1000);
      }, 200);
    },
    hrDisconnect() {
      stop();
      receive('status', { status: 'off' });
    },
  };
}

const source = native || (sim ? simSource() : null);
if (native) g.__hiitHr = receive;

export function hrScan() {
  hr.devices = [];
  source?.hrScan();
}
export const hrStopScan = () => source?.hrStopScan();
export function hrConnect(dev) {
  hr.name = dev.name;
  source?.hrConnect(dev.id);
}
export const hrDisconnect = () => source?.hrDisconnect();
