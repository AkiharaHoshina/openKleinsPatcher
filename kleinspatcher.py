#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《环行旅舍》客户端补丁器 —— 把任意一份干净的停服客户端改成能连本地假服务端。

    python kleinspatcher.py <客户端目录>              # 打补丁
    python kleinspatcher.py <客户端目录> --dry-run     # 只看会做什么，一个字节都不改
    python kleinspatcher.py <客户端目录> --revert      # 从 _kleins_backup 还原
    python kleinspatcher.py <客户端目录> --list        # 列出各项状态

## 打的五件事

| # | 目标 | 干什么 |
|---|---|---|
| 1 | `Win\\File_res\\DescriptionFile.json` | **Steam 版出厂没有这个目录**，不补上客户端会 `CheckVersion_LocalFile_NotExists` → `Hotfix.Reset()`（删目录）→ 重启 → 无限循环。从 `StreamingAssets\\DescriptionFile.json` 复制一份。 |
| 2 | `GameAssembly.dll` | 资源完整性校验 `0x75`(JNE) → `0xEB`(JMP) |
| 3 | `环行旅舍_Data\\resources.assets` | 平台 URL 指向本机；`IsOpenHot`→1；`PlatType` `steam`→`bingkolo` |
| 4 | `环行旅舍_Data\\StreamingAssets\\bk.zip` | **Steam 版的 Lua 补丁走这里**：把 wrapper 换进去、把原版另存为 `_orig` |
| 5 | `Win\\lua\\...` | **国服版的 Lua 补丁走这里**：同上，但是**就地写文件**。见下。 |

## ★★★ 为什么 Lua 要打**两**条路

Steam 版每次启动都执行 HotUpdate 的 Decompress，把 `bk.zip` 整包解开覆盖 `Win\\lua`
⇒ 直接改 `Win\\lua` 活不过一次启动，只能改源包。

但**国服版不解压** —— 它直接读 `Win\\lua`。只打 `bk.zip` 的话，国服客户端跑的还是原版 Lua。
（2026-10-17 实测踩到：拿国服客户端跑补丁器，`bk.zip` 里 31/31 wrapper 都在，可
 `Win\\lua` 一个都没变 ⇒ 白屏在 `logic_login_main.InitServerList` 的原版 bug 上。）
⇒ 两条路都打，谁生效看客户端；打重了没关系（幂等）。

## 为什么 Lua 补丁要打进 `bk.zip`

Steam 版每次启动都执行 HotUpdate 的 Decompress，把 `bk.zip` 整包解开覆盖 `Win\\lua` ——
直接改 `Win\\lua` 活不过一次启动。而服务端那条 `baseapi/v1/update` 下载通道**走不通**：
客户端下完是 `File.Move(临时文件, 目标)`，**从不删已存在的目标**，必然 `ERROR_ALREADY_EXISTS`。

⇒ 改源包是唯一正路：解压步骤一跑，补丁自然就位。

## 幂等 / 可逆

* 重复运行：`bk.zip` 里该条目的内容已经 == wrapper 就跳过，不重复动刀。
* `--revert`：从 `<客户端>\\_kleins_backup\\` 还原所有被改过的文件（含 bk.zip）。
* **先全量校验、再动手**：任何一步前置条件不满足就整体中止，一个字节都不改。
"""
import argparse
import json
import os
import shutil
import sys


def base_dir():
    """程序目录 = exe(或脚本)自己所在的目录。

    ★★★ PyInstaller 打过之后 `__file__` 指向的是**临时解包目录**
      (`sys._MEIPASS`), 而 `patches\\lua` 是**跟着 exe 走**的 ⇒ 必须用
      `sys.executable` 的目录。不判这一下的话, 打成 exe 之后会找不到补丁集
      (在临时目录里找 `patches\\lua`, 那里只有代码)。
      ★ 和 openKleinsServer/paths.py 的 base_dir() 是同一个道理。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = base_dir()
sys.path.insert(0, HERE)
from patchlib import binpatch, bkzip                                # noqa: E402

# ★★ 补丁集: **exe 旁边的优先**, 包里那份兜底。
#   为什么两边都要留:
#     · 打成 exe 分发时, `patches\lua` 被打进了包(`sys._MEIPASS`) ⇒ 单文件就能用;
#     · 但作者想单独换一套补丁集(不重新打包)时, 往 exe 旁边放个 `patches\lua` 就行 ⇒
#       这一级优先。
PATCH_LUA = os.path.join(HERE, "patches", "lua")
if not os.path.isdir(PATCH_LUA) and getattr(sys, "frozen", False):
    PATCH_LUA = os.path.join(getattr(sys, "_MEIPASS", HERE), "patches", "lua")

ASSETS = os.path.join("环行旅舍_Data", "resources.assets")
BKZIP = os.path.join("环行旅舍_Data", "StreamingAssets", "bk.zip")
DESCFILE = os.path.join("环行旅舍_Data", "StreamingAssets", "DescriptionFile.json")
FILE_RES = os.path.join("Win", "File_res")
LUAROOT = os.path.join("Win", "lua")
BACKUP = "_kleins_backup"

GA = "GameAssembly.dll"

OK = BAD = 0


def say(ok, msg):
    global OK, BAD
    if ok is None:
        print("      %s" % msg)
        return
    if ok:
        OK += 1
        print("  [OK]   %s" % msg)
    else:
        BAD += 1
        print("  [FAIL] %s" % msg)


# ── 补丁清单 ─────────────────────────────────────────────
def lua_targets():
    """patches\\lua 下每个 .lua 都对应 bk.zip 里的一个条目 /lua/<相对路径>。"""
    out = []
    if not os.path.isdir(PATCH_LUA):
        return out
    for dp, _dn, fn in os.walk(PATCH_LUA):
        for f in fn:
            if f.endswith(".lua"):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, PATCH_LUA).replace("\\", "/")
                out.append((rel, p))
    out.sort()
    return out


def check_layout(root):
    need = [GA, ASSETS, os.path.join("环行旅舍_Data", "StreamingAssets"),
            os.path.join("Win", "lua")]
    miss = [x for x in need if not os.path.exists(os.path.join(root, x))]
    return miss


def backup(root, rel):
    """把 root/rel 备份到 backup 目录（只在第一次改之前存）。"""
    src = os.path.join(root, rel)
    dst = os.path.join(root, BACKUP, rel)
    if os.path.exists(dst):
        return dst                      # 已经有原版备份，别再覆盖
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


# ── 各项 ─────────────────────────────────────────────────
def step_file_res(root, dry):
    """补 Win\\File_res\\DescriptionFile.json。返回 (改了没, 说明)。"""
    dst = os.path.join(root, FILE_RES, "DescriptionFile.json")
    src = os.path.join(root, DESCFILE)
    if os.path.exists(dst):
        return False, "已有 %s（跳过）" % os.path.join(FILE_RES, "DescriptionFile.json")
    if not os.path.exists(src):
        return False, "!! 找不到 %s —— 客户端不完整?" % DESCFILE
    if not dry:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    return True, "建 %s（从 StreamingAssets 复制，%d 字节）" % (
        os.path.join(FILE_RES, "DescriptionFile.json"), os.path.getsize(src))


def step_gameassembly(root, dry):
    p = os.path.join(root, GA)
    st, msg = binpatch.gameassembly_state(p)
    if st == "patched":
        return False, msg
    if st == "unknown":
        raise ValueError("GameAssembly.dll: %s" % msg)
    if not dry:
        binpatch.patch_gameassembly(p)
    return True, msg.replace("（未打）", " → 0xEB")


def step_assets(root, dry):
    p = os.path.join(root, ASSETS)
    state, err = binpatch.assets_state(p)
    if err:
        raise ValueError("resources.assets: %s" % err)
    todo = [m for need, m in state if need]
    if not todo:
        return False, "URL / PlatType / IsOpenHot 都已是目标值（跳过）"
    if not dry:
        binpatch.patch_assets(p)
    return True, "改 %d 处: %s" % (len(todo), " ; ".join(todo))


def step_bkzip(root, dry):
    p = os.path.join(root, BKZIP)
    data = open(p, "rb").read()
    names, blobs, cap = bkzip.parse(data)
    idx = {n: i for i, n in enumerate(names)}
    tg = lua_targets()
    rep, add, skip_already, skip_missing = [], [], [], []
    for rel, wpath in tg:
        key = "/lua/" + rel
        key_o = "/lua/" + rel[:-4] + "_orig.lua"
        if key not in idx:
            skip_missing.append(rel)
            continue
        w = open(wpath, "rb").read()
        cur = blobs[idx[key]]
        if cur == w:
            skip_already.append(rel)
            continue
        # ★ `_orig` 取自 **bk.zip 里的当前内容**（干净客户端里它就是原版），
        #   不依赖 Win\lua —— 在「已经打过补丁」的客户端上那已经是 wrapper 了。
        #   ★★ 但如果 `_orig` 条目**已经存在**，绝不能拿 `cur` 去盖它：
        #   那种情况下 `cur` 是**上一版的 wrapper**，盖下去就把原版永久弄丢了。
        #   （wrapper 升级时会走到这条：`cur != w` ⇒ 不算"已是最新"。）
        rep.append((key, cur, w))
        add.append((key_o, None if key_o in idx else cur))
    msg = "替换 %d / 新增 _orig %d" % (len(rep), len(add))
    if skip_already:
        msg += "，已是最新 %d" % len(skip_already)
    if skip_missing:
        msg += "，本版本没有 %d" % len(skip_missing)
    if not rep and not add:
        return False, msg + " —— 无事可做"
    if not dry:
        for key, _old, w in rep:
            blobs[idx[key]] = w
        for key_o, o in add:
            if o is None:
                continue                      # _orig 已存在，保持原样
            names.append(key_o)
            blobs.append(o)
            idx[key_o] = len(names) - 1
        out = bkzip.build(names, blobs, cap)
        open(p, "wb").write(out)
        # 回读校验
        n2, b2, _c2 = bkzip.parse(open(p, "rb").read())
        if n2 != names or any(b2[i] != blobs[i] for i in range(len(n2))):
            raise RuntimeError("bk.zip 回读校验失败")
    return True, msg + "（共 %d 条目）" % len(names)


def step_lualive(root, dry):
    """把 wrapper **就地**写进 `Win\\lua\\`（国服版走这条；Steam 版走 bk.zip）。

    ★★★ 两条路的由来见模块开头那段。幂等规则和 bk.zip 那份**完全一样**：
      * 已经是 wrapper ⇒ 跳过；
      * 目标文件不存在（这个客户端没这个模块）⇒ 跳过；
      * `_orig` 已存在 ⇒ **绝不覆盖**（那可能是上一版 wrapper 留下的原版备份）。
    """
    root_lua = os.path.join(root, LUAROOT)
    rep, add, skip_already, skip_missing = [], [], [], []
    for rel, wpath in lua_targets():
        dst = os.path.join(root_lua, *rel.split("/"))
        if not os.path.exists(dst):
            skip_missing.append(rel)
            continue
        w = open(wpath, "rb").read()
        cur = open(dst, "rb").read()
        if cur == w:
            skip_already.append(rel)
            continue
        rep.append((dst, w))
        orig = dst[:-4] + "_orig.lua"
        if not os.path.exists(orig):
            add.append((orig, cur))
    msg = "就地替换 %d / 新写 _orig %d" % (len(rep), len(add))
    if skip_already:
        msg += "，已是最新 %d" % len(skip_already)
    if skip_missing:
        msg += "，本版本没有 %d" % len(skip_missing)
    if not rep and not add:
        return False, msg + " —— 无事可做"
    if not dry:
        for dst, w in rep:
            # ★ 每个要被覆盖的文件都单独备份（run_plan 只能备份 `BACKUP_OF` 里那一个路径）
            backup(root, os.path.relpath(dst, root))
            open(dst, "wb").write(w)
        for orig, cur in add:
            open(orig, "wb").write(cur)
            with open(os.path.join(root, BACKUP, "_created.txt"), "a",
                      encoding="utf-8") as f:
                f.write(os.path.relpath(orig, root) + "\n")
    return True, msg


# ── 主流程 ───────────────────────────────────────────────
STEPS = [("File_res", step_file_res), ("GameAssembly", step_gameassembly),
         ("resources.assets", step_assets), ("bk.zip", step_bkzip),
         ("Win\\lua", step_lualive)]

# 各项对应要备份的相对路径（File_res 是新建的，没有原版可备）
BACKUP_OF = {"GameAssembly": GA, "resources.assets": ASSETS, "bk.zip": BKZIP}
# 「我们新建出来的东西」——`--revert` 时要删掉。（`Win\lua` 那步自己登记，见 step_lualive）
CREATED_OF = {"File_res": [FILE_RES]}

_STEP_FN = dict(STEPS)


def build_plan(root):
    """预检: 每一项都"只看不改"跑一遍。**不改任何文件**。

    返回 `[(name, changed, msg)]`。
    ★ 任一项抛异常就原样往上抛 —— 由调用方决定整体中止（一个字节都不改）。
    ★ CLI 和 TUI 都走这一个函数, 保证"命令行看到的"和"界面上看到的"永远一致。
    """
    out = []
    for name, fn in STEPS:
        changed, msg = fn(root, True)
        out.append((name, changed, msg))
    return out


def run_plan(root, plan, dry=False, emit=None):
    """按预检结果执行（会备份）。返回 `[(name, msg)]`。

    `emit(name, msg)` 每项回调一次; 不给就打到 stdout。

    ★ 预检时拿到的 msg 只是"会改什么"; 真改完要**再调一次**才知道具体结果
      （比如 resources.assets 那项, 真改完才报得出改了哪几处）。
    """
    emit = emit or (lambda name, msg: say(True, "%-18s %s" % (name, msg)))
    if not dry:
        os.makedirs(os.path.join(root, BACKUP), exist_ok=True)
    res = []
    for name, changed, _msg in plan:
        if changed and not dry:
            rel = BACKUP_OF.get(name)
            if rel:
                backup(root, rel)
            else:
                # 新建出来的东西（File_res），记一笔，--revert 时删掉
                for cr in CREATED_OF.get(name, ()):
                    with open(os.path.join(root, BACKUP, "_created.txt"), "a",
                              encoding="utf-8") as f:
                        f.write(cr + "\n")
            _, msg = _STEP_FN[name](root, False)
        else:
            msg = _msg
        res.append((name, msg))
        emit(name, msg)
    return res


def do_revert(root):
    bdir = os.path.join(root, BACKUP)
    if not os.path.isdir(bdir):
        print("没有 %s —— 没打过补丁，或备份被删了" % BACKUP)
        return 1
    n = 0
    for dp, _dn, fn in os.walk(bdir):
        for f in fn:
            if f == "_created.txt":
                continue
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, bdir)
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            print("  还原 %s" % rel)
            n += 1
    # 删掉当初是我们新建的文件
    cm = os.path.join(bdir, "_created.txt")
    if os.path.exists(cm):
        for line in open(cm, encoding="utf-8"):
            rel = line.strip()
            if not rel:
                continue
            tgt = os.path.join(root, rel)
            if os.path.exists(tgt):
                # ★ 可能是目录（File_res），也可能是文件（Win\lua 那步写下的 `_orig`）
                if os.path.isdir(tgt):
                    shutil.rmtree(tgt, ignore_errors=True)
                else:
                    try:
                        os.remove(tgt)
                    except OSError:
                        pass
                print("  删除（原本是我们新建的）%s" % rel)
    print("还原了 %d 个文件。" % n)
    print("★ 注意：`Win\\lua` 里的补丁要等客户端**再启动一次**（解压步骤会按还原后的 bk.zip 覆盖）才复原。")
    return 0


def main():
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("client", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    a = ap.parse_args()
    if a.help or not a.client:
        print(__doc__)
        return 2

    root = os.path.abspath(a.client)
    if not os.path.isdir(root):
        print("目录不存在: %s" % root)
        return 2

    print("=" * 72)
    print("客户端: %s" % root)
    print("=" * 72)

    miss = check_layout(root)
    if miss:
        print("★ 这看起来不是《环行旅舍》客户端，缺:")
        for m in miss:
            print("    %s" % m)
        return 1

    if a.revert:
        return do_revert(root)

    tg = lua_targets()
    print("补丁集: %d 个 Lua 包装层 + 2 个二进制 + File_res（Lua 同时打 bk.zip 与 Win\\lua）" % len(tg))

    if a.list:
        for name, fn in STEPS:
            try:
                # list 模式下别真写盘
                changed, msg = fn(root, True)
                say(None, "%-18s %s %s" % (name, "[需处理]" if changed else "[已就绪]", msg))
            except Exception as e:
                say(False, "%-18s %s" % (name, e))
        return 0

    # ★★ 先全量预检：任何一步炸就整体中止，一个字节都不改
    try:
        plan = build_plan(root)
    except Exception as e:
        print("★ 预检失败：%s" % e)
        print("  一个字节都没改。")
        return 1
    print("预检通过，开始%s。" % ("（dry-run，不会落盘）" if a.dry_run else ""))
    print()

    run_plan(root, plan, a.dry_run)

    print()
    print("=" * 72)
    if a.dry_run:
        print("dry-run 结束，没有改动任何文件。")
    else:
        print("补丁完成。接下来：")
        print("  1. 启动服务端（openKleinsServer 的 `启动服务端.bat`）")
        print("  2. 启动游戏")
        print("  3. 第一次启动会走一遍解压（把 Lua 补丁铺进 Win\\lua），正常现象")
    print("=" * 72)
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
