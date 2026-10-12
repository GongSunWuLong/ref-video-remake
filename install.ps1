# One-line install (Windows PowerShell):
#   irm https://raw.githubusercontent.com/GongSunWuLong/ref-video-remake/main/install.ps1 | iex
# Copies the skill into %USERPROFILE%\.claude\skills\ref-video-remake and installs the Python deps.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# Windows PowerShell 5.1 defaults to TLS 1.0/1.1, which GitHub rejects ("The underlying connection was closed")
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$repo = 'GongSunWuLong/ref-video-remake'
$dest = Join-Path $env:USERPROFILE '.claude\skills\ref-video-remake'
$tmp = Join-Path $env:TEMP ('ref-video-remake-' + [guid]::NewGuid())
New-Item -ItemType Directory -Force $tmp | Out-Null
Write-Host "Downloading $repo ..."
$srcDir = $null
if (Get-Command git -ErrorAction SilentlyContinue) {
  for ($i = 1; $i -le 4 -and -not $srcDir; $i++) {
    git clone --depth 1 -q "https://github.com/$repo.git" "$tmp\src" 2>$null
    if ($LASTEXITCODE -eq 0) { $srcDir = "$tmp\src" } else { Remove-Item -Recurse -Force "$tmp\src" -ErrorAction SilentlyContinue; Start-Sleep 3 }
  }
}
if (-not $srcDir) {
  for ($i = 1; $i -le 4 -and -not $srcDir; $i++) {
    try {
      Invoke-WebRequest -Uri "https://github.com/$repo/archive/refs/heads/main.zip" -OutFile "$tmp\src.zip" -UseBasicParsing
      Expand-Archive "$tmp\src.zip" -DestinationPath $tmp -Force
      $srcDir = (Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like 'ref-video-remake-*' } | Select-Object -First 1).FullName
    } catch { Write-Host "download failed ($i): $($_.Exception.Message)"; Start-Sleep 3 }
  }
}
if (-not $srcDir) { throw "Could not download $repo. Check the network and run the command again." }
$skill = Join-Path $srcDir 'plugins\ref-video-remake\skills\ref-video-remake'
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest -Confirm:$false }
New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
Copy-Item -Recurse $skill $dest
Remove-Item -Recurse -Force $tmp -Confirm:$false
Write-Host "Skill installed to $dest"

$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
if ($py) {
  & $py.Source -m pip install -q -r (Join-Path $dest 'requirements.txt')
  & $py.Source (Join-Path $dest 'scripts\check_env.py')
} else {
  Write-Host 'Python not found. Install Python 3.9+ (https://www.python.org/downloads/), then run:'
  Write-Host "  python -m pip install -r `"$dest\requirements.txt`""
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host 'ffmpeg not found. Install it with:  winget install Gyan.FFmpeg   (then reopen the terminal)'
}
Write-Host 'Done. Restart Claude Code, then say: 参考这个视频帮我做一条新的'
