#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在文件里搜「特征码」——支持通配符，用来定位不同构建里漂移的补丁点。

    python find_sig.py <文件> --hex "45 33 c0 48 8b d0 ?? ?? ?? ?? 84 c0 75"
    python find_sig.py <文件> --text "base-product.bingkolo.com"
    python find_sig.py <文件> --hex "..." --ctx 24 --max 10

★★ 为什么需要它
   二进制补丁如果写死文件偏移，换个客户端构建就废了。正确做法是搜「周边特征字节」，
   把会漂移的部分（比如 rel32 调用位移）用 `??` 通配掉。

★ 用法约定
   `--hex` 里 `??` 或 `?` 表示"任意一个字节"。空格可省。
   找到多处会全部列出——若预期唯一却找到多个，说明特征码选得太弱，要加长。
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")


def parse_pattern(spec):
    """'45 33 ?? c0' -> (bytes, mask)；mask=True 表示该位参与比较。"""
    spec = spec.replace(" ", "").replace(",", "")
    if len(spec) % 2:
        raise ValueError("十六进制串长度必须是偶数: %r" % spec)
    vals, mask = [], []
    for i in range(0, len(spec), 2):
        pair = spec[i:i + 2]
        if pair in ("??", "?"):
            vals.append(0)
            mask.append(False)
        else:
            vals.append(int(pair, 16))
            mask.append(True)
    return bytes(vals), mask


_re_cache = {}


def _compiled(spec):
    """把 hex 特征码编成 bytes 正则（`.` = 通配，配 DOTALL）。带缓存。"""
    if spec in _re_cache:
        return _re_cache[spec]
    vals, mask = parse_pattern(spec)
    parts = []
    for v, m in zip(vals, mask):
        parts.append(re.escape(bytes([v])) if m else b".")
    rx = re.compile(b"".join(parts), re.DOTALL)
    _re_cache[spec] = rx
    return rx


def find_all(data, spec):
    """返回所有匹配偏移。走 C 实现的正则，47MB 的 DLL 也就秒级。"""
    return [m.start() for m in _compiled(spec).finditer(data)]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    mode = None
    spec = None
    ctx = 16
    maxhits = 20
    i = 2
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--hex":
            mode, spec = "hex", sys.argv[i + 1]; i += 2; continue
        if a == "--text":
            mode, spec = "text", sys.argv[i + 1]; i += 2; continue
        if a == "--ctx":
            ctx = int(sys.argv[i + 1]); i += 2; continue
        if a == "--max":
            maxhits = int(sys.argv[i + 1]); i += 2; continue
        print("未知参数: %s" % a)
        return 2

    if mode is None:
        print(__doc__)
        return 2

    data = open(path, "rb").read()
    print("文件: %s  (%d 字节)" % (os.path.abspath(path), len(data)))

    if mode == "text":
        needle = spec.encode("utf-8")
        hits = []
        s = 0
        while True:
            k = data.find(needle, s)
            if k < 0:
                break
            hits.append(k)
            s = k + 1
        print("文本 needles: %r  (%d 字节)" % (spec, len(needle)))
    else:
        hits = find_all(data, spec)
        vals, mask = parse_pattern(spec)
        needle = vals
        print("特征码: %s  (%d 字节, %d 个通配)"
              % (spec, len(vals), sum(1 for x in mask if not x)))

    print("命中 %d 处%s" % (len(hits), "" if len(hits) <= maxhits else "（只显示前 %d）" % maxhits))
    for off in hits[:maxhits]:
        lo, hi = max(0, off - ctx), min(len(data), off + len(needle) + ctx)
        print("  @ 0x%X (文件偏移 %d)" % (off, off))
        print("     前置: %s" % data[max(0, off - ctx):off].hex(" "))
        print("     本体: %s" % data[off:off + len(needle)].hex(" "))
        print("     后置: %s" % data[off + len(needle):hi].hex(" "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
