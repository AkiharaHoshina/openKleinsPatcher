#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给一份客户端做「体检」：二进制补丁打了没 / Lua 目录是不是被整包洗过。

    python check_client.py <客户端根> [<客户端根> ...]

输出三项：
  1. `环行旅舍_Data\\resources.assets` 里的 gameconf（PlatfromUrl / PlatType /
     SubPlatType / GameId / IsEncryption / **IsOpenHot** / VerSionType / SvnVersion）
  2. `GameAssembly.dll` 里 HotUpdate 完整性校验那一刀（0x75 JNE -> 0xEB JMP）
  3. `Win\\lua` 里有多少个文件跟「真原版」一致 —— 用来判断
     **Steam 版启动时整包解压是不是把补丁冲掉了**（冲掉后每个 `xxx.lua`
     都会和它的 `xxx_orig.lua` 一模一样）

★ 体检只读，不改任何文件。
"""
import hashlib
import os
import struct
import sys

sys.stdout.reconfigure(errors="replace")

ASSETS_REL = r"环行旅舍_Data\resources.assets"
URL_A = b"https://base-product.bingkolo.com:10300/"
URL_B = b"http://127.0.0.1:10300/kleins/origin/v1/"

# HotUpdate 完整性校验：`... 84 c0 75 2f 4c 8b 47 20 4d 85 c0`，`75` 在签名内 +16
# ★★ 判别位必须写成通配 `??` —— 打完补丁后它是 `EB`，**签名就再也匹配不上了**。
#    只写 `75` 版的话，在已打补丁的客户端上会报「命中 0 处 ⇒ 版本不符」，把人带沟里。
GA_SIG = "45 33 c0 48 8b d0 48 8b cb e8 ?? ?? ?? ?? 84 c0 ?? 2f 4c 8b 47 20 4d 85 c0"
GA_AT = 16


def gameconf(root):
    p = os.path.join(root, ASSETS_REL)
    if not os.path.exists(p):
        return None, "没有 %s" % ASSETS_REL
    d = open(p, "rb").read()
    anchor = URL_A if d.count(URL_A) else URL_B
    if d.count(anchor) != 1:
        return None, "URL 锚点命中 %d 处" % d.count(anchor)
    o = d.find(anchor)
    url_len = struct.unpack_from("<i", d, o - 4)[0]
    p1 = o + ((url_len + 3) // 4) * 4
    pl = struct.unpack_from("<i", d, p1)[0]
    po = p1 + 4
    p2 = po + ((pl + 3) // 4) * 4
    sl = struct.unpack_from("<i", d, p2)[0]
    so = p2 + 4
    tail = so + ((sl + 3) // 4) * 4
    gid, enc, hot, vt = struct.unpack_from("<iiii", d, tail)
    # SvnVersion: int32 长度 + 内容
    sv_len = struct.unpack_from("<i", d, tail + 16)[0]
    sv = d[tail + 20:tail + 20 + sv_len] if 0 < sv_len < 64 else b"?"
    return {
        "size": len(d),
        "url": bytes(d[o:o + url_len]),
        "plat": bytes(d[po:po + pl]),
        "sub": bytes(d[so:so + sl]),
        "gameId": gid, "isEncryption": enc, "isOpenHot": hot, "verSionType": vt,
        "svnVersion": sv,
        "tail_off": tail,
    }, None


def gameassembly(root):
    p = os.path.join(root, "GameAssembly.dll")
    if not os.path.exists(p):
        return None, "没有 GameAssembly.dll"
    raw = open(p, "rb").read()
    vals = [None if x == "??" else int(x, 16) for x in GA_SIG.split()]
    hits = []
    lim = len(raw) - len(vals)
    for i in range(lim):
        for j, v in enumerate(vals):
            if v is not None and raw[i + j] != v:
                break
        else:
            hits.append(i)
    if len(hits) != 1:
        return {"size": len(raw), "hits": len(hits)}, None
    off = hits[0] + GA_AT
    return {"size": len(raw), "hits": 1, "off": off, "byte": raw[off]}, None


def lua_state(root):
    lua = os.path.join(root, "Win", "lua")
    if not os.path.isdir(lua):
        return None, "没有 Win\\lua"
    n_orig = n_same = 0
    for dp, _dn, fn in os.walk(lua):
        for f in fn:
            if not f.endswith("_orig.lua"):
                continue
            n_orig += 1
            plain = os.path.join(dp, f[:-len("_orig.lua")] + ".lua")
            if os.path.exists(plain):
                a = open(plain, "rb").read()
                b = open(os.path.join(dp, f), "rb").read()
                if a == b:
                    n_same += 1
    return {"n_orig": n_orig, "n_same": n_same}, None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rc = 0
    for root in sys.argv[1:]:
        root = os.path.abspath(root)
        print("=" * 74)
        print("客户端: %s" % root)
        print("-" * 74)
        c, err = gameconf(root)
        if err:
            print("  assets : !! %s" % err)
            rc = 1
        else:
            print("  assets : %d 字节" % c["size"])
            print("    PlatfromUrl : %s" % c["url"].decode("utf-8", "replace"))
            print("    PlatType    : %-12r   SubPlatType: %r"
                  % (c["plat"].decode(), c["sub"].decode()))
            print("    GameId=%d  IsEncryption=%d  ★IsOpenHot=%d  VerSionType=%d  SvnVersion=%s"
                  % (c["gameId"], c["isEncryption"], c["isOpenHot"], c["verSionType"],
                     c["svnVersion"].decode("utf-8", "replace")))
            if c["url"] == URL_A:
                print("    → ★ 平台 URL 还是出厂的，**没打补丁**：客户端会去连真服")
                rc = 1
            if c["isOpenHot"] == 0:
                print("    → ★ IsOpenHot=0：客户端**根本不请求 baseapi/v1/update**，"
                      "热更新下载通道用不上")
            if c["plat"] != b"bingkolo":
                print("    → ★ PlatType=%r：会加载 sdk_steam → 唤起 Steam（需改成 bingkolo）"
                      % c["plat"].decode())
        print("-" * 74)
        g, err = gameassembly(root)
        if err:
            print("  GameAssembly : !! %s" % err)
            rc = 1
        elif g["hits"] != 1:
            print("  GameAssembly : !! 特征码命中 %d 处（要求恰好 1 处）—— 版本不符?" % g["hits"])
            rc = 1
        else:
            b = g["byte"]
            tag = ("★已打 (JMP)" if b == 0xEB else
                   ("未打 (JNE)" if b == 0x75 else "★未知字节 %#04x" % b))
            print("  GameAssembly : %d 字节, 校验点 @0x%X = 0x%02X  %s"
                  % (g["size"], g["off"], b, tag))
            if b != 0xEB:
                rc = 1
        print("-" * 74)
        l, err = lua_state(root)
        if err:
            print("  Win\\lua : !! %s" % err)
        elif l["n_orig"] == 0:
            print("  Win\\lua : 没有 `_orig.lua` ⇒ **这份客户端没打过 Lua 补丁**")
        else:
            print("  Win\\lua : %d 个带 `_orig.lua` 的模块，其中 %d 个 **xxx.lua == xxx_orig.lua**"
                  % (l["n_orig"], l["n_same"]))
            if l["n_same"] == l["n_orig"]:
                print("            → ★ 全部和备份一模一样 ⇒ Lua 补丁**已被整包解压冲掉**"
                      "（Steam 版每次启动都会这样）")
                rc = 1
    print("=" * 74)
    return rc


if __name__ == "__main__":
    sys.exit(main())
