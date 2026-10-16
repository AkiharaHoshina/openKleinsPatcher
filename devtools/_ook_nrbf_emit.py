# -*- coding: utf-8 -*-
"""纯 Python 复刻 bk.zip 头块（ZipInfo 的 .NET BinaryFormatter 序列化）。

验收标准：拿真实的 hdr.bin（65536 字节，前 40708 有内容）逐字节比对。
"""
import re
import struct
import sys

sys.stdout.reconfigure(errors="replace")

LIB = "Assembly-CSharp, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"
LIST_S = ("System.Collections.Generic.List`1[[System.String, mscorlib, "
          "Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]]")
LIST_I = ("System.Collections.Generic.List`1[[System.Int32, mscorlib, "
          "Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]]")


def p32(v):
    return struct.pack("<i", v)


def lpstr(s):
    b = s.encode("utf-8")
    n = len(b)
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n:
            out.append(x | 0x80)
        else:
            out.append(x)
            break
    return bytes(out) + b


def serialize_zipinfo(names, sizes, capacity=None, version=None):
    """ZipInfo 的 NRBF 字节流。

    capacity=None 时用 len(names)（数组长度=元素数，合法且最省）。
    ★ `_version` 是 List<T> 的改动计数器，**不参与反序列化**，但实测游戏写出来的是 n+1，
      为了能逐字节复现原文件，默认取 n+1。
    """
    n = len(names)
    cap = n if capacity is None else capacity
    ver = (n + 1) if version is None else version
    o = bytearray()
    o += b"\x00" + p32(1) + p32(-1) + p32(1) + p32(0)             # SerializedStreamHeader
    o += b"\x0c" + p32(2) + lpstr(LIB)                            # BinaryLibrary
    # --- ClassWithMembersAndTypes: ZipInfo (oid 1) ---
    o += b"\x05" + p32(1) + lpstr("ZipInfo") + p32(2)
    o += lpstr("allFileNames") + lpstr("allFileSizes")
    o += bytes([3, 3]) + lpstr(LIST_S) + lpstr(LIST_I) + p32(2)   # Types + 附加 + LibraryId
    o += b"\x09" + p32(3) + b"\x09" + p32(4)                      # 成员值 -> 引用 3 / 4
    # --- SystemClassWithMembersAndTypes: List<string> (oid 3) ---
    o += b"\x04" + p32(3) + lpstr(LIST_S) + p32(3)
    o += lpstr("_items") + lpstr("_size") + lpstr("_version")
    o += bytes([6, 0, 0]) + bytes([8, 8])                         # Types=[StringArray,Prim,Prim]
    o += b"\x09" + p32(5) + p32(n) + p32(ver)                     # _items 引用 5, _size, _version
    # --- SystemClassWithMembersAndTypes: List<int> (oid 4) ---
    o += b"\x04" + p32(4) + lpstr(LIST_I) + p32(3)
    o += lpstr("_items") + lpstr("_size") + lpstr("_version")
    o += bytes([7, 0, 0]) + bytes([8, 8, 8])                      # Types=[PrimArray,Prim,Prim]
    o += b"\x09" + p32(6) + p32(n) + p32(ver)
    # --- ArraySingleString (oid 5) ---
    o += b"\x11" + p32(5) + p32(cap)
    for i, s in enumerate(names):
        o += b"\x06" + p32(7 + i) + lpstr(s)
    left = cap - n
    while left > 0:
        if left > 255:
            o += b"\x0e" + p32(left if left <= 0x7FFFFFFF else 0x7FFFFFFF)
            left = 0
        else:
            o += b"\x0d" + bytes([left])
            left = 0
    # --- ArraySinglePrimitive(Int32) (oid 6) ---
    o += b"\x0f" + p32(6) + p32(cap) + b"\x08"
    o += b"".join(p32(x) for x in sizes)
    o += b"\x00" * (4 * (cap - n))
    o += b"\x0b"                                                  # MessageEnd
    return bytes(o)


def parse_zipinfo(blob):
    """从真实的 NRBF 头块里抠出 (names, sizes, capacity)。"""
    names, sizes = [], []
    pos = blob.find(b"\x11" + p32(5))
    if pos < 0:
        raise ValueError("找不到 ArraySingleString")
    cap = struct.unpack_from("<i", blob, pos + 5)[0]
    q, done = pos + 9, 0
    while done < cap:
        t = blob[q]
        if t == 0x06:
            ln = blob[q + 5]
            names.append(blob[q + 6:q + 6 + ln].decode("utf-8"))
            q += 6 + ln
            done += 1
        elif t == 0x0D:
            done += blob[q + 1]
            q += 2
        elif t == 0x0E:
            done += struct.unpack_from("<i", blob, q + 1)[0]
            q += 5
        else:
            raise ValueError("数组里出现未知记录 %#x @%d" % (t, q))
    pos = blob.find(b"\x0f" + p32(6))
    if pos < 0:
        raise ValueError("找不到 ArraySinglePrimitive")
    sizes = list(struct.unpack_from("<%di" % len(names), blob, pos + 10))
    return names, sizes, cap


def main():
    bk = r"D:\openKleinsPatcher\devtools\multiver\_bk"
    hdr = open(bk + r"\hdr.bin", "rb").read()
    names, sizes, cap = parse_zipinfo(hdr)
    print("数组容量 %d, 名字 %d, 尺寸 %d" % (cap, len(names), len(sizes)))
    print("  前 3 名: %s" % names[:3])
    print("  前 3 尺寸: %s" % sizes[:3])

    end = hdr.rfind(b"\x0b", 0, 65536)
    real = hdr[:end + 1]
    mine = serialize_zipinfo(names, sizes, capacity=cap)
    print("真实有效长度 = %d   我的输出长度 = %d" % (len(real), len(mine)))
    if mine == real:
        print("★★★ 逐字节完全一致 —— 纯 Python emitter 可用")
        return 0
    k = min(len(mine), len(real))
    for i in range(k):
        if mine[i] != real[i]:
            print("第一处不同 @%d: 我=%02x  真=%02x" % (i, mine[i], real[i]))
            print("  我: %s" % " ".join("%02x" % x for x in mine[max(0, i - 8):i + 16]))
            print("  真: %s" % " ".join("%02x" % x for x in real[max(0, i - 8):i + 16]))
            break
    else:
        print("前 %d 字节相同，只是长度不同" % k)
    return 1


if __name__ == "__main__":
    sys.exit(main())
