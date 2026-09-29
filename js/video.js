// 種目ごとに登録する参考動画URLの解釈
const YT_ID = /^[A-Za-z0-9_-]{11}$/;

function parseStart(v) {
  if (!v) return 0;
  if (/^\d+$/.test(v)) return Number(v);
  const m = v.match(/(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?/);
  return m ? Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0) : 0;
}

// → { type: 'youtube', id, start } | { type: 'file', src } | null
export function parseVideo(input) {
  const raw = String(input || '').trim();
  if (!raw) return null;
  let url;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (!/^https?:$/.test(url.protocol)) return null;
  const host = url.hostname.replace(/^(www|m|music)\./, '');
  let id = null;
  if (host === 'youtu.be') id = url.pathname.slice(1).split('/')[0];
  else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    if (url.pathname === '/watch') id = url.searchParams.get('v');
    else {
      const m = url.pathname.match(/^\/(?:shorts|embed|live|v)\/([^/?#]+)/);
      if (m) id = m[1];
    }
  }
  if (id && YT_ID.test(id)) {
    return { type: 'youtube', id, start: parseStart(url.searchParams.get('t') || url.searchParams.get('start')) };
  }
  if (/\.(mp4|webm|m4v|mov|ogv)$/i.test(url.pathname)) return { type: 'file', src: url.href };
  return null;
}

export function youtubeEmbedUrl({ id, start }, { autoplay = true, mute = true, loop = true } = {}) {
  const p = new URLSearchParams({
    playsinline: '1',
    rel: '0',
    modestbranding: '1',
    autoplay: autoplay ? '1' : '0',
    mute: mute ? '1' : '0',
  });
  if (loop) {
    p.set('loop', '1');
    p.set('playlist', id);
  }
  if (start) p.set('start', String(start));
  return `https://www.youtube-nocookie.com/embed/${id}?${p}`;
}
