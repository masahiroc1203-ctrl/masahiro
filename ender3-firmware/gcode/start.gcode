; ===== Ender-3 Pro Sprite 開始Gコード（PrusaSlicer / OrcaSlicer 用・相対E前提）=====
; 方針：ベッドを先に温め切ってから原点を取る（熱で反ったベッドで原点・メッシュを合わせる）
M140 S[first_layer_bed_temperature]   ; ベッド加熱開始
M104 S150                             ; ノズルは垂れない温度で予熱
M190 S[first_layer_bed_temperature]   ; ベッドが温まるまで待つ
G28                                   ; 原点（Z は BLTouch でベッド中央）
G29 L0                                ; 保存済みメッシュ（スロット0）を読み込み
G29 A                                 ; メッシュ補正を有効化
M420 Z10                              ; 10mm かけて補正を薄める
G1 Z5 F600
G1 X3 Y20 F6000                       ; プライム位置へ
M109 S[first_layer_temperature]       ; ノズル本加熱
M83                                   ; 相対E
G1 Z0.28 F600
G1 X3 Y180 E12 F1500                  ; プライムライン1本目
G1 X3.5 Y180 F3000
G1 X3.5 Y20 E12 F1500                 ; 2本目
G1 E-0.8 F2400                        ; 少し引き込み
G1 Z2 F600
G92 E0
; ===== ここまで =====
