// ============================================================================
//  ロールカーテン自動巻き取り機  チェーン駆動ユニット（STS3215 + ボールチェーン）
//  OpenSCAD 2021.01 以降
//
//  座標系（組立状態）: X = 窓の幅方向（スプロケット軸）, Y = 壁から手前方向,
//                      Z = 上方向。壁（取付面）は Y = 0。スプロケット中心 = (0, y_c, 0)
//
//  出力する部品は `part` で切り替える:
//    openscad -D 'part="sprocket"' -o stl/sprocket.stl winder.scad
//    part = "assembly" | "assembly_open"（カバーなし） | "sprocket" | "housing" | "cover" | "cap"
//
//  [要実測] の付いた値は実物を測って書き換えること（docs/build_and_test.md 参照）。
// ============================================================================

part = "assembly";
$fn = 64;

// ---------------------------------------------------------------- チェーン
ball_d   = 4.5;   // [要実測] ボール径（樹脂ボールチェーン標準 4.5）
pitch    = 6.0;   // [要実測] ボール中心間ピッチ（標準 6.0）
cord_d   = 1.8;   // [要実測] ボール間の芯ひも径
n_teeth  = 14;    // スプロケット歯数（calc/winder_calc.py で決定）

// チェーンジョイント（ループをつなぐ部品）の逃げポケット
joint_relief = true;
joint_d      = 5.2;  // [要実測] ジョイント外径
joint_span   = 2;    // ジョイントが占めるピッチ数（2 = ボール3個分の長さを1つの溝にする）

// ---------------------------------------------------------------- 取付位置
y_c   = 45;   // [要実測] 取付面からチェーン2本の中心までの距離
z_top = 40;   // スプロケット中心からガード上端までの高さ

// ---------------------------------------------------------------- サーボ（STS3215）
srv_L = 45.2;  // ケース長さ
srv_W = 24.7;  // ケース幅
srv_H = 35.0;  // ケース高さ（出力軸方向）
srv_e = 11.5;  // [要実測] 出力軸中心から近い側のケース端までの距離
horn_stack = 5.5;  // [要実測] ケース上面からホーン上面までの高さ

horn_d        = 20.0; // [要実測] メタルホーン外径
horn_bolt_pcd = 14.0; // [要実測] ホーンのねじ穴ピッチ円径
horn_bolt_n   = 4;    // [要実測] ホーンのねじ穴数
horn_bolt_d   = 2.4;  // ねじ通し穴径（M2 = 2.4, M3 = 3.4）[要実測]
horn_bolt_hd  = 4.4;  // ねじ頭の座ぐり径（M2 = 4.4, M3 = 6.0）
center_hole_d = 6.0;  // ホーン中心ねじへのアクセス穴

// ---------------------------------------------------------------- 造形・すきま
clr     = 0.3;   // はめあいクリアランス
wall    = 2.4;   // 基本肉厚
plate_t = 4.0;   // 取付板厚
gap_x   = 0.8;   // スプロケット側面とガード壁のすきま
gap_r   = 1.0;   // フランジ外周とガード内周のすきま
guard_wall = 4.5; // ガード外周壁の厚さ（カバー固定ねじの下穴を壁の中に設ける）
hub_len = 4.5;   // ホーン当たり面からフランジ背面までのハブ長

// ============================================================================
//  派生寸法（ここから下は通常いじらない）
// ============================================================================
pcd_r      = pitch / (2 * sin(180 / n_teeth));
pocket_d   = ball_d + 0.4;
groove_w   = cord_d + 0.6;
groove_r   = pcd_r * cos(180 / n_teeth) - cord_d / 2 - 0.4;  // 芯ひも溝の底半径
tip_r      = pcd_r + 0.3 * ball_d;                            // 歯先半径
flange_r   = pcd_r + ball_d / 2 + 0.8;                        // フランジ外半径
flange_t   = 1.6;
chain_w    = pocket_d + 0.2;                                  // フランジ間の幅
spr_w      = chain_w + 2 * flange_t;                          // チェーン部の全幅
hub_r      = horn_d / 2 + 1.5;
guard_r    = flange_r + gap_r;                                // ガード内半径
guard_ro   = guard_r + guard_wall;                            // ガード外半径

// X 方向の位置関係（チェーン中心面を X = 0 とする）
x_flange_back = -spr_w / 2;
x_horn        = x_flange_back - hub_len;          // ホーン上面
x_case_top    = x_horn - horn_stack;              // サーボケース上面
x_case_bot    = x_case_top - srv_H;
x_bw1         = x_flange_back - gap_x;            // 背面壁（サーボ側の仕切り）の +X 面
x_bw0         = x_bw1 - wall;
x_cv0         = spr_w / 2 + gap_x;                // カバーの -X 面
x_cv1         = x_cv0 + wall;

// サーボケースの Y 範囲（出力軸を手前側の端に寄せて壁側へ伸ばす）
y_srv_lo = y_c + srv_e - srv_L;
y_srv_hi = y_c + srv_e;

echo(str("PCD = ", 2 * pcd_r, " mm, tip_r = ", tip_r, ", flange_r = ", flange_r,
         ", groove_r = ", groove_r, ", spr_w = ", spr_w));
echo(str("servo case Y = [", y_srv_lo, ", ", y_srv_hi, "], X = [", x_case_bot, ", ", x_case_top, "]"));
assert(y_srv_lo - clr - wall >= plate_t - 0.01, "サーボが取付板に干渉: y_c を大きくする");
assert(groove_r > center_hole_d / 2 + 3, "歯数が少なすぎる（ハブ強度不足）");
assert(hub_len > gap_x + wall, "hub_len が背面壁を貫通しない");

// ============================================================================
//  スプロケット（ローカル座標: 軸 = Z, z = 0 がホーン当たり面）
// ============================================================================
module pocket_at(i, d) {
    a = i * 360 / n_teeth;
    translate([pcd_r * cos(a), pcd_r * sin(a), 0]) sphere(d = d, $fn = 32);
}

module sprocket() {
    zc = hub_len + flange_t + chain_w / 2;   // チェーン中心面
    difference() {
        union() {
            cylinder(r = hub_r, h = hub_len);                                // ハブ
            translate([0, 0, hub_len]) cylinder(r = flange_r, h = flange_t);  // 背面フランジ
            translate([0, 0, hub_len + flange_t]) cylinder(r = tip_r, h = chain_w);
            translate([0, 0, hub_len + flange_t + chain_w]) cylinder(r = flange_r, h = flange_t);
        }
        // ボールポケット
        translate([0, 0, zc]) for (i = [0 : n_teeth - 1]) pocket_at(i, pocket_d);
        // 芯ひも溝
        translate([0, 0, zc - groove_w / 2])
            difference() {
                cylinder(r = flange_r + 1, h = groove_w);
                translate([0, 0, -1]) cylinder(r = groove_r, h = groove_w + 2);
            }
        // ジョイント逃げ（ポケット 0..joint_span を1本の溝にする）
        if (joint_relief)
            translate([0, 0, zc]) hull() for (i = [0 : joint_span]) {
                pocket_at(i, joint_d + 0.6);
                a = i * 360 / n_teeth;
                translate([(pcd_r + 3) * cos(a), (pcd_r + 3) * sin(a), 0]) sphere(d = joint_d + 0.6, $fn = 32);
            }
        // ホーン位置決め用の座ぐり
        translate([0, 0, -0.01]) cylinder(d = horn_d + clr, h = 1.0);
        // 中心穴
        translate([0, 0, -1]) cylinder(d = center_hole_d, h = 100);
        // ホーン固定ねじ（前面から座ぐり）
        for (i = [0 : horn_bolt_n - 1]) rotate([0, 0, 45 + i * 360 / horn_bolt_n]) {
            translate([horn_bolt_pcd / 2, 0, -1]) cylinder(d = horn_bolt_d, h = 100, $fn = 24);
            translate([horn_bolt_pcd / 2, 0, hub_len + 2.0]) cylinder(d = horn_bolt_hd, h = 100, $fn = 24);
        }
        // 合わせマーク（ジョイント逃げの位置）
        if (joint_relief) {
            a = joint_span * 180 / n_teeth;
            translate([0, 0, hub_len + spr_w - 0.6])
                rotate([0, 0, a]) translate([groove_r - 4, -0.6, 0]) cube([4, 1.2, 1]);
        }
    }
}

// ============================================================================
//  ハウジング（取付板 + サーボスリーブ + 背面壁 + チェーンガード）
// ============================================================================
plate_x0 = x_case_bot - wall - 1;
plate_x1 = x_cv1 + 16;
plate_z0 = -50;
plate_z1 = 54;

slot_w   = 4.5;   // 取付ねじ（φ4 木ねじ / M4）
slot_len = 20;    // 上下調整量 = チェーン張り調整
slots = [  // [x, z_center]
    [(x_case_bot + x_case_top) / 2,  34],
    [(x_case_bot + x_case_top) / 2, -34],
    [x_cv1 + 9, 0],
];

// YZ 断面でのガード外形（背面壁・カバーと共通）
module guard_outline_2d() {
    hull() {
        translate([y_c, 0]) circle(r = guard_ro);
        translate([0, 0]) square([y_c + guard_ro, z_top]);
        translate([0, -guard_ro]) square([plate_t, guard_ro + z_top]);
    }
}

// チェーンが通る空間（YZ 断面）
module chain_space_2d() {
    translate([y_c, 0]) circle(r = guard_r);
    translate([y_c - guard_r, 0]) square([2 * guard_r, z_top + 1]);
}

// YZ の2D形状を X 範囲 [x0, x1] に押し出す
module extrude_x(x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = x1 - x0) children();
}

module cap_boss_positions() {
    for (s = [-1, 1])
        translate([x_case_bot, (y_srv_lo + y_srv_hi) / 2, s * (srv_W / 2 + clr + wall + 3)])
            children();
}

module cover_screw_positions() {
    m = guard_r + guard_wall / 2;
    for (p = [[y_c - m, z_top - 6], [y_c + m, z_top - 6], [y_c, -m]])
        translate([x_cv0, p[0], p[1]]) children();
}

module housing() {
    yi0 = y_srv_lo - clr;  yi1 = y_srv_hi + clr;
    zi  = srv_W / 2 + clr;
    difference() {
        union() {
            // 取付板（XZ 面）
            translate([plate_x0, 0, plate_z0])
                cube([plate_x1 - plate_x0, plate_t, plate_z1 - plate_z0]);
            // サーボスリーブ（ケース底面から背面壁まで）
            translate([x_case_bot, 0, -zi - wall])
                cube([x_bw0 - x_case_bot + 0.01, yi1 + wall, 2 * (zi + wall)]);
            // カバー止めボス（サーボ後端）
            cap_boss_positions() rotate([0, 90, 0]) cylinder(r = 3.5, h = 8);
            // 背面壁（サーボとスプロケットの仕切り）
            extrude_x(x_bw0, x_bw1) guard_outline_2d();
            // ガード外周壁
            extrude_x(x_bw1 - 0.01, x_cv0) difference() {
                guard_outline_2d();
                chain_space_2d();
            }
        }
        // サーボ収納空間
        translate([x_case_bot - 1, yi0, -zi]) cube([srv_H + 1 + 0.01, yi1 - yi0, 2 * zi]);
        // ホーン回転空間（ケース上面から背面壁まで。壁側はケース当たり面として残す）
        translate([x_case_top - 0.01, y_c - horn_d / 2 - 1.5, -zi])
            cube([x_bw0 - x_case_top + 0.02, yi1 - (y_c - horn_d / 2 - 1.5), 2 * zi]);
        translate([x_case_top - 0.01, y_c, 0]) rotate([0, 90, 0]) cylinder(r = horn_d / 2 + 1.5, h = x_bw0 - x_case_top + 0.02);
        // ハブ貫通穴
        translate([x_bw0 - 1, y_c, 0]) rotate([0, 90, 0]) cylinder(r = hub_r + 1.0, h = wall + 2);
        // 取付スロット（上下に長穴 = チェーン張り調整）
        for (s = slots) translate([s[0], -1, s[1]]) hull() for (dz = [-slot_len / 2, slot_len / 2])
            translate([0, 0, dz]) rotate([-90, 0, 0]) cylinder(d = slot_w, h = plate_t + 2, $fn = 24);
        // ねじ下穴（M3 タッピング）
        cap_boss_positions() translate([-1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 2.5, h = 12, $fn = 16);
        cover_screw_positions() translate([1, 0, 0]) rotate([0, -90, 0]) cylinder(d = 2.5, h = 9, $fn = 16);
        // チェーン入口の面取り（ガード外周壁の内側上端）
        for (s = [-1, 1]) translate([(x_bw1 + x_cv0) / 2, y_c + s * guard_r, z_top])
            rotate([0, 90, 0]) cylinder(r = 2.5, h = x_cv0 - x_bw1 + 0.02, center = true, $fn = 4);
    }
}

// ============================================================================
//  カバー（+X 側。外すとチェーンを掛け外しできる）
// ============================================================================
module cover() {
    difference() {
        // 取付板とは干渉させない（Y >= plate_t + clr）
        extrude_x(x_cv0, x_cv1) intersection() {
            guard_outline_2d();
            translate([plate_t + clr, -200]) square([400, 400]);
        }
        // 合わせマーク確認窓
        translate([x_cv0 - 1, y_c, 0]) rotate([0, 90, 0]) cylinder(r = groove_r - 1, h = wall + 2);
        cover_screw_positions() {
            translate([-1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 3.4, h = wall + 2, $fn = 16);
            translate([wall - 1.2, 0, 0]) rotate([0, 90, 0]) cylinder(d = 6.2, h = 2, $fn = 24);
        }
    }
}

// ============================================================================
//  サーボ押さえ（後端キャップ。中央は配線用に大きく開ける）
// ============================================================================
module cap() {
    zi = srv_W / 2 + clr;
    y0 = y_srv_lo - clr - wall;  y1 = y_srv_hi + clr + wall;
    difference() {
        hull() {
            translate([x_case_bot - wall, y0, -zi - wall]) cube([wall, y1 - y0, 2 * (zi + wall)]);
            cap_boss_positions() translate([-wall, 0, 0]) rotate([0, 90, 0]) cylinder(r = 3.5, h = wall);
        }
        translate([x_case_bot - wall - 1, y0 + wall + 5, -zi + 4]) cube([wall + 2, y1 - y0 - 2 * wall - 10, 2 * zi - 8]);
        cap_boss_positions() translate([-wall - 1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 3.4, h = wall + 2, $fn = 16);
    }
}

// ============================================================================
//  プレビュー用ダミー
// ============================================================================
module servo_dummy() {
    color("#333") translate([x_case_bot, y_srv_lo, -srv_W / 2]) cube([srv_H, srv_L, srv_W]);
    color("silver") translate([x_case_top, y_c, 0]) rotate([0, 90, 0]) cylinder(d = horn_d, h = horn_stack);
}

module chain_dummy(leg = 90) {
    color("white") {
        for (i = [0 : n_teeth / 2]) {
            a = 180 + i * 360 / n_teeth;
            translate([0, y_c + pcd_r * cos(a), pcd_r * sin(a)]) sphere(d = ball_d, $fn = 20);
        }
        for (s = [-1, 1]) for (k = [1 : floor(leg / pitch)])
            translate([0, y_c + s * pcd_r, k * pitch]) sphere(d = ball_d, $fn = 20);
        for (s = [-1, 1]) translate([0, y_c + s * pcd_r, 0]) cylinder(d = cord_d, h = leg, $fn = 12);
    }
}

module sprocket_placed() {
    // ローカル角 a のポケットは YZ 面で角度 a-90 に来る。270 回すとポケット0が壁側チェーンの接点に一致
    translate([x_horn, y_c, 0]) rotate([0, 90, 0]) rotate([0, 0, 270]) sprocket();
}

// ============================================================================
if (part == "assembly" || part == "assembly_open") {
    color("#4a7bd0") housing();
    color("#e0a030") sprocket_placed();
    if (part == "assembly") color("#4a7bd0", 0.35) cover();
    color("#4a7bd0") cap();
    servo_dummy();
    chain_dummy();
} else if (part == "sprocket") {
    // 前面（ねじ頭側）を下にして造形
    rotate([180, 0, 0]) translate([0, 0, -(hub_len + spr_w)]) sprocket();
} else if (part == "housing") {
    // 取付板を下にして造形
    rotate([90, 0, 0]) housing();
} else if (part == "cover") {
    rotate([0, -90, 0]) translate([-x_cv0, 0, 0]) cover();
} else if (part == "cap") {
    rotate([0, -90, 0]) translate([-(x_case_bot - wall), 0, 0]) cap();
} else if (part == "section" || part == "section_teeth") {
    // 断面図（2D）: 横軸 = Y（左が壁）, 縦軸 = Z。section = チェーン中心面, section_teeth = 歯の面
    dx = (part == "section") ? 0 : 1.5;
    rotate([0, 0, -90]) {
        color("#e0a030") projection(cut = true) rotate([0, -90, 0]) translate([-dx, 0, 0]) sprocket_placed();
        color("#222") translate([0, 0, 1]) projection(cut = true) rotate([0, -90, 0]) translate([-dx, 0, 0]) chain_dummy(36);
        if (part == "section")
            color("#4a7bd0") translate([0, 0, -1]) projection(cut = true) rotate([0, -90, 0]) housing();
    }
}
