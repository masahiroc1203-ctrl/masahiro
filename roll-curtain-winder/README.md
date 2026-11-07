# ロールカーテン自動巻き取り機

既製のチェーン式ロールスクリーン（幅 1.8 m × 高さ 2.0 m）のボールチェーンを、STS3215 で引いて自動で昇降させる後付けユニット。
人がチェーンを引くと、それを検出してモーターが続きを巻き取る「アシスト式」にする。

![組立図](cad/images/assembly.png)

## これまでに決めたこと

| 項目 | 内容 | 決めた段階 |
|---|---|---|
| モーター | Feetech STS3215-C001（7.4 V、19.5 kg·cm、1:345、4096 分解能） | Gemini |
| 手動操作 | アシスト式（チェーンを引くと検出して自動で巻き取る） | Gemini |
| カーテン | 幅 1.8 m × 高さ 2.0 m、吊り下げ質量 約 1.7 kg | Gemini |
| 駆動方法 | パイプ直結ではなくチェーン（紐）を引く | Gemini |
| マイコン / 電源 | ESP32 / AC アダプタ 7.5 V 3 A の 1 系統 | Gemini |
| 駆動輪 | **14 歯ボールチェーン用スプロケット（PCD 26.96 mm、1 回転 84 mm）** | 本設計 |
| 取付 | **チェーンループの下端に壁付け。長穴で張りを調整。ガード + カバーで外れ止め** | 本設計 |
| 性能（推定） | 設計トルク 3.8 kg·cm（ストールの 19%）、全行程 約 40 秒 | 本設計 |
| 位置管理 | 速度モードで回し、回転数は ESP32 で数える。上限で原点出し、下限はソフトリミット | 本設計 |

## ドキュメント

- [docs/mechanical_design.md](docs/mechanical_design.md)：メカ設計書（方式・負荷計算・スプロケット・ハウジング・設置・制御側への要求・安全・未決事項）
- [docs/build_and_test.md](docs/build_and_test.md)：実測チェックリスト、部品表、配線、組立、試験手順

## ファイル

```
roll-curtain-winder/
├── calc/winder_calc.py   負荷・トルク・速度の計算（実測値で再計算できる）
├── cad/winder.scad       パラメトリック CAD（OpenSCAD）
├── cad/build.sh          STL と画像の再生成
├── cad/stl/              3D プリント用 STL（sprocket / housing / cover / cap）
└── cad/images/           組立図・断面図
```

## 使い方

```bash
python3 calc/winder_calc.py                                # 推定値で計算
```

```bash
python3 calc/winder_calc.py --f-up 22 --travel 1.85        # 実測値で再計算
```

```bash
./cad/build.sh                                             # STL と画像を作り直す（openscad が必要）
```

## 次にやること

1. 実物を測る（[build_and_test.md](docs/build_and_test.md) §1）：チェーン寸法、F_up、全行程 L、STS3215 のホーン寸法、取付位置
2. 測った値で歯数と CAD を確定 → スプロケットとハウジングを試し刷り
3. 試験 T1〜T8
4. ESP32 ファームウェア（[mechanical_design.md](docs/mechanical_design.md) §6 の仕様で実装）
