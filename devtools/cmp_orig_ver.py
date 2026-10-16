# -*- coding: utf-8 -*-
"""比较两个客户端里同一批 Lua 模块的原版是否一致。

    python cmp_orig_ver.py <A根> <B根> [--list <文件>]

A = 老客户端(如 D:\\hxls)，B = Steam 客户端(如 F:\\originKleinsSteam)。
用于判断：把老客户端抽出来的 `_orig.lua` 发给 Steam 客户端，是否等于在
「把 Steam 自己的模块降级回旧版」。若两者一致则无影响。
"""
import hashlib
import os
import sys

sys.stdout.reconfigure(errors="replace")


def h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    a_root, b_root = sys.argv[1], sys.argv[2]
    a_lua = os.path.join(a_root, "Win", "lua")
    b_lua = os.path.join(b_root, "Win", "lua")

    names = []
    if "--list" in sys.argv:
        with open(sys.argv[sys.argv.index("--list") + 1], encoding="utf-8") as f:
            names = [l.strip() for l in f if l.strip()]
    else:
        for dp, _dn, fn in os.walk(a_lua):
            for f in fn:
                if f.endswith("_orig.lua"):
                    rel = os.path.relpath(os.path.join(dp, f[:-len("_orig.lua")] + ".lua"),
                                          a_lua).replace("\\", "/")
                    names.append(rel)
        names.sort()

    same, diff, miss_b, miss_a = [], [], [], []
    for rel in names:
        # ★ A 侧要比的是 `xxx_orig.lua`（A 里 xxx.lua 已经是我们的 wrapper 了）
        pa = os.path.join(a_lua, rel[:-4].replace("/", os.sep) + "_orig.lua")
        pb = os.path.join(b_lua, rel.replace("/", os.sep))
        if not os.path.exists(pa):
            miss_a.append(rel)
            continue
        if not os.path.exists(pb):
            miss_b.append(rel)
            continue
        (same if h(pa) == h(pb) else diff).append(rel)

    print("共 %d 个模块" % len(names))
    print("  一致   : %d" % len(same))
    print("  ★不一致 : %d" % len(diff))
    print("  A 缺   : %d   B 缺: %d" % (len(miss_a), len(miss_b)))
    for r in diff:
        pa = os.path.join(a_lua, r[:-4].replace("/", os.sep) + "_orig.lua")
        pb = os.path.join(b_lua, r.replace("/", os.sep))
        print("   差 %-60s A(orig)=%d B=%d" % (r, os.path.getsize(pa), os.path.getsize(pb)))
    for r in miss_b:
        print("   B 无此文件: %s" % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
