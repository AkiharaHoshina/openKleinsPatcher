#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看一份客户端的 gameconf：平台 URL / PlatType / SubPlatType / IsOpenHot ...

    python devtools\\_gameconf.py <客户端根> [<客户端根> ...]

★★ 为什么要这个工具: 「动态渠道识别」靠的是客户端**自报** PlatType/SubPlatType,
   而补丁器会把 PlatType 改成 `bingkolo`(否则会去唤起 Steam)。
   两件事叠在一起 ⇒ **打过补丁的 Steam 客户端会自报成国服**,
   服务端据此去读国服那份表 —— 道具 5133 / 头像 64,65 / 卡池 19 全是这个根。
   所以改渠道相关的东西之前, 先拿这个工具看一眼**客户端到底会说什么**。
"""
import os
import struct
import sys

sys.stdout.reconfigure(errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from patchlib import binpatch                                    # noqa: E402

ASSETS = os.path.join("环行旅舍_Data", "resources.assets")


def show(root):
    p = os.path.join(root, ASSETS)
    print("%s" % root)
    if not os.path.exists(p):
        print("    ★ 没有 %s" % ASSETS)
        return
    d = open(p, "rb").read()
    try:
        f = binpatch._find_fields(d)
    except ValueError as e:
        print("    ★ 定位不到 gameconf: %s" % e)
        return
    url = bytes(d[f["url"]:f["url"] + 45]).split(b"\x00")[0].decode("utf-8", "replace")
    plat = bytes(d[f["plat"]:f["plat"] + f["plat_len"]]).decode("utf-8", "replace")
    sub = bytes(d[f["sub"]:f["sub"] + f["sub_len"]]).decode("utf-8", "replace")
    gid, enc, hot, vt = struct.unpack_from("<iiii", d, f["tail"])
    print("    PlatfromUrl : %s" % url)
    print("    PlatType    : %-10s @0x%X" % (plat, f["plat"]))
    print("    SubPlatType : %-10s @0x%X   ← 渠道识别就靠这俩" % (sub, f["sub"]))
    print("    GameId=%d  IsEncryption=%d  IsOpenHot=%d  VerSionType=%d" % (gid, enc, hot, vt))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for r in sys.argv[1:]:
        show(r)
        print()
