// ============================================================================
//  ロールカーテン自動巻き取り機  駆動ユニット v2（ロール直下・チェーン2本挟み込み式）
//  OpenSCAD 2021.01 以降
//
//  構成: ヘッドから垂れる2本のチェーンの間にスプロケットを置き、各チェーンを外側の
//        ピンチローラー（MR63ZZ）で押し付けて約 50° 巻き掛ける。ループの下側は自由に
//        垂れたままなので、これまでどおり手で引いて操作できる。
//
//  座標系（組立状態）: X = 窓の幅方向（スプロケット軸、+X = スクリーン側, -X = 外側）,
//                      Y = 取付面から手前方向, Z = 上。取付面は Y = 0。
//                      スプロケット中心 = (0, y_c, 0)。-Y 側 = 奥（壁側）のチェーン。
//
//  部品の出力:  openscad -D 'part="sprocket"' -o stl/sprocket.stl winder.scad
//    part = "assembly" | "assembly_open"（カバーなし） | "section"（断面図）
//         | "sprocket" | "housing" | "cover" | "cap" | "stopper"
//
//  [要実測] の値は実物を測って書き換える（docs/build_and_test.md §1）。
// ============================================================================

part = "assembly";
$fn = 64;

// ---------------------------------------------------------------- チェーン
ball_d  = 4.5;   // [要実測] ボール径
pitch   = 6.0;   // [要実測] ボール中心間ピッチ
cord_d  = 1.8;   // [要実測] 芯ひも径
n_teeth = 14;    // スプロケット歯数（calc/winder_calc.py で決定）

// ---------------------------------------------------------------- ヘッド・取付
y_c       = 50;  // [要実測] 取付面から、ヘッドの2本のチェーンの中間まで
s_head    = 19;  // [要実測] ヘッドから垂れる2本のチェーンの中心間距離の 1/2
head_gap  = 30;  // ユニット上面からヘッドボックス下面まで
head_drop = 25;  // [要実測] ヘッドボックス下面からヘッドのチェーンホイール中心まで（概略）
x_screen  = 12;  // [要実測] チェーン面からスクリーン（ウエイトバー）端まで

// ---------------------------------------------------------------- ピンチローラー
brg_od    = 6.0; // MR63ZZ（3 x 6 x 2.5）
brg_w     = 2.5;
gamma     = 57;  // ローラー位置: スプロケット中心から見て水平から下に何度か
pinch_clr = 0.2; // ローラーとスプロケットでボールを挟むすきま

// ---------------------------------------------------------------- サーボ（STS3215）
srv_L = 45.2;  srv_W = 24.7;  srv_H = 35.0;
srv_e = 11.5;       // [要実測] 出力軸中心から近い側のケース端まで
horn_stack = 5.5;   // [要実測] ケース上面からホーン上面まで
horn_d        = 20.0; // [要実測] ホーン外径
horn_bolt_pcd = 14.0; // [要実測] ホーンのねじ穴ピッチ円径
horn_bolt_n   = 4;    // [要実測]
horn_bolt_d   = 2.4;  // [要実測] M2 = 2.4 / M3 = 3.4
horn_bolt_hd  = 4.4;  // M2 = 4.4 / M3 = 6.0
center_hole_d = 6.0;

// ---------------------------------------------------------------- 原点ストッパー・センサー
stp_x = 10;  stp_y = 12;  stp_h = 15;   // ストッパー外形（X, Y, Z）
mag_d = 4.2; mag_t = 2.2;               // 磁石 φ4 x 2 用のポケット
hall_w = 5.4; hall_t = 4.2; hall_h = 6; // ホール IC（TO-92）用ポケット

// ---------------------------------------------------------------- 造形・すきま
clr        = 0.3;
wall       = 2.4;
plate_t    = 4.0;
gap_x      = 0.6;  // スプロケット側面と背面壁・カバーのすきま
gap_r      = 1.0;  // ボール外端とガイド壁のすきま
guard_wall = 5.0;
cover_t    = 3.0;
hub_len    = 4.5;
z_top      = 20;   // スプロケット中心からユニット上面まで
z_bot      = -30;  // スプロケット中心からユニット下面（ストッパーが当たる面）まで

// ============================================================================
//  派生寸法
// ============================================================================
pcd_r    = pitch / (2 * sin(180 / n_teeth));
pocket_d = ball_d + 0.4;
groove_w = cord_d + 0.6;
groove_r = pcd_r * cos(180 / n_teeth) - cord_d / 2 - 0.4;
tip_r    = pcd_r + 0.3 * ball_d;
chain_w  = pocket_d + 0.2;              // スプロケットのチェーン部の幅
clr_disk = tip_r + 0.4;                 // ここより外にボールは出られない（はぎ取り）
r_ch     = ball_d / 2 + gap_r;          // チェーン通路の半幅

rho    = brg_od / 2 + ball_d / 2;       // ローラー周りのボール中心半径
D_roll = pcd_r + rho + pinch_clr;       // スプロケット中心〜ローラー中心
roll_u = D_roll * cos(gamma);
roll_z = -D_roll * sin(gamma);
leg_u  = roll_u - rho;                  // ユニット下でのチェーン位置（中心から）

z_head = z_top + head_gap + head_drop;
a_in   = atan2(z_head, s_head) - acos(pcd_r / sqrt(s_head * s_head + z_head * z_head));
wrap   = gamma + a_in;

// X 方向（チェーン中心面 X = 0）
x_core_back = -chain_w / 2;
x_bw1       = x_core_back - gap_x;      // 背面壁 +X 面
x_bw0       = x_bw1 - wall;             // 背面壁 -X 面
x_cv0       = chain_w / 2 + gap_x;      // カバー -X 面
x_cv1       = x_cv0 + cover_t;          // カバー +X 面（スクリーン側の最外面）
x_horn      = x_core_back - hub_len;
x_case_top  = x_horn - horn_stack;
x_case_bot  = x_case_top - srv_H;
cav_w       = x_cv0 - x_bw1;
sp_t        = (cav_w - brg_w) / 2;      // 軸受の左右スペーサー厚
hub_r       = horn_d / 2 + 1.5;

y_srv_lo = y_c + srv_e - srv_L;
y_srv_hi = y_c + srv_e;

echo(str("PCD=", 2 * pcd_r, " tip_r=", tip_r, " roller D=", D_roll, " at (", roll_u, ", ", roll_z, ")"));
echo(str("wrap=", wrap, " deg (", a_in, " .. ", -gamma, "), legs below at +-", leg_u, " mm"));
echo(str("cover outer X=", x_cv1, " (screen at ", x_screen, ")"));
assert(wrap >= 40, "巻き掛け角が小さすぎる: gamma を大きく / s_head を測り直す");
assert(leg_u - ball_d / 2 - gap_x >= 1.2, "ユニット下の2本が近すぎる: gamma を小さく");
assert(D_roll - brg_od / 2 - tip_r >= 0.5, "ローラーが歯先に近すぎる");
assert(x_cv1 + 1 <= x_screen, "カバーがスクリーンに当たる: x_screen を確認");
assert(y_srv_lo - clr - wall >= plate_t - 0.01, "サーボが取付板に干渉: y_c を大きく");

// ============================================================================
//  チェーンの通り道（YZ 平面, u = Y - y_c）
// ============================================================================
// ヘッドからの直線上で高さ z の点
function in_u(z) = let(t1u = pcd_r * cos(a_in), t1z = pcd_r * sin(a_in))
    s_head + (t1u - s_head) * (z - z_head) / (t1z - z_head);

// 右側（s = +1: 手前）/ 左側（s = -1: 奥）のボール中心の経路
function leg_path(s, z_from, z_to) = concat(
    [[s * in_u(z_from), z_from]],
    [for (a = [a_in : -3 : -gamma]) [s * pcd_r * cos(a), pcd_r * sin(a)]],
    [[s * pcd_r * cos(gamma), -pcd_r * sin(gamma)]],
    [for (t = [180 - gamma : 6 : 179]) [s * (roll_u + rho * cos(t)), roll_z + rho * sin(t)]],
    [[s * leg_u, roll_z], [s * leg_u, z_to]]
);

module path_band_2d(p, r) {
    for (i = [0 : len(p) - 2]) hull() {
        translate(p[i]) circle(r = r, $fn = 24);
        translate(p[i + 1]) circle(r = r, $fn = 24);
    }
}

// チェーンが通る空間（取付面基準の YZ 座標）
module cavity_2d(open = true) {
    zt = open ? z_top + 10 : z_top - 1;
    zb = open ? z_bot - 10 : z_bot + 1;
    translate([y_c, 0]) {
        circle(r = clr_disk);
        for (s = [-1, 1]) {
            path_band_2d(leg_path(s, zt, zb), r_ch);
            // 上部入口: ヘッドの位置ずれ ±3 mm を受ける
            if (open) hull() {
                translate([s * in_u(z_top - 6), z_top - 6]) circle(r = r_ch, $fn = 24);
                translate([s * in_u(z_top) - 3 - r_ch, z_top - 0.01]) square([2 * (r_ch + 3), zt - z_top + 0.01]);
            }
            translate([s * roll_u, roll_z]) circle(r = brg_od / 2 + 0.6);
        }
    }
}

// ハウジング外形（YZ）
module housing_outline_2d() {
    intersection() {
        hull() {
            offset(r = guard_wall) cavity_2d(open = false);
            translate([0, z_bot]) square([plate_t, z_top - z_bot]);
        }
        translate([0, z_bot]) square([500, z_top - z_bot]);
    }
}

module extrude_x(x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = x1 - x0) children();
}

// ============================================================================
//  スプロケット（ローカル: 軸 = Z, z = 0 がホーン当たり面）
// ============================================================================
module sprocket() {
    zc = hub_len + chain_w / 2;
    difference() {
        union() {
            cylinder(r = hub_r, h = hub_len);
            translate([0, 0, hub_len]) cylinder(r = tip_r, h = chain_w);
        }
        translate([0, 0, zc]) for (i = [0 : n_teeth - 1]) rotate([0, 0, i * 360 / n_teeth])
            translate([pcd_r, 0, 0]) sphere(d = pocket_d, $fn = 32);
        translate([0, 0, zc - groove_w / 2]) difference() {
            cylinder(r = tip_r + 1, h = groove_w);
            translate([0, 0, -1]) cylinder(r = groove_r, h = groove_w + 2);
        }
        translate([0, 0, -0.01]) cylinder(d = horn_d + clr, h = 1.0);
        translate([0, 0, -1]) cylinder(d = center_hole_d, h = 100);
        for (i = [0 : horn_bolt_n - 1]) rotate([0, 0, 45 + i * 360 / horn_bolt_n]) {
            translate([horn_bolt_pcd / 2, 0, -1]) cylinder(d = horn_bolt_d, h = 100, $fn = 24);
            translate([horn_bolt_pcd / 2, 0, hub_len + 2.0]) cylinder(d = horn_bolt_hd, h = 100, $fn = 24);
        }
    }
}

// ============================================================================
//  ハウジング
// ============================================================================
plate_x0 = x_case_bot - wall - 1;
plate_x1 = x_cv1;
plate_z0 = -46;
plate_z1 = 46;
slot_w = 4.5;  slot_len = 10;   // 上下 ±5 mm の位置合わせ
slots = [[(x_case_bot + x_case_top) / 2, 36], [(x_case_bot + x_case_top) / 2, -36]];

ear_t  = 5.5;                       // センサー台の厚さ（X）
ear_z0 = z_bot - 10;
ear_z1 = z_bot + 8;

module roller_positions() { for (s = [-1, 1]) translate([0, y_c + s * roll_u, roll_z]) children(); }

module cap_boss_positions() {
    for (s = [-1, 1])
        translate([x_case_bot, (y_srv_lo + y_srv_hi) / 2, s * (srv_W / 2 + clr + wall + 3)]) children();
}

cover_screws = [[16, 10], [16, -22], [y_c + pcd_r + r_ch + guard_wall / 2, -2]];
module cover_screw_positions() { for (p = cover_screws) translate([x_cv0, p[0], p[1]]) children(); }

module housing() {
    yi0 = y_srv_lo - clr;  yi1 = y_srv_hi + clr;  zi = srv_W / 2 + clr;
    difference() {
        union() {
            translate([plate_x0, 0, plate_z0]) cube([plate_x1 - plate_x0, plate_t, plate_z1 - plate_z0]);
            translate([x_case_bot, 0, -zi - wall]) cube([x_bw0 - x_case_bot + 0.01, yi1 + wall, 2 * (zi + wall)]);
            cap_boss_positions() rotate([0, 90, 0]) cylinder(r = 3.5, h = 8);
            extrude_x(x_bw0, x_bw1) housing_outline_2d();                                   // 背面壁
            extrude_x(x_bw1 - 0.01, x_cv0) difference() { housing_outline_2d(); cavity_2d(); } // 通路
            // ローラー軸のボス（背面壁の外側）と軸受スペーサー（内側）
            roller_positions() {
                translate([x_bw0 - 5, 0, 0]) rotate([0, 90, 0]) cylinder(r = 3.5, h = 5.01);
                translate([x_bw1 - 0.01, 0, 0]) rotate([0, 90, 0]) cylinder(r = 2.0, h = sp_t + 0.01);
            }
            // 原点・下限センサー台（外側の下端。ストッパーの側面がここに沿って当たる）
            translate([x_bw0 - ear_t, y_c - leg_u - stp_y / 2, ear_z0])
                cube([ear_t + 0.01, 2 * leg_u + stp_y, ear_z1 - ear_z0]);
        }
        // サーボ収納・ホーン回転空間
        translate([x_case_bot - 1, yi0, -zi]) cube([srv_H + 1 + 0.01, yi1 - yi0, 2 * zi]);
        translate([x_case_top - 0.01, y_c - horn_d / 2 - 1.5, -zi])
            cube([x_bw0 - x_case_top + 0.02, yi1 - (y_c - horn_d / 2 - 1.5), 2 * zi]);
        translate([x_case_top - 0.01, y_c, 0]) rotate([0, 90, 0]) cylinder(r = horn_d / 2 + 1.5, h = x_bw0 - x_case_top + 0.02);
        // ハブ貫通穴
        translate([x_bw0 - 1, y_c, 0]) rotate([0, 90, 0]) cylinder(r = hub_r + 1.0, h = wall + 2);
        // ローラー軸の下穴（M3 タッピング）
        roller_positions() translate([x_bw0 - 6, 0, 0]) rotate([0, 90, 0]) cylinder(d = 2.5, h = x_bw1 - x_bw0 + sp_t + 7, $fn = 16);
        // 取付スロット
        for (s = slots) translate([s[0], -1, s[1]]) hull() for (dz = [-slot_len / 2, slot_len / 2])
            translate([0, 0, dz]) rotate([-90, 0, 0]) cylinder(d = slot_w, h = plate_t + 2, $fn = 24);
        // ねじ下穴
        cap_boss_positions() translate([-1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 2.5, h = 12, $fn = 16);
        cover_screw_positions() translate([1, 0, 0]) rotate([0, -90, 0]) cylinder(d = 2.5, h = cav_w + wall, $fn = 16);
        // ホール IC ポケット（下から差し込み、平らな検出面を +X = ストッパー側に向ける）
        for (s = [-1, 1]) translate([x_bw0 - 0.8 - hall_t, y_c + s * leg_u - hall_w / 2, ear_z0 - 1])
            cube([hall_t, hall_w, (z_bot - 1.5) - ear_z0 + 1]);
    }
}

// ============================================================================
//  カバー（スクリーン側。ローラー軸を兼ねた M3 ねじで固定）
// ============================================================================
module cover() {
    difference() {
        union() {
            extrude_x(x_cv0, x_cv1) intersection() {
                housing_outline_2d();
                translate([plate_t + clr, -200]) square([500, 400]);
            }
            roller_positions() translate([x_cv0 - sp_t, 0, 0]) rotate([0, 90, 0]) cylinder(r = 2.0, h = sp_t + 0.01);
        }
        for (p = cover_screws) translate([0, p[0], p[1]]) {
            translate([x_cv0 - 1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 3.4, h = cover_t + 2, $fn = 16);
            translate([x_cv1 - 1.8, 0, 0]) rotate([0, 90, 0]) cylinder(d = 6.2, h = 2, $fn = 24);
        }
        roller_positions() {
            translate([x_cv0 - sp_t - 1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 3.4, h = cover_t + sp_t + 2, $fn = 16);
            translate([x_cv1 - 1.8, 0, 0]) rotate([0, 90, 0]) cylinder(d = 6.2, h = 2, $fn = 24);
        }
    }
}

// ============================================================================
//  サーボ押さえ（後端キャップ）
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
//  ストッパー（チェーンにはさんで止める2つ割り。上面がユニット下面に当たる）
//  ローカル: チェーン軸 = Z、上面 z = stp_h。half = -1 / +1 で X の左右半分
// ============================================================================
module stopper_half(half) {
    difference() {
        translate([half < 0 ? -stp_x / 2 : 0.1, -stp_y / 2, 0]) cube([stp_x / 2 - 0.1, stp_y, stp_h]);
        translate([0, 0, -1]) cylinder(d = cord_d + 0.4, h = stp_h + 2, $fn = 16);
        for (z = [stp_h / 2 - pitch / 2, stp_h / 2 + pitch / 2]) translate([0, 0, z]) sphere(d = ball_d + 0.3, $fn = 32);
        // 締結 M2（-X 側は通し穴、+X 側は下穴）
        for (y = [-stp_y / 2 + 2, stp_y / 2 - 2]) translate([0, y, stp_h / 2]) rotate([0, 90, 0])
            cylinder(d = half < 0 ? 2.2 : 1.6, h = stp_x + 2, center = true, $fn = 16);
        // 磁石（外側の面、上面から 3.75 mm 下 = ホール IC の高さ）
        translate([half * (stp_x / 2 - mag_t / 2 + 0.01), 0, stp_h - 3.75]) rotate([0, 90, 0])
            cylinder(d = mag_d, h = mag_t, center = true, $fn = 24);
    }
}

// ============================================================================
//  プレビュー用ダミー
// ============================================================================
module servo_dummy() {
    color("#333") translate([x_case_bot, y_srv_lo, -srv_W / 2]) cube([srv_H, srv_L, srv_W]);
    color("silver") translate([x_case_top, y_c, 0]) rotate([0, 90, 0]) cylinder(d = horn_d, h = horn_stack);
}

module ball_line(p, q) {
    n = max(1, floor(norm(q - p) / pitch));
    for (k = [0 : n]) translate(p + (q - p) * k / n) sphere(d = ball_d, $fn = 16);
    hull() { translate(p) sphere(d = cord_d, $fn = 8); translate(q) sphere(d = cord_d, $fn = 8); }
}

spr_rot = -gamma;  // ポケット 0 の位置（YZ 面の角度）
function wrap180(a) = let(b = ((a % 360) + 360) % 360) b > 180 ? b - 360 : b;
module chain_dummy(z_low = -90) {
    color("white") for (s = [-1, 1]) {
        // ヘッド〜巻き掛け開始
        ball_line([0, y_c + s * s_head, z_head], [0, y_c + s * pcd_r * cos(a_in), pcd_r * sin(a_in)]);
        // スプロケット上（巻き掛け範囲にあるポケット）。左側は右側の鏡像の範囲で判定
        for (k = [0 : n_teeth - 1]) let(a = wrap180(spr_rot + k * 360 / n_teeth), m = wrap180(180 - a))
            if ((s > 0 ? a : m) >= -gamma - 0.1 && (s > 0 ? a : m) <= a_in + 0.1)
                translate([0, y_c + pcd_r * cos(a), pcd_r * sin(a)]) sphere(d = ball_d, $fn = 16);
        // ローラー周り〜下へ
        for (t = [180 - gamma : 360 * pitch / (2 * PI * rho) : 180])
            translate([0, y_c + s * (roll_u + rho * cos(t)), roll_z + rho * sin(t)]) sphere(d = ball_d, $fn = 16);
        ball_line([0, y_c + s * leg_u, roll_z], [0, y_c + s * leg_u, z_low]);
    }
}

module stopper_docked() {
    // 奥側（-Y）のチェーンに付けた上限ストッパーがユニット下面に当たった状態 = 原点
    translate([0, y_c - leg_u, z_bot - stp_h]) { stopper_half(-1); stopper_half(1); }
}

module rollers() {
    color("silver") roller_positions() translate([-brg_w / 2, 0, 0]) rotate([0, 90, 0])
        difference() { cylinder(d = brg_od, h = brg_w); translate([0, 0, -1]) cylinder(d = 3, h = brg_w + 2); }
}

module sprocket_placed() {
    translate([x_horn, y_c, 0]) rotate([0, 90, 0]) rotate([0, 0, spr_rot + 90]) sprocket();
}

module head_dummy() {
    color("#cccccc", 0.35) translate([-15, y_c - 40, z_top + head_gap]) cube([140, 80, 55]);
}

// ============================================================================
if (part == "assembly" || part == "assembly_open") {
    color("#4a7bd0") housing();
    color("#e0a030") sprocket_placed();
    rollers();
    if (part == "assembly") color("#4a7bd0", 0.35) cover();
    color("#4a7bd0") cap();
    color("#d04a4a") stopper_docked();
    servo_dummy();
    chain_dummy();
    head_dummy();
} else if (part == "section") {
    // チェーン中心面（X = 0）の断面。横軸 = Y（左が取付面）、縦軸 = Z
    rotate([0, 0, -90]) {
        color("#4a7bd0") translate([0, 0, -1]) projection(cut = true) rotate([0, -90, 0]) housing();
        color("#e0a030") projection(cut = true) rotate([0, -90, 0]) translate([-1.5, 0, 0]) sprocket_placed();
        color("silver") translate([0, 0, 0.5]) projection(cut = true) rotate([0, -90, 0]) rollers();
        color("#222") translate([0, 0, 1]) projection(cut = true) rotate([0, -90, 0]) chain_dummy(z_bot - 25);
        color("#d04a4a") translate([0, 0, 0.8]) projection(cut = true) rotate([0, -90, 0]) translate([1, 0, 0]) stopper_docked();
    }
} else if (part == "sprocket") {
    rotate([180, 0, 0]) translate([0, 0, -(hub_len + chain_w)]) sprocket();
} else if (part == "housing") {
    rotate([90, 0, 0]) housing();
} else if (part == "cover") {
    rotate([0, -90, 0]) translate([-x_cv0, 0, 0]) cover();
} else if (part == "cap") {
    rotate([0, -90, 0]) translate([-(x_case_bot - wall), 0, 0]) cap();
} else if (part == "stopper") {
    // 割り面を下にして 2 個分（上限用・下限用）並べる
    for (i = [0, 1]) translate([0, i * 20, 0]) {
        translate([0, 0, -0.1]) rotate([0, 90, 0]) translate([0, 0, -stp_h / 2]) stopper_half(-1);
        translate([20, 0, -0.1]) rotate([0, -90, 0]) translate([0, 0, -stp_h / 2]) stopper_half(1);
    }
}
