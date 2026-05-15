/** 3つのキーワードから `kw1_kw2_kw3.pdf` 形式のファイル名を生成する。空欄はスキップ。 */
export function buildFilename(kw1: string, kw2: string, kw3: string): string {
  const parts = [kw1.trim(), kw2.trim(), kw3.trim()].filter(Boolean);
  if (parts.length === 0) return "";
  return parts.join("_") + ".pdf";
}
