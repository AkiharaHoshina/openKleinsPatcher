#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「打过补丁的 Lua」做成假服的**远程更新下发**内容。

    python make_update_route.py --patched <已打补丁的客户端根> --pristine <干净客户端根>
                                --serve <假服 res 目录> --routes <routes.json> [--dry-run]

## 为什么走这条路

Steam 版每次启动都会执行 HotUpdate 的 Decompress 步骤 ——
把 `StreamingAssets\\bk.zip`（Lua 源包）整包解开覆盖 `Win\\lua`（实测每次 672 个文件）。
我们打进 `Win\\lua` 的 Lua 补丁活不过一次启动。

但 HotUpdate 的任务顺序是：

    CheckEnvironment -> CheckVersion -> **Decompress（覆盖）** -> **Download（最后落地）**

而 Download 的地址和清单来自假服的 `baseapi/v1/update`（`routes.json`，**热读**）。
⇒ 让假服返回一份「文件更新列表」，客户端就会在解压之后把我们的补丁**下载回来覆盖**。
这条是游戏自己支持的通道，不用改客户端一个字节。

## 下发的两类文件

1. `<module>.lua`        —— 我们的 wrapper（由 inject 脚本产出）
2. `<module>_orig.lua`   —— 原版副本。wrapper 靠 `require("..._orig")` 拿原模块，
                            而 `bk.zip` 里没有它 ⇒ **必须一起下发**，否则 wrapper 加载即失败。

★ `<module>_orig.lua` 的内容取自**干净客户端**（就是你自己的原版文件）。
  它是服务端本地喂给本机客户端的，不进任何仓库。

## updateList 的字段名

`ResInfoPart { ResName, Md5, Size }` / `ResInfo { parts, Version, UpdateFlag }`
（来自 Steam 版反编译）。但 JSON 里具体用哪种大小写没定死，
所以这里**同时写多个别名**（`ResName`/`resName`/`name`、`Md5`/`md5`/`MD5` …）——
解析方按它想要的那个取，多余的键无害。这样一次就能试出正确格式。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

# ★ 这两个是**诊断探针**（inject_homeprobe / inject_shopclick），不是产品补丁，
#   不下发 —— 它们只在开发时用，且每次都写日志。
EXCLUDE = {
    "logic/home_ui/view_home_ui.lua",
    "logic/shop_ui/view_shopping_center_ui.lua",
}


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patched", required=True)
    ap.add_argument("--pristine", required=True)
    ap.add_argument("--serve", required=True)
    ap.add_argument("--routes", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    patched = os.path.abspath(a.patched)
    pristine = os.path.abspath(a.pristine)
    serve = os.path.abspath(a.serve)
    routes_path = os.path.abspath(a.routes)

    lua_p = os.path.join(patched, "Win", "lua")
    lua_q = os.path.join(pristine, "Win", "lua")
    if not os.path.isdir(lua_p):
        print("找不到 %s" % lua_p)
        return 2

    # 1) 收集「已打补丁」的目标（有 _orig.lua 兄弟的那些）
    targets = []
    for dp, dn, fn in os.walk(lua_p):
        for f in fn:
            if not f.endswith("_orig.lua"):
                continue
            mod = f[:-len("_orig.lua")] + ".lua"
            if not os.path.exists(os.path.join(dp, mod)):
                continue
            rel = os.path.relpath(os.path.join(dp, mod), lua_p).replace("\\", "/")
            if rel in EXCLUDE:
                continue
            targets.append(rel)
    targets.sort()
    print("发现 %d 个已打补丁的模块" % len(targets))

    # 2) 铺到 res 目录：wrapper + 干净端的 _orig
    parts = []
    miss_orig = []
    for rel in targets:
        src_wrapper = os.path.join(lua_p, rel.replace("/", os.sep))
        src_orig = os.path.join(lua_q, rel.replace("/", os.sep))
        dst_w = os.path.join(serve, "lua", rel.replace("/", os.sep))
        dst_o = os.path.join(serve, "lua", (rel[:-4] + "_orig.lua").replace("/", os.sep))
        if not os.path.exists(src_orig):
            miss_orig.append(rel)
            continue
        if not a.dry_run:
            for dst, src in ((dst_w, src_wrapper), (dst_o, src_orig)):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        for name, src in (("lua/" + rel, src_wrapper),
                          ("lua/" + rel[:-4] + "_orig.lua", src_orig)):
            size = os.path.getsize(src)
            parts.append({"resName": name, "ResName": name, "name": name,
                          "md5": md5_of(src), "Md5": md5_of(src), "MD5": md5_of(src),
                          "size": size, "Size": size, "SIZE": size})
    if miss_orig:
        print("★ 干净端缺这些原版文件（跳过）: %s" % miss_orig)
    print("下发 %d 个文件" % len(parts))

    # 3) 写进 routes.json
    raw = open(routes_path, "rb").read()
    routes = json.loads(raw.decode("utf-8"))
    entry = {
        "parts": parts, "Parts": parts,
        "Version": "kleinslocal-1", "version": "kleinslocal-1",
        "UpdateFlag": 1, "updateFlag": 1,
    }
    data = {"updateType": "res", "updateList": [entry],
            "resUrl": "http://127.0.0.1:10300/res/", "bin": ""}
    for key in ("baseapi/v1/update", "baseapi/v1/getResVer"):
        if key in routes:
            routes[key]["data"] = data

    if a.dry_run:
        print("(dry-run) 未写 routes.json")
        print(json.dumps(entry, ensure_ascii=False)[:400])
        return 0

    bak = routes_path + ".updatepatch.bak"
    if not os.path.exists(bak):
        shutil.copyfile(routes_path, bak)
        print("已备份 routes.json -> %s" % bak)
    open(routes_path, "w", encoding="utf-8").write(
        json.dumps(routes, ensure_ascii=False, indent=1))
    print("已写回 %s (%d 字节)" % (routes_path, os.path.getsize(routes_path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
