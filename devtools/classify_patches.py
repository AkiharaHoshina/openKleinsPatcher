#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「老客户端上的全部改动」按**跨版本可移植性**分类。

    python classify_patches.py <老版pristine> <已打补丁的老版> <Steam pristine> [-o 报告.md]

对每个被改过的文件，取四个哈希：
    P = 老版 pristine            M = 已打补丁的老版           S = Steam pristine
然后归类：

  ① SAME_S      M == S            → **根本不是补丁**，是把 Steam 版的文件拷了过来。
                                    对 Steam 目标：无需处理；对老版目标：属于"版本升级"，不可分发。
  ② ONE_HASH    P == S            → 两个客户端的原版**完全一样**。
                                    ⇒ 一条 `expect_original` 就能同时适配两版（最理想）。
  ③ TWO_HASH    P != S            → 两版原版不同。
                                    ⇒ 清单里这个文件需要**按版本分两条**（各自的原版哈希）。

另外标出：
  - 目标模块在 Steam 里**不存在**的（那些补丁对 Steam 无意义）
  - 该文件是否有 `_orig.lua` 兄弟（第二代 wrapper）/ 无（第一代直接改写）

输出一份 Markdown，直接可以贴进 docs/PATCHSET.md。
"""
import hashlib
import os
import sys

sys.stdout.reconfigure(errors="replace")

SKIP_DIRS = {"_re", "_pkg", "docs", "_backup_lua", "_backup_LocalLow",
             "__pycache__", ".git"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(root):
    """{相对路径(正斜杠): 绝对路径}"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            out[os.path.relpath(full, root).replace("\\", "/")] = full
    return out


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    p_root, m_root, s_root = sys.argv[1], sys.argv[2], sys.argv[3]
    out_md = None
    if "-o" in sys.argv:
        out_md = sys.argv[sys.argv.index("-o") + 1]

    P, M, S = walk(p_root), walk(m_root), walk(s_root)

    # wapper 集合 = 有 <name>_orig.lua 兄弟的那些
    wrappers = {r[:-len("_orig.lua")] + ".lua" for r in M
                if r.endswith("_orig.lua") and (r[:-len("_orig.lua")] + ".lua") in M}

    rows = []
    for rel in sorted(set(P) & set(M)):
        if sha(P[rel]) == sha(M[rel]):
            continue                                   # 没改
        p, m = sha(P[rel]), sha(M[rel])
        s = sha(S[rel]) if rel in S else None
        if s is None:
            kind = "GONE"
        elif m == s:
            kind = "SAME_S"
        elif p == s:
            kind = "ONE_HASH"
        else:
            kind = "TWO_HASH"
        rows.append({
            "rel": rel, "p": p, "m": m, "s": s, "kind": kind,
            "gen": "2" if rel in wrappers else "1",
            "size_p": os.path.getsize(P[rel]),
            "size_s": os.path.getsize(S[rel]) if rel in S else None,
        })

    order = {"SAME_S": 0, "GONE": 1, "TWO_HASH": 2, "ONE_HASH": 3}
    rows.sort(key=lambda r: (order[r["kind"]], r["rel"]))

    counts = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1

    print("被改过的文件共 %d 个" % len(rows))
    print("  ① SAME_S   (改成了 Steam 原版)      : %d" % counts.get("SAME_S", 0))
    print("  ② ONE_HASH (两版原版相同)            : %d" % counts.get("ONE_HASH", 0))
    print("  ③ TWO_HASH (两版原版不同)            : %d" % counts.get("TWO_HASH", 0))
    print("  ?  GONE     (Steam 里没这个文件)     : %d" % counts.get("GONE", 0))
    print()

    lines = ["# 老客户端改动 → 跨版本可移植性分类", "",
             "| 类别 | 数量 | 含义 |", "|---|---|---|",
             "| ① SAME_S | %d | 改成了 Steam 原版 —— **不是补丁** |" % counts.get("SAME_S", 0),
             "| ② ONE_HASH | %d | 两版原版相同 —— 一条哈希可同时适配 |" % counts.get("ONE_HASH", 0),
             "| ③ TWO_HASH | %d | 两版原版不同 —— 需按版本分条 |" % counts.get("TWO_HASH", 0),
             "| ? GONE | %d | Steam 里没这个文件 |" % counts.get("GONE", 0),
             "", "## ① SAME_S —— 其实是 Steam 的文件，别当补丁", "",
             "| 文件 | 代 | 老版原版 | 补丁后 == Steam |", "|---|---|---|---|"]
    for r in rows:
        if r["kind"] == "SAME_S":
            lines.append("| `%s` | %s | %d B | `%s` |"
                         % (r["rel"], r["gen"], r["size_p"], r["m"][:12]))

    for k, title in (("GONE", "? GONE —— Steam 里不存在（补丁对 Steam 无意义）"),
                     ("TWO_HASH", "③ TWO_HASH —— 两版原版不同，清单需按版本分条"),
                     ("ONE_HASH", "② ONE_HASH —— 两版原版相同（最理想）")):
        lines += ["", "## " + title, "",
                  "| 文件 | 代 | 老版原版 sha | Steam 原版 sha | 老版大小 | Steam 大小 |",
                  "|---|---|---|---|---|---|"]
        for r in rows:
            if r["kind"] == k:
                lines.append("| `%s` | %s | `%s` | `%s` | %s | %s |"
                             % (r["rel"], r["gen"], (r["p"] or "")[:12],
                                (r["s"] or "-")[:12] if r["s"] else "-",
                                r["size_p"], r["size_s"] if r["size_s"] else "-"))

    md = "\n".join(lines) + "\n"
    if out_md:
        open(out_md, "w", encoding="utf-8").write(md)
        print("报告已写出: %s" % out_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
