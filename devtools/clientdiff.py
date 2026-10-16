#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户端目录全量比对 —— 建立「字节级权威基线」。

    python clientdiff.py <干净客户端> <已打补丁客户端> [-o 输出目录] [--jobs N]

产出（输出目录默认 ./out）:
    pristine.json     干净端的 (相对路径, 长度, sha256)
    patched.json      已打补丁端的 (相对路径, 长度, sha256)
    diff.json         权威差异表：新增 / 删除 / 长度异 / ★等长但内容不同
    diff.txt          人类可读报告

★★ 为什么必须逐文件算 sha256，不能只比长度 ——
   只比长度会漏掉「长度相同但内容被改」的文件。2026-10-16 实测：
   D:\\KleinsPatch 相对 D:\\hxls 有 **4 个 Lua 文件**属于这一类（隐形补丁），
   纯长度比对一个都没抓到。

用法示例（本项目的实际调用）:
    python clientdiff.py D:\\hxls D:\\KleinsPatch -o D:\\openKleinsPatcher\\base
"""
import concurrent.futures
import hashlib
import json
import os
import sys
import time

sys.stdout.reconfigure(errors="replace")

# 只排除**目录**，其余一律扫。运行期产物不做排除，由报告层标出来。
EXCLUDE_DIRS = {
    "_re",                 # 作者的工具与分析目录，不属于客户端本体
    "_pkg",                # 作者的打包目录（PyInstaller 产物 + spec），不属于客户端本体
    "docs",                # 作者文档
    "_backup_lua",         # 补丁系统的 Lua 树备份
    "_backup_LocalLow",    # 补丁系统的 LocalLow 备份
    "__pycache__",
    ".git",
    "_kleins_backup",      # 补丁器的备份目录
    "_kleinscfg",          # 配置表共享输出目录
}

# 这些是**运行时写出来**的状态，不是补丁。报告里单独归类，避免误判。
RUNTIME_NAMES = {"userprofile.bin", "Player.log", "Player-prev.log"}
RUNTIME_SUFFIX = (".log", ".flag")

CHUNK = 1 << 20  # 1 MB


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def scan(root, jobs=8):
    """返回 {相对路径(正斜杠): [长度, sha256]}。"""
    root = os.path.abspath(root)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 就地过滤，避免 os.walk 走进被排除的目录
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                files.append((rel, full, os.path.getsize(full)))
            except OSError as e:
                print("  !! 读不到 %s: %s" % (rel, e))

    out = {}
    done = [0]
    t0 = time.time()

    def work(item):
        rel, full, size = item
        try:
            digest = sha256_of(full)
        except OSError as e:
            digest = "ERR:%s" % e
        done[0] += 1
        if done[0] % 2000 == 0:
            print("    ... %d/%d  (%.0fs)" % (done[0], len(files), time.time() - t0))
        return rel, size, digest

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for rel, size, digest in ex.map(work, files):
            out[rel] = [size, digest]
    print("  扫完 %s: %d 个文件, %.1fs" % (root, len(out), time.time() - t0))
    return out


def classify(name):
    base = os.path.basename(name)
    if base in RUNTIME_NAMES or base.endswith(RUNTIME_SUFFIX) or base.startswith("player.json"):
        return "运行时产物"
    return "补丁"


def main():
    # 手工解析：-o/--jobs 各自吃掉后面一个值，剩下的才是位置参数
    positional, outdir, jobs, i = [], "out", 8, 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a in ("-o", "--out"):
            outdir = sys.argv[i + 1]; i += 2; continue
        if a == "--jobs":
            jobs = int(sys.argv[i + 1]); i += 2; continue
        if a.startswith("-"):
            print("未知参数: %s" % a); return 2
        positional.append(a); i += 1
    args = positional

    if len(args) != 2:
        print(__doc__)
        return 2

    a_root, b_root = args
    os.makedirs(outdir, exist_ok=True)

    print("=== 扫干净端 %s ===" % a_root)
    a = scan(a_root, jobs)
    print("=== 扫已打补丁端 %s ===" % b_root)
    b = scan(b_root, jobs)

    only_a = sorted(set(a) - set(b))          # 只在干净端 → 被删
    only_b = sorted(set(b) - set(a))          # 只在补丁端 → 新增
    grew, shrank, samelen, same = [], [], [], 0
    for rel in sorted(set(a) & set(b)):
        la, ha = a[rel]
        lb, hb = b[rel]
        if ha == hb:
            same += 1
            continue
        if la != lb:
            (grew if lb > la else shrank).append((rel, la, lb, ha, hb))
        else:
            samelen.append((rel, la, lb, ha, hb))

    diff = {
        "pristine_root": os.path.abspath(a_root),
        "patched_root": os.path.abspath(b_root),
        "counts": {
            "pristine": len(a), "patched": len(b),
            "same": same, "deleted": len(only_a), "added": len(only_b),
            "size_changed": len(grew) + len(shrank),
            "samelen_changed": len(samelen),
        },
        "deleted": only_a,
        "added": only_b,
        "size_changed": [
            {"path": r, "from": la, "to": lb, "sha_old": ha, "sha_new": hb}
            for r, la, lb, ha, hb in (grew + shrank)],
        "samelen_changed": [
            {"path": r, "size": la, "sha_old": ha, "sha_new": hb}
            for r, la, lb, ha, hb in samelen],
    }

    j = lambda o: json.dumps(o, ensure_ascii=False, indent=1, sort_keys=True)
    open(os.path.join(outdir, "pristine.json"), "w", encoding="utf-8").write(j(a))
    open(os.path.join(outdir, "patched.json"), "w", encoding="utf-8").write(j(b))
    open(os.path.join(outdir, "diff.json"), "w", encoding="utf-8").write(j(diff))

    lines = []
    lines.append("字节级权威差异表")
    lines.append("  干净端: %s" % diff["pristine_root"])
    lines.append("  补丁端: %s" % diff["patched_root"])
    lines.append("")
    lines.append("  相同文件      : %d" % same)
    lines.append("  删除(只在A)   : %d" % len(only_a))
    lines.append("  新增(只在B)   : %d" % len(only_b))
    lines.append("  长度变化      : %d" % (len(grew) + len(shrank)))
    lines.append("  ★等长但内容不同: %d" % len(samelen))
    lines.append("")

    lines.append("=== ★ 等长但内容不同（纯长度比对会全漏）===")
    if not samelen:
        lines.append("  （无）")
    for r, la, lb, ha, hb in samelen:
        lines.append("  %s  (%d 字节)  [%s]  %s -> %s"
                     % (r, la, classify(r), ha[:12], hb[:12]))
    lines.append("")

    lines.append("=== 新增文件 ===")
    for r in only_b:
        lines.append("  %s  [%s]  %d 字节" % (r, classify(r), b[r][0]))
    lines.append("")

    lines.append("=== 删除文件 ===")
    if not only_a:
        lines.append("  （无）")
    for r in only_a:
        lines.append("  %s  %d 字节" % (r, a[r][0]))
    lines.append("")

    lines.append("=== 长度变化 ===")
    for r, la, lb, ha, hb in sorted(grew + shrank):
        lines.append("  %-72s %8d -> %8d  [%s]" % (r, la, lb, classify(r)))

    report = "\n".join(lines)
    open(os.path.join(outdir, "diff.txt"), "w", encoding="utf-8").write(report)
    print()
    print(report)
    print()
    print("已写出: %s/{pristine,patched,diff}.json + diff.txt" % outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
