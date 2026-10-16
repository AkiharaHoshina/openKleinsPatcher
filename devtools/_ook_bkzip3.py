# -*- coding: utf-8 -*-
"""拆开 bk.zip：验证 [NRBF(ZipInfo)][文件数据...] 的结构。"""
import struct
import sys

import lz4.block

sys.stdout.reconfigure(errors="replace")
P = sys.argv[1] if len(sys.argv) > 1 else r"F:\originKleinsSteam\环行旅舍_Data\StreamingAssets\bk.zip"
d = open(P, "rb").read()


def rdvarint(b, o):
    v = sh = 0
    while True:
        x = b[o]
        o += 1
        v |= (x & 0x7F) << sh
        if not (x & 0x80):
            return v, o
        sh += 7


raw = bytearray()
o = 0
while o < len(d):
    o += 1                                   # 分块标记 0x01
    unc, o = rdvarint(d, o)
    cpr, o = rdvarint(d, o)
    raw += lz4.block.decompress(d[o:o + cpr], uncompressed_size=unc)
    o += cpr
print("解出 %d 字节" % len(raw))

print()
print("=== 头 64 字节 ===")
print(" ".join("%02x" % x for x in raw[:64]))
print()
print("=== NRBF 记录逐个看（前 400 字节，手工标注）===")
print("  [0:4]   = %s   <- 4 字节前缀（非 NRBF）" % " ".join("%02x" % x for x in raw[:4]))
print("  [4:21]  = %s" % " ".join("%02x" % x for x in raw[4:21]))
print("            ↑ NRBF SerializedStreamHeader: 00 | RootId=1 | HeaderId=-1 | Major=1 | Minor=0")
# 15,20 与 36 字节的库名
i = 21
print("  [%d] = %#x  <- BinaryLibrary" % (i, raw[i]))
i += 1
libid = struct.unpack_from("<i", raw, i)[0]
i += 4
n, i = rdvarint(raw, i)
name = bytes(raw[i:i + n * 2]).decode("utf-16-le", "replace")
i += n * 2
print("       LibraryId=%d  name=%r" % (libid, name))

print()
print("=== 找第一处 LuaJIT 字节码头 1b 4c 4a 02 ===")
k = raw.find(b"\x1b\x4c\x4a\x02")
print("  首次出现在偏移 %#x" % k)
print("  该处前 48 字节: %s" % " ".join("%02x" % x for x in raw[max(0, k - 48):k]))
print("  该处前 80 字节可读: %s"
      % "".join(chr(x) if 32 <= x < 127 else "." for x in raw[max(0, k - 80):k]))
print("  ⇒ NRBF 段 = [4, %#x)，长度 %d" % (k, k - 4))
