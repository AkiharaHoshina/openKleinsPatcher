$ErrorActionPreference = 'Stop'
$bk  = 'D:\openKleinsPatcher\devtools\multiver\_bk'
$dll = Join-Path $bk 'Assembly-CSharp.dll'
if (-not (Test-Path $dll)) {
    $cs = @'
using System;
using System.Collections.Generic;
[Serializable]
public class ZipInfo { public List<string> allFileNames; public List<int> allFileSizes; }
'@
    Add-Type -TypeDefinition $cs -OutputAssembly $dll -OutputType Library
}
[Reflection.Assembly]::LoadFrom($dll) | Out-Null

function Dump($n, $names, $sizes) {
    $zi = New-Object ZipInfo
    $zi.allFileNames = New-Object 'System.Collections.Generic.List[string]'
    $zi.allFileSizes = New-Object 'System.Collections.Generic.List[int]'
    for ($i = 0; $i -lt $n; $i++) { $zi.allFileNames.Add($names[$i]); $zi.allFileSizes.Add($sizes[$i]) }
    $bf = New-Object System.Runtime.Serialization.Formatters.Binary.BinaryFormatter
    $ms = New-Object IO.MemoryStream
    $bf.Serialize($ms, $zi)
    $b = $ms.ToArray()
    Write-Host ("=== n=$n  serialized $($b.Length) bytes ===")
    for ($i = 0; $i -lt $b.Length; $i += 16) {
        $row = $b[$i..([Math]::Min($i+15, $b.Length-1))]
        $hx = ($row | ForEach-Object { $_.ToString('x2') }) -join ' '
        $asc = ($row | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } }) -join ''
        Write-Host ("  {0,4}: {1,-47} |{2}|" -f $i, $hx, $asc)
    }
    [IO.File]::WriteAllBytes((Join-Path $bk ("min$n.bin")), $b)
}

Dump 1 @('/lua/A.lua') @(11)
Dump 2 @('/lua/A.lua','/lua/Bb.lua') @(11,2222)
Dump 3 @('/lua/A.lua','/lua/Bb.lua','/lua/Ccc.lua') @(11,2222,333333)
