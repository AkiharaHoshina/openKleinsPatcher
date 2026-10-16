#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《环行旅舍》客户端补丁器 —— 交互式外壳。

    python kleinspatcher_tui.py

流程(2026-10-17 用户指定): **先弹文件夹选择器**让用户选客户端目录, 然后按需补丁。

    选目录  ->  识别 + 预检  ->  打补丁 / dry-run / 还原  ->  结果

## 「按需」是谁判的

**不是这个界面判的**。四项补丁各自先看现状:
  * `File_res`        目标已经有了 → 跳过
  * `GameAssembly`    校验点已是 EB → 跳过
  * `resources.assets` 三处都已是目标值 → 跳过
  * `bk.zip`          该条目内容已经是 wrapper → 跳过; 目标包里**没有**这个条目 → 也跳过
    (国服专有模块在 Steam 版上就靠这条自动不打)
所以任何一份干净的停服客户端拿来都能用, **不需要按版本维护 N 套清单**。

## 和命令行的关系

`kleinspatcher.py <目录>` 那份还在, 而且和这里**共用同一套代码**
(`build_plan` / `run_plan` / `STEPS`) ⇒ 不会出现"界面上对、命令行不对"。

## 不可逆操作的保护

打补丁前会把要改的文件**先备份**到 `<客户端>\\_kleins_backup\\`(含 bk.zip),
`还原` 就是照它恢复。预检是**整体**的: 任何一项不满足就一个字节都不改。
"""
import os
import sys
import traceback

# ★★ 程序目录: **不是** `__file__` 的目录 —— PyInstaller 打过之后那是临时解包目录,
#   而 `patches\lua` 是跟着 exe 走的。和 kleinspatcher.base_dir() 同一套判断。
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kleinspatcher                                   # noqa: E402
from patchlib import clientinfo, ui                     # noqa: E402


def show_client(root):
    """识别 + 预检, 打印一屏。返回 `(info, plan, plan_err)`。

    plan 为 None 表示预检没过(plan_err 里有原因)。
    """
    info = clientinfo.identify(root)
    ui.hr()
    print("  客户端: %s" % root)
    ui.hr()
    for line in clientinfo.describe(info):
        print("  " + line)

    if info["missing"]:
        return info, None, None          # 连客户端都不是, 不用预检了

    print()
    print("  预检（只看不改）:")
    try:
        plan = kleinspatcher.build_plan(root)
    except Exception as e:
        print("    ★ 预检失败: %s" % e)
        return info, None, str(e)
    for name, changed, msg in plan:
        print("    [%s] %-16s %s" % ("需处理" if changed else "已就绪", name, msg))
    todo = [n for n, c, _ in plan if c]
    print()
    if todo:
        print("  ⇒ 有 %d 项需要处理: %s" % (len(todo), "、".join(todo)))
    else:
        print("  ⇒ 五项都已是目标状态, 无事可做。")
    return info, plan, None


def do_patch(root, plan, dry):
    """执行。dry=True 时不落盘。返回是否成功。"""
    todo = [n for n, c, _ in plan if c]
    ui.hr("-")
    if not todo:
        print("  五项都已经是目标状态, 没有要改的。")
        ui.hr("-")
        return True
    if dry:
        print("  dry-run: 下面这些会改, **不会真写盘**:")
    else:
        print("  开始打补丁。要改的文件先备份到 %s\\" % kleinspatcher.BACKUP)
    ui.hr("-")
    try:
        res = kleinspatcher.run_plan(
            root, plan, dry,
            emit=lambda name, msg: print("  [OK]   %-16s %s" % (name, msg)))
    except Exception as e:
        print("  ★★ 执行中失败: %s" % e)
        print("     备份在 %s\\ —— 可以用「还原」退回去。" % kleinspatcher.BACKUP)
        return False
    ui.hr("-")
    if dry:
        print("  dry-run 结束, 一个字节都没改。")
    else:
        print("  补丁完成。接下来:")
        print("    1. 启动服务端（openKleinsServer 的「启动服务端.bat」）")
        print("    2. 启动游戏")
        print("    3. 第一次启动会走一遍解压（把 Lua 补丁铺进 Win\\lua），正常现象")
    ui.hr("-")
    return True


def do_revert(root):
    """还原。走 kleinspatcher.do_revert（和命令行完全一样）。"""
    if not ui.confirm("确定要从 _kleins_backup 还原这份客户端吗?", default=False):
        print("    已取消。")
        return
    ui.hr("-")
    kleinspatcher.do_revert(root)
    ui.hr("-")


def pick_screen(state):
    """选目录那一屏。返回 True=选好了, False=用户要退出。"""
    ui.hr()
    print("  《环行旅舍》客户端补丁器")
    ui.hr()
    try:
        n = len(kleinspatcher.lua_targets())
        print("  补丁集: %d 个 Lua 包装层 + 2 个二进制 + File_res（Lua 同时打 bk.zip 与 Win\\lua）" % n)
    except Exception:
        pass
    if state.get("last"):
        print("  上次选的: %s" % state["last"])
    print("  还没选客户端。")

    opts = []
    if ui.has_folder_picker():
        opts.append(("1", "选择客户端目录", "打开系统的文件夹选择框"))
    opts.append(("2", "手动输入路径", "直接敲/粘贴一个目录"))
    opts.append(("Q", "退出", ""))
    c = ui.menu("请选择", opts, default="Q")
    if c is None or c == "Q":
        return False

    if c == "1":
        p = ui.pick_folder(initial=state.get("last"))
        if not p:
            print("    （取消了选择框；可以用 [2] 手动输入路径）")
            return True
    else:
        p = ui.ask("客户端根目录", default=state.get("last") or "")
        if not p:
            return True

    p = os.path.abspath(os.path.expanduser(p))
    if not os.path.isdir(p):
        print("    ★ 目录不存在: %s" % p)
        return True
    state["root"] = p
    state["last"] = p
    return True


def client_screen(state):
    """识别/操作那一屏。返回动作字符串。"""
    root = state["root"]
    info, plan, plan_err = show_client(root)
    print()

    if info["missing"]:
        opts = [("B", "换一个客户端", ""), ("Q", "退出", "")]
        c = ui.menu("请选择", opts, default="B")
        # ★★ 这里必须返回**动作名** "quit", 不能返回菜单键 'Q' ——
        #   main() 判的是 `act == "quit"`, 返回 'Q' 就永远不相等 ⇒ 退出键失效、
        #   一直刷同一屏(自检里就是这么发现的: 空目录 + 按 Q ⇒ 无限循环)。
        return "quit" if (c is None or c == "Q") else "reselect"

    opts = []
    if plan_err is None:
        if any(ch for _n, ch, _m in plan):
            opts.append(("P", "开始打补丁", "会先备份到 _kleins_backup"))
        opts.append(("D", "只看不写", "dry-run：列出会改什么, 一个字节都不动"))
    if info["backup"]:
        opts.append(("R", "还原", "从 _kleins_backup 恢复"))
    opts.append(("C", "重新识别", "改完文件后刷新这一屏"))
    opts.append(("B", "换一个客户端", ""))
    opts.append(("Q", "退出", ""))

    c = ui.menu("请选择", opts, default="Q")
    if c is None or c == "Q":
        return "quit"
    if c == "B":
        state["root"] = None
        return "reselect"
    if c == "C":
        return "again"
    if c == "D":
        do_patch(root, plan, dry=True)
        ui.ask("回车继续")
        return "again"
    if c == "R":
        do_revert(root)
        ui.ask("回车继续")
        return "again"
    if c == "P":
        todo = [n for n, ch, _ in plan if ch]
        if not ui.confirm("要改这 %d 项: %s。先备份、再动手, 继续吗?" % (
                len(todo), "、".join(todo)), default=True):
            print("    已取消。")
            return "again"
        do_patch(root, plan, dry=False)
        ui.ask("回车继续")
        return "again"
    return "again"


def main():
    ui.setup_console()
    print()
    print("  ★ 提醒：打补丁前请先**关掉游戏** —— 它占着 bk.zip。")
    state = {"root": None, "last": None}
    while True:
        if state["root"] is None:
            if not pick_screen(state):
                return 0
            continue
        act = client_screen(state)
        if act == "quit":
            return 0
    return 0


if __name__ == "__main__":
    # ★★ 带了参数就**直接走命令行那条路**(同一个 exe 兼顾脚本用法):
    #     kleinspatcher.exe                  -> 交互界面
    #     kleinspatcher.exe <目录> --list    -> 列状态(只读, 可以随便跑)
    #     kleinspatcher.exe <目录> --dry-run -> 只看会改什么
    #     kleinspatcher.exe <目录> --revert  -> 还原
    #   两条路共用 kleinspatcher.build_plan / run_plan, 不会有"界面上对、命令行不对"。
    if len(sys.argv) > 1:
        sys.exit(kleinspatcher.main())
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  已中断。")
        sys.exit(130)
    except Exception:
        print("\n  ★★ 出错了:")
        traceback.print_exc()
        try:
            input("  回车退出…")
        except Exception:
            pass
        sys.exit(1)
