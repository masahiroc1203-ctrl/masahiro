# -*- coding: utf-8 -*-
"""
dxf2obj.py  -  DXF を Blender で読める OBJ（レイヤーごとに 1 つの物体）に変換する

必要: Python 3.9 以降と ezdxf（py -m pip install ezdxf）

使い方
  py dxf2obj.py house.dxf                    -> house_converted.obj / .mtl / _dxf_report.txt
  py dxf2obj.py house.dxf -o out.obj
  py dxf2obj.py plan.dxf --extrude "壁=2400,床=0"   2D の図面: 「壁」レイヤーの閉じた図形を 2400mm 立ち上げ、
                                                   「床」レイヤーは平らな面にする（高さは mm、* も使える: "壁*=2400"）

変換できるもの
  3D の面: 3DFACE / POLYFACE・ポリゴンメッシュ / MESH / SOLID・TRACE（厚さ付きも）
  厚さ（thickness）付きの線・ポリライン・円・円弧 -> 縦の面
  --extrude で指定したレイヤーの閉じた図形と HATCH -> 立ち上げた立体（内側の図形は穴として扱う）
  ブロック（INSERT）は展開し、レイヤー 0 の中身は INSERT のレイヤーに入れる
変換できないもの
  3DSOLID / BODY / REGION / SURFACE（ACIS 形式）-> CAD 側で「分解」するか、メッシュ・STL で書き出してください
"""

import argparse
import fnmatch
import math
import os
import sys
from collections import Counter, defaultdict

try:
    import ezdxf
    from ezdxf import colors, path as dxfpath, recover
    from ezdxf.math import Vec3
    from ezdxf.math.triangulation import mapbox_earcut_3d
    from ezdxf.render import MeshBuilder
except ImportError:  # pragma: no cover
    sys.stderr.write("ezdxf が見つかりません。先に「py -m pip install ezdxf」を実行してください。\n")
    sys.exit(2)

UNIT_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1}
UNIT_NAME = {1: "インチ", 2: "フィート", 4: "mm", 5: "cm", 6: "m", 14: "dm"}
ACIS = {"3DSOLID", "BODY", "REGION", "SURFACE", "EXTRUDEDSURFACE", "LOFTEDSURFACE", "REVOLVEDSURFACE",
        "SWEPTSURFACE", "PLANESURFACE", "NURBSURFACE"}
CURVES = {"LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE"}
IGNORED = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MLEADER", "ATTRIB", "ATTDEF", "POINT", "VIEWPORT",
           "IMAGE", "WIPEOUT", "XLINE", "RAY", "TOLERANCE", "ACAD_TABLE"}
NO_COLOR = (0.8, 0.8, 0.8)


class LayerMesh:
    def __init__(self):
        self.verts = []
        self.index = {}
        self.faces = []

    def vid(self, v):
        key = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
        i = self.index.get(key)
        if i is None:
            i = len(self.verts)
            self.index[key] = i
            self.verts.append(key)
        return i

    def add(self, pts):
        ids = []
        for p in pts:
            i = self.vid(p)
            if not ids or ids[-1] != i:
                ids.append(i)
        if len(ids) > 1 and ids[0] == ids[-1]:
            ids.pop()
        if len(set(ids)) >= 3:
            self.faces.append(ids)
            return True
        return False


def parse_extrude(spec):
    rules = []
    for part in (spec or "").replace("、", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"--extrude の書き方が違います: {part}（例: 壁=2400）")
        name, h = part.rsplit("=", 1)
        rules.append((name.strip().lower(), float(h)))
    return rules


def extrude_height(layer, rules):
    low = layer.lower()
    for pat, h in rules:
        if fnmatch.fnmatchcase(low, pat):
            return h
    return None


def polygon_area_normal(pts):
    n = Vec3()
    for a, b in zip(pts, pts[1:] + pts[:1]):
        n += a.cross(b)
    return n.magnitude / 2.0, n


def point_in_polygon_2d(p, poly):
    x, y = p.x, p.y
    inside = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a.y > y) != (b.y > y):
            xi = a.x + (y - a.y) * (b.x - a.x) / ((b.y - a.y) or 1e-30)
            if xi > x:
                inside = not inside
    return inside


def add_prism(mesh, ring, holes, height):
    """ring/holes: 閉じた輪郭（Vec3 のリスト、同じ高さ）。height=0 なら平らな面だけ"""
    up = Vec3(0, 0, height)
    try:
        tris = list(mapbox_earcut_3d(ring, holes))
    except Exception:
        tris = []
    for t in tris:
        mesh.add(list(t))
        if height:
            mesh.add([v + up for v in reversed(t)])
    if height:
        for loop in [ring] + holes:
            for a, b in zip(loop, loop[1:] + loop[:1]):
                mesh.add([a, b, b + up, a + up])
    return bool(tris)


def flatten(entity, dist):
    try:
        p = dxfpath.make_path(entity)
    except Exception:
        return []
    out = []
    for sp in p.sub_paths():
        pts = list(sp.flattening(dist))
        if len(pts) >= 2:
            out.append((pts, sp.is_closed))
    return out


def resolve_rgb(doc, e, layer, parent_rgb):
    try:
        if e.dxf.hasattr("true_color"):
            return tuple(c / 255 for c in colors.int2rgb(e.dxf.true_color))
        aci = e.dxf.get("color", 256)
        if aci == 0:
            return parent_rgb
        if aci == 256:
            lay = doc.layers.get(layer) if doc.layers.has_entry(layer) else None
            if lay is None:
                return None
            if lay.dxf.hasattr("true_color"):
                return tuple(c / 255 for c in colors.int2rgb(lay.dxf.true_color))
            aci = abs(lay.dxf.get("color", 7))
        if aci in (7, 256) or aci <= 0:
            return None
        return tuple(c / 255 for c in colors.aci2rgb(aci))
    except Exception:
        return None


def walk(doc, entities, parent_layer=None, parent_rgb=None, depth=0, stats=None):
    for e in entities:
        layer = e.dxf.get("layer", "0")
        if layer == "0" and parent_layer:
            layer = parent_layer
        if e.dxftype() == "INSERT":
            if depth > 20:
                continue
            stats["INSERT"] += 1
            rgb = resolve_rgb(doc, e, layer, parent_rgb)
            try:
                inserts = list(e.multi_insert()) if e.mcount > 1 else [e]   # MINSERT（配列）にも対応
                for ins in inserts:
                    yield from walk(doc, ins.virtual_entities(), layer, rgb, depth + 1, stats)
            except Exception:
                stats["INSERT（展開できず）"] += 1
            continue
        yield e, layer, resolve_rgb(doc, e, layer, parent_rgb)


def convert(src, dst=None, extrude="", use_colors=False, out=print):
    rules = parse_extrude(extrude)
    doc, auditor = recover.readfile(src)
    insunits = doc.header.get("$INSUNITS", 0)
    scale = UNIT_TO_M.get(insunits)
    unit_known = scale is not None
    if not unit_known:
        scale = 0.001          # 単位なしの図面は mm とみなして高さ（--extrude）を解釈する
    mm = 0.001 / scale          # 1mm が図面の単位でいくつか
    flat_dist = 5 * mm          # 曲線を 5mm 以内の誤差で折れ線にする

    meshes = defaultdict(LayerMesh)
    layer_rgb = {}
    stats = Counter()
    faces_by_type = Counter()
    curves_by_layer = Counter()
    pending = defaultdict(list)   # (layer, elevation) -> 閉じた輪郭（--extrude 用）

    for e, layer, rgb in walk(doc, doc.modelspace(), stats=stats):
        t = e.dxftype()
        stats[t] += 1
        m = meshes[layer]
        if use_colors and rgb and layer not in layer_rgb:
            layer_rgb[layer] = rgb
        made = 0
        try:
            if t == "3DFACE":
                v = [Vec3(e.dxf.get(f"vtx{i}")) for i in range(4)]
                made += m.add(v if not v[3].isclose(v[2]) else v[:3])
            elif t in ("SOLID", "TRACE"):
                ocs = e.ocs()
                v = [Vec3(e.dxf.get(f"vtx{i}", e.dxf.vtx2)) for i in range(4)]
                quad = list(ocs.points_to_wcs([v[0], v[1], v[3], v[2]]))
                made += m.add(quad)
                th = e.dxf.get("thickness", 0)
                if th:
                    up = Vec3(e.dxf.get("extrusion", (0, 0, 1))).normalize(th)
                    made += m.add([p + up for p in reversed(quad)])
                    for a, b in zip(quad, quad[1:] + quad[:1]):
                        made += m.add([a, b, b + up, a + up])
            elif t == "POLYLINE" and (e.is_poly_face_mesh or e.is_polygon_mesh):
                mb = MeshBuilder.from_polyface(e)
                for f in mb.faces:
                    made += m.add([mb.vertices[i] for i in f])
            elif t == "MESH":
                mb = MeshBuilder.from_mesh(e)
                for f in mb.faces:
                    made += m.add([mb.vertices[i] for i in f])
            elif t in CURVES or t in ("HATCH", "MPOLYGON"):
                th = e.dxf.get("thickness", 0) if e.dxf.is_supported("thickness") else 0
                h = extrude_height(layer, rules)
                loops = flatten(e, flat_dist)
                if th and t in CURVES:
                    up = Vec3(e.dxf.get("extrusion", (0, 0, 1))).normalize(th)
                    for pts, _closed in loops:
                        for a, b in zip(pts, pts[1:]):
                            made += m.add([a, b, b + up, a + up])
                elif h is not None:
                    for pts, closed in loops:
                        if closed or t in ("HATCH", "MPOLYGON", "CIRCLE"):
                            ring = pts[:-1] if pts[0].isclose(pts[-1]) else pts
                            if len(ring) >= 3:
                                pending[(layer, round(ring[0].z, 3))].append((ring, h * mm))
                    curves_by_layer[layer] += 1
                elif t in ("HATCH", "MPOLYGON") or (t in CURVES and any(c for _p, c in loops)):
                    curves_by_layer[layer] += 1
            elif t in ACIS:
                stats["ACIS"] += 1
        except Exception as ex:  # 1 つの図形の失敗で全体を止めない
            stats["変換エラー"] += 1
            if stats["変換エラー"] <= 3:
                out(f"  注意: {t}（レイヤー {layer}）を変換できませんでした: {ex}")
        if made:
            faces_by_type[t] += made

    # --extrude: 同じレイヤー・同じ高さの輪郭を、外側と穴（内側）に分けて立体にする
    for (layer, _z), rings in pending.items():
        items = []
        for ring, h in rings:
            area, _n = polygon_area_normal(ring)
            if area > 1e-12:
                items.append((area, ring, h))
        items.sort(key=lambda x: -x[0])
        depth = []
        parent = []
        for i, (_a, ring, _h) in enumerate(items):
            d, par = 0, None
            for j in range(i):
                if point_in_polygon_2d(ring[0], items[j][1]):
                    d += 1
                    par = j if par is None or items[j][0] < items[par][0] else par
            depth.append(d)
            parent.append(par)
        holes = defaultdict(list)
        for i, d in enumerate(depth):
            if d % 2 == 1 and parent[i] is not None:
                holes[parent[i]].append(items[i][1])
        for i, (_a, ring, h) in enumerate(items):
            if depth[i] % 2 == 0:
                if add_prism(meshes[layer], ring, holes[i], h):
                    faces_by_type["立ち上げ（--extrude）"] += 1

    # 書き出し
    base = os.path.splitext(src)[0]
    dst = dst or base + "_converted.obj"
    mtl = os.path.splitext(dst)[0] + ".mtl"
    used = [(name, lm) for name, lm in meshes.items() if lm.faces]
    all_v = [v for _n, lm in used for v in lm.verts]
    names = {}
    for name, _lm in used:
        clean = "_".join(name.split()) or "layer"
        n, k = clean, 2
        while n in names.values():
            n = f"{clean}_{k}"
            k += 1
        names[name] = n
    with open(mtl, "w", encoding="utf-8") as f:
        for name, _lm in used:
            r, g, b = layer_rgb.get(name, NO_COLOR)
            f.write(f"newmtl {names[name]}\nKd {r:.4f} {g:.4f} {b:.4f}\nNs 50\nd 1\nillum 2\n\n")
    out_scale = scale if unit_known else 1.0
    with open(dst, "w", encoding="utf-8") as f:
        f.write(f"# dxf2obj: {os.path.basename(src)}  単位 {'m' if unit_known else '図面のまま'}  Y-up\n")
        f.write(f"mtllib {os.path.basename(mtl)}\n")
        offset = 1
        for name, lm in used:
            f.write(f"o {names[name]}\nusemtl {names[name]}\n")
            for x, y, z in lm.verts:   # DXF は Z が上。OBJ の標準（Y が上）に合わせる
                f.write(f"v {x * out_scale:.6f} {z * out_scale:.6f} {-y * out_scale:.6f}\n")
            for face in lm.faces:
                f.write("f " + " ".join(str(i + offset) for i in face) + "\n")
            offset += len(lm.verts)

    # レポート
    lines = [f"DXF: {src}",
             f"単位: {UNIT_NAME.get(insunits, '指定なし')}（$INSUNITS={insunits}）"
             + ("。m に直して書き出しました" if unit_known else "。そのまま書き出し、Blender 側で大きさから判定します"),
             f"監査で直した問題: {len(auditor.fixes)} 件" if auditor.fixes else "",
             "図形の数: " + "、".join(f"{k} {v}" for k, v in stats.most_common() if k not in ("ACIS",)),
             "面にしたもの: " + ("、".join(f"{k} {v}" for k, v in faces_by_type.most_common()) or "なし")]
    if used:
        mn = [min(v[i] for v in all_v) * out_scale for i in range(3)]
        mx = [max(v[i] for v in all_v) * out_scale for i in range(3)]
        u = "m" if unit_known else ""
        lines.append(f"大きさ: 幅 {mx[0] - mn[0]:.2f}{u} × 奥行 {mx[1] - mn[1]:.2f}{u} × 高さ {mx[2] - mn[2]:.2f}{u}")
        lines.append("レイヤー（= Blender の物体名）: " + "、".join(
            f"{names[n]}（{len(lm.faces)} 面）" for n, lm in sorted(used, key=lambda x: -len(x[1].faces))))
    if stats["ACIS"]:
        lines.append(f"注意: 3DSOLID などの ACIS 形式 {stats['ACIS']} 個は変換できません。"
                     "CAD 側で「分解（EXPLODE）」するか、メッシュ・STL で書き出してください")
    flat_layers = [n for n, c in curves_by_layer.most_common() if extrude_height(n, rules) is None]
    if not used:
        lines.append("面が 1 つもありません。" + ("" if stats["ACIS"] else "この DXF は 2D の図面のようです。"))
    if flat_layers and (not used or not rules):
        lines.append("閉じた図形がある 2D のレイヤー: " + "、".join(f"{n}（{curves_by_layer[n]}）" for n in flat_layers[:15]))
        lines.append(f'立体にするには、例: --extrude "{flat_layers[0]}=2400"（高さ mm。床は =0 で平らな面）')
    report = "\n".join(l for l in lines if l)
    with open(base + "_dxf_report.txt", "w", encoding="utf-8") as f:
        f.write(report + "\n")
    out(report)
    return dst if used else None


def main():
    ap = argparse.ArgumentParser(description="DXF を OBJ に変換（レイヤーごとに物体を分ける）")
    ap.add_argument("dxf")
    ap.add_argument("-o", "--output")
    ap.add_argument("--extrude", default="", help='2D 図面のレイヤーを立ち上げる。例: "壁=2400,床=0"（高さ mm）')
    ap.add_argument("--use-colors", action="store_true", help="DXF の線の色をマテリアルの色に使う")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        res = convert(a.dxf, a.output, a.extrude, a.use_colors)
    except (OSError, ezdxf.DXFError, ValueError) as ex:
        print(f"エラー: {ex}")
        sys.exit(1)
    if res is None:
        sys.exit(3)
    print(f"書き出し: {res}")


if __name__ == "__main__":
    main()
