#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条对比 `patches\\lua` 与某份客户端 `bk.zip` 里的 Lua 条目(只读)。

    python devtools\\_cmp_patchset.py <客户端根> [<客户端根> ...]

`kleinspatcher.py --list` 只会说「替换 N」, 不说是**哪几个**。
换过导出源(比如从另一个客户端 export 过)之后, 就需要这个来看清楚差异。

★ 输出 sha 只取前 12 位。
"""
import hashlib
import os
import sys

sys.stdout.reconfigure(errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import kleinspatcher                                   # noqa: E402
from patchlib import bkzip                             # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


for root in sys.argv[1:]:
    root = os.path.abspath(root)
    print("=" * 74)
    print("客户端: %s" % root)
    print("-" * 74)
    p = os.path.join(root, kleinspatcher.BKZIP)
    if not os.path.exists(p):
        print("  !! 没有 bk.zip")
        continue
    names, blobs, _cap = bkzip.parse(open(p, "rb").read())
    idx = {n: i for i, n in enumerate(names)}
    same = diff = missing = 0
    for rel, wpath in kleinspatcher.lua_targets():
        key = "/lua/" + rel
        w = open(wpath, "rb").read()
        if key not in idx:
            missing += 1
            print("  [本版本没有] %-52s wrap=%s" % (rel, sha(w)))
            continue
        cur = blobs[idx[key]]
        if cur == w:
            same += 1
        else:
            diff += 1
            print("  [★不一致]     %-52s 包里=%s(%dB) 补丁=%s(%dB)"
                  % (rel, sha(cur), len(cur), sha(w), len(w)))
    print("-" * 74)
    print("  一致 %d / 不一致 %d / 本版本没有 %d" % (same, diff, missing))
print("=" * 74)
