// ===================================================================
// ImageJ/Fiji バッチ HSB 解析マクロ
//
// 処理フロー:
//   1. 画像フォルダ選択
//   2. 代表画像で円形ROIを複数設定・ナンバリング
//   3. HSB 閾値パラメータ設定
//   4. 全画像に同一ROIを適用してバッチ処理
//   5. 抽出面積を CSV に出力
//
// 必要環境: Fiji (ImageJ 2.x 以上)
// ===================================================================

// --- 閾値パラメータ ---
var hMin = 0,  hMax = 255;
var sMin = 50, sMax = 255;
var bMin = 50, bMax = 255;

// ===================================================================
// Step 1: フォルダ選択
// ===================================================================
inputDir  = getDirectory("解析対象の画像フォルダを選択してください");
outputDir = getDirectory("結果の出力フォルダを選択してください");

// ===================================================================
// Step 2: 画像ファイルリスト取得
// ===================================================================
allFiles   = getFileList(inputDir);
imgFiles   = newArray(allFiles.length);
imgCount   = 0;
supportExt = newArray(".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp");

for (i = 0; i < allFiles.length; i++) {
    fn = toLowerCase(allFiles[i]);
    for (j = 0; j < supportExt.length; j++) {
        if (endsWith(fn, supportExt[j])) {
            imgFiles[imgCount++] = allFiles[i];
            break;
        }
    }
}
imgFiles = Array.trim(imgFiles, imgCount);

if (imgCount == 0)
    exit("指定フォルダに対応する画像ファイルが見つかりませんでした。\n" +
         "(.tif .tiff .png .jpg .jpeg .bmp)");

print("=== HSB バッチ解析 開始 ===");
print("対象ファイル数: " + imgCount);

// ===================================================================
// Step 3: 代表画像を開いて円形ROIを設定
// ===================================================================
open(inputDir + imgFiles[0]);
repID = getImageID();

if (bitDepth() != 24) {
    close();
    exit("RGB カラー画像（24-bit）が必要です。\n対象ファイル: " + imgFiles[0]);
}

// 楕円ツールに切り替え
setTool("oval");

// ROI Manager を初期化して表示
run("ROI Manager...");
roiManager("reset");
roiManager("Show All");

waitForUser("【Step 1/2】  検査エリア（ROI）の設定",
    "代表画像で検査エリアを設定してください。\n\n" +
    "　画像: " + imgFiles[0] + "\n\n" +
    "【操作手順】\n" +
    "  1. ツールバーの楕円ツール（○）を選択\n" +
    "     ・Shift + ドラッグ で正円になります\n\n" +
    "  2. 検査したいエリアを描く\n\n" +
    "  3. ROI Manager の「Add」ボタン、または T キーで登録\n\n" +
    "  4. 手順1〜3 を繰り返して全エリアを登録\n\n" +
    "登録が完了したら「OK」を押してください。");

roiCount = roiManager("count");
if (roiCount == 0) {
    selectImage(repID);
    close();
    exit("ROI が登録されていません。マクロを終了します。");
}

// ROI にナンバリング（Area_1, Area_2 ...）
for (i = 0; i < roiCount; i++) {
    roiManager("select", i);
    roiManager("rename", "Area_" + (i + 1));
}
roiManager("deselect");

print("登録 ROI 数: " + roiCount + " エリア");

// 代表画像を閉じる
selectImage(repID);
close();

// ===================================================================
// Step 4: HSB 閾値設定ダイアログ
// ===================================================================
Dialog.create("【Step 2/2】  HSB 閾値設定");
Dialog.addMessage("抽出したい色の HSB 範囲を指定してください（0 〜 255）\n");
Dialog.addMessage("── Hue（色相）──────────────────────────");
Dialog.addMessage("  0=赤  43=黄  85=緑  128=シアン  170=青  213=マゼンタ");
Dialog.addNumber("  最小値", hMin);
Dialog.addNumber("  最大値", hMax);
Dialog.addMessage("── Saturation（彩度）───────────────────");
Dialog.addMessage("  0=白・グレー  255=鮮やか");
Dialog.addNumber("  最小値", sMin);
Dialog.addNumber("  最大値", sMax);
Dialog.addMessage("── Brightness（明度）───────────────────");
Dialog.addMessage("  0=黒  255=明るい");
Dialog.addNumber("  最小値", bMin);
Dialog.addNumber("  最大値", bMax);
Dialog.show();

hMin = Dialog.getNumber();
hMax = Dialog.getNumber();
sMin = Dialog.getNumber();
sMax = Dialog.getNumber();
bMin = Dialog.getNumber();
bMax = Dialog.getNumber();

print("H: " + hMin + "-" + hMax +
      "  S: " + sMin + "-" + sMax +
      "  B: " + bMin + "-" + bMax);

// ===================================================================
// Step 5: バッチ処理
// ===================================================================
setOption("BlackBackground", true);  // 閾値内 → 白(255)、外 → 黒(0)
setBatchMode(true);

// CSV ヘッダー
csvPath = outputDir + "hsb_analysis_results.csv";
csvFile = File.open(csvPath);

header = "ファイル名";
for (r = 0; r < roiCount; r++) {
    label = "Area_" + (r + 1);
    header += "," + label + "_抽出面積(px)";
    header += "," + label + "_ROI面積(px)";
    header += "," + label + "_割合(%)";
}
print(csvFile, header);

// 各画像を処理
errorCount = 0;
for (i = 0; i < imgCount; i++) {
    fname = imgFiles[i];

    open(inputDir + fname);
    if (nImages == 0) {
        print("SKIP (読込失敗): " + fname);
        errorCount++;
        continue;
    }
    imgID = getImageID();

    if (bitDepth() != 24) {
        print("SKIP (非RGB): " + fname);
        selectImage(imgID); close();
        errorCount++;
        continue;
    }

    // --- 全体 HSB マスクを1回作成 ---
    run("Select None");
    run("Duplicate...", "title=work");
    workID = getImageID();

    // HSB スタックへ変換（スライス1=H, 2=S, 3=B）
    run("HSB Stack");

    // H チャンネルのバイナリマスク
    selectImage(workID); setSlice(1);
    run("Duplicate...", "title=mask_H use");
    maskH = getImageID();
    setThreshold(hMin, hMax);
    run("Convert to Mask");

    // S チャンネルのバイナリマスク
    selectImage(workID); setSlice(2);
    run("Duplicate...", "title=mask_S use");
    maskS = getImageID();
    setThreshold(sMin, sMax);
    run("Convert to Mask");

    // B チャンネルのバイナリマスク
    selectImage(workID); setSlice(3);
    run("Duplicate...", "title=mask_B use");
    maskB = getImageID();
    setThreshold(bMin, bMax);
    run("Convert to Mask");

    // AND 合成: H ∩ S ∩ B → 条件に合致するピクセルだけ白
    imageCalculator("AND create", "mask_H", "mask_S");
    maskHS = getImageID();
    rename("mask_HS");
    imageCalculator("AND create", "mask_HS", "mask_B");
    finalMask = getImageID();
    rename("final_mask");

    // 中間マスクをクローズ
    selectImage(maskH);  close();
    selectImage(maskS);  close();
    selectImage(maskB);  close();
    selectImage(maskHS); close();
    selectImage(workID); close();

    // --- 各 ROI で面積を計測 ---
    line = fname;

    for (r = 0; r < roiCount; r++) {
        selectImage(finalMask);
        roiManager("select", r);

        // ROI 内のヒストグラム（選択範囲内のみカウント）
        getHistogram(vals, cnts, 256);

        whitePx = cnts[255];   // 閾値に合致したピクセル数

        // ROI の総ピクセル数（ヒストグラムの合計 = 楕円内の全ピクセル）
        totalROIPx = 0;
        for (k = 0; k < cnts.length; k++) totalROIPx += cnts[k];

        pct = (totalROIPx > 0) ? (whitePx / totalROIPx * 100) : 0;

        line += "," + whitePx + "," + totalROIPx + "," + d2s(pct, 2);
    }

    print(csvFile, line);

    // クリーンアップ
    selectImage(finalMask); close();
    selectImage(imgID);     close();

    print("  [" + (i + 1) + "/" + imgCount + "] " + fname);
}

File.close(csvFile);
setBatchMode(false);

// ===================================================================
// 完了
// ===================================================================
print("\n=== 解析完了 ===");
print("処理: " + (imgCount - errorCount) + " 件成功 / " + errorCount + " 件エラー");
print("ROI: " + roiCount + " エリア");
print("結果: " + csvPath);

showMessage("解析完了",
    "すべての解析が完了しました！\n\n" +
    "処理画像数: " + (imgCount - errorCount) + " / " + imgCount + " ファイル\n" +
    "ROI 数:     " + roiCount + " エリア\n\n" +
    "結果ファイル:\n" + csvPath);
