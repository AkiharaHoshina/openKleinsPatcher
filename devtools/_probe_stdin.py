#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断: 从**管道**喂一个 "Q" 进来, 到底收到了什么?

    "Q" | python devtools\\_probe_stdin.py

★ 为什么要这个: `ui.clean()` 的"假绿"教训 ——
  自检直接调 `clean("﻿Q")` 全绿, 可 exe 从管道读进来的东西照样认不出。
  ⇒ 先看清楚**字节层面**收到的是什么, 别拿"我认为它是什么"当判据。
"""
import sys

sys.stdout.reconfigure(errors="replace")
s = sys.stdin.readline()
print("stdin.encoding = %r" % (sys.stdin.encoding,))
print("stdin.errors   = %r" % (sys.stdin.errors,))
print("len            = %d" % len(s))
print("codepoints     = %s" % ([hex(ord(c)) for c in s],))
print("repr           = %r" % (s,))
