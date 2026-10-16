#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python 的 LZ4 **block** 格式编解码（不依赖 `lz4` 扩展模块）。

## 为什么自己写

补丁器要求**零第三方依赖**（拿去就能跑）。而 `bk.zip` 外面套的是 LZ4 分块流，
所以至少要能解压；要重建就得能压缩。

## block 格式（LZ4 规范，注意这里**不是** frame 格式）

一串「序列」拼起来，每个序列::

    token(1B) = 字面量长度(高 4 位) | 匹配长度-4(低 4 位)
    若字面量长度 == 15: 再读若干字节累加（每读到 255 就继续）
    字面量（上面算出的字节数）
    —— 如果已经到输入末尾，序列到此结束（最后一个序列**只有字面量**）——
    偏移量(2B, 小端)
    若匹配长度 nibble == 15: 再读若干字节累加
    实际匹配长度 = 低 4 位 + 4

约束（写压缩器时必须满足，否则客户端解不出来）::

    * 最后 5 字节必须是字面量        （LASTLITERALS）
    * 匹配不能**开始**在倒数 12 字节内（MFLIMIT）
    * 偏移量 1..65535，且不能超过当前输出位置

★ 匹配可以**重叠**（offset < matchLen），解压时必须逐字节复制，不能整块拷贝。
"""
MFLIMIT = 12
LASTLITERALS = 5
MINMATCH = 4
MAX_OFFSET = 65535
HASH_BITS = 16
HASH_SIZE = 1 << HASH_BITS


def decompress(src, out_len=None):
    """解一个 LZ4 block。out_len 只是用来做断言，不给也行。"""
    n = len(src)
    out = bytearray()
    i = 0
    while i < n:
        token = src[i]
        i += 1
        # 字面量长度
        ll = token >> 4
        if ll == 15:
            while True:
                b = src[i]
                i += 1
                ll += b
                if b != 255:
                    break
        if ll:
            out += src[i:i + ll]
            i += ll
        if i >= n:
            break                       # 最后一个序列：只有字面量
        # 偏移量
        off = src[i] | (src[i + 1] << 8)
        i += 2
        if off == 0:
            raise ValueError("LZ4 block: 偏移量为 0")
        # 匹配长度
        ml = token & 0x0F
        if ml == 15:
            while True:
                b = src[i]
                i += 1
                ml += b
                if b != 255:
                    break
        ml += MINMATCH
        start = len(out) - off
        if start < 0:
            raise ValueError("LZ4 block: 偏移量越界")
        # ★ 逐字节复制（支持重叠匹配）
        for k in range(ml):
            out.append(out[start + k])
    if out_len is not None and len(out) != out_len:
        raise ValueError("LZ4 block: 解出 %d 字节，期望 %d" % (len(out), out_len))
    return bytes(out)


def _hash4(b, i):
    return ((b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24))
            * 2654435761) >> (32 - HASH_BITS) & (HASH_SIZE - 1)


def _emit_len(out, n):
    """写「超过 15 的部分」的累加字节。"""
    while n >= 255:
        out.append(255)
        n -= 255
    out.append(n)


def compress(src):
    """极简贪心 LZ4 压缩。输出合法、能解回原样，压缩率略差于参考实现。"""
    n = len(src)
    out = bytearray()
    if n == 0:
        return bytes(out)
    if n < MFLIMIT + 1:
        out.append(min(n, 15) << 4)
        if n >= 15:
            _emit_len(out, n - 15)
        out += src
        return bytes(out)

    table = {}
    anchor = 0
    i = 0
    limit = n - MFLIMIT
    while i < limit:
        h = _hash4(src, i)
        ref = table.get(h, -1)
        table[h] = i
        if ref < 0 or i - ref > MAX_OFFSET or src[ref:ref + MINMATCH] != src[i:i + MINMATCH]:
            i += 1
            continue
        # 扩展匹配（匹配不能碰到最后 5 字节）
        ml = MINMATCH
        maxml = n - LASTLITERALS - i
        while ml < maxml and src[ref + ml] == src[i + ml]:
            ml += 1
        lit = i - anchor
        tp = len(out)
        out.append(0)
        if lit >= 15:
            out[tp] = 0xF0
            _emit_len(out, lit - 15)
        else:
            out[tp] = lit << 4
        out += src[anchor:i]
        off = i - ref
        out.append(off & 0xFF)
        out.append((off >> 8) & 0xFF)
        m = ml - MINMATCH
        if m >= 15:
            out[tp] |= 0x0F
            _emit_len(out, m - 15)
        else:
            out[tp] |= m
        i += ml
        anchor = i
    # 尾部字面量
    lit = n - anchor
    tp = len(out)
    out.append(0)
    if lit >= 15:
        out[tp] = 0xF0
        _emit_len(out, lit - 15)
    else:
        out[tp] = lit << 4
    out += src[anchor:]
    return bytes(out)
