#Requires -Version 5.1
# fontctl.ps1 — 设计字体临时安装/卸载（Windows，当前用户范围）
# 用法:
#   fontctl.ps1 status [家族名] [-FontRoot <字体根目录>]
#   fontctl.ps1 install <家族名> [-Force] | -All [-FontRoot <字体根目录>]
#   fontctl.ps1 remove  <家族名> | -All
param(
    [Parameter(Position = 0)][string]$Command = 'status',
    [Parameter(Position = 1)][string]$Name,
    [switch]$All,
    [switch]$Force,
    [switch]$Overwrite,
    [string]$FontRoot = ''
)

$ErrorActionPreference = 'Stop'

# 随包时默认用户字体根目录；放在 <fontroot>\tools 下时仍按原位解析。
$Root = if ($FontRoot) { $FontRoot }
        elseif ((Split-Path -Leaf $PSScriptRoot) -ieq 'tools') { Split-Path -Parent $PSScriptRoot }
        else { Join-Path $env:USERPROFILE 'fonts' }
$Readme    = Join-Path $Root 'README.md'
$TargetDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$RegPath   = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$StateDir  = Join-Path $env:LOCALAPPDATA 'fontctl'
$StateFile = Join-Path $StateDir 'state.json'

Add-Type -Namespace Fontctl -Name Native -MemberDefinition @'
[DllImport("user32.dll", SetLastError = true)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, IntPtr lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@

function Read-RegistryRows {
    if (-not (Test-Path -LiteralPath $Readme)) { throw "找不到登记表: $Readme" }
    $lines = [System.IO.File]::ReadAllLines($Readme, [System.Text.UTF8Encoding]::new($false))
    $rows = New-Object System.Collections.Generic.List[object]
    $inSection = $false
    $inFence = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*```') { $inFence = -not $inFence; continue }
        if ($inFence) { continue }
        if ($line -match '^\s*##\s+') { $inSection = ($line -match '登记表'); continue }
        if (-not $inSection) { continue }
        $t = $line.Trim()
        if (-not $t.StartsWith('|')) { continue }
        $cells = @($t.Trim('|') -split '\|' | ForEach-Object { $_.Trim() })
        if ($cells.Count -ne 8) { Write-Warning "登记表行无法解析（列数不是 8），已跳过: $t"; continue }
        if ($cells[0] -eq '字体文件') { continue }
        if (($cells -join '') -match '^[-\s:]*$') { continue }
        if ($cells[0] -eq '') { continue }
        $rows.Add([pscustomobject]@{
            File        = $cells[0]
            Family      = $cells[1]
            Style       = $cells[2]
            Source      = $cells[3]
            License     = $cells[4]
            LicenseFile = $cells[5]
            Sha256      = $cells[6]
            Note        = $cells[7]
        })
    }
    return , $rows
}

function Read-State {
    $list = New-Object System.Collections.Generic.List[object]
    if (-not (Test-Path -LiteralPath $StateFile)) { return , $list }
    try {
        $data = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "状态文件损坏，无法解析: $StateFile（$($_.Exception.Message)）"
    }
    foreach ($e in @($data.entries)) {
        if ($null -ne $e) { $list.Add($e) }
    }
    return , $list
}

function Write-State([System.Collections.Generic.List[object]]$entries) {
    if (-not (Test-Path -LiteralPath $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
    $json = @{ entries = $entries.ToArray() } | ConvertTo-Json -Depth 5
    $tmp = "$StateFile.tmp"
    [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tmp -Destination $StateFile -Force
}

function Get-FontKind([string]$path) {
    $fs = [System.IO.File]::OpenRead($path)
    try {
        $buf = New-Object byte[] 4
        if ($fs.Read($buf, 0, 4) -lt 4) { return 'unknown' }
        $hex = ($buf | ForEach-Object { $_.ToString('X2') }) -join ''
        switch ($hex) {
            '00010000' { return 'ttf' }
            '4F54544F' { return 'otf' }
            '74746366' { return 'ttc' }
            '74727565' { return 'ttf' }
            '774F4646' { return 'woff' }
            '774F4632' { return 'woff2' }
            default    { return 'unknown' }
        }
    }
    finally { $fs.Dispose() }
}

function Get-RegLabel([string]$family, [string]$style, [string]$path) {
    $type = if ([System.IO.Path]::GetExtension($path) -ieq '.otf') { 'OpenType' } else { 'TrueType' }
    $base = if ($style -ne '' -and $style -ne 'Regular') { "$family $style" } else { $family }
    return "$base ($type)"
}

function Broadcast-FontChange {
    $res = [UIntPtr]::Zero
    [void][Fontctl.Native]::SendMessageTimeout([IntPtr]0xffff, 0x001D, [UIntPtr]::Zero, [IntPtr]::Zero, 2, 5000, [ref]$res)
}

function Remove-StateEntry([System.Collections.Generic.List[object]]$state, [string]$source) {
    for ($i = $state.Count - 1; $i -ge 0; $i--) {
        if ($state[$i].source -eq $source) { $state.RemoveAt($i) }
    }
}

function Assert-License($row) {
    $lic = ($row.License -replace '\s', '')
    if ($lic -eq '') { throw "「$($row.Family)」未登记商用授权，先在 README 登记表补上" }
    if ($lic -match '不可商用|禁止商用|不可使用') { throw "「$($row.Family)」登记为不可商用，拒绝安装" }
    # 只有明确的免费/开源授权才免 -Force；「不免费商用」这类否定写法必须以白名单开头才放行
    if ($lic -match '^(免费商用|OFL|MIT|Apache|开源|公有领域)') { return }
    if (-not $Force) { throw "「$($row.Family)」授权为「$($row.License)」，确认已获授权后加 -Force 安装" }
    Write-Warning "按 -Force 安装「$($row.Family)」（授权：$($row.License)）。临时安装不等于获得授权。"
}

function Install-Row($row, [System.Collections.Generic.List[object]]$state) {
    $src = Join-Path $Root ($row.File -replace '/', '\')
    if (-not (Test-Path -LiteralPath $src)) { throw "字体文件不存在: $($row.File)" }
    $kind = Get-FontKind $src
    if ($kind -eq 'woff' -or $kind -eq 'woff2') { throw "$($row.File) 是 WOFF/WOFF2，只收 TTF/OTF/TTC" }
    if ($kind -eq 'unknown') { throw "$($row.File) 不是有效的 TTF/OTF/TTC 字体文件" }
    Assert-License $row

    $sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLower()
    if ($row.Sha256 -ne '' -and $row.Sha256.ToLower() -ne $sha) {
        throw "$($row.File) 的 SHA256 与登记表不一致，文件可能被换过"
    }

    $label  = Get-RegLabel $row.Family $row.Style $src
    $target = Join-Path $TargetDir ([System.IO.Path]::GetFileName($src))
    $own = $state | Where-Object { $_.source -eq $row.File } | Select-Object -First 1
    $dup = $state | Where-Object { $_.label -eq $label -and $_.source -ne $row.File } | Select-Object -First 1
    if ($null -ne $dup) { throw "「$label」已由登记行「$($dup.source)」装入，先 remove 再装这一行" }

    $cur = Get-ItemProperty -Path $RegPath -Name $label -ErrorAction SilentlyContinue
    if ($null -ne $cur -and $null -eq $own) {
        throw "注册表已有同名项「$label」且不是 fontctl 装的，先手动处理冲突"
    }
    if ((Test-Path -LiteralPath $target) -and $null -eq $own) {
        if (-not $Overwrite) { throw "目标位置已有同名文件且不是 fontctl 装的: $target（确认可覆盖加 -Overwrite）" }
        Write-Warning "覆盖已存在的同名文件: $target"
    }

    if (-not (Test-Path -LiteralPath $TargetDir)) { New-Item -ItemType Directory -Path $TargetDir | Out-Null }
    Copy-Item -LiteralPath $src -Destination $target -Force
    New-ItemProperty -Path $RegPath -Name $label -PropertyType String -Value $target -Force | Out-Null

    $entry = [pscustomobject]@{
        source      = $row.File
        family      = $row.Family
        style       = $row.Style
        label       = $label
        target      = $target
        sha256      = $sha
        installedAt = (Get-Date).ToString('s')
    }
    if ($null -ne $own) { Remove-StateEntry $state $row.File }
    $state.Add($entry)
    Write-State $state
    Broadcast-FontChange
    Write-Output "已安装: $($row.Family) $($row.Style) -> $target"
}

function Remove-Entry($e, [System.Collections.Generic.List[object]]$state) {
    $prop = Get-ItemProperty -Path $RegPath -Name $e.label -ErrorAction SilentlyContinue
    if ($null -ne $prop) {
        $val = $prop.PSObject.Properties[$e.label].Value
        if ($val -eq $e.target) {
            Remove-ItemProperty -Path $RegPath -Name $e.label
        }
        else {
            Write-Warning "注册表「$($e.label)」指向别处（$val），不动它"
        }
    }
    if (Test-Path -LiteralPath $e.target) {
        $curSha = (Get-FileHash -LiteralPath $e.target -Algorithm SHA256).Hash.ToLower()
        if ($curSha -eq $e.sha256) {
            Remove-Item -LiteralPath $e.target -Force
        }
        else {
            Write-Warning "目标文件已被替换（哈希不符），不删文件: $($e.target)"
        }
    }
    Remove-StateEntry $state $e.source
    Write-Output "已卸载: $($e.family) $($e.style)"
}

function Show-Status($rows, [System.Collections.Generic.List[object]]$state) {
    foreach ($row in $rows) {
        $src = Join-Path $Root ($row.File -replace '/', '\')
        $fileOk = if (Test-Path -LiteralPath $src) { '文件OK' } else { '文件缺失' }
        $shaNote = ''
        if ($row.Sha256 -ne '' -and (Test-Path -LiteralPath $src)) {
            $sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLower()
            $shaNote = if ($sha -eq $row.Sha256.ToLower()) { ' sha一致' } else { ' sha不一致!' }
        }
        $own = $state | Where-Object { $_.source -eq $row.File } | Select-Object -First 1
        $inst = if ($null -ne $own) { "已安装 $($own.installedAt)" } else { '未安装' }
        $targetNote = ''
        if ($null -ne $own) {
            if (-not (Test-Path -LiteralPath $own.target)) {
                $targetNote = ' 目标缺失!'
            }
            else {
                $curSha = (Get-FileHash -LiteralPath $own.target -Algorithm SHA256).Hash.ToLower()
                if ($curSha -ne $own.sha256) { $targetNote = ' 目标哈希不符!' }
            }
        }
        Write-Output ("{0} [{1}] {2} 授权:{3} {4}{5}{6}" -f $row.Family, $row.Style, $fileOk, $row.License, $inst, $shaNote, $targetNote)
    }
    foreach ($e in $state) {
        $known = $rows | Where-Object { $_.File -eq $e.source } | Select-Object -First 1
        if ($null -eq $known) {
            Write-Output "$($e.family) [$($e.style)] 登记表已删行，但仍是已安装状态（remove 可清）"
        }
    }
}

$state = Read-State

switch ($Command) {
    'status' {
        $rows = Read-RegistryRows
        if ($Name -ne '') { $rows = @($rows | Where-Object { $_.Family -eq $Name }) }
        if ($rows.Count -eq 0) { Write-Output '登记表里没有匹配的条目'; break }
        Show-Status $rows $state
    }
    'install' {
        $rows = Read-RegistryRows
        if ($All) { $targets = $rows.ToArray() }
        elseif ($Name -ne '') { $targets = @($rows | Where-Object { $_.Family -eq $Name }) }
        else { throw '用法: fontctl.ps1 install <家族名> | -All' }
        if ($targets.Count -eq 0) { throw "登记表里没有「$Name」" }
        foreach ($row in $targets) { Install-Row $row $state }
    }
    'remove' {
        if ($All) { $targets = $state.ToArray() }
        elseif ($Name -ne '') { $targets = @($state | Where-Object { $_.family -eq $Name }) }
        else { throw '用法: fontctl.ps1 remove <家族名> | -All' }
        if ($targets.Count -eq 0) { Write-Output '没有可清理的安装记录'; break }
        foreach ($e in $targets) { Remove-Entry $e $state }
        Write-State $state
        Broadcast-FontChange
    }
    default { throw "未知命令: $Command（status / install / remove）" }
}
