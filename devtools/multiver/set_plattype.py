#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验：把 `GameConfig.PlatType` 从 "steam" 改成别的值，看能不能绕开 Steam。

    python set_plattype.py <客户端根> [--value bingkolo] [--show]

## 背景

`sdk_mgr.lua`（proto#0）是这样选 SDK 模块的：

    platType = DataCenter.Instance.GameConfig.PlatType      -- 来自 resources.assets
    if platType == PlatType.BiliBili then sdkPlat = sdk_bili
    elseif platType == PlatType.BingKolo then
        sdkPlat = (osInfo == OsType.Ios) and sdk_ios or sdk_bing_kolo
    elseif platType == PlatType.Huya  then sdkPlat = sdk_huya
    elseif platType == PlatType.Steam then sdkPlat = sdk_steam      -- ← Steam 版走这条
    ...

Steam 版把 `PlatType` 设成 `"steam"`，于是加载 `sdk_steam` → 初始化 Steamworks →
`SteamAPI.RestartAppIfNecessary()` 会把进程重启到 Steam 里再退掉当前实例
（用户实测症状：唤起 Steam，Steam 又把实例杀掉）。

老客户端用的是 `"bingkolo"`，走 `sdk_bing_kolo` —— **纯 Lua，完全不碰 Steam**，
而且这套路径在我们这个假服务端下是跑通的（老客户端就是证明）。

## 槽位

Unity SerializedFile 的 string = int32 长度前缀 + 内容，**按 4 字节对齐**。

    "steam"    (5 字符) -> 槽 8 字节
    "bingkolo" (8 字符) -> 槽 8 字节     ★ 同槽！所以文件大小不变

`SubPlatType` 就没这么幸运了（steam 版 `"steam-GL"` 8 字节 / 老版 `"bingkolo-Win"` 12 字节，
槽位不同，不能直接换），本脚本先不动它。
"""
import os
import struct
import sys

sys.stdout.reconfigure(errors="replace")

ASSETS_REL = r"环行旅舍_Data\resources.assets"
URL_ANCHOR = b"https://base-product.bingkolo.com:10300/"
URL_ANCHOR_NEW = b"http://127.0.0.1:10300/kleins/origin/v1/"


def find_fields(d):
    """返回 (url_off, plat_off, plat_len_off, plat_len, sub_off, sub_len, tail_off)。

    `tail_off` = SubPlatType 之后那串 int32 字段的起始：
        +0 GameId  +4 IsEncryption  +8 **IsOpenHot**  +12 VerSionType
    后面紧跟 SvnVersion（int32 长度 + 内容）。
    ★ 不要去硬编码 0xFE994 —— 两版的 SubPlatType 长度不同（老版 12 / Steam 8），
      后面的字段整体会挪 4 字节。
    """
    anchor = URL_ANCHOR if d.count(URL_ANCHOR) == 1 else URL_ANCHOR_NEW
    hits = []
    s = 0
    while True:
        k = d.find(anchor, s)
        if k < 0:
            break
        hits.append(k)
        s = k + 1
    if len(hits) != 1:
        raise ValueError("URL 锚点命中 %d 处" % len(hits))
    url_off = hits[0]
    url_len = struct.unpack_from("<i", d, url_off - 4)[0]
    # 对齐到 4 字节后的下一个字段
    p = url_off + ((url_len + 3) // 4) * 4
    plat_len = struct.unpack_from("<i", d, p)[0]
    plat_off = p + 4
    q = plat_off + ((plat_len + 3) // 4) * 4
    sub_len = struct.unpack_from("<i", d, q)[0]
    sub_off = q + 4
    tail = sub_off + ((sub_len + 3) // 4) * 4
    return url_off, plat_off, p, plat_len, sub_off, sub_len, tail


def set_open_hot(d, on=True):
    """把 gameconf.IsOpenHot 置为 1/0。返回 (偏移, 旧值)。"""
    _u, _p, _pl, _pll, _s, _sl, tail = find_fields(d)
    off = tail + 8                      # GameId +4, IsEncryption +4, IsOpenHot +8
    old = struct.unpack_from("<i", d, off)[0]
    struct.pack_into("<i", d, off, 1 if on else 0)
    return off, old


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 2
    root = args[0]
    value = "bingkolo"
    if "--value" in sys.argv:
        value = sys.argv[sys.argv.index("--value") + 1]
    show_only = "--show" in sys.argv

    path = os.path.join(root, ASSETS_REL)
    d = bytearray(open(path, "rb").read())

    # ★ IsOpenHot：客户端自己的「热更新总开关」。
    #   Steam 版出厂是 **0**（关）⇒ 它根本不请求 baseapi/v1/update，
    #   于是「在解压之后把补丁下载回来」这条通道永远用不上。老版出厂是 1。
    fwd = root.replace("\\", "/")
    dirty = False
    if "--open-hot" in sys.argv or "--close-hot" in sys.argv:
        on = "--open-hot" in sys.argv
        off, old = set_open_hot(d, on)
        if old != (1 if on else 0):
            dirty = True
        print("IsOpenHot @0x%X: %d -> %d" % (off, old, 1 if on else 0))

    url_off, plat_off, plat_len_off, plat_len, sub_off, sub_len, _tail = find_fields(d)
    cur = bytes(d[plat_off:plat_off + plat_len])

    print("文件      : %s (%d 字节)" % (path, len(d)))
    print("PlatfromUrl @0x%X  len=%d" % (url_off, struct.unpack_from("<i", d, url_off - 4)[0]))
    print("PlatType    @0x%X  len=%d  值=%r" % (plat_off, plat_len, cur))
    print("SubPlatType @0x%X  len=%d  值=%r"
          % (sub_off, sub_len, bytes(d[sub_off:sub_off + sub_len])))

    new = value.encode()
    slot = ((plat_len + 3) // 4) * 4
    new_slot = ((len(new) + 3) // 4) * 4
    print()
    print("目标值 %r：%d 字符 -> 需要槽 %d 字节（当前槽 %d 字节）"
          % (value, len(new), new_slot, slot))
    if new_slot != slot:
        print("!! 槽位大小变了，会移动后面所有字段 —— 拒绝执行")
        return 1
    if cur == new:
        print("PlatType 已经是目标值，无需改动")
    else:
        d[plat_len_off:plat_len_off + 4] = struct.pack("<i", len(new))
        d[plat_off:plat_off + slot] = new + b"\x00" * (slot - len(new))
        dirty = True

    # ★ 只有真改过才写盘。原来这里 `cur == new` 就直接 return 0，
    #   会把 --open-hot 的改动一起吞掉（工具里踩过）。
    if show_only or not dirty:
        if not dirty:
            print("没有任何改动。")
        return 0

    open(path, "wb").write(bytes(d))
    chk = open(path, "rb").read()
    print("已写入。文件大小 %d -> %d (应相等)" % (len(d), len(chk)))
    _u, po, _plo, pll, _s, _sl, _t = find_fields(chk)
    print("复核 PlatType = %r" % bytes(chk[po:po + pll]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
