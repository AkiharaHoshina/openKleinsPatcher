# -*- coding: utf-8 -*-
"""核对「补丁集 ↔ 客户端 bk.zip」是否一致。

    python devtools\\_check_patched_bkzip.py <客户端根>
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(errors="replace")

from patchlib import bkzip                                          # noqa: E402

PATCHES = os.path.join(HERE, "patches", "lua")


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else r"F:\KleinsPatchNew")
    zp = os.path.join(root, "环行旅舍_Data", "StreamingAssets", "bk.zip")
    names, blobs, cap = bkzip.read(zp)
    idx = {n: i for i, n in enumerate(names)}
    print("bk.zip: %d 条目, 容量 %d" % (len(names), cap))

    ok = bad = 0
    for dp, _dn, fn in os.walk(PATCHES):
        for f in sorted(fn):
            if not f.endswith(".lua"):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, PATCHES).replace(os.sep, "/")
            key = "/lua/" + rel
            key_o = "/lua/" + rel[:-4] + "_orig.lua"
            w = open(p, "rb").read()
            good = (key in idx and blobs[idx[key]] == w and key_o in idx)
            if good:
                ok += 1
            else:
                bad += 1
                print("  !! %-56s wrapper=%s orig=%s"
                      % (rel, key in idx and blobs[idx[key]] == w, key_o in idx))
    print("wrapper 就位 %d / 缺失或不符 %d" % (ok, bad))
    print("_orig 条目数: %d" % sum(1 for n in names if n.endswith("_orig.lua")))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
