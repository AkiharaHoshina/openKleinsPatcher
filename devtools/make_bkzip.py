#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Lua 补丁打进客户端的资源源包 `bk.zip`。

    python make_bkzip.py --clean <真原版客户端> --patched <已打补丁的客户端> -o <输出 bk.zip>
    python make_bkzip.py --clean ... --patched ... -o ... --dry-run

## 为什么走这条路

Steam 版的 `HotUpdate` 每次启动都会把 `bk.zip` 整包解开覆盖 `Win\\lua`，
所以「把补丁写进 `Win\\lua`」活不过一次启动。

试过的另一条路（服务端的 `baseapi/v1/update` 下载通道）**走不通**：
客户端下完是 `File.Move(临时文件, 目标)`，**从不删已存在的目标**，
而目标文件刚被解压写好 ⇒ 必然 `ERROR_ALREADY_EXISTS`。
那条通道只能下发「本地不存在的新文件」。

⇒ 正路就是**改源包**：解压步骤一跑，补丁自然就到位了。

## 做法

对每个「已打补丁」的模块（就是有 `xxx_orig.lua` 兄弟的那些）：

1. **替换** `/lua/<相对路径>` 的内容 → wrapper
2. **新增** `/lua/<相对路径去掉 .lua>_orig.lua` → 真原版（wrapper 靠 `require` 读它）

条目名带前导 `/`（实测原包就是 `/lua/Global.lua` 这种写法）。
原包的 `_items` 数组容量是 **1024**，装得下 672+25 个条目，所以容量保持不变。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bkzip                                                        # noqa: E402

sys.stdout.reconfigure(errors="replace")

BK_REL = r"环行旅舍_Data\StreamingAssets\bk.zip"
LUA_REL = os.path.join("Win", "lua")

# ★ 诊断探针，不是产品补丁，不进源包
EXCLUDE = {
    "logic/home_ui/view_home_ui.lua",
    "logic/shop_ui/view_shopping_center_ui.lua",
}


def find_patched(patched_lua):
    """找出「xxx.lua 与 xxx_orig.lua 兄弟都在」的模块，返回 [(rel, wrapper路径, orig路径)]。"""
    out = []
    for dp, _dn, fn in os.walk(patched_lua):
        for f in fn:
            if not f.endswith("_orig.lua"):
                continue
            mod = f[:-len("_orig.lua")] + ".lua"
            p = os.path.join(dp, mod)
            if not os.path.exists(p):
                continue
            rel = os.path.relpath(p, patched_lua).replace("\\", "/")
            if rel in EXCLUDE:
                continue
            out.append((rel, p, os.path.join(dp, f)))
    out.sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True, help="真原版客户端根（bk.zip 和 _orig 的来源）")
    ap.add_argument("--patched", required=True, help="已打补丁的客户端根（wrapper 的来源）")
    ap.add_argument("-o", "--out", required=True, help="输出的 bk.zip")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    clean = os.path.abspath(a.clean)
    patched = os.path.abspath(a.patched)
    src_zip = os.path.join(clean, BK_REL)
    patched_lua = os.path.join(patched, LUA_REL)
    if not os.path.exists(src_zip):
        print("找不到 %s" % src_zip)
        return 2
    if not os.path.isdir(patched_lua):
        print("找不到 %s" % patched_lua)
        return 2

    names, blobs, cap = bkzip.read(src_zip)
    print("原包: %d 条目, 容量 %d, 数据 %d 字节" % (len(names), cap, sum(map(len, blobs))))
    idx = {n: i for i, n in enumerate(names)}

    targets = find_patched(patched_lua)
    print("待打补丁的模块: %d" % len(targets))

    added, replaced, washed = 0, 0, 0
    for rel, wrapper, _o in targets:
        key = "/lua/" + rel
        key_o = "/lua/" + rel[:-4] + "_orig.lua"
        if key not in idx:
            print("  !! 原包里没有 %s —— 跳过" % key)
            continue
        w = open(wrapper, "rb").read()
        if w == blobs[idx[key]]:
            washed += 1
            print("  !! %s 与原包内容一样 ⇒ 这个是**空补丁**（客户端被整包洗过？）" % rel)
            continue
        blobs[idx[key]] = w
        replaced += 1
        # _orig：优先用 clean 端的真原版
        o = open(os.path.join(clean, LUA_REL, rel.replace("/", os.sep)), "rb").read()
        if key_o in idx:
            blobs[idx[key_o]] = o
        else:
            names.append(key_o)
            blobs.append(o)
            idx[key_o] = len(names) - 1
            added += 1

    print("替换 %d 个, 新增 %d 个 _orig, 空补丁 %d 个" % (replaced, added, washed))
    if washed and not a.dry_run:
        print("!! 有空补丁，拒绝写出（拿一个真正打好补丁的客户端来）")
        return 1
    print("新包: %d 条目 (容量 %d)" % (len(names), cap))
    if a.dry_run:
        print("(dry-run) 未写出")
        return 0

    raw = bkzip.write(a.out, names, blobs, cap)
    print("已写出 %s  (%d 字节)" % (a.out, os.path.getsize(a.out)))

    # 自检：重新读一遍，逐条核对
    n2, b2, cap2 = bkzip.read(a.out)
    assert n2 == names and cap2 == cap, "回读名字/容量不一致"
    bad = [n2[i] for i in range(len(n2)) if b2[i] != blobs[i]]
    if bad:
        print("!! 回读校验失败: %s" % bad[:5])
        return 1
    print("★ 回读校验通过：%d 条目逐条一致" % len(n2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
