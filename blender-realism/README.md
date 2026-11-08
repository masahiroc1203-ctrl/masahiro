# blender-realism

Blender に読み込んだ家・部屋のモデルを、1回の実行で写真に近い見た目にするスクリプトです。

![箱を組み合わせただけの部屋に実行した結果](sample_render.png)

上の画像は、箱を並べただけのテスト用の部屋（cm 単位の .glb）にこのスクリプトを実行して Cycles で描いたものです（CPU・960×540・200 サンプル）。

## やること

| 項目 | 内容 |
|---|---|
| 単位 | モデルの大きさから mm / cm / m を判定して m にそろえる |
| レンダー | Cycles・GPU 自動選択（OptiX → CUDA → CPU）・ノイズ除去・AgX の色 |
| 光 | 物理ベースの空と、時刻・方角から決めた太陽。ガラスが日差しをさえぎらないよう設定 |
| 明るさ | カメラが室内なら露出 +2.5、外観なら 0 を自動で設定 |
| 材質 | オブジェクト名・マテリアル名から推測して付け替え（下の表）。元の色は生かす |
| 面取り | 家具などの角に 3mm の丸みを付ける |
| 地面・カメラ | 地面がなければ追加。カメラがなければ室内（目線 160cm）と外観の 2 台を作る |

何度実行しても大丈夫です。自動で作ったものは名前が `AUTO_` で始まり、実行のたびに作り直します。元のマテリアルは消しません。

## 必要なもの

- Blender 4.2 以降（5.2 で動作確認済み）
- モデルの形式: .blend / .glb / .gltf / .obj / .fbx / .stl / .ply / .usd

## 使い方（Windows）

### 1. スクリプトをモデルのフォルダに置く

PowerShell で:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/masahiroc1203-ctrl/masahiro/claude/determined-lamport-q4ahej/blender-realism/make_realistic.py" -OutFile "C:\dev\house-3d-model\make_realistic.py"
```

### 2-A. Blender の画面から使う

1. Blender でモデルを開く（.blend 以外は「ファイル → インポート」）
2. 上のタブ「Scripting」→ テキストエディタの「開く」で `make_realistic.py` を選ぶ
3. ▶ ボタン（または Alt+P）で実行
4. F12 でレンダリング

結果の説明はテキストエディタの「REALISM_REPORT」に出ます。設定を変えるときは、ファイル冒頭の `SETTINGS` を書き換えて、もう一度実行します。

### 2-B. コマンドで使う（画面を開かずに画像を作る）

```powershell
$blender = (Get-ChildItem "C:\Program Files\Blender Foundation\*\blender.exe" | Select-Object -Last 1).FullName
```

```powershell
& $blender -b -P "C:\dev\house-3d-model\make_realistic.py" -- --model "C:\dev\house-3d-model\モデルのファイル名.glb" --render "C:\dev\house-3d-model\render.png" --preview
```

`--preview` は下書き（64 サンプル・半分の解像度）です。仕上がりを確かめたら外して本番の画質で描きます。.blend のときは `& $blender -b "house.blend" -P make_realistic.py -- --render out.png` の形でも使えます。

主なオプション:

| オプション | 意味 | 例 |
|---|---|---|
| `--time` | 太陽の時刻（6〜18） | `--time 10` |
| `--south` | モデルの南の向き | `--south +Y` |
| `--camera` | `auto` / `interior` / `exterior` / `keep` | `--camera exterior` |
| `--exposure` | 明るさ（+1 で 2 倍） | `--exposure 3` |
| `--samples` | 画質（多いほどきれいで遅い） | `--samples 512` |
| `--res` | 解像度 | `--res 2560x1440` |
| `--unit-scale` | 単位の判定を上書き（cm なら 0.01） | `--unit-scale 0.01` |
| `--hdri` | 背景に HDRI 画像を使う | `--hdri sky.exr` |
| `--save` | 設定後の .blend を保存 | `--save house_real.blend` |
| `--no-materials` / `--no-bevel` | 材質の付け替え・面取りをしない | |

## 材質が自動で付く名前

オブジェクト名かマテリアル名に次の言葉が入っていると、その材質になります（大文字小文字は区別しません）。上から順に判定するので、`Window_Frame` は「金属」、`Window_Glass` は「ガラス」になります。

| 材質 | 名前に含む言葉（一部） |
|---|---|
| 金属 | frame, sash, handle, metal, 枠, サッシ, 取っ手, アルミ |
| ガラス | glass, window, 窓, ガラス |
| 床（フローリング） | floor, 床, フローリング |
| 壁（しっくい） / 天井 | wall, 壁, クロス / ceiling, 天井 |
| 木 | wood, table, desk, shelf, door, 木, テーブル, 棚, ドア, 家具 |
| 布 | sofa, curtain, bed, rug, ソファ, カーテン, ベッド, ラグ |
| タイル | tile, bath, タイル, 浴室 |
| 屋根・コンクリート・地面 | roof, 屋根 / concrete, 基礎 / ground, grass, 庭, 芝 |
| 植物・樹脂 | plant, leaf, 植物 / tv, テレビ, plastic |

名前から判断できなかったものは、そのまま残してレポートに一覧を出します。照明（lamp, light, 照明）と、画像テクスチャ付きのマテリアルには手を付けません。

## うまくいかないとき

- **暗い・明るすぎる**: `--exposure` で調整（室内は 2〜4 くらい）。日差しを強くするなら `SUN_STRENGTH`、部屋全体を明るくするなら `SKY_STRENGTH` を上げる
- **大きさがおかしい**（家が小人サイズ・巨大）: `--unit-scale` で単位を指定（mm なら 0.001、cm なら 0.01、m なら 1）
- **日差しが入ってこない**: `--south` を実際の南の向きに合わせる。窓の外に壁や屋根があると光は入りません
- **材質が付かない**: オブジェクト名を上の表の言葉を含む名前に変える（例: `Cube.012` → `Floor_LDK`）
- **GPU が使われない**: Blender の「編集 → プリファレンス → システム → Cycles レンダーデバイス」で OptiX か CUDA を選ぶ。GTX 1660 Ti はどちらにも対応しています
