# -*- coding: utf-8 -*-
"""嗅探 bk.zip 的容器格式（lz4net 的 LZ4Stream 包着 BinaryFormatter(ZipInfo)）。"""
import sys

sys.stdout.reconfigure(errors="replace")
P = sys.argv[1] if len(sys.argv) > 1 else r"F:\originKleinsSteam\环行旅舍_Data\StreamingAssets\bk.zip"
d = open(P, "rb").read()
print("文件 %s  %d 字节" % (P, len(d)))
print("头 16 字节: %s" % " ".join("%02x" % b for b in d[:16]))

# 可打印比例
pr = sum(1 for b in d[:65536] if 32 <= b < 127 or b in (9, 10, 13))
print("前 64KB 可打印比例: %.1f%%" % (100.0 * pr / 65536))
prall = sum(1 for b in d[:2000000] if 32 <= b < 127)
print("前 2MB  可打印比例: %.1f%%" % (100.0 * prall / min(2000000, len(d))))

print()
print("=== 找已知 magic ===")
for name, m in [("LZ4 frame 04 22 4D 18", b"\x04\x22\x4d\x18"),
                ("LZ4 legacy 02 21 4C 18", b"\x02\x21\x4c\x18"),
                ("NRBF hdr 00 01 00 00 00 ff", b"\x00\x01\x00\x00\x00\xff"),
                ("BinaryLibrary 0c", b"\x0c")]:
    ks = []
    s = 0
    while len(ks) < 5:
        k = d.find(m, s)
        if k < 0:
            break
        ks.append(k)
        s = k + 1
    print("  %-26s 命中 %s" % (name, ks if ks else "无"))

print()
print("=== 头 8 字节按整数解释 ===")
import struct
print("  u32 LE[0:4] = %#x   u32 LE[4:8] = %#x" % (struct.unpack_from("<I", d, 0)[0],
                                                   struct.unpack_from("<I", d, 4)[0]))
print("  u64 LE[0:8] = %#x" % struct.unpack_from("<Q", d, 0)[0])

print()
print("=== 偏移 8 开始按 NRBF 试读 ===")
o = 8
for i in range(12):
    print("  %04X: %02x" % (o + i, d[o + i]))

print()
try:
    import lz4.frame  # noqa
    print("lz4 模块可用")
except Exception as e:
    print("lz4 模块不可用: %s" % e)
try:
    import lz4.block  # noqa
    print("lz4.block 可用")
except Exception as e:
    print("lz4.block 不可用: %s" % e)
