# install.ps1 —— 把 plugin-resolver 一键注册成 DSH 全局 skill
# 用法（在仓库根目录）： powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"

$DSH_HOME  = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $HOME ".dsh" }
$SkillsDir = Join-Path $DSH_HOME "skills"
$SkillName = "plugin-resolver.md"

$Root = $PSScriptRoot
$Src  = Join-Path $Root "SKILL.md"
$Dst  = Join-Path $SkillsDir $SkillName

if (-not (Test-Path $Src)) {
    Write-Error "找不到 $Src —— 请在仓库根目录运行本脚本"
    exit 1
}

New-Item -ItemType Directory -Force $SkillsDir | Out-Null

# 读取 SKILL.md，把工程根目录占位符替换为实际绝对路径，写入无 BOM 的 UTF-8
$Content = Get-Content -Raw -Encoding UTF8 $Src
$Content = $Content.Replace("__PLUGIN_RESOLVER_ROOT__", $Root)
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Dst, $Content, $Utf8NoBom)

Write-Host ""
Write-Host "已安装 skill 到: $Dst"
Write-Host "插件工程目录已写入: $Root"
Write-Host ""
Write-Host "下一步："
Write-Host "  1) 若 DSH 未热加载，重启 dsh web"
Write-Host "  2) 在工程目录首次运行: python tools/build_registry.py"
Write-Host "  3) 之后直接对智能体说任务即可，它会自动走 plugin-resolver 能力发现"
Write-Host ""