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
$LogPath = Join-Path $PSScriptRoot "setup_ai.log"
$ModelName = "Qwen3.5-4B-Q4_K_M.gguf"
$ModelPath = Join-Path $ModelsDir $ModelName
$ModelUrl = "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/$ModelName?download=true"

New-Item -ItemType Directory -Force -Path $RuntimeDir, $ModelsDir, $DownloadDir | Out-Null
try { Start-Transcript -Path $LogPath -Append | Out-Null } catch {}

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
            if ($asset.name -like $Pattern) { return $asset }
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
            Copy-Item $_.FullName (Join-Path $RuntimeDir $_.Name) -Force
        }
    }
    finally {
        Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Prepare-Backend {
    param([string]$Selected)
    if ($Selected -eq "cuda12") {
        $assets = @(
            (Get-LlamaReleaseAsset "llama-*-bin-win-cuda-12.4-x64.zip"),
            (Get-LlamaReleaseAsset "cudart-llama-bin-win-cuda-12.4-x64.zip")
        )
    }
    else {
        $assets = @((Get-LlamaReleaseAsset "llama-*-bin-win-cpu-x64.zip"))
    }
    foreach ($asset in $assets) {
        $zipPath = Join-Path $DownloadDir $asset.name
        if ($Force -or -not (Test-Path $zipPath)) { Download-File $asset.browser_download_url $zipPath }
        else { Write-Host "已存在，跳过下载: $($asset.name)" }
        Expand-RuntimeZip $zipPath
    }
    if (-not (Test-Path (Join-Path $RuntimeDir "llama-server.exe"))) { throw "Runtime\\llama-server.exe 未准备成功" }
}

Write-Host ""
Write-Host "========================================"
Write-Host "短剧文案拆解工具 - 本地AI环境准备"
Write-Host "模型: $ModelName"
Write-Host "后端: $Backend"
Write-Host "========================================"

try {
    if ($Force -or -not (Test-Path (Join-Path $RuntimeDir "llama-server.exe"))) {
        try { Prepare-Backend $Backend }
        catch {
            if ($Backend -eq "cuda12") {
                Write-Warning "NVIDIA CUDA12 运行时准备失败，自动回退 CPU。"
                Remove-Item $RuntimeDir -Recurse -Force -ErrorAction SilentlyContinue
                New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
                $Backend = "cpu"
                Prepare-Backend "cpu"
            }
            else { throw }
        }
    }

    $existingModel = Get-ChildItem $ModelsDir -Filter "*.gguf" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 1GB } | Select-Object -First 1
    if (-not $existingModel) {
        Write-Host ""
        Write-Host "模型约 2.7 GB，支持断点续传。"
        Download-File $ModelUrl $ModelPath
        $existingModel = Get-Item $ModelPath
    }
    else {
        Write-Host "检测到现有 GGUF，跳过模型下载: $($existingModel.FullName)"
    }

    if ($Backend -eq "cpu") {
        '{"server_path":"","model_path":"","port":18080,"context_size":8192,"gpu_mode":"cpu","startup_timeout":180,"request_timeout":360,"temperature":0.45}' |
            Set-Content -Path (Join-Path $PSScriptRoot "ai_config.json") -Encoding ASCII
    }

    $llamaLicense = Join-Path $RuntimeDir "LICENSE_llama.cpp.txt"
    try { Download-File "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/LICENSE" $llamaLicense }
    catch { Write-Warning "llama.cpp LICENSE 自动下载失败，请发货前手动补齐。" }

    $modelSource = Join-Path $ModelsDir "MODEL_SOURCE.txt"
    @"
Model: $($existingModel.Name)
Recommended source: https://huggingface.co/unsloth/Qwen3.5-4B-GGUF
Recommended file: Qwen3.5-4B-Q4_K_M.gguf
Before commercial redistribution, verify the actual model file source/license and keep required LICENSE/NOTICE files.
"@ | Set-Content -Path $modelSource -Encoding UTF8

    Write-Host ""
    Write-Host "[完成] 本地AI环境已准备。"
    Write-Host "日志: $LogPath"
}
catch {
    Write-Host ""
    Write-Host "[失败] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "详细日志: $LogPath"
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
}
