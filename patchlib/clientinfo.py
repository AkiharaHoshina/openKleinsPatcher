#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户端「识别 / 体检」—— 补丁器 TUI 的识别页, 也是 `kleinspatcher.py --list` 的数据源。

**只读, 一个字节都不改。**

为什么单独一个模块: 识别要用的东西散落在三处 ——
  * `resources.assets` 里的 gameconf(渠道/版本/热更开关)
  * `GameAssembly.dll` 里那一刀打没打(`patchlib.binpatch` 已经有状态机)
  * `bk.zip` 里的条目数(补丁进不去的时候要看它)
把它们收在一个函数里, TUI 和 CLI 就都只调 `identify()` 一件事。

★ 判断「补丁该不该打」的事**不在这里** —— 那是 `kleinspatcher.STEPS` 的活
  (预检 + 幂等 + 备份都跟着它走)。这里只说"这份客户端**是什么**"。
"""
import os
import struct

from . import binpatch, bkzip

ASSETS_REL = os.path.join("环行旅舍_Data", "resources.assets")
BKZIP_REL = os.path.join("环行旅舍_Data", "StreamingAssets", "bk.zip")
DESC_REL = os.path.join("环行旅舍_Data", "StreamingAssets", "DescriptionFile.json")
FILE_RES_REL = os.path.join("Win", "File_res")
BACKUP_DIR = "_kleins_backup"

GA = "GameAssembly.dll"

# 打补丁前必须存在的路径(缺了就不是一份完整的客户端)
REQUIRED = (GA, ASSETS_REL,
            os.path.join("环行旅舍_Data", "StreamingAssets"),
            os.path.join("Win", "lua"))

# 已知渠道 —— 只用来在界面上给个**人话标签**; 权威值永远是 assets 里的 SubPlatType。
# (svn: 国服 80891 / Steam 82743, 2026-10-17 实测)
KNOWN_SUB = {
    "bingkolo-Win": "国服版",
    "steam-GL": "Steam 版",
}


def looks_like_client(root):
    """返回缺失的必需路径列表; 空列表 = 看着像一份客户端。"""
    return [r for r in REQUIRED if not os.path.exists(os.path.join(root, r))]


def gameconf(root):
    """读 `resources.assets` 里的 gameconf。返回 (dict, 错误说明)。

    ★ 用**平台 URL 当锚点**定位, 不写死偏移 —— 两个版本的文件布局不一样。
      新旧两种 URL 都认(打过补丁的客户端里是新的那个)。
    """
    p = os.path.join(root, ASSETS_REL)
    if not os.path.exists(p):
        return None, "没有 %s" % ASSETS_REL
    try:
        d = open(p, "rb").read()
    except OSError as e:
        return None, "读不了 %s: %r" % (ASSETS_REL, e)
    anchor = None
    for u in (binpatch.URL_OLD, binpatch.URL_NEW):
        n = d.count(u)
        if n == 1:
            anchor = u
            break
        if n > 1:
            return None, "URL 锚点 %r 命中 %d 处(要求恰好 1 处)" % (u[:28], n)
    if anchor is None:
        return None, "两种平台 URL 都没找到 —— 看着不像这份客户端"
    o = d.find(anchor)
    url_len = struct.unpack_from("<i", d, o - 4)[0]
    if url_len != len(anchor):
        return None, "URL 长度前缀 %d != %d" % (url_len, len(anchor))
    p1 = o + ((url_len + 3) // 4) * 4
    pl = struct.unpack_from("<i", d, p1)[0]
    po = p1 + 4
    p2 = po + ((pl + 3) // 4) * 4
    sl = struct.unpack_from("<i", d, p2)[0]
    so = p2 + 4
    tail = so + ((sl + 3) // 4) * 4
    try:
        gid, enc, hot, vt = struct.unpack_from("<iiii", d, tail)
    except struct.error:
        return None, "gameconf 尾部越界(文件被截断了?)"
    sv_len = struct.unpack_from("<i", d, tail + 16)[0]
    sv = d[tail + 20:tail + 20 + sv_len] if 0 < sv_len < 64 else b"?"
    return {
        "size": len(d),
        "url": bytes(d[o:o + url_len]),
        "plat": bytes(d[po:po + pl]),
        "sub": bytes(d[so:so + sl]),
        "gameId": gid, "isEncryption": enc, "isOpenHot": hot, "verSionType": vt,
        "svnVersion": sv,
    }, None


def channel_label(sub):
    """渠道名 -> 人话标签。认不出来就原样返回。"""
    return KNOWN_SUB.get(sub, "")


def bkzip_stats(root):
    """bk.zip 的条目数。读不动就返回 (None, 原因)。"""
    p = os.path.join(root, BKZIP_REL)
    if not os.path.exists(p):
        return None, "没有 %s" % BKZIP_REL
    try:
        names, _blobs, cap = bkzip.parse(open(p, "rb").read())
    except Exception as e:
        return None, "解析 bk.zip 失败: %r" % (e,)
    return {"count": len(names), "cap": cap}, None


def lua_state(root):
    """`Win\\lua` 里有多少个 `xxx.lua` 和它的 `xxx_orig.lua` 一模一样。

    ★ 这个数是**判断"补丁有没有被整包解压冲掉"**用的: 冲掉之后每个 wrapper
      都会变得和它的 `_orig` 完全相同。(Steam 版每次启动都会解压覆盖 `Win\\lua`。)
    """
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
                try:
                    if open(plain, "rb").read() == open(os.path.join(dp, f), "rb").read():
                        n_same += 1
                except OSError:
                    pass
    return {"n_orig": n_orig, "n_same": n_same}, None


def identify(root):
    """把上面几样拼成一份「这份客户端是什么」。**只读**。

    返回的 dict 里每一项都带证据, TUI / CLI 直接照着打印就行。
    """
    root = os.path.abspath(root)
    out = {"root": root, "missing": looks_like_client(root)}

    gc, err = gameconf(root)
    out["gameconf"], out["gameconf_err"] = gc, err
    if gc:
        out["plat"] = gc["plat"].decode("utf-8", "replace")
        out["sub"] = gc["sub"].decode("utf-8", "replace")
        out["svn"] = gc["svnVersion"].decode("utf-8", "replace")
        out["label"] = channel_label(out["sub"])
        out["url_patched"] = (gc["url"] == binpatch.URL_NEW)
        out["hot_open"] = (gc["isOpenHot"] == 1)
        out["plat_ok"] = (gc["plat"] == binpatch.PLAT_WANT)

    try:
        st, msg = binpatch.gameassembly_state(os.path.join(root, GA))
    except OSError as e:
        st, msg = "unknown", repr(e)
    out["ga_state"], out["ga_msg"] = st, msg

    try:
        st2, err2 = binpatch.assets_state(os.path.join(root, ASSETS_REL))
    except OSError as e:
        st2, err2 = None, repr(e)
    out["assets_state"], out["assets_err"] = st2, err2

    out["bkzip"], out["bkzip_err"] = bkzip_stats(root)
    out["lua"], out["lua_err"] = lua_state(root)
    out["file_res"] = os.path.exists(os.path.join(root, FILE_RES_REL,
                                                  "DescriptionFile.json"))
    out["backup"] = os.path.isdir(os.path.join(root, BACKUP_DIR))
    return out


def describe(info):
    """TUI / CLI 用的多行描述。返回字符串列表(调用方自己决定缩进)。"""
    L = []
    if info["missing"]:
        L.append("★ 这看起来**不是**《环行旅舍》客户端, 缺:")
        for m in info["missing"]:
            L.append("    %s" % m)
        return L

    gc = info.get("gameconf")
    if gc is None:
        L.append("渠道      : !! %s" % info.get("gameconf_err"))
    else:
        tag = info.get("label") or "（未知渠道）"
        L.append("渠道      : %s / %s   [%s]" % (info["plat"], info["sub"], tag))
        L.append("版本      : svnVersion=%s  GameId=%d  VerSionType=%d"
                 % (info["svn"], gc["gameId"], gc["verSionType"]))
        L.append("平台 URL  : %s" % gc["url"].decode("utf-8", "replace"))
        L.append("热更开关  : IsOpenHot=%d %s / IsEncryption=%d"
                 % (gc["isOpenHot"], "（已开）" if info["hot_open"] else "（★未开）",
                    gc["isEncryption"]))

    ga = info["ga_state"]
    L.append("GameAssembly: %s"
             % ("已打（校验点=EB）" if ga == "patched" else
                ("未打（=75，会被判 CheckEnv_Illegal_modification）" if ga == "clean"
                 else "!! %s" % info["ga_msg"])))

    if info["assets_err"]:
        L.append("resources.assets: !! %s" % info["assets_err"])
    else:
        todo = [m for need, m in (info["assets_state"] or []) if need]
        L.append("resources.assets: %s"
                 % ("三处都已是目标值" if not todo else "需改 %d 处: %s"
                    % (len(todo), " ; ".join(todo))))

    L.append("Win\\File_res: %s" % ("已有 DescriptionFile.json" if info["file_res"]
                                    else "缺（Steam 版出厂没有，会无限重启）"))
    if info["bkzip_err"]:
        L.append("bk.zip    : !! %s" % info["bkzip_err"])
    else:
        L.append("bk.zip    : %d 条目 (容量 %d)" % (info["bkzip"]["count"],
                                                   info["bkzip"]["cap"]))
    if info["lua_err"]:
        L.append("Win\\lua  : -- %s" % info["lua_err"])
    else:
        lu = info["lua"]
        if lu["n_orig"] == 0:
            L.append("Win\\lua  : 没有 `_orig.lua` ⇒ 这份客户端没打过 Lua 补丁")
        else:
            L.append("Win\\lua  : %d 个模块带 `_orig.lua`，其中 %d 个和备份一模一样%s"
                     % (lu["n_orig"], lu["n_same"],
                        "  ★ 全一样 ⇒ 补丁已被整包解压冲掉" if lu["n_same"] == lu["n_orig"]
                        else ""))
    L.append("备份      : %s" % ("有 _kleins_backup（可以 --revert）" if info["backup"]
                                 else "没有 _kleins_backup（还没打过，或备份被删了）"))
    return L
