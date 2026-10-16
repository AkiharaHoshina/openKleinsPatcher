#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冒烟: 把**打好的 exe** 真的跑起来, 用管道喂几个脏输入, 看它认不认。

    python devtools\\_check_tui_smoke.py

★★ 为什么必须跑 exe, 而不是直接调 `clean()`:
   `ui.clean()` 的假绿出过**两次** —— 自检直接调 `clean("﻿Q")` 全绿,
   可**打包后的 exe** 从管道读进来的东西照样认不出。
   ⇒ 判据必须落在"exe 自己的行为"上。

★★ 为什么下面有一个"必须失败"的对照项 (`ZZZ`):
   老判据是"看进程退出码 = 0" —— 可"没匹配上 → 回车 → EOF 退出"**也是 0**,
   所以它**永远**通过。现在改成看输出里有没有"没这个选项",
   并且用 `ZZZ` 证明这个 "看得见" 的能力是真的存在**(对照组)**。

★ 管道喂进去的东西实测是 `'\\ufeffQ\\n'`(codepoint 0xFEFF 打头),
  见 `_probe_stdin.py` —— 这不是假想, 是 PowerShell 管道的真实行为。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXE = os.path.join(ROOT, "kleinspatcher.exe")

MARK = "没这个选项"                 # 菜单"认不出这个键"时才打的一句

# (输入, 期望认得出吗, 说明)
CASES = [
    ("Q",       True,  "干净 Q"),
    ("﻿Q", True,  "BOM + Q（管道实况）"),
    ("  Q  ",   True,  "前后空格"),
    ("q",       True,  "小写 q"),
    ("ZZZ",     False, "对照组: 本来就该认不出"),
]


def run(payload, timeout=90):
    """跑一次 exe, 把 "\n"-结尾的 payload 从管道喂进去。返回 (退出码, 原始 bytes)。"""
    p = subprocess.run([EXE], input=(payload + "\n").encode("utf-8"),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout


def saw_bad_mark(raw):
    """输出里有没有"没这个选项"。★ 逐种编码试 —— exe 的 stdout 编码随控制台走,
    Windows 上可能是 gbk 也可能是 utf-8, 只认一种会把结论判反。"""
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            if MARK in raw.decode(enc):
                return True
        except Exception:
            pass
    return False


def main():
    if not os.path.exists(EXE):
        print("  没有 %s —— 先打包再跑这个。" % EXE)
        return 2

    bad = 0
    for payload, want_ok, name in CASES:
        try:
            rc, raw = run(payload)
        except subprocess.TimeoutExpired:
            print("  [!!] %-22s 超时（界面卡住/死循环?）" % name)
            bad += 1
            continue
        got_bad = saw_bad_mark(raw)
        ok = (got_bad != want_ok)          # 认得出 ⇒ 不该出现那句
        bad += 0 if ok else 1
        print("  %s %-22s 退出码=%-4s %s"
              % ("[OK] " if ok else "[!!] ", name, rc,
                 "认得了" if not got_bad else "菜单报了『没这个选项』"))

    print()
    if bad:
        print("★★ %d 项不对 —— 菜单会「键失灵」, 而且一声不响" % bad)
        return 1
    print("✓ %d 项全对（含 1 个对照组，证明这个判据真的看得见问题）" % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
