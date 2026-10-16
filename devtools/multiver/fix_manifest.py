#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""让 `DescriptionFile.json` 与磁盘上的 `Win\\lua` 保持一致。

    python fix_manifest.py <客户端根> [--dry-run] [--all]

## 为什么需要它

Steam 版启动时会做一次**资源完整性核对**：

    DescriptionFile.json  {"files": {"lua/Main.lua": "<md5>", ...}}
        ↓ 逐个比对
    Win\\lua\\Main.lua 的实际 md5
        ↓ 对不上
    从 bk.zip（本地更新包）里还原那个文件

⇒ 我们打进 `Win\\lua` 的 Lua 补丁，**在下一次启动前就会被还原掉**。
   （实测：清单覆盖 672 个 lua 文件，游戏运行时**恰好这 672 个**被重写。）

## 解法

既然核对是"拿清单比对磁盘"，那就**把清单改成和磁盘一致** —— 客户端就没得可还原了。
这是改数据、不是逆代码，既干净又完全可逆（备份原清单即可）。

★ `--all` 会把清单里**所有**条目都重算（含 22000+ 个 AB 文件，要几分钟）。
  默认只重算 `lua/` 那 672 条 —— 我们的补丁只碰 lua，几毫秒搞定。
"""
import hashlib
import json
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

MANIFEST_REL = r"环行旅舍_Data\StreamingAssets\DescriptionFile.json"


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 2
    root = os.path.abspath(args[0])
    dry = "--dry-run" in sys.argv
    do_all = "--all" in sys.argv

    mpath = os.path.join(root, MANIFEST_REL)
    if not os.path.exists(mpath):
        print("找不到清单: %s" % mpath)
        return 2

    raw = open(mpath, "rb").read()
    data = json.loads(raw.decode("utf-8"))
    files = data.get("files") or {}
    print("清单: %s (%d 字节, %d 条)" % (mpath, len(raw), len(files)))

    # 只处理 lua/（除非 --all）
    keys = list(files) if do_all else [k for k in files if k.startswith("lua/")]
    print("本次检查 %d 条%s" % (len(keys), "" if do_all else "（只查 lua/）"))

    changed, missing, same = [], [], 0
    for k in keys:
        rel = k.replace("/", os.sep)
        # 清单路径是相对 `Win\` 的（第一层就是 "AB/..." / "lua/..."）
        real = os.path.join(root, "Win", rel)
        if not os.path.exists(real):
            missing.append(k)
            continue
        want = md5_of(real)
        if want == files[k]:
            same += 1
        else:
            changed.append((k, files[k], want))
            files[k] = want

    print("  一致 %d / 需更新 %d / 磁盘上缺失 %d" % (same, len(changed), len(missing)))
    for k, old, new in changed[:40]:
        print("     %-58s %s -> %s" % (k, old[:10], new[:10]))
    if len(changed) > 40:
        print("     ... 还有 %d 条" % (len(changed) - 40))
    if missing:
        print("  ★ 磁盘上找不到（清单有、文件无）:")
        for k in missing[:20]:
            print("     %s" % k)

    if not changed:
        print("无需改动。")
        return 0
    if dry:
        print("(dry-run，未写入)")
        return 0

    bak = mpath + ".orig"
    if not os.path.exists(bak):
        shutil.copyfile(mpath, bak)
        print("已备份原清单 -> %s" % bak)

    out = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    open(mpath, "w", encoding="utf-8", newline="").write(out)
    print("已写回: %d 字节" % os.path.getsize(mpath))
    return 0


if __name__ == "__main__":
    sys.exit(main())
