#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`环行旅舍_Data\\StreamingAssets\\bk.zip` 的读写（**零第三方依赖**）。

## 这个文件是什么

`bk.zip` 不是 zip —— 它是客户端 HotUpdate 的「资源源包」，
`HotUpdate.DecompressTask` 每次启动把它整包解开覆盖 `Win\\lua`。

```
[0:4]        int32 LE = 65536              头块长度
[4:4+65536]  .NET BinaryFormatter(ZipInfo) 序列化，**零填充到固定 64K**
[4+65536:]   文件数据 —— 按 ZipInfo.allFileSizes 顺序首尾相接
```

外面套一层 **LZ4 分块流**（`LZ4.LZ4Stream`，lz4net）::

    重复: 0x01 | varint 未压缩长度(≤1MB) | varint 压缩长度 | LZ4 raw block
    读到文件尾为止

## ZipInfo 的 NRBF 布局

（反汇编 `LZ4Helper.Decompress` + 拿 .NET 的 `BinaryFormatter` 当对照组推出来的，
纯 Python 输出与真实头块 **40708 字节逐字节一致**。）

```
00                 SerializedStreamHeader (RootId=1, HeaderId=-1, 1, 0)
0C                 BinaryLibrary(2, "Assembly-CSharp, Version=0.0.0.0, ...")
05                 ClassWithMembersAndTypes(oid=1, "ZipInfo",
                       [allFileNames, allFileSizes], Types=[3,3],
                       附加=[List<string>名, List<int>名], LibraryId=2)
   09→3  09→4        两个成员的值
04                 SystemClassWithMembersAndTypes(oid=3, "List<string>",
                       [_items,_size,_version], Types=[6,0,0], 附加=[8,8])
   09→5  _size=N  _version=N+1
04                 SystemClassWithMembersAndTypes(oid=4, "List<int>",
                       [_items,_size,_version], Types=[7,0,0], 附加=[8,8,8])
   09→6  _size=N  _version=N+1
11                 ArraySingleString(oid=5, len=容量) + N×(06 oid 长度前缀UTF8)
0F                 ArraySinglePrimitive(oid=6, len=容量, type=8=Int32) + N×int32
0B                 MessageEnd
```

★★ 三个坑（都踩过）：
  1. `ClassWithMembersAndTypes` 末尾**有** LibraryId，`SystemClassWithMembersAndTypes` **没有**
     —— 少读/多读都会让后面全串位。
  2. `_items` 数组的 `len` 是**容量**不是元素数（实测 1024 装 672），多出来的用
     `ObjectNullMultiple(0x0E)` / `ObjectNullMultiple256(0x0D)` 填。读的时候必须按容量消费。
  3. `_version` 是 `List<T>` 的改动计数器，**不参与反序列化**，但客户端写的是 N+1；
     要逐字节复现就得跟着写 N+1。

条目名带前导 `/`（`/lua/Global.lua`）。
"""
import struct

from . import lz4block

HEADER_SIZE = 65536
BLOCK = 1 << 20

LIB = "Assembly-CSharp, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"
LIST_S = ("System.Collections.Generic.List`1[[System.String, mscorlib, "
          "Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]]")
LIST_I = ("System.Collections.Generic.List`1[[System.Int32, mscorlib, "
          "Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]]")


def p32(v):
    return struct.pack("<i", v)


def _varint_write(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n:
            out.append(x | 0x80)
        else:
            out.append(x)
            return bytes(out)


def _varint_read(b, o):
    v = sh = 0
    while True:
        x = b[o]
        o += 1
        v |= (x & 0x7F) << sh
        if not (x & 0x80):
            return v, o
        sh += 7


def _lpstr(s):
    b = s.encode("utf-8")
    return _varint_write(len(b)) + b


# ── LZ4 分块流 ────────────────────────────────────────────
def unstream(d):
    out = bytearray()
    o = 0
    while o < len(d):
        if d[o] != 0x01:
            raise ValueError("分块标记应为 0x01，实为 %#x @%d" % (d[o], o))
        o += 1
        unc, o = _varint_read(d, o)
        cpr, o = _varint_read(d, o)
        out += lz4block.decompress(d[o:o + cpr], out_len=unc)
        o += cpr
    return bytes(out)


def stream(raw):
    out = bytearray()
    for i in range(0, max(1, len(raw)), BLOCK):
        chunk = raw[i:i + BLOCK]
        blk = lz4block.compress(chunk)
        out += b"\x01" + _varint_write(len(chunk)) + _varint_write(len(blk)) + blk
    return bytes(out)


# ── ZipInfo 的 NRBF ──────────────────────────────────────
def serialize_zipinfo(names, sizes, capacity=None, version=None):
    n = len(names)
    cap = n if capacity is None else capacity
    ver = (n + 1) if version is None else version
    o = bytearray()
    o += b"\x00" + p32(1) + p32(-1) + p32(1) + p32(0)
    o += b"\x0c" + p32(2) + _lpstr(LIB)
    o += b"\x05" + p32(1) + _lpstr("ZipInfo") + p32(2)
    o += _lpstr("allFileNames") + _lpstr("allFileSizes")
    o += bytes([3, 3]) + _lpstr(LIST_S) + _lpstr(LIST_I) + p32(2)
    o += b"\x09" + p32(3) + b"\x09" + p32(4)
    o += b"\x04" + p32(3) + _lpstr(LIST_S) + p32(3)
    o += _lpstr("_items") + _lpstr("_size") + _lpstr("_version")
    o += bytes([6, 0, 0]) + bytes([8, 8])
    o += b"\x09" + p32(5) + p32(n) + p32(ver)
    o += b"\x04" + p32(4) + _lpstr(LIST_I) + p32(3)
    o += _lpstr("_items") + _lpstr("_size") + _lpstr("_version")
    o += bytes([7, 0, 0]) + bytes([8, 8, 8])
    o += b"\x09" + p32(6) + p32(n) + p32(ver)
    o += b"\x11" + p32(5) + p32(cap)
    for i, s in enumerate(names):
        o += b"\x06" + p32(7 + i) + _lpstr(s)
    left = cap - n
    if left > 0:
        o += b"\x0e" + p32(left)
    o += b"\x0f" + p32(6) + p32(cap) + b"\x08"
    o += b"".join(p32(x) for x in sizes)
    o += b"\x00" * (4 * (cap - n))
    o += b"\x0b"
    return bytes(o)


def parse_zipinfo(blob):
    """从 NRBF 头块里抠出 (names, sizes, capacity, 有效长度)。"""
    names = []
    pos = blob.find(b"\x11" + p32(5))
    if pos < 0:
        raise ValueError("找不到 ArraySingleString —— 不是预期的 ZipInfo 布局")
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
    return names, sizes, cap, blob.rfind(b"\x0b") + 1


# ── 对外接口 ─────────────────────────────────────────────
def parse(data):
    raw = unstream(data)
    hl = struct.unpack_from("<i", raw, 0)[0]
    if hl != HEADER_SIZE:
        raise ValueError("头块长度 %d，期望 %d —— 这个客户端版本没见过" % (hl, HEADER_SIZE))
    names, sizes, cap, _end = parse_zipinfo(raw[4:4 + hl])
    payload = raw[4 + hl:]
    if sum(sizes) != len(payload):
        raise ValueError("尺寸合计 %d 与数据段 %d 对不上" % (sum(sizes), len(payload)))
    blobs, off = [], 0
    for s in sizes:
        blobs.append(payload[off:off + s])
        off += s
    return names, blobs, cap


def build(names, blobs, capacity=1024):
    assert len(names) == len(blobs)
    cap = max(capacity, len(names))
    hdr = serialize_zipinfo(names, [len(b) for b in blobs], capacity=cap)
    if len(hdr) > HEADER_SIZE:
        raise ValueError("头块 %d 字节超过 %d" % (len(hdr), HEADER_SIZE))
    return stream(p32(HEADER_SIZE) + hdr + b"\x00" * (HEADER_SIZE - len(hdr))
                  + b"".join(blobs))


def read(path):
    names, blobs, cap = parse(open(path, "rb").read())
    return names, blobs, cap


def write(path, names, blobs, capacity=1024):
    data = build(names, blobs, capacity)
    open(path, "wb").write(data)
    return len(data)
