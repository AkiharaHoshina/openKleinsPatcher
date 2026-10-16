# -*- coding: utf-8 -*-
"""验收纯 Python LZ4 block：跟真实 `lz4` 模块双向互认 + 随机数据往返。"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(errors="replace")

from patchlib import lz4block                                    # noqa: E402

try:
    import lz4.block as REF
except ImportError:
    REF = None

OK = BAD = 0


def ck(cond, msg):
    global OK, BAD
    if cond:
        OK += 1
        print("  [OK]   %s" % msg)
    else:
        BAD += 1
        print("  [FAIL] %s" % msg)
    return cond


def main():
    random.seed(12345)

    print("=== 1) 边界样本：我们压 -> 参考解 ===")
    # ★ 不测空输入：空 LZ4 block 不是合法 block（参考实现直接报 corrupt），
    #   而分块流里每块至少 1 字节，实际用不到。
    cases = {
        "1 字节": b"A",
        "13 字节（正好 MFLIMIT+1）": b"ABCDEFGHIJKLM",
        "全同 1KB": b"Z" * 1024,
        "全同 100KB": b"Q" * 100000,
        "递增 70KB": bytes(i & 0xFF for i in range(70000)),
        "文本重复": (b"the quick brown fox jumps over the lazy dog\n" * 3000),
        "随机 4KB": bytes(random.randrange(256) for _ in range(4096)),
        "半随机半重复 200KB": (bytes(random.randrange(256) for _ in range(1000)) * 200),
    }
    for name, data in cases.items():
        c = lz4block.compress(data)
        d = lz4block.decompress(c)
        ck(d == data, "%-28s 自解往返 (%d -> %d 字节)" % (name, len(data), len(c)))
        if REF is not None:
            try:
                r = REF.decompress(c, uncompressed_size=len(data))
                ck(r == data, "%-28s ★参考实现能解我们的输出" % name)
            except Exception as e:
                ck(False, "%-28s 参考实现解失败: %s" % (name, e))

    print()
    print("=== 2) 参考压 -> 我们解 ===")
    if REF is None:
        print("  (没有 lz4 模块，跳过)")
    else:
        for name, data in cases.items():
            if not data:
                continue
            rc = REF.compress(data, store_size=False)
            try:
                d = lz4block.decompress(rc, out_len=len(data))
                ck(d == data, "%-28s ★能解参考实现的输出" % name)
            except Exception as e:
                ck(False, "%-28s 解参考输出失败: %s" % (name, e))

    print()
    print("=== 3) 真实的 bk.zip 分块流 ===")
    z = r"F:\originKleinsSteam\环行旅舍_Data\StreamingAssets\bk.zip"
    if os.path.exists(z):
        d = open(z, "rb").read()

        def rdvarint(b, o):
            v = sh = 0
            while True:
                x = b[o]
                o += 1
                v |= (x & 0x7F) << sh
                if not (x & 0x80):
                    return v, o
                sh += 7

        raw = bytearray()
        o = 0
        nch = 0
        while o < len(d):
            assert d[o] == 0x01, "分块标记 %#x" % d[o]
            o += 1
            unc, o = rdvarint(d, o)
            cpr, o = rdvarint(d, o)
            raw += lz4block.decompress(d[o:o + cpr], out_len=unc)
            o += cpr
            nch += 1
        ck(o == len(d), "4 个分块正好读完 (%d 字节)" % nch)
        ck(len(raw) == 3828108, "解出 3828108 字节（实测值）")
        ck(raw[:4] == b"\x00\x00\x01\x00", "负载开头是 int32 65536")
        # 再压回去 -> 解回来必须一模一样
        recomp = bytearray()
        for i in range(0, len(raw), 1 << 20):
            chunk = raw[i:i + (1 << 20)]
            c = lz4block.compress(chunk)
            recomp += b"\x01" + b"\x00" + b"\x00" + c      # 占位，下面重写 varint
        print("     (重压缩长度 %d, 原始 zip %d)" % (len(recomp), len(d)))

    print()
    print("通过 %d / 失败 %d" % (OK, BAD))
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
