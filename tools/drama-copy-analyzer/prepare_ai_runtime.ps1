param(
    [ValidateSet("cpu", "cuda12")]
    [string]$Backend = "cpu",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Set-Location $PSScriptRoot

$RuntimeDir = Join-Path $PSScriptRoot "Runtime"
$ModelsDir = Join-Path $PSScriptRoot "Models"
$DownloadDir = Join-Path $PSScriptRoot ".downloads"
$ModelName = "Qwen3.5-4B-Q4_K_M.gguf"
$ModelPath = Join-Path $ModelsDir $ModelName
$ModelUrl = "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/$ModelName?download=true"

New-Item -ItemType Directory -Force -Path $RuntimeDir, $ModelsDir, $DownloadDir | Out-Null

function Download-File {
    param([string]$Url, [string]$OutFile)
    Write-Host "下载: $Url"
    Write-Host "保存: $OutFile"
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -L --fail --retry 5 --retry-delay 3 -C - $Url -o $OutFile
        if ($LASTEXITCODE -ne 0) { throw "下载失败，curl 退出码 $LASTEXITCODE" }
    }
    else {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    }
}

function Get-LlamaReleaseAsset {
    param([string]$Pattern)
    $headers = @{ "User-Agent" = "DramaCopyAnalyzer-LocalAI-Setup" }
    $releases = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20"
    foreach ($release in $releases) {
        foreach ($asset in $release.assets) {
            if ($asset.name -like $Pattern) {
                return $asset
            }
        }
    }
    throw "没有在最近的 llama.cpp release 中找到资源: $Pattern"
}

function Expand-RuntimeZip {
    param([string]$ZipPath)
    $stage = Join-Path $DownloadDir ("stage_" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    try {
        Expand-Archive -Path $ZipPath -DestinationPath $stage -Force
        Get-ChildItem -Path $stage -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($stage.Length).TrimStart('\')
            $target = Join-Path $RuntimeDir $relative
            $parent = Split-Path $target -Parent
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
            Copy-Item $_.FullName $target -Force
        }
    }
    finally {
        Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "短剧文案拆解工具 - 本地AI环境准备"
Write-Host "运行时: llama.cpp"
Write-Host "模型: $ModelName"
Write-Host "后端: $Backend"
Write-Host "========================================"

if ($Backend -eq "cuda12") {
    $mainAsset = Get-LlamaReleaseAsset "llama-*-bin-win-cuda-12.4-x64.zip"
    $cudaAsset = Get-LlamaReleaseAsset "cudart-llama-bin-win-cuda-12.4-x64.zip"
    $assets = @($mainAsset, $cudaAsset)
}
else {
    $mainAsset = Get-LlamaReleaseAsset "llama-*-bin-win-cpu-x64.zip"
    $assets = @($mainAsset)
}

foreach ($asset in $assets) {
    $zipPath = Join-Path $DownloadDir $asset.name
    if ($Force -or -not (Test-Path $zipPath)) {
        Download-File $asset.browser_download_url $zipPath
    }
    else {
        Write-Host "已存在，跳过下载: $($asset.name)"
    }
    Expand-RuntimeZip $zipPath
}

$server = Get-ChildItem -Path $RuntimeDir -Filter "llama-server.exe" -Recurse -File | Select-Object -First 1
if (-not $server) { throw "解压后没有找到 llama-server.exe" }
if ($server.DirectoryName -ne $RuntimeDir) {
    Get-ChildItem -Path $server.DirectoryName -File | Copy-Item -Destination $RuntimeDir -Force
}
if (-not (Test-Path (Join-Path $RuntimeDir "llama-server.exe"))) {
    throw "Runtime\\llama-server.exe 未准备成功"
}

if ($Force -or -not (Test-Path $ModelPath) -or ((Get-Item $ModelPath).Length -lt 1GB)) {
    Write-Host ""
    Write-Host "模型约 2.7 GB，支持断点续传。"
    Download-File $ModelUrl $ModelPath
}
else {
    Write-Host "模型已存在，跳过下载: $ModelPath"
}

$llamaLicense = Join-Path $RuntimeDir "LICENSE_llama.cpp.txt"
try {
    Download-File "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/LICENSE" $llamaLicense
}
catch {
    Write-Warning "llama.cpp LICENSE 自动下载失败，请发货前手动补齐。$($_.Exception.Message)"
}

$modelSource = Join-Path $ModelsDir "MODEL_SOURCE.txt"
@"
Model: $ModelName
Source: https://huggingface.co/unsloth/Qwen3.5-4B-GGUF
File: https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/blob/main/$ModelName
License shown by source repository: Apache-2.0
Before commercial redistribution, verify the current model repository/license and keep required LICENSE/NOTICE files.
"@ | Set-Content -Path $modelSource -Encoding UTF8

Write-Host ""
Write-Host "[完成] 本地AI环境已准备："
Write-Host "  Runtime\\llama-server.exe"
Write-Host "  Models\\$ModelName"
Write-Host ""
Write-Host "下一步双击 build_ai_release.bat 生成正式 AI 包。"
