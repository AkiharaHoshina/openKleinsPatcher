# -*- coding: utf-8 -*-
"""把 bk.zip 拆成 [头块 NRBF] + [文件数据]，落到磁盘供 .NET 的 BinaryFormatter 处理。"""
import struct
import sys

import lz4.block

sys.stdout.reconfigure(errors="replace")
P = sys.argv[1] if len(sys.argv) > 1 else r"F:\originKleinsSteam\环行旅舍_Data\StreamingAssets\bk.zip"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"D:\openKleinsPatcher\devtools\multiver\_bk"
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
    o += 1
    unc, o = rdvarint(d, o)
    cpr, o = rdvarint(d, o)
    raw += lz4.block.decompress(d[o:o + cpr], uncompressed_size=unc)
    o += cpr

hl = struct.unpack_from("<i", raw, 0)[0]
open(OUT + r"\hdr.bin", "wb").write(bytes(raw[4:4 + hl]))
open(OUT + r"\data.bin", "wb").write(bytes(raw[4 + hl:]))
print("头块 %d 字节 -> hdr.bin" % hl)
print("文件数据 %d 字节 -> data.bin" % (len(raw) - 4 - hl))
print("原始 bk.zip %d 字节" % len(d))
