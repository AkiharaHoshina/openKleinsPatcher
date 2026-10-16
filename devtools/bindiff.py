#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出两个二进制文件的**全部差异字节**（偏移 + 前后值 + 上下文）。

    python bindiff.py <文件A> <文件B> [--ctx 16] [--max 40]

用途：确认某个二进制到底改了几处、改在哪 —— 比看工具脚本的注释可靠得多。
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")


def main():
    # 手工解析：带值的开关先吃掉自己的值，剩下的才是位置参数
    positional, ctx, maxruns, i = [], 16, 40, 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--ctx":
            ctx = int(sys.argv[i + 1]); i += 2; continue
        if a == "--max":
            maxruns = int(sys.argv[i + 1]); i += 2; continue
        if a.startswith("-"):
            print("未知参数: %s" % a); return 2
        positional.append(a); i += 1
    args = positional

    if len(args) != 2:
        print(__doc__)
        return 2

    pa, pb = args
    a = open(pa, "rb").read()
    b = open(pb, "rb").read()
    print("A: %s  (%d 字节)" % (os.path.abspath(pa), len(a)))
    print("B: %s  (%d 字节)" % (os.path.abspath(pb), len(b)))
    if len(a) != len(b):
        print("!! 长度不同，只比较公共前缀 %d 字节" % min(len(a), len(b)))
    n = min(len(a), len(b))

    # 收集所有不同的偏移，合并成连续段
    runs = []
    i = 0
    while i < n:
        if a[i] != b[i]:
            j = i
            while j + 1 < n and a[j + 1] != b[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1

    total = sum(j - i + 1 for i, j in runs)
    print("差异字节总数: %d   （分布在 %d 个连续段）" % (total, len(runs)))
    print()
    for k, (i, j) in enumerate(runs[:maxruns]):
        lo, hi = max(0, i - ctx), min(n, j + 1 + ctx)
        print("--- 段 %d: 0x%X .. 0x%X  (%d 字节) ---" % (k + 1, i, j, j - i + 1))
        print("  A[%#X] %s" % (lo, a[lo:hi].hex(" ")))
        print("  B[%#X] %s" % (lo, b[lo:hi].hex(" ")))
        try:
            sa = a[i:j + 1].decode("ascii")
            sb = b[i:j + 1].decode("ascii")
            print("  A 文本: %r" % sa)
            print("  B 文本: %r" % sb)
        except Exception:
            pass
        # 4 字节小端 int 解读（Unity SerializedFile 的长度前缀就是这种）
        for off in range(max(0, i - 4), i + 1):
            try:
                ia = int.from_bytes(a[off:off + 4], "little", signed=True)
                ib = int.from_bytes(b[off:off + 4], "little", signed=True)
            except Exception:
                continue
            if ia != ib and 0 < ib < 1 << 24:
                print("  若按 int32(小端)@%#X 读: %d -> %d" % (off, ia, ib))
        print()
    if len(runs) > maxruns:
        print("... 还有 %d 段未显示" % (len(runs) - maxruns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
