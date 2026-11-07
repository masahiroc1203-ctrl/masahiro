#!/usr/bin/env bash
# STL とプレビュー画像を winder.scad から再生成する。
# 必要: openscad（画像出力はヘッドレス環境なら xvfb-run も）
#   ./build.sh            # STL + 画像
#   ./build.sh stl        # STL のみ
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p stl images

run() { if command -v xvfb-run >/dev/null 2>&1 && [ -z "${DISPLAY:-}" ]; then xvfb-run -a openscad "$@"; else openscad "$@"; fi; }

for p in sprocket housing cover cap stopper; do
  echo "== stl/$p.stl"
  openscad -D "part=\"$p\"" -o "stl/$p.stl" winder.scad
done

[ "${1:-}" = "stl" ] && exit 0

img() { # name part camera(tx,ty,tz,rx,ry,rz,dist) [extra...]
  local name=$1 part=$2 cam=$3; shift 3
  echo "== images/$name.png"
  # 追加オプション（--render 等）は -o より前に置く（2021.01 の引数解釈対策）
  run -D "part=\"$part\"" "$@" -o "images/$name.png" --imgsize=1200,900 --viewall --autocenter \
      --camera="$cam" --colorscheme=Tomorrow winder.scad
}
img assembly       assembly       0,0,0,70,0,50,0
img assembly_open  assembly_open  0,0,0,70,0,50,0
img assembly_back  assembly       0,0,0,70,0,230,0
img section        section        0,0,0,0,0,0,0 --projection=o
img sprocket       sprocket       0,0,0,140,0,20,0 --render
img stopper        stopper        0,0,0,50,0,30,0 --render
