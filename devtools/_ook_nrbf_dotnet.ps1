$ErrorActionPreference = 'Stop'
$bk  = 'D:\openKleinsPatcher\devtools\multiver\_bk'
$dll = Join-Path $bk 'Assembly-CSharp.dll'

$cs = @'
using System;
using System.Collections.Generic;

[Serializable]
public class ZipInfo
{
    public List<string> allFileNames;
    public List<int>    allFileSizes;
}
'@

Add-Type -TypeDefinition $cs -OutputAssembly $dll -OutputType Library

$asm = [Reflection.Assembly]::LoadFrom($dll)
Write-Host ("assembly : " + $asm.FullName)
Write-Host ("ZipInfo  : " + $asm.GetType('ZipInfo').AssemblyQualifiedName)

$bf = New-Object System.Runtime.Serialization.Formatters.Binary.BinaryFormatter
$bytes = [IO.File]::ReadAllBytes((Join-Path $bk 'hdr.bin'))
$ms = New-Object IO.MemoryStream (,$bytes)
$obj = $bf.Deserialize($ms)

Write-Host ("deserialized -> " + $obj.GetType().FullName)
Write-Host ("allFileNames count: " + $obj.allFileNames.Count)
Write-Host ("allFileSizes count: " + $obj.allFileSizes.Count)
Write-Host ("first 3 names : " + ($obj.allFileNames[0..2] -join ' | '))
Write-Host ("first 3 sizes : " + ($obj.allFileSizes[0..2] -join ', '))

$ms2 = New-Object IO.MemoryStream
$bf.Serialize($ms2, $obj)
$back = $ms2.ToArray()
[IO.File]::WriteAllBytes((Join-Path $bk 'hdr_rt.bin'), $back)
Write-Host ("round-trip length: " + $back.Length + "  (orig 65536)")

$n = [Math]::Min($back.Length, $bytes.Length)
$firstDiff = -1
for ($i = 0; $i -lt $n; $i++) { if ($back[$i] -ne $bytes[$i]) { $firstDiff = $i; break } }
if ($firstDiff -lt 0) { Write-Host ("IDENTICAL first " + $n + " bytes") }
else { Write-Host ("first difference at offset " + $firstDiff) }
