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
