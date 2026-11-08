# -*- coding: utf-8 -*-
"""
make_realistic.py  -  Blender のモデルを写真に近い見た目にする一括設定スクリプト
対応: Blender 4.2 以降（5.2 で動作確認）

やること
  1. モデルの単位（mm / cm / m）を判定して m にそろえる
  2. Cycles の設定（GPU 自動選択・ノイズ除去・光の跳ね返り・AgX の色）
  3. 空（物理ベースのスカイ）と、時刻・方角から決めた太陽光
  4. 名前（Floor / 壁 / Glass / Sofa など）からマテリアルを推測して、木目・しっくい・ガラス・布などに付け替え
  5. 角に小さな面取り（Bevel）を付けて、角の光り方を本物に近づける
  6. カメラがなければ「室内（目線 160cm）」と「外観」のカメラを作る

使い方（Blender の画面から）
  1. Blender でモデルを開く（.blend）か、下の MODEL_PATH にモデルのファイルを書く
  2. 上のタブ「Scripting」→ テキストエディタの「開く」でこのファイルを選ぶ → ▶（Alt+P）で実行
  3. F12 でレンダリング。結果の説明はテキストエディタの「REALISM_REPORT」に出ます

使い方（コマンドで・画面なし）
  blender -b -P make_realistic.py -- --model "C:\\dev\\house-3d-model\\house.glb" --render "C:\\dev\\house-3d-model\\render.png"
  blender -b "house.blend" -P make_realistic.py -- --render out.png --preview
  DXF も読めます（同じフォルダに dxf2obj.py を置き、Python に ezdxf を入れておく: py -m pip install ezdxf）
  blender -b -P make_realistic.py -- --model house.dxf --render out.png
  2D の図面なら: --dxf-extrude "壁=2400,床=0"（レイヤー名=立ち上げる高さ mm）
  オプション: --samples 256 --time 15.5 --south -Y --res 1920x1080 --camera interior --exposure 0.5
              --hdri sky.exr --unit-scale 0.01 --no-materials --no-bevel --save out.blend --preview
              --dxf-extrude "壁=2400,床=0" --dxf-colors --python "C:\\Python312\\python.exe"

何度実行しても大丈夫です（自動で作ったもの「AUTO_...」は作り直します）。元のマテリアルは消さずに残ります。
"""

import math
import os
import sys
import traceback
import warnings

import bpy
from mathutils import Matrix, Vector

# ============================================================
#  設定（ここを書き換えて使います）
# ============================================================
SETTINGS = dict(
    MODEL_PATH="",            # 例: r"C:\dev\house-3d-model\house.dxf"  空なら今開いているシーンを使う
    DXF_EXTRUDE="",           # DXF が 2D の図面のとき: 例 "壁=2400, 床=0"（レイヤー名=立ち上げる高さ mm、* も使える）
    DXF_COLORS=False,         # DXF の線の色をマテリアルの色に使う（ふつうは線の色＝材質ではないので False）
    PYTHON="",                # DXF 変換に使う Python（空なら py / python を自動で探す）
    UNIT_SCALE=None,          # None=自動判定 / 1=m / 0.01=cm / 0.001=mm
    TIME_OF_DAY=15.5,         # 太陽の時刻（6〜18）。15〜16時は窓から斜めに光が入ってきれい
    SOUTH="-Y",               # モデルの「南」の向き: "+X" "-X" "+Y" "-Y"（Blender の正面図は -Y 側から見ています）
    SUN_STRENGTH=4.0,         # 太陽の強さ
    SKY_STRENGTH=0.35,        # 空の明るさ（室内が暗ければ上げる）
    HDRI_PATH="",             # HDRI 画像（.hdr / .exr）を使うときはパスを書く。空なら物理ベースの空
    HDRI_STRENGTH=1.0,
    EXPOSURE=None,            # 画面全体の明るさ（+1 で 2 倍）。None=自動（カメラが室内なら +2.5、外観なら 0）
    SAMPLES=256,              # 本番 256〜512 / 下書きは --preview で 64
    RESOLUTION=(1920, 1080),
    USE_GPU=True,
    APPLY_MATERIALS=True,
    KEEP_ORIGINAL_COLORS=True,  # 元の色（ソファの色など）を生かす
    SKIP_TEXTURED=True,       # 画像テクスチャ付きのマテリアルは触らない
    ADD_BEVEL=True,
    BEVEL_MM=3.0,             # 面取りの幅（mm）
    ADD_GROUND=True,          # 地面がなければ作る
    CAMERA="auto",            # "auto" / "interior" / "exterior" / "keep"（既存カメラをそのまま使う）
    EYE_HEIGHT=1.6,           # 室内カメラの目の高さ（m）
    DISABLE_OTHER_SUNS=True,  # 元からある太陽ライトは重複しないようにレンダーで隠す
    CLEAR_DEFAULT_SCENE=True, # Blender 起動時のままの立方体・ライト・カメラが残っていたら消す
    RENDER_PATH="",           # 書くとレンダリングして保存する（例: r"C:\dev\house-3d-model\render.png"）
    SAVE_BLEND="",            # 書くと設定後の .blend を保存する
    PREVIEW=False,            # True で下書き（64 サンプル・半分の解像度）
)

# 名前に含まれる言葉 → 材質。上から順に判定します（"window_frame" は frame が先に当たって金属になる）
CATEGORIES = [
    ("skip",     ["lamp", "light", "bulb", "照明", "ライト", "電球", "screen", "display", "monitor", "画面"]),
    ("metal",    ["frame", "sash", "handle", "knob", "rail", "metal", "steel", "alumi", "chrome", "faucet",
                  "枠", "サッシ", "取っ手", "ノブ", "金属", "アルミ", "ステンレス", "手すり", "蛇口"]),
    ("wood",     ["sill", "窓台"]),
    ("mirror",   ["mirror", "鏡"]),
    ("glass",    ["glass", "window", "pane", "glazing", "glaz", "窓", "ガラス"]),
    ("tile",     ["tile", "bath", "タイル", "浴室", "風呂"]),
    ("floor",    ["floor", "flooring", "flor", "slab", "床", "フローリング", "スラブ"]),
    ("ceiling",  ["ceiling", "clng", "天井"]),
    ("wall",     ["wall", "partition", "plaster", "壁", "間仕切", "しっくい", "漆喰", "クロス"]),
    ("roof",     ["roof", "屋根"]),
    ("ground",   ["ground", "grass", "lawn", "terrain", "garden", "yard", "地面", "芝", "庭"]),
    ("concrete", ["concrete", "foundation", "pavement", "基礎", "コンクリ", "土間", "外構"]),
    ("fabric",   ["sofa", "couch", "cushion", "pillow", "curtain", "bed", "mattress", "rug", "carpet", "fabric",
                  "cloth", "duvet", "ソファ", "クッション", "枕", "カーテン", "ベッド", "マットレス", "ラグ",
                  "カーペット", "布", "布団"]),
    ("plant",    ["plant", "leaf", "leaves", "tree", "foliage", "bush", "植物", "葉", "観葉", "植栽"]),
    ("wood",     ["wood", "table", "desk", "shelf", "cabinet", "chair", "door", "board", "counter", "dresser",
                  "chest", "drawer", "stair", "furn", "column", "beam", "木", "テーブル", "机", "棚", "チェア",
                  "椅子", "ドア", "扉", "カウンター", "家具", "収納", "階段", "柱", "梁", "框", "ボード"]),
    ("plastic",  ["tv", "television", "テレビ", "plastic", "樹脂", "appliance", "家電"]),
]
CATEGORY_JA = {"metal": "金属", "wood": "木", "mirror": "鏡", "glass": "ガラス", "tile": "タイル", "floor": "床（フローリング）",
               "ceiling": "天井", "wall": "壁（しっくい）", "roof": "屋根", "ground": "地面", "concrete": "コンクリート",
               "fabric": "布", "plant": "植物", "plastic": "樹脂"}

REPORT = []


def log(msg):
    print("[make_realistic] " + msg)
    REPORT.append(msg)


# ------------------------------------------------------------
#  小さな道具
# ------------------------------------------------------------
def scene():
    return bpy.context.scene


def set_input(node, names, value):
    """Blender のバージョンで名前が違う入力に値を入れる（例: Transmission / Transmission Weight）"""
    for n in names if isinstance(names, (list, tuple)) else [names]:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def sock(sockets, *keys):
    """identifier か名前でソケットを探す（ShaderNodeMix は A_Color のような identifier を持つ）"""
    for k in keys:
        for s in sockets:
            if s.identifier == k and s.enabled:
                return s
    for k in keys:
        if k in sockets:
            return sockets[k]
    raise KeyError(keys)


def try_set(obj, attr, *values):
    for v in values:
        try:
            setattr(obj, attr, v)
            return v
        except (TypeError, AttributeError, ValueError):
            continue
    return None


def model_meshes():
    return [o for o in scene().objects
            if o.type == "MESH" and not o.name.startswith("AUTO_") and o.visible_get()]


def world_bbox(objs):
    mn = Vector((1e18, 1e18, 1e18))
    mx = Vector((-1e18, -1e18, -1e18))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
            mx = Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
    return mn, mx


def remove_object(name):
    o = bpy.data.objects.get(name)
    if o:
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            for coll in (bpy.data.lights, bpy.data.cameras, bpy.data.meshes):
                if data.name in coll and coll[data.name] == data:
                    coll.remove(data)
                    break


def look_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------
#  1. 読み込みと単位
# ------------------------------------------------------------
def clear_default_scene():
    """Blender 起動時の立方体・ライト・カメラを、まったく手が加わっていない場合だけ消す"""
    defaults = (("Cube", "MESH", (0.0, 0.0, 0.0)), ("Light", "LIGHT", (4.0762, 1.0055, 5.9039)),
                ("Camera", "CAMERA", (7.3589, -6.9258, 4.9583)))
    names = []
    for n, t, loc in defaults:
        o = bpy.data.objects.get(n)
        if not o or o.type != t or o.parent is not None or (o.location - Vector(loc)).length > 0.01:
            continue
        if t == "MESH" and (len(o.data.vertices) != 8 or (o.dimensions - Vector((2, 2, 2))).length > 1e-4):
            continue
        bpy.data.objects.remove(o, do_unlink=True)
        names.append(n)
    if names:
        log("起動時の " + "・".join(names) + " を削除しました")


def import_model(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"モデルが見つかりません: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext == ".stl":
            bpy.ops.wm.stl_import(filepath=path)
        elif ext == ".ply":
            bpy.ops.wm.ply_import(filepath=path)
        elif ext in (".usd", ".usda", ".usdc", ".usdz"):
            bpy.ops.wm.usd_import(filepath=path)
        elif ext == ".dxf":
            bpy.ops.wm.obj_import(filepath=convert_dxf(path))
        else:
            raise RuntimeError(f"この形式は読み込めません: {ext}（.blend .glb .gltf .obj .fbx .stl .ply .usd .dxf に対応）")
    log(f"モデルを読み込みました: {path}")


def find_converter(model_path):
    """dxf2obj.py を、このスクリプトの隣・モデルの隣・.blend の隣から探す"""
    dirs = []
    f = globals().get("__file__")
    if f:
        dirs.append(os.path.dirname(os.path.abspath(f)))
    for t in bpy.data.texts:
        if t.filepath and os.path.basename(t.filepath).lower().startswith("make_realistic"):
            dirs.append(os.path.dirname(bpy.path.abspath(t.filepath)))
    dirs.append(os.path.dirname(os.path.abspath(model_path)))
    if bpy.data.filepath:
        dirs.append(os.path.dirname(bpy.data.filepath))
    for d in dirs:
        p = os.path.join(d, "dxf2obj.py")
        if os.path.isfile(p):
            return p
    raise RuntimeError("dxf2obj.py が見つかりません。make_realistic.py かモデルと同じフォルダに置いてください")


def find_python():
    """ezdxf が入っている Python を探す（Blender 本体の Python には入れない）"""
    import shutil
    import subprocess
    cands = []
    if SETTINGS["PYTHON"]:
        cands.append([SETTINGS["PYTHON"]])
    for name, extra in (("py", ["-3"]), ("python", []), ("python3", [])):
        exe = shutil.which(name)
        if exe and "WindowsApps" not in exe:      # Microsoft Store の案内だけ出す python.exe は除く
            cands.append([exe] + extra)
    for c in cands:
        try:
            r = subprocess.run(c + ["-c", "import ezdxf"], capture_output=True, timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0:
                return c
        except (OSError, subprocess.SubprocessError):
            continue
    raise RuntimeError("ezdxf の入った Python が見つかりません。PowerShell で「py -m pip install ezdxf」を実行してください"
                       "（Python がなければ python.org から入れる）。場所を指定するときは PYTHON 設定か --python")


def convert_dxf(path):
    import subprocess
    conv = find_converter(path)
    py = find_python()
    out = os.path.splitext(path)[0] + "_converted.obj"
    cmd = py + [conv, path, "-o", out]
    if SETTINGS["DXF_EXTRUDE"]:
        cmd += ["--extrude", SETTINGS["DXF_EXTRUDE"]]
    if SETTINGS["DXF_COLORS"]:
        cmd.append("--use-colors")
    log("DXF を変換しています…")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = (r.stdout or b"").decode("utf-8", "replace").strip()
    for line in text.splitlines():
        if line and not line.startswith(("DXF:", "書き出し:")):
            log("  " + line)
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-3:]
        raise RuntimeError("DXF を立体にできませんでした。" + (" / ".join(err) if r.returncode != 3 else
                           "2D の図面なら DXF_EXTRUDE（--dxf-extrude）で立ち上げるレイヤーを指定してください"))
    return out


def fix_units(meshes):
    mn, mx = world_bbox(meshes)
    size = max(mx - mn)
    s = SETTINGS["UNIT_SCALE"]
    auto = s is None
    if auto:
        s = 1.0 if size < 60 else (0.01 if size <= 2500 else 0.001)
    if abs(s - 1.0) > 1e-9:
        m = Matrix.Scale(s, 4)
        for o in scene().objects:
            if o.parent is None:
                o.matrix_world = m @ o.matrix_world
        bpy.context.view_layer.update()
        unit = {0.01: "cm", 0.001: "mm"}.get(s, f"×{s}")
        log(f"モデルの大きさが {size:.0f} だったので、単位を {unit} と{'判断して' if auto else 'して'} m に直しました"
            "（違っていたら UNIT_SCALE を指定）")
    else:
        log(f"モデルの大きさは {size:.1f} m（単位は m のまま）")
    us = scene().unit_settings
    us.system = "METRIC"
    us.scale_length = 1.0


# ------------------------------------------------------------
#  2. レンダー設定
# ------------------------------------------------------------
def setup_render():
    sc = scene()
    r = sc.render
    r.engine = "CYCLES"
    preview = SETTINGS["PREVIEW"]
    r.resolution_x, r.resolution_y = SETTINGS["RESOLUTION"]
    r.resolution_percentage = 50 if preview else 100
    r.film_transparent = False
    if hasattr(r, "use_persistent_data"):
        r.use_persistent_data = True

    c = sc.cycles
    c.samples = 64 if preview else SETTINGS["SAMPLES"]
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02 if preview else 0.01
    c.use_denoising = True
    try_set(c, "denoiser", "OPENIMAGEDENOISE", "OPTIX")
    if hasattr(c, "denoising_use_gpu"):
        c.denoising_use_gpu = True
    c.max_bounces = 12
    c.diffuse_bounces = 6
    c.glossy_bounces = 6
    c.transmission_bounces = 12
    c.transparent_max_bounces = 16
    c.sample_clamp_indirect = 10.0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 1.0

    device = "CPU"
    if SETTINGS["USE_GPU"]:
        device = pick_gpu()
    c.device = "GPU" if device != "CPU" else "CPU"

    vs = sc.view_settings
    vt = try_set(vs, "view_transform", "AgX", "Filmic")
    try_set(vs, "look", "AgX - Medium High Contrast", "Medium High Contrast", "None")
    log(f"Cycles: {c.samples} サンプル・ノイズ除去あり・{device} で計算・色の変換 {vt}"
        + ("（下書きモード）" if preview else ""))


def pick_gpu():
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except (KeyError, AttributeError):
        return "CPU"
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
        except (TypeError, ValueError):
            continue
        try:
            prefs.refresh_devices()
        except AttributeError:
            prefs.get_devices()
        found = [d for d in prefs.devices if d.type == kind]
        if found:
            for d in prefs.devices:
                d.use = d.type == kind
            return f"GPU（{kind}: {found[0].name}）"
    try:
        prefs.compute_device_type = "NONE"
    except (TypeError, ValueError):
        pass
    return "CPU"


# ------------------------------------------------------------
#  3. 空と太陽
# ------------------------------------------------------------
def sun_direction():
    """太陽のある方向（シーンから太陽へ向かう単位ベクトル）と高度を返す"""
    t = SETTINGS["TIME_OF_DAY"]
    elev = math.radians(max(5.0, min(75.0, 65.0 * math.sin(math.pi * (t - 6.0) / 12.0))))
    az = math.radians(90.0 + (t - 6.0) * 15.0)          # 6時=東, 12時=南, 18時=西
    south = {"+X": Vector((1, 0, 0)), "-X": Vector((-1, 0, 0)),
             "+Y": Vector((0, 1, 0)), "-Y": Vector((0, -1, 0))}[SETTINGS["SOUTH"].upper()]
    north = -south
    east = Vector((north.y, -north.x, 0))               # 上から見て北を時計回りに 90°
    h = north * math.cos(az) + east * math.sin(az)
    d = Vector((h.x * math.cos(elev), h.y * math.cos(elev), math.sin(elev))).normalized()
    return d, elev


def setup_world(d, elev):
    sc = scene()
    w = sc.world or bpy.data.worlds.new("World")
    sc.world = w
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    hdri = SETTINGS["HDRI_PATH"]
    if hdri:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri, check_existing=True)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = SETTINGS["HDRI_STRENGTH"]
        log(f"背景に HDRI を使います: {hdri}")
        return
    sky = nt.nodes.new("ShaderNodeTexSky")
    kind = try_set(sky, "sky_type", "MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "HOSEK_WILKIE")
    if hasattr(sky, "sun_disc"):
        sky.sun_disc = False          # 太陽そのものは下のサンライトで出す
    if hasattr(sky, "sun_elevation"):
        sky.sun_elevation = elev
        sky.sun_rotation = math.atan2(d.x, -d.y) % (2 * math.pi)
    if hasattr(sky, "sun_direction"):
        try:
            sky.sun_direction = d
        except (TypeError, AttributeError):
            pass
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = SETTINGS["SKY_STRENGTH"]
    log(f"空: 物理ベースのスカイ（{kind}）、明るさ {SETTINGS['SKY_STRENGTH']}")


def setup_sun(d, elev):
    if SETTINGS["DISABLE_OTHER_SUNS"]:
        hidden = 0
        for o in scene().objects:
            if o.type == "LIGHT" and o.data.type == "SUN" and not o.name.startswith("AUTO_") and not o.hide_render:
                o.hide_render = True
                hidden += 1
        if hidden:
            log(f"元からあった太陽ライト {hidden} 個をレンダーで非表示にしました")
    remove_object("AUTO_Sun")
    ld = bpy.data.lights.new("AUTO_Sun", "SUN")
    ld.energy = SETTINGS["SUN_STRENGTH"]
    ld.angle = math.radians(0.8)
    ld.color = (1.0, 0.95, 0.88)
    sun = bpy.data.objects.new("AUTO_Sun", ld)
    scene().collection.objects.link(sun)
    sun.location = d * 20
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    log(f"太陽: {SETTINGS['TIME_OF_DAY']:.1f} 時ごろ、高さ {math.degrees(elev):.0f}°、南は {SETTINGS['SOUTH']} 方向として配置")


# ------------------------------------------------------------
#  4. マテリアル
# ------------------------------------------------------------
GENERIC_NAME = ("material", "mat_", "color", "default", "none", "マテリアル")


def classify(obj, mat):
    def match(text):
        t = text.lower()
        for cat, words in CATEGORIES:
            if any(w in t for w in words):
                return cat
        return None
    if mat is not None:
        c = match(mat.name)
        if c:
            return c
    names = [obj.name, obj.data.name if obj.data else ""]
    p = obj.parent
    while p is not None:
        names.append(p.name)
        p = p.parent
    return match(" ".join(names))


def has_image_texture(mat):
    if mat is None or mat.node_tree is None:
        return False
    return any(n.type == "TEX_IMAGE" and n.image is not None for n in mat.node_tree.nodes)


def original_color(mat):
    if mat is None:
        return None
    col = None
    if mat.node_tree is not None:
        for n in mat.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                s = n.inputs["Base Color"]
                if not s.is_linked:
                    col = tuple(s.default_value[:3])
                break
    if col is None:
        col = tuple(mat.diffuse_color[:3])
    if all(abs(v - 0.8) < 0.01 for v in col):   # Blender の初期色はなかったことにする
        return None
    return col


def new_material(name):
    old = bpy.data.materials.get(name)
    if old:
        return old, None
    m = bpy.data.materials.new(name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    return m, (nt, bsdf)


def node(nt, kind, x, y, **props):
    n = nt.nodes.new(kind)
    n.location = (x, y)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def planar_coords(nt, x=-1400, y=0):
    """面の向きで XY / XZ / YZ を選ぶ座標（ワールド座標・m 単位）。床でも壁でも模様が伸びない"""
    geo = node(nt, "ShaderNodeNewGeometry", x, y)
    sep_n = node(nt, "ShaderNodeSeparateXYZ", x + 200, y + 200)
    nt.links.new(geo.outputs["Normal"], sep_n.inputs[0])
    sep_p = node(nt, "ShaderNodeSeparateXYZ", x + 200, y - 150)
    nt.links.new(geo.outputs["Position"], sep_p.inputs[0])

    def absn(o, yy):
        m = node(nt, "ShaderNodeMath", x + 400, yy, operation="ABSOLUTE")
        nt.links.new(o, m.inputs[0])
        return m.outputs[0]
    ax, ay, az = absn(sep_n.outputs[0], y + 300), absn(sep_n.outputs[1], y + 200), absn(sep_n.outputs[2], y + 100)

    def comb(a, b, yy):
        c = node(nt, "ShaderNodeCombineXYZ", x + 400, yy)
        nt.links.new(a, c.inputs[0])
        nt.links.new(b, c.inputs[1])
        return c.outputs[0]
    xy = comb(sep_p.outputs[0], sep_p.outputs[1], y - 100)
    xz = comb(sep_p.outputs[0], sep_p.outputs[2], y - 250)
    yz = comb(sep_p.outputs[1], sep_p.outputs[2], y - 400)

    def gt(a, b, yy):
        m = node(nt, "ShaderNodeMath", x + 600, yy, operation="GREATER_THAN")
        nt.links.new(a, m.inputs[0])
        nt.links.new(b, m.inputs[1])
        return m.outputs[0]

    def mixv(fac, a, b, yy):
        m = node(nt, "ShaderNodeMix", x + 800, yy, data_type="VECTOR")
        nt.links.new(fac, sock(m.inputs, "Factor_Float", "Factor"))
        nt.links.new(a, sock(m.inputs, "A_Vector", "A"))
        nt.links.new(b, sock(m.inputs, "B_Vector", "B"))
        return sock(m.outputs, "Result_Vector", "Result")
    wall = mixv(gt(ax, ay, y - 50), xz, yz, y - 200)       # 壁: X 向きなら YZ、Y 向きなら XZ
    z_up = node(nt, "ShaderNodeMath", x + 600, y + 150, operation="GREATER_THAN")
    nt.links.new(az, z_up.inputs[0])
    z_up.inputs[1].default_value = 0.5
    return mixv(z_up.outputs[0], wall, xy, y)


def mix_color(nt, a, b, fac, blend, x, y):
    m = node(nt, "ShaderNodeMix", x, y, data_type="RGBA", blend_type=blend)
    sock(m.inputs, "Factor_Float", "Factor").default_value = fac
    for target, src in (("A_Color", a), ("B_Color", b)):
        s = sock(m.inputs, target)
        if isinstance(src, tuple):
            s.default_value = (*src[:3], 1.0)
        else:
            nt.links.new(src, s)
    return sock(m.outputs, "Result_Color")


def add_bump(nt, bsdf, height, strength, distance=0.002, invert=False, x=-250, y=-400):
    b = node(nt, "ShaderNodeBump", x, y, invert=invert)
    b.inputs["Strength"].default_value = strength
    set_input(b, ["Distance"], distance)
    nt.links.new(height, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return b


def noise(nt, coords, scale, detail, x, y):
    n = node(nt, "ShaderNodeTexNoise", x, y)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    if coords is not None:
        nt.links.new(coords, n.inputs["Vector"])
    return n


def position(nt, x, y):
    return node(nt, "ShaderNodeNewGeometry", x, y).outputs["Position"]


def darker(c, k):
    return tuple(max(0.0, v * k) for v in c[:3])


def build_material(cat, color):
    """カテゴリと元の色から AUTO_ マテリアルを作る（同じ組み合わせは使い回す）"""
    keep = SETTINGS["KEEP_ORIGINAL_COLORS"] and color is not None
    key = cat + (("_%02x%02x%02x" % tuple(int(v * 255) for v in color)) if keep else "")
    m, made = new_material("AUTO_" + key)
    if made is None:
        return m
    nt, bsdf = made
    set_input(bsdf, "Roughness", 0.5)

    if cat == "floor":
        base = color if keep else (0.55, 0.36, 0.20)
        uv = planar_coords(nt)
        brick = node(nt, "ShaderNodeTexBrick", -500, 200, offset=0.5, offset_frequency=1)
        nt.links.new(uv, brick.inputs["Vector"])
        brick.inputs["Color1"].default_value = (*base, 1)
        brick.inputs["Color2"].default_value = (*darker(base, 0.78), 1)
        brick.inputs["Mortar"].default_value = (*darker(base, 0.35), 1)
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Mortar Size"].default_value = 0.0012
        brick.inputs["Brick Width"].default_value = 1.2     # 板の長さ 120cm
        brick.inputs["Row Height"].default_value = 0.15     # 板の幅 15cm
        set_input(brick, ["Bias"], 0.0)
        wave = node(nt, "ShaderNodeTexWave", -500, -100, wave_type="BANDS", bands_direction="Y")
        nt.links.new(uv, wave.inputs["Vector"])
        wave.inputs["Scale"].default_value = 9.0
        wave.inputs["Distortion"].default_value = 7.0
        wave.inputs["Detail"].default_value = 3.0
        ramp = node(nt, "ShaderNodeValToRGB", -300, -100)
        ramp.color_ramp.elements[0].color = (0.78, 0.78, 0.78, 1)
        ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
        nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
        col = mix_color(nt, brick.outputs["Color"], ramp.outputs["Color"], 1.0, "MULTIPLY", -120, 100)
        nt.links.new(col, bsdf.inputs["Base Color"])
        set_input(bsdf, "Roughness", 0.32)
        set_input(bsdf, ["Coat Weight", "Coat"], 0.15)
        set_input(bsdf, ["Coat Roughness"], 0.12)
        add_bump(nt, bsdf, brick.outputs["Fac"], 0.5, 0.001, invert=True)

    elif cat == "wood":
        base = color if keep else (0.50, 0.32, 0.18)
        # 面ごとの 2D 座標を縦方向に強く縮めたノイズ → 水平に流れる細い木目
        mp = node(nt, "ShaderNodeMapping", -700, 0)
        nt.links.new(planar_coords(nt, -1600, 0), mp.inputs["Vector"])
        mp.inputs["Scale"].default_value = (2.5, 45.0, 1.0)
        n = noise(nt, mp.outputs["Vector"], 1.0, 8.0, -500, 0)
        set_input(n, ["Roughness"], 0.6)
        set_input(n, ["Distortion"], 0.4)
        ramp = node(nt, "ShaderNodeValToRGB", -300, 0)
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[1].position = 0.65
        ramp.color_ramp.elements[0].color = (*darker(base, 0.8), 1)
        ramp.color_ramp.elements[1].color = (*base, 1)
        nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        set_input(bsdf, "Roughness", 0.45)
        add_bump(nt, bsdf, n.outputs["Fac"], 0.04, 0.001)

    elif cat in ("wall", "ceiling"):
        base = color if keep else ((0.86, 0.85, 0.82) if cat == "wall" else (0.90, 0.90, 0.88))
        bsdf.inputs["Base Color"].default_value = (*base, 1)
        set_input(bsdf, "Roughness", 0.92)
        if cat == "wall":
            n = noise(nt, position(nt, -700, -300), 70.0, 8.0, -500, -300)
            add_bump(nt, bsdf, n.outputs["Fac"], 0.06, 0.002)

    elif cat == "glass":
        bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
        set_input(bsdf, "Roughness", 0.0)
        set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)
        if set_input(bsdf, ["Thin Wall"], True):
            set_input(bsdf, "IOR", 1.5)
        else:
            set_input(bsdf, "IOR", 1.05)   # 板ガラスで景色がゆがまないように

    elif cat == "mirror":
        bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1)
        set_input(bsdf, "Metallic", 1.0)
        set_input(bsdf, "Roughness", 0.02)

    elif cat == "metal":
        base = color if keep else (0.78, 0.78, 0.78)
        bsdf.inputs["Base Color"].default_value = (*base, 1)
        set_input(bsdf, "Metallic", 1.0)
        set_input(bsdf, "Roughness", 0.3)

    elif cat == "tile":
        base = color if keep else (0.90, 0.90, 0.88)
        uv = planar_coords(nt)
        brick = node(nt, "ShaderNodeTexBrick", -500, 100, offset=0.0)
        nt.links.new(uv, brick.inputs["Vector"])
        brick.inputs["Color1"].default_value = (*base, 1)
        brick.inputs["Color2"].default_value = (*darker(base, 0.96), 1)
        brick.inputs["Mortar"].default_value = (0.55, 0.55, 0.53, 1)
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Mortar Size"].default_value = 0.003
        brick.inputs["Brick Width"].default_value = 0.3
        brick.inputs["Row Height"].default_value = 0.3
        nt.links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
        set_input(bsdf, "Roughness", 0.15)
        add_bump(nt, bsdf, brick.outputs["Fac"], 0.4, 0.001, invert=True)

    elif cat in ("roof", "concrete", "ground"):
        base = color if keep else {"roof": (0.09, 0.09, 0.095), "concrete": (0.55, 0.55, 0.53),
                                   "ground": (0.16, 0.24, 0.09)}[cat]
        n = noise(nt, position(nt, -700, 0), {"roof": 30.0, "concrete": 12.0, "ground": 4.0}[cat], 10.0, -500, 0)
        ramp = node(nt, "ShaderNodeValToRGB", -300, 0)
        ramp.color_ramp.elements[0].color = (*darker(base, 0.8), 1)
        ramp.color_ramp.elements[1].color = (*darker(base, 1.15), 1)
        nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        set_input(bsdf, "Roughness", {"roof": 0.6, "concrete": 0.85, "ground": 0.95}[cat])
        add_bump(nt, bsdf, n.outputs["Fac"], 0.15, 0.003)

    elif cat == "fabric":
        base = color if keep else (0.55, 0.55, 0.52)
        bsdf.inputs["Base Color"].default_value = (*base, 1)
        set_input(bsdf, "Roughness", 0.95)
        set_input(bsdf, ["Sheen Weight", "Sheen"], 0.6)
        set_input(bsdf, ["Sheen Roughness"], 0.5)
        n = noise(nt, position(nt, -700, -300), 900.0, 2.0, -500, -300)
        add_bump(nt, bsdf, n.outputs["Fac"], 0.12, 0.0005)

    elif cat == "plant":
        base = color if keep else (0.10, 0.26, 0.07)
        bsdf.inputs["Base Color"].default_value = (*base, 1)
        set_input(bsdf, "Roughness", 0.5)
        set_input(bsdf, ["Subsurface Weight", "Subsurface"], 0.1)

    elif cat == "plastic":
        base = color if keep else (0.03, 0.03, 0.03)
        bsdf.inputs["Base Color"].default_value = (*base, 1)
        set_input(bsdf, "Roughness", 0.25)
    return m


def apply_materials(meshes):
    counts, skipped_tex, unknown = {}, 0, []
    glass_objs = set()
    for o in meshes:
        slots = o.material_slots
        if len(slots) == 0:
            cat = classify(o, None)
            if cat and cat != "skip":
                o.data.materials.append(build_material(cat, None))
                counts[cat] = counts.get(cat, 0) + 1
                if cat == "glass":
                    glass_objs.add(o)
            elif not cat:
                unknown.append(o.name)
            continue
        for slot in slots:
            mat = slot.material
            if mat is not None and mat.name.startswith("AUTO_"):
                cat = mat.name[5:].split("_")[0]
            else:
                if SETTINGS["SKIP_TEXTURED"] and has_image_texture(mat):
                    skipped_tex += 1
                    continue
                cat = classify(o, mat)
                if not cat:
                    unknown.append(f"{o.name}（{mat.name if mat else 'マテリアルなし'}）")
                    continue
                if cat == "skip":
                    continue
                slot.material = build_material(cat, original_color(mat))
                counts[cat] = counts.get(cat, 0) + 1
            if cat == "glass":
                glass_objs.add(o)
    for o in glass_objs:
        o.visible_shadow = False     # ガラスが太陽の光をさえぎらないように（Cycles の仕様対策）
    if counts:
        log("マテリアルを付け替えました: " + "、".join(f"{CATEGORY_JA.get(k, k)} {v}" for k, v in sorted(counts.items())))
    if skipped_tex:
        log(f"画像テクスチャ付きのマテリアル {skipped_tex} 個はそのままにしました")
    if unknown:
        shown = "、".join(unknown[:12]) + (f" ほか {len(unknown) - 12} 個" if len(unknown) > 12 else "")
        log(f"名前から材質がわからず、そのままにしたもの: {shown}"
            "（オブジェクト名に floor / wall / sofa / 床 / 壁 などを入れると自動で付きます）")
    return glass_objs


# ------------------------------------------------------------
#  5. 面取り
# ------------------------------------------------------------
def add_bevels(meshes, skip):
    n = 0
    for o in meshes:
        if o in skip or "AUTO_Bevel" in o.modifiers or len(o.data.vertices) > 300000:
            continue
        if min(o.dimensions) < 0.02:     # 板や平面には付けない
            continue
        cat = classify(o, o.active_material)
        if cat in ("plant", "ground", "glass", "fabric"):
            continue
        s = o.matrix_world.to_scale()
        k = max(1e-9, (abs(s.x) + abs(s.y) + abs(s.z)) / 3)
        mod = o.modifiers.new("AUTO_Bevel", "BEVEL")
        mod.width = SETTINGS["BEVEL_MM"] / 1000.0 / k
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(40)
        if hasattr(mod, "use_clamp_overlap"):
            mod.use_clamp_overlap = True
        n += 1
    if n:
        log(f"{n} 個の物の角に {SETTINGS['BEVEL_MM']:.0f}mm の面取りを付けました")


# ------------------------------------------------------------
#  6. 地面とカメラ
# ------------------------------------------------------------
def add_ground(mn, mx, meshes):
    if any(classify(o, o.active_material) == "ground" for o in meshes):
        return
    remove_object("AUTO_Ground")
    size = max(200.0, max(mx - mn) * 20)
    me = bpy.data.meshes.new("AUTO_Ground")
    h = size / 2
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("AUTO_Ground", me)
    scene().collection.objects.link(g)
    c = (mn + mx) / 2
    g.location = (c.x, c.y, mn.z - 0.02)
    me.materials.append(build_material("ground", None))
    log("地面を追加しました（モデルのいちばん下の 2cm 下）")


def largest_glass(meshes):
    best, area = None, 0.0
    for o in meshes:
        if classify(o, o.active_material) != "glass":
            continue
        a, b = world_bbox([o])
        s = sorted(b - a, reverse=True)
        if s[0] * s[1] > area:
            best, area = (a + b) / 2, s[0] * s[1]
    return best


def setup_cameras(mn, mx, meshes):
    sc = scene()
    mode = SETTINGS["CAMERA"]
    if mode == "keep" or (mode == "auto" and sc.camera is not None and not sc.camera.name.startswith("AUTO_")):
        if sc.camera is not None:
            sc.camera.data.clip_start = min(sc.camera.data.clip_start, 0.05)
            log(f"カメラは今のもの（{sc.camera.name}）を使います")
            return
    size = mx - mn
    c = (mn + mx) / 2
    for n in ("AUTO_Cam_Interior", "AUTO_Cam_Exterior"):
        remove_object(n)

    def make(name, lens):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_start = 0.05
        cd.clip_end = 2000
        o = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(o)
        return o
    inner = make("AUTO_Cam_Interior", 18)
    eye = mn.z + SETTINGS["EYE_HEIGHT"]
    win = largest_glass(meshes)
    if win is not None:
        # いちばん大きい窓の反対側から、窓に向かって見る（日差しが床に落ちる様子が入る）
        d = Vector((c.x - win.x, c.y - win.y, 0))
        d = d.normalized() if d.length > 1e-6 else Vector((0, 1, 0))
        lo, hi = mn + Vector((0.3, 0.3, 0)), mx - Vector((0.3, 0.3, 0))
        t = min(((hi[i] if d[i] > 0 else lo[i]) - win[i]) / d[i] for i in (0, 1) if abs(d[i]) > 1e-6)
        p = win + d * max(0.5, t * 0.85)
        inner.location = Vector((p.x, p.y, eye))
        look_at(inner, Vector((win.x, win.y, mn.z + 1.1)))
    else:
        inner.location = Vector((c.x, mn.y + size.y * 0.22, eye))
        look_at(inner, Vector((c.x, mx.y, eye - 0.15)))
    outer = make("AUTO_Cam_Exterior", 35)
    diag = size.length
    outer.location = c + Vector((-0.75, -1.25, 0)).normalized() * diag * 1.35 + Vector((0, 0, size.z * 0.35 + 1.5))
    look_at(outer, c)
    if mode == "interior" or (mode != "exterior" and max(size.x, size.y) <= 8.0):
        sc.camera = inner
        log("室内カメラ（目線 %.2fm・18mm%s）を作ってアクティブにしました。外観は AUTO_Cam_Exterior"
            % (SETTINGS["EYE_HEIGHT"], "・いちばん大きい窓に向けて" if win is not None else ""))
    else:
        sc.camera = outer
        log("外観カメラを作ってアクティブにしました。室内は AUTO_Cam_Interior")
    log("カメラの向きを変えるには: 好きな視点にしてから Ctrl+Alt+テンキー0（今の視点にカメラを合わせる）")


def set_exposure(mn, mx):
    cam = scene().camera
    loc = cam.location if cam else None
    inside = loc is not None and mn.x < loc.x < mx.x and mn.y < loc.y < mx.y and loc.z < mx.z
    exp = SETTINGS["EXPOSURE"]
    if exp is None:
        exp = 2.5 if inside else 0.0
        log(f"明るさ（露出）: {exp:+.1f}（カメラが{'室内' if inside else '外'}にあるため自動。EXPOSURE で変更可）")
    scene().view_settings.exposure = exp


# ------------------------------------------------------------
#  まとめ
# ------------------------------------------------------------
def write_report():
    t = bpy.data.texts.get("REALISM_REPORT") or bpy.data.texts.new("REALISM_REPORT")
    t.clear()
    t.write("make_realistic.py の結果\n\n" + "\n".join("・" + r for r in REPORT) + "\n")


def output_path(p):
    if not p:
        return ""
    if p.startswith("//") and not bpy.data.filepath:
        base = os.path.dirname(SETTINGS["MODEL_PATH"]) if SETTINGS["MODEL_PATH"] else os.path.expanduser("~")
        p = os.path.join(base, p[2:])
    return bpy.path.abspath(p)


DEFAULTS = dict(SETTINGS)


def main(**overrides):
    REPORT.clear()
    SETTINGS.clear()
    SETTINGS.update(DEFAULTS)
    SETTINGS.update({k: v for k, v in overrides.items() if v is not None})
    try:
        path = SETTINGS["MODEL_PATH"]
        if path:
            sc = scene()
            if sc.get("make_realistic_model") == os.path.abspath(path) and model_meshes():
                log("モデルは読み込み済みなので、もう一度は読み込みません")
            else:
                import_model(path)
                scene()["make_realistic_model"] = os.path.abspath(path)
        if SETTINGS["CLEAR_DEFAULT_SCENE"]:
            clear_default_scene()
        meshes = model_meshes()
        if not meshes:
            raise RuntimeError("シーンにメッシュがありません。モデルを開くか MODEL_PATH を指定してください")
        log(f"対象のメッシュ: {len(meshes)} 個")
        fix_units(meshes)
        mn, mx = world_bbox(meshes)
        setup_render()
        d, elev = sun_direction()
        setup_world(d, elev)
        setup_sun(d, elev)
        glass = set()
        if SETTINGS["APPLY_MATERIALS"]:
            glass = apply_materials(meshes)
        if SETTINGS["ADD_BEVEL"]:
            add_bevels(meshes, glass)
        if SETTINGS["ADD_GROUND"]:
            add_ground(mn, mx, meshes)
        setup_cameras(mn, mx, meshes)
        set_exposure(mn, mx)
        write_report()
        if SETTINGS["SAVE_BLEND"]:
            bpy.ops.wm.save_as_mainfile(filepath=output_path(SETTINGS["SAVE_BLEND"]))
            log("保存しました: " + SETTINGS["SAVE_BLEND"])
        if SETTINGS["RENDER_PATH"]:
            out = output_path(SETTINGS["RENDER_PATH"])
            scene().render.filepath = out
            log("レンダリング中…（終わるまで数分かかることがあります）")
            bpy.ops.render.render(write_still=True)
            log("画像を保存しました: " + out)
            write_report()
        print("\n".join(["", "==== make_realistic 完了 ===="] + ["・" + r for r in REPORT]))
    except Exception as e:
        log("エラー: " + str(e))
        write_report()
        traceback.print_exc()
        if bpy.app.background:
            sys.exit(1)


def parse_cli():
    if "--" not in sys.argv:
        return {}
    import argparse
    p = argparse.ArgumentParser(prog="make_realistic.py")
    p.add_argument("--model")
    p.add_argument("--render")
    p.add_argument("--save")
    p.add_argument("--samples", type=int)
    p.add_argument("--time", type=float)
    p.add_argument("--south", choices=["+X", "-X", "+Y", "-Y"])
    p.add_argument("--res")
    p.add_argument("--camera", choices=["auto", "interior", "exterior", "keep"])
    p.add_argument("--exposure", type=float)
    p.add_argument("--sky", type=float)
    p.add_argument("--sun", type=float)
    p.add_argument("--hdri")
    p.add_argument("--unit-scale", type=float)
    p.add_argument("--dxf-extrude")
    p.add_argument("--dxf-colors", action="store_true")
    p.add_argument("--python")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--no-materials", action="store_true")
    p.add_argument("--no-bevel", action="store_true")
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    o = dict(MODEL_PATH=a.model, RENDER_PATH=a.render, SAVE_BLEND=a.save, SAMPLES=a.samples, TIME_OF_DAY=a.time,
             SOUTH=a.south, CAMERA=a.camera, EXPOSURE=a.exposure, SKY_STRENGTH=a.sky, SUN_STRENGTH=a.sun,
             HDRI_PATH=a.hdri, UNIT_SCALE=a.unit_scale, DXF_EXTRUDE=a.dxf_extrude, PYTHON=a.python)
    if a.dxf_colors:
        o["DXF_COLORS"] = True
    if a.res:
        w, h = a.res.lower().split("x")
        o["RESOLUTION"] = (int(w), int(h))
    if a.preview:
        o["PREVIEW"] = True
    if a.cpu:
        o["USE_GPU"] = False
    if a.no_materials:
        o["APPLY_MATERIALS"] = False
    if a.no_bevel:
        o["ADD_BEVEL"] = False
    return o


if __name__ == "__main__":
    main(**parse_cli())
