; OctoPrint「設定 → GCODEスクリプト → 印刷ジョブがキャンセルされた後」に貼る
M104 S0
M140 S0
M106 S0
G91
G1 Z10 F600
G90
G1 X0 Y200 F6000
M84 X Y E
