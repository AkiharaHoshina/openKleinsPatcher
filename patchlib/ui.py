#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁器控制台界面用的小工具。**只用标准库。**

## 为什么不上 textual / rich

这个补丁器最后要用 PyInstaller 打成 exe 发出去。少一层第三方依赖, 就少一类
"在我机器上好看、在别人那儿炸"的问题 —— 这个项目已经吃过 `chcp` / GBK / 打包路径的亏。
所以: 编号菜单 + 原生文件夹选择框 + 纯文本输出, 一个依赖都不加。

## 目录选择器

`tkinter.filedialog.askdirectory()` —— 这是 **CPython for Windows 自带**的原生
文件夹选择框(和 exe 打包也不冲突, PyInstaller 会带上 tcl/tk)。调不起来
(精简版 Python / 没有 tk)就返回 None, 上层退回"手动输入路径"。
"""
import os
import sys

WIDTH = 74


def setup_console():
    """让中文进出都不会因为编码炸掉 —— 但**控制台和管道要分开对待**。

    ★ 真终端(tty): 只改 `errors`, **不动 encoding**。Windows 上 Python 直连
      控制台时走的是 UTF-16 控制台 API, 强制换成 utf-8 反而会乱码。
      (项目里其它脚本也是这么干的。)

    ★★★ 管道/重定向(**不是** tty): 必须**强制 utf-8**。
      打好的 exe 里 stdio 会退回系统 ANSI 代码页(cp936), 而且**不认
      `PYTHONIOENCODING`**(实测 2026-10-17, 见 devtools/\\_probe_tui_bytes.py)。
      于是

          "Q" | kleinspatcher.exe

      送进来的 UTF-8 字节 `EF BB BF 51` 被按 GBK 解成「锘縌」两个字,
      菜单**当场认不出这个键**, 而且一声不响 —— 查了半天才发现
      根本不是"看不见的字符"的问题, 是 stdio 编码。

      ★ 为什么管道才改成 utf-8: 真控制台里用户敲/粘的是**字符**, 控制台自己
        负责转换, 用的就是系统代码页, 那条路是对的, 别去动它。
    """
    for s in (sys.stdout, sys.stderr):
        try:
            if s.isatty():
                s.reconfigure(errors="replace")
            else:
                s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        if sys.stdin is not None and not sys.stdin.isatty():
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def hr(ch="=", width=WIDTH):
    print(ch * width)


def head(title):
    hr()
    print("  " + title)
    hr()


def item(label, value, note=""):
    """一行「标签 : 值」, 对齐用。"""
    print("  %-10s: %s%s" % (label, value, ("   " + note) if note else ""))


# ★ 用户粘进来的东西可能带这些"看不见的字符"(UTF-8 BOM、零宽空格、NUL)。
#   ★★★ 必须用 `chr()` 拼, **不要在源码里直接打那些字符** ——
#   第一版就是直接打的, 它们在编辑/替换过程中**没真的进到字符串里**,
#   `clean()` 形同虚设; 而当时的验证只看"进程退出码 0"(没匹配上、回车、EOF 退出**也是 0**)
#   ⇒ **假绿**。现在源码里全是 ASCII, 能 grep、能一眼看出对不对。
#   ★ 这是**第二道防线**: 头号原因(打包后 stdio 退回 cp936)在 `setup_console()` 里治。
_JUNK = "".join(chr(c) for c in (
    0xFEFF,                    # UTF-8 BOM
    0x200B, 0x200C, 0x200D,    # 零宽 空格 / 不连字 / 连字
    0x200E, 0x200F,            # LRM / RLM
    0x2060,                    # word joiner
    0x0000))                   # NUL


def clean(s):
    """去掉首尾空白和看不见的字符。"""
    return (s or "").strip(_JUNK).strip()


def ask(prompt, default=""):
    """读一行。EOF/Ctrl-C 都当成"返回 None"(调用方据此退出)。"""
    try:
        s = clean(input("    %s%s: " % (prompt, ("[%s]" % default) if default else "")))
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return s or default


def confirm(question, default=False):
    """是/否。直接回车 = default。EOF/Ctrl-C = 否。"""
    d = "Y/n" if default else "y/N"
    try:
        s = clean(input("    %s (%s): " % (question, d))).lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not s:
        return default
    return s in ("y", "yes", "是", "1")


def menu(prompt, options, default=None):
    """编号菜单。`options` = [(key, label, hint), ...]。

    既认**键**(如 `P`)也认**序号**(如 `1`)—— 有人习惯敲字母, 有人习惯敲数字。
    返回选中的 key; EOF/Ctrl-C 返回 None。
    """
    print()
    for i, (key, label, hint) in enumerate(options, 1):
        print("  [%s] %-16s %s" % (key, label, hint or ""))
    print()
    while True:
        try:
            s = clean(input("    %s: " % prompt))
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not s:
            if default:
                return default
            continue
        for key, _label, _hint in options:
            if s == key or s.upper() == key.upper():
                return key
        if s.isdigit():
            n = int(s)
            if 1 <= n <= len(options):
                return options[n - 1][0]
        print("    （没这个选项: %r，再试一次；直接回车退出）" % s)


def pick_folder(initial=None, title="选择《环行旅舍》客户端目录"):
    """弹**系统原生**文件夹选择框。返回绝对路径; 取消 / 没有 tkinter 返回 None。"""
    try:
        import tkinter
        from tkinter import filedialog
    except Exception:
        return None
    root = None
    try:
        root = tkinter.Tk()
        root.withdraw()                     # 别显示那个空白主窗口
        root.update()
        p = filedialog.askdirectory(
            title=title,
            initialdir=initial or os.path.expanduser("~"),
            mustexist=True)
        return os.path.abspath(p) if p else None
    except Exception:
        return None
    finally:
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass


def has_folder_picker():
    """有没有可用的目录选择框 —— 没有就让上层直接提示"手动输入路径"。"""
    try:
        import tkinter                       # noqa: F401
        from tkinter import filedialog       # noqa: F401
        return True
    except Exception:
        return False
