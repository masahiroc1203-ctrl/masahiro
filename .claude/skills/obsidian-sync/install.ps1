<#
.SYNOPSIS
  obsidian-sync スキルを配布する（Windows / PowerShell 版。install.sh の等価物）。

.DESCRIPTION
  配布先:
    1. %USERPROFILE%\.claude\skills\obsidian-sync         （ローカルの全プロジェクトで利用可）
    2. <vault>\.claude\skills\obsidian-sync               （Web で Vault を add した際に利用可。-Vault 指定時）
  設定ファイル %USERPROFILE%\.claude\obsidian-sync.json が無ければ雛形を作成する。

.PARAMETER Link
  コピーではなくディレクトリ ジャンクションで配置（管理者権限不要。ローカル開発時に便利）。

.PARAMETER Vault
  指定 Vault リポジトリにもミラー配置。省略時は config の vaultPath を試す。

.EXAMPLE
  .\install.ps1 -Vault "C:/Users/masah/ObsidianVaults/claude-code-vault"
#>
param(
    [switch]$Link,
    [string]$Vault = ""
)

$ErrorActionPreference = "Stop"
$Src  = $PSScriptRoot
$Name = "obsidian-sync"

function Place([string]$DestParent) {
    $dest = Join-Path $DestParent $Name
    New-Item -ItemType Directory -Force -Path $DestParent | Out-Null
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    if ($Link) {
        New-Item -ItemType Junction -Path $dest -Target $Src | Out-Null
        Write-Host "linked (junction): $dest -> $Src"
    } else {
        Copy-Item -Recurse -Force -Path $Src -Destination $dest
        Write-Host "copied: $dest"
    }
}

# 1. ローカルグローバル
$skillsParent = Join-Path $env:USERPROFILE ".claude\skills"
Place $skillsParent

# 設定ファイルの雛形
$config  = Join-Path $env:USERPROFILE ".claude\obsidian-sync.json"
$example = Join-Path $Src "obsidian-sync.example.json"
if ((-not (Test-Path $config)) -and (Test-Path $example)) {
    Copy-Item -Path $example -Destination $config
    Write-Host "created config: $config （vaultPath / vaultRepo を編集してください）"
}

# 2. Vault リポジトリへミラー
if ((-not $Vault) -and (Test-Path $config)) {
    try {
        $cfg = Get-Content -Raw -Path $config | ConvertFrom-Json
        if ($cfg.vaultPath) { $Vault = [string]$cfg.vaultPath }
    } catch { }
}
if ($Vault) {
    if ($Vault.StartsWith("~")) { $Vault = $env:USERPROFILE + $Vault.Substring(1) }
    if (Test-Path $Vault) {
        Place (Join-Path $Vault ".claude\skills")
    } else {
        Write-Warning "指定された Vault が見つかりません: $Vault"
    }
}

Write-Host "done."
