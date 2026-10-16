#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体检：第二代 wrapper 留下的 *_orig.lua 备份，到底是不是「原版」？

    python check_orig_backups.py <干净客户端> <已打补丁客户端>

对每个 `<dir>/<name>_orig.lua`，拿它和干净客户端里对应的 `<dir>/<name>.lua` 比 sha256。

★★ 为什么必须查：
   `*_orig.lua` 是 wrapper 的**基底**（`pcall(require, "xxx_orig")` 包的就是它）。
   如果备份本身已经不是原版，那说明这个 wrapper 是**打在更早一代改写之上**的 ——
   补丁器若只搬 wrapper、拿原版当基底，就会丢掉那一代改动。

结论分三类：
   SAME  备份 == 原版   -> wrapper 直接可移植
   DIFF  备份 != 原版   -> ★ 基底已被更早一代改写，必须追查那代改了什么
   MISS  干净端没这个文件 -> 备份来自别处
"""
import hashlib
import os
import sys

sys.stdout.reconfigure(errors="replace")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    a_root, b_root = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])

    rows = []
    for dirpath, dirnames, filenames in os.walk(b_root):
        dirnames[:] = [d for d in dirnames
                       if d not in ("_re", "docs", "_backup_lua", "_backup_LocalLow",
                                    "_pkg", "__pycache__", ".git")]
        for fn in filenames:
            if not fn.endswith("_orig.lua"):
                continue
            bak = os.path.join(dirpath, fn)
            rel_bak = os.path.relpath(bak, b_root).replace("\\", "/")
            rel_src = rel_bak[:-len("_orig.lua")] + ".lua"
            pristine = os.path.join(a_root, rel_src.replace("/", os.sep))
            cur = os.path.join(b_root, rel_src.replace("/", os.sep))

            if not os.path.exists(pristine):
                rows.append(("MISS", rel_src, os.path.getsize(bak), 0, ""))
                continue
            ok = "SAME" if sha(bak) == sha(pristine) else "DIFF"
            rows.append((ok, rel_src, os.path.getsize(bak),
                         os.path.getsize(pristine),
                         "" if ok == "SAME"
                         else ("当前 wrapper: %d 字节" % os.path.getsize(cur)
                               if os.path.exists(cur) else "<无>")))
        # os.walk 的 dirnames 过滤要在循环里持续生效，这里重设一次
        dirnames[:] = [d for d in dirnames
                       if d not in ("_re", "docs", "_backup_lua", "_backup_LocalLow",
                                    "_pkg", "__pycache__", ".git")]

    same = [r for r in rows if r[0] == "SAME"]
    diff = [r for r in rows if r[0] == "DIFF"]
    miss = [r for r in rows if r[0] == "MISS"]

    print("共 %d 个 *_orig.lua 备份" % len(rows))
    print("  SAME (== 原版)      : %d" % len(same))
    print("  ★DIFF (!= 原版)     : %d" % len(diff))
    print("  MISS (原版找不到)   : %d" % len(miss))
    print()
    if diff:
        print("=== ★ 基底已被更早一代改写（备份长度 -> 原版长度）===")
        for _, rel, lb, la, extra in sorted(diff, key=lambda r: r[1]):
            print("  %-66s %7d -> %7d   %s" % (rel, la, lb, extra))
        print()
    if miss:
        print("=== 原版里找不到对应文件 ===")
        for _, rel, lb, _, _ in sorted(miss, key=lambda r: r[1]):
            print("  %-66s %7d" % (rel, lb))
        print()
    if same:
        print("=== SAME 的（可安全移植）===")
        for _, rel, lb, _, _ in sorted(same, key=lambda r: r[1]):
            print("  %s" % rel)

    return 1 if diff or miss else 0


if __name__ == "__main__":
    sys.exit(main())
