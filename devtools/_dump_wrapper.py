# -*- coding: utf-8 -*-
"""从 inject_*.py 里把内嵌的 Lua 源码抠出来打印。"""
import io
import re
import sys

sys.stdout.reconfigure(errors="replace")
p = sys.argv[1]
src = io.open(p, encoding="utf-8").read()
# 找最长的三引号块（一般就是 Lua 源码）
blocks = re.findall(r'r?u?"""(.*?)"""', src, re.S) or re.findall(r"r?u?'''(.*?)'''", src, re.S)
if not blocks:
    print("没找到三引号块")
    sys.exit(1)
big = max(blocks, key=len)
print("=== %s 里最长的 Lua 块（%d 字符）===" % (p, len(big)))
print(big)
