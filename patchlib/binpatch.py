#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两个二进制补丁 —— 全部**靠特征码/锚点定位**，不写死偏移。

## ① GameAssembly.dll —— 资源完整性校验

`HotUpdate.CheckEnvironmentTask.<Execute>d__0.MoveNext` 里：
```
... 84 c0 75 2f 4c 8b 47 20 4d 85 c0
          ↑ 0x75 = JNE（校验失败则跳走）
```
改成 `EB`（JMP，无条件跳过）⇒ 校验永远走成功分支，不再报 `CheckEnv_Illegal_modification`。

★ 特征码里那个判别位**必须写成通配 `??`** —— 打完补丁后它是 `EB`，
只写 `75` 的话第二次运行就再也匹配不上（会误报"版本不符"）。
实测：老客户端文件偏移 `0x1192AD7`，Steam `0x11BE7F8`，两版都恰好唯一命中。

## ② 环行旅舍_Data\\resources.assets —— Unity SerializedFile 里的 gameconf

不动偏移，用**平台 URL 字符串当锚点**，向前读 int32 长度前缀校验，再顺藤摸瓜找后面的字段：
```
  0xFE944  int32 = 40                     ← PlatfromUrl 长度前缀
  0xFE948  "https://base-product.bingkolo.com:10300/"   → "http://127.0.0.1:10300/kleins/origin/v1/"
  ...      PlatType / SubPlatType
  ...      GameId / IsEncryption / **IsOpenHot** / VerSionType
```
改三处：
  * `PlatfromUrl` → 本机假服（**必须等长 40 字符**，槽位 44 字节）
  * `IsOpenHot` → 1（Steam 版出厂是 0 ⇒ 它根本不请求 `baseapi/v1/update`）
  * `PlatType` → `bingkolo`（否则 `sdk_mgr` 加载 `sdk_steam` → 唤起 Steam → Steam 又杀掉实例）
    ★ `"steam"`(5) 与 `"bingkolo"`(8) **槽位都是 8 字节**，文件大小不变
"""
import struct

URL_OLD = b"https://base-product.bingkolo.com:10300/"
URL_NEW = b"http://127.0.0.1:10300/kleins/origin/v1/"

# HotUpdate 完整性校验的特征码；`??` 是判别位（打完补丁是 EB，打之前是 75）
GA_SIG = "45 33 c0 48 8b d0 48 8b cb e8 ?? ?? ?? ?? 84 c0 ?? 2f 4c 8b 47 20 4d 85 c0"
GA_AT = 16
GA_JNE = 0x75
GA_JMP = 0xEB

PLAT_WANT = b"bingkolo"


def _sig_vals(sig):
    out = []
    for x in sig.split():
        out.append(None if x == "??" else int(x, 16))
    return out


def _find_sig(raw, vals):
    hits = []
    for i in range(len(raw) - len(vals) + 1):
        for j, v in enumerate(vals):
            if v is not None and raw[i + j] != v:
                break
        else:
            hits.append(i)
    return hits


# ── ① GameAssembly.dll ───────────────────────────────────
def gameassembly_state(path):
    """返回 (状态, 说明)。状态 ∈ {'clean','patched','unknown'}"""
    raw = open(path, "rb").read()
    hits = _find_sig(raw, _sig_vals(GA_SIG))
    if len(hits) != 1:
        return "unknown", "特征码命中 %d 处（要求恰好 1 处）—— 版本不符?" % len(hits)
    off = hits[0] + GA_AT
    b = raw[off]
    if b == GA_JMP:
        return "patched", "校验点 @0x%X = 0xEB（已打）" % off
    if b == GA_JNE:
        return "clean", "校验点 @0x%X = 0x75（未打）" % off
    return "unknown", "校验点 @0x%X = 0x%02X（既不是 75 也不是 EB）" % (off, b)


def patch_gameassembly(path):
    raw = bytearray(open(path, "rb").read())
    hits = _find_sig(raw, _sig_vals(GA_SIG))
    if len(hits) != 1:
        raise ValueError("GameAssembly: 特征码命中 %d 处（要求恰好 1 处）" % len(hits))
    off = hits[0] + GA_AT
    if raw[off] == GA_JMP:
        return None, "已经是 EB，跳过"
    if raw[off] != GA_JNE:
        raise ValueError("GameAssembly: 校验点是 0x%02X，期望 0x75" % raw[off])
    raw[off] = GA_JMP
    open(path, "wb").write(bytes(raw))
    return bytes([GA_JNE]), "校验点 @0x%X：0x75 -> 0xEB" % off


# ── ② resources.assets ───────────────────────────────────
def _find_url(d):
    """找平台 URL 锚点。★ 新旧两种写法都要认 —— 否则在「已经打过补丁」的客户端上
    就再也定位不到（旧串已经被换掉了），幂等检查会误报"版本不符"。"""
    empt = []
    for u in (URL_OLD, URL_NEW):
        hits = []
        s = 0
        while True:
            k = d.find(u, s)
            if k < 0:
                break
            hits.append(k)
            s = k + 1
        if len(hits) == 1:
            return u, hits[0]
        if len(hits) > 1:
            raise ValueError("%r 锚点命中 %d 处（要求恰好 1 处）" % (u[:32], len(hits)))
        empt.append(u[:32])
    raise ValueError("两种平台 URL 都没找到（试过 %s）" % empt)


def _find_fields(d):
    """用 URL 锚点定位 gameconf 各字段。返回 dict 偏移/长度。"""
    cur_url, url_off = _find_url(d)
    url_len = struct.unpack_from("<i", d, url_off - 4)[0]
    if url_len != len(cur_url):
        raise ValueError("URL 长度前缀 = %d，期望 %d" % (url_len, len(cur_url)))
    p = url_off + ((url_len + 3) // 4) * 4
    plat_len = struct.unpack_from("<i", d, p)[0]
    plat_off = p + 4
    q = plat_off + ((plat_len + 3) // 4) * 4
    sub_len = struct.unpack_from("<i", d, q)[0]
    sub_off = q + 4
    tail = sub_off + ((sub_len + 3) // 4) * 4
    return {"url": url_off, "url_len": url_off - 4,
            "plat": plat_off, "plat_len": plat_len, "plat_len_off": p,
            "sub": sub_off, "sub_len": sub_len,
            "tail": tail}


def assets_state(path):
    """返回 list of (是否需要改, 说明)。"""
    d = open(path, "rb").read()
    try:
        f = _find_fields(d)
    except ValueError as e:
        return None, str(e)
    out = []
    cur = bytes(d[f["url"]:f["url"] + len(URL_NEW)])
    out.append((cur != URL_NEW,
                "PlatfromUrl @0x%X = %s" % (f["url"], cur.decode("utf-8", "replace"))))
    out.append((bytes(d[f["plat"]:f["plat"] + f["plat_len"]]) != PLAT_WANT,
                "PlatType    @0x%X = %s" % (f["plat"], d[f["plat"]:f["plat"] + f["plat_len"]].decode())))
    gid, enc, hot, vt = struct.unpack_from("<iiii", d, f["tail"])
    out.append((hot != 1, "IsOpenHot   @0x%X = %d" % (f["tail"] + 8, hot)))
    return out, None


def patch_assets(path):
    d = bytearray(open(path, "rb").read())
    f = _find_fields(d)
    undone = []
    # URL（等长替换）
    cur = bytes(d[f["url"]:f["url"] + len(URL_OLD)])
    if cur != URL_NEW:
        if len(URL_OLD) != len(URL_NEW):
            raise ValueError("新旧 URL 不等长，不能原地替换")
        old = bytes(d[f["url"]:f["url"] + len(URL_OLD)])
        d[f["url"]:f["url"] + len(URL_NEW)] = URL_NEW
        undone.append(("url", old))
    # PlatType
    cur = bytes(d[f["plat"]:f["plat"] + f["plat_len"]])
    if cur != PLAT_WANT:
        slot = ((f["plat_len"] + 3) // 4) * 4
        newslot = ((len(PLAT_WANT) + 3) // 4) * 4
        if slot != newslot:
            raise ValueError("PlatType 槽位 %d != 目标 %d，会移动后面所有字段，拒绝" % (slot, newslot))
        undone.append(("plat", (f["plat_len_off"], cur)))
        d[f["plat_len_off"]:f["plat_len_off"] + 4] = struct.pack("<i", len(PLAT_WANT))
        d[f["plat"]:f["plat"] + slot] = PLAT_WANT + b"\x00" * (slot - len(PLAT_WANT))
    # IsOpenHot
    gid, enc, hot, vt = struct.unpack_from("<iiii", d, f["tail"])
    if hot != 1:
        undone.append(("hot", (f["tail"] + 8, hot)))
        struct.pack_into("<i", d, f["tail"] + 8, 1)
    if not undone:
        return [], "三处都已经是目标值，跳过"
    open(path, "wb").write(bytes(d))
    return undone, "改了 %s" % ", ".join(x[0] for x in undone)
