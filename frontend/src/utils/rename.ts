/** ファイル名から拡張子を除いたステムを返す。 */
export function getStem(filename: string): string {
  return filename.replace(/\.[^.]+$/, "");
}

/**
 * キーワードからリネーム後のファイル名を生成する。
 * withStem=true  → 元ファイル名_kw1_kw2_kw3.pdf
 * withStem=false → kw1_kw2_kw3.pdf
 * kw2・kw3 が空の場合は省略される。
 */
export function buildFilename(
  stem: string,
  kw1: string,
  kw2: string,
  kw3: string,
  withStem: boolean
): string {
  const parts = [kw1.trim(), kw2.trim(), kw3.trim()].filter(Boolean);
  if (parts.length === 0) return "";
  const base = withStem ? `${stem}_${parts.join("_")}` : parts.join("_");
  return base + ".pdf";
}
