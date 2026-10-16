# -*- coding: utf-8 -*-
"""验证 bk.zip 的分块格式： [0x01][varint 未压缩长][varint 压缩长][LZ4 block]×N"""
import sys

import lz4.block

sys.stdout.reconfigure(errors="replace")
P = sys.argv[1] if len(sys.argv) > 1 else r"F:\originKleinsSteam\环行旅舍_Data\StreamingAssets\bk.zip"
d = open(P, "rb").read()


def rdvarint(b, o):
    v = 0
    sh = 0
    while True:
        x = b[o]
        o += 1
        v |= (x & 0x7F) << sh
        if not (x & 0x80):
            return v, o
        sh += 7


print("文件 %d 字节, 头 %s" % (len(d), " ".join("%02x" % x for x in d[:8])))
o = 0
lead = d[0]            # 每个 chunk 头都以这个字节开头（实测 0x01）
print("分块标记字节 = %#x" % lead)

chunks = []
while o < len(d):
    marker = d[o]
    o += 1
    if marker != lead:
        print("!! 分块标记异常 @%#x: %#x（期望 %#x）" % (o - 1, marker, lead))
        break
    unc, o = rdvarint(d, o)
    cpr, o = rdvarint(d, o)
    chunks.append((o, cpr, unc))
    o += cpr
    if len(chunks) <= 4:
        print("  chunk%-2d 压缩 %8d -> 未压缩 %8d  数据 @%#x" % (len(chunks) - 1, cpr, unc, chunks[-1][0]))
print("共 %d 个 chunk, 解析到偏移 %#x (文件 %#x)  %s"
      % (len(chunks), o, len(d), "★ 正好读完" if o == len(d) else "!! 差 %d 字节" % (len(d) - o)))

print()
out = bytearray()
for (p, cpr, unc) in chunks:
    blk = d[p:p + cpr]
    try:
        out += lz4.block.decompress(blk, uncompressed_size=unc)
    except Exception as e:
        print("!! chunk 解压失败 @%#x: %s" % (p, e))
        break
print("解出 %d 字节" % len(out))
print("前 96 字节:")
print("  " + " ".join("%02x" % x for x in out[:96]))
print("前 200 字节可读视图:")
print("  " + "".join(chr(x) if 32 <= x < 127 else "." for x in out[:200]))
