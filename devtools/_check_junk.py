#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`patchlib.ui.clean()` 真的能清掉那些看不见的字符吗?

    python devtools\\_check_junk.py

★★ 为什么要单独一个脚本: 这个功能**假绿过** ——
   判据一度是"通过管道喂一个 Q 给 exe, 再看**进程退出码**",
   可"没匹配上 → 回车 → EOF 退出"**也是 0** ⇒ 看起来永远是对的。

★★ 但它只测**第二道防线**(`clean()` 本身)。
   2026-10-17 查明: 管道那条路的**真正**根因是"打好的 exe 里 stdio 退回 cp936,
   UTF-8 字节被按 GBK 解码", 治它的是 `ui.setup_console()`。
   ⇒ 端到端那条判据在 `devtools\\_check_tui_smoke.py`(真的跑 exe)。两个都绿才算数。

★★★ 下面一律用 `chr()` 拼, **绝不写裸的不可见字符** ——
   裸写的时候它们会在编辑/传输过程中没真的进到字符串里, 判据静默失效;
   连写成 `\\uXXXX` 都不保险(某些工具链会把转义先解掉)。
   `chr()` 拼出来的源码**全是 ASCII**, 能 grep、能一眼看出对不对。
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from patchlib import ui                              # noqa: E402

B = chr(0xFEFF)
ZWSP, ZWNJ, ZWJ = chr(0x200B), chr(0x200C), chr(0x200D)
LRM, RLM = chr(0x200E), chr(0x200F)
WJ = chr(0x2060)

CASES = [
    (B + "Q", "Q", "UTF-8 BOM"),
    (ZWSP + "Q", "Q", "零宽空格"),
    (ZWNJ + "Q", "Q", "零宽不连字"),
    (ZWJ + "Q", "Q", "零宽连字"),
    (LRM + "Q", "Q", "LRM"),
    (RLM + "Q", "Q", "RLM"),
    (WJ + "Q", "Q", "word joiner"),
    ("\u0000Q", "Q", "NUL"),
    ("  Q  ", "Q", "普通前后空格"),
    (B + "  2  ", "2", "BOM + 空格 + 数字"),
    ("", "", "空串"),
    (B, "", "只有 BOM"),
    ("Q" + B, "Q", "BOM 在后面"),
]

bad = 0
for src, want, name in CASES:
    got = ui.clean(src)
    ok = (got == want)
    bad += 0 if ok else 1
    print("  %s %-18s %-14s -> %-14s (期望 %s)"
          % ("[OK] " if ok else "[!!] ", name,
             " ".join("U+%04X" % ord(c) for c in src) or "(空)",
             " ".join("U+%04X" % ord(c) for c in got) or "(空)",
             " ".join("U+%04X" % ord(c) for c in want) or "(空)"))

print()
if bad:
    print("★★ 有 %d 项没清干净 —— 菜单会「键失灵」, 而且一声不响" % bad)
    sys.exit(1)
print("✓ clean() 对全部 %d 种脏输入都正确" % len(CASES))
sys.exit(0)
