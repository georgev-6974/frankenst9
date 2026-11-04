param([Parameter(Mandatory)][string]$Name)
# Pull the logs of the previous boot from a Galaxy S9+ (star2lte) in TWRP.
#  - loader log: 64 blocks just below the kernel ring in USERDATA (sda25)
#    -> logs/ldrlog-NAME.txt   (tools/star2lte/ldrlog.py)
#  - kernel console ring: last 1025 blocks of sda25 -> logs/sweetlog-NAME.txt
#    (tools/sweet-log.py; only written once the XNU UFS driver runs)
# No ramoops on this phone. Usage: tools\star2lte\pull-log.ps1 v1
$ErrorActionPreference = 'Continue'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$dir = Join-Path $repo 'logs'
New-Item -ItemType Directory -Force $dir | Out-Null
$ldrBin = Join-Path $dir "ldrlog-$Name.bin"; $ldrTxt = Join-Path $dir "ldrlog-$Name.txt"
$krnBin = Join-Path $dir "sweetlog-$Name.bin"; $krnTxt = Join-Path $dir "sweetlog-$Name.txt"
adb shell 'b=$(blockdev --getsize64 /dev/block/sda25); n=$((b/4096)); dd if=/dev/block/sda25 of=/tmp/ldr.bin bs=4096 skip=$((n-1025-64)) count=64 2>/dev/null; dd if=/dev/block/sda25 of=/tmp/krn.bin bs=4096 skip=$((n-1025)) count=1025 2>/dev/null'
adb pull /tmp/ldr.bin $ldrBin | Out-Null
adb pull /tmp/krn.bin $krnBin | Out-Null
function Wsl($p) { (wsl -d Ubuntu wslpath -a ($p -replace '\\', '/')).Trim() }
wsl -d Ubuntu python3 (Wsl (Join-Path $repo 'tools\star2lte\ldrlog.py')) (Wsl $ldrBin) (Wsl $ldrTxt)
wsl -d Ubuntu python3 (Wsl (Join-Path $repo 'tools\sweet-log.py')) (Wsl $krnBin) (Wsl $krnTxt)
Write-Output "loader log: $ldrTxt"
Write-Output "kernel log: $krnTxt"
