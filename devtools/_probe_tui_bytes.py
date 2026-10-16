#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断: 给 exe 喂 BOM+Q, 把它的**原始输出字节**挖出来看菜单到底收到了什么。

    python devtools\\_probe_tui_bytes.py

★ 目的: 菜单报错那句是 `%r` 打印的 —— 只要把它周围的字节 hexdump 出来,
  就知道 exe 里的 `input()` 到底返回了什么 codepoint。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(os.path.dirname(HERE), "kleinspatcher.exe")

p = subprocess.run([EXE], input="﻿Q\n".encode("utf-8"),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
raw = p.stdout
print("退出码 = %s, 输出 %d 字节" % (p.returncode, len(raw)))
print()

for enc in ("utf-8", "gbk"):
    mark = "没这个选项".encode(enc)
    i = raw.find(mark)
    print("按 %-6s 找 %r: %s" % (enc, "没这个选项", ("命中 @%d" % i) if i >= 0 else "没有"))
    if i >= 0:
        seg = raw[i:i + 120]
        print("    片段 repr: %r" % seg.decode(enc, "replace"))
        print("    片段 hex : %s" % seg[:60].hex(" "))
    print()

# 不管什么编码, 输出里"Q 后面跟的那个字符"是什么 —— 直接找所有含 0x51 的位置
print("输出里所有 'Q'(0x51) 周围 8 字节:")
n = 0
for i, b in enumerate(raw):
    if b == 0x51 and n < 6:
        lo = max(0, i - 4)
        seg = raw[lo:i + 5]
        print("    @%-6d %s" % (i, seg.hex(" ")))
        n += 1
