#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从一份「已打好补丁」的客户端里，把 wrapper 导出成补丁集数据 `patches/lua/`。

    python devtools\\export_lua_patches.py <已打补丁的客户端> [--dry-run]

判据跟注入脚本一致：**有 `xxx_orig.lua` 兄弟的 `xxx.lua` 就是 wrapper**。
导出的目录树镜像 `Win\\lua`，补丁器据此推出它在 bk.zip 里的条目名 `/lua/<相对路径>`。

★ 只导出 wrapper（**我们的代码**，几十 KB）。**不导出 `_orig`** ——
  那是游戏本体的东西，补丁器运行时从用户自己客户端的 bk.zip 里取。
"""
import argparse
import filecmp
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "patches", "lua")

EXCLUDE = {
    # ★★ 2026-10-17: `view_home_ui` **移出黑名单了** —— 现在 `inject_homeblock.py`
    #   是它的**正式**补丁（在按钮回调层拦「先切场景再开界面」的入口，比如贸区）。
    #   ★ 注意: `inject_homeprobe.py`(探针) 和 `inject_homeblock.py` **打的是同一个
    #     lua 文件** —— 同一个文件只能有一个补丁脚本，别同时上。
    "logic/shop_ui/view_shopping_center_ui.lua",  # inject_shopclick 探针
}


def main():
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("client")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    lua = os.path.join(os.path.abspath(a.client), "Win", "lua")
    if not os.path.isdir(lua):
        print("找不到 %s" % lua)
        return 2

    found, washed = [], []
    for dp, _dn, fn in os.walk(lua):
        for f in fn:
            if not f.endswith("_orig.lua"):
                continue
            mod = f[:-len("_orig.lua")] + ".lua"
            p = os.path.join(dp, mod)
            if not os.path.exists(p):
                continue
            rel = os.path.relpath(p, lua).replace("\\", "/")
            if rel in EXCLUDE:
                continue
            if filecmp.cmp(p, os.path.join(dp, f), shallow=False):
                washed.append(rel)
            else:
                found.append((rel, p))
    found.sort()
    print("发现 %d 个 wrapper" % len(found))
    if washed:
        print("★ %d 个模块的 xxx.lua 与 xxx_orig.lua 一模一样 ⇒ 已被整包解压洗过，本次不导出:"
              % len(washed))
        for r in washed:
            print("    %s" % r)
        print("  ⇒ 先 `robocopy <真原版>\\Win\\lua <目标>\\Win\\lua /MIR` 再重跑注入脚本。")
        return 1

    if os.path.isdir(OUT) and not a.dry_run:
        shutil.rmtree(OUT)
    tot = 0
    for rel, p in found:
        dst = os.path.join(OUT, rel.replace("/", os.sep))
        sz = os.path.getsize(p)
        tot += sz
        if not a.dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(p, dst)
        print("  %-58s %6d" % (rel, sz))
    print("合计 %d 字节 -> %s%s" % (tot, OUT, "（dry-run，未写盘）" if a.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
