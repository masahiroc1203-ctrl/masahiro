export interface FileInfo {
  filename: string;
  size: number;
  modified_at: string;
}

export interface UploadResult {
  filename: string;
  size: number;
}

export interface PreviewResult {
  original_filename: string;
  hinmei: string | null;
  suggested_filename: string | null;
}

export interface RenameResult {
  old_filename: string;
  new_filename: string;
}

export async function uploadFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/files/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export async function listFiles(): Promise<FileInfo[]> {
  const res = await fetch("/api/files");
  if (!res.ok) {
    throw new Error("Failed to fetch file list");
  }
  return res.json();
}

export function downloadFile(filename: string): void {
  const a = document.createElement("a");
  a.href = `/api/files/${encodeURIComponent(filename)}/download`;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export async function previewRename(filename: string): Promise<PreviewResult> {
  const res = await fetch(`/api/rename/${encodeURIComponent(filename)}/preview`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Preview failed");
  }
  return res.json();
}

export async function executeRename(
  filename: string,
  newFilename: string
): Promise<RenameResult> {
  const res = await fetch(`/api/rename/${encodeURIComponent(filename)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_filename: newFilename }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Rename failed");
  }
  return res.json();
}

export interface ContentResult {
  filename: string;
  total_pages: number;
  pages: { page_num: number; text: string }[];
}

export async function getContent(filename: string): Promise<ContentResult> {
  const res = await fetch(`/api/content/${encodeURIComponent(filename)}/text`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Failed to fetch content");
  }
  return res.json();
}

export interface MergeResult {
  output_filename: string;
  merged_count: number;
}

export async function mergeFiles(
  filenames: string[],
  outputFilename: string
): Promise<MergeResult> {
  const res = await fetch("/api/merge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filenames, output_filename: outputFilename }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Merge failed");
  }
  return res.json();
}

export interface SplitResult {
  original_filename: string;
  output_files: string[];
  split_count: number;
}

export interface ClearResult {
  deleted_count: number;
  deleted_files: string[];
}

export async function clearAllFiles(): Promise<ClearResult> {
  const res = await fetch("/api/files/all", { method: "DELETE" });
  if (!res.ok) {
    throw new Error("Failed to clear files");
  }
  return res.json();
}

export interface BatchRenameItem {
  original_filename: string;
  new_filename: string;
}

export interface BatchRenameResult {
  results: { old_filename: string; new_filename: string }[];
  errors: { original_filename: string; error: string }[];
}

export async function batchRename(renames: BatchRenameItem[]): Promise<BatchRenameResult> {
  const res = await fetch("/api/rename/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ renames }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Batch rename failed");
  }
  return res.json();
}

export async function splitFile(
  filename: string,
  mode: "ranges" | "every",
  ranges?: [number, number][],
  every?: number
): Promise<SplitResult> {
  const res = await fetch(`/api/split/${encodeURIComponent(filename)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, ranges, every }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Split failed");
  }
  return res.json();
}
