#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`kleinspatcher_tui.py` 的自检 —— 用**脚本化的输入**把整个流程真跑一遍。

    python devtools\\_selftest_tui.py

★ 为什么不手工点: 分支有「选目录 / 取消 / 手动输入 / 不是客户端 / 预检失败 /
  dry-run / 真打 / 还原」七八条, 手工点一遍半小时, 改完还得再点一遍。
  这里把 `input()` 换成脚本化回答, 对着一个**临时造出来的假客户端**真跑,
  最后断言"该不动的地方一个字节都没动"。

造的假客户端(**全部按真格式拼, 不是随便塞几个字节**):
  * `GameAssembly.dll` —— 按 `binpatch.GA_SIG` 真写进去, 判别位 = 0x75(未打)
  * `resources.assets` —— 按 gameconf 布局真拼(URL 锚点 + int32 长度前缀 + 各字段)
  * `bk.zip`           —— 用 `patchlib.bkzip.build()` 真打包
  * `Win\\lua\\...`     —— 同一批模块**也按原版内容**放在盘上（国服版客户端只读这里）
  * `Win\\File_res`     —— **故意不给**(Steam 版出厂就没有 ⇒ 补丁该把它建出来)

验:
  * 选目录屏: 退出 / 手动输入不存在的路径 / 取消选择框, 都不崩
  * 不是客户端 ⇒ 提示缺什么, 不崩
  * ★★ dry-run **一个字节都不改**(整目录哈希前后一致)
  * ★★ 真打: 三处二进制 + bk.zip 条目 + **Win\\lua 就地换 wrapper** 都到位, `_kleins_backup` 建出来
  * ★★ 还原: 回到**打过之前一模一样**的字节(含把新建的 `_orig` 删干净)
  * ★ 打完再预检 ⇒ 0 项需处理(幂等)
"""
import builtins
import hashlib
import io
import os
import shutil
import struct
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import kleinspatcher                                   # noqa: E402
import kleinspatcher_tui as TUI                        # noqa: E402
from patchlib import bkzip, binpatch, ui               # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print("  %s %s %s" % ("[OK] " if cond else "[!!] ", name, extra))


# ── 造一个假客户端 ────────────────────────────────────────────────────────
def _pack4(b):
    """按 4 字节对齐铺(patchlib 读字符串时就是按这个走的)。"""
    return b + b"\x00" * ((4 - len(b) % 4) % 4)


def _fake_ga(path):
    vals = [0xAA if x == "??" else int(x, 16) for x in binpatch.GA_SIG.split()]
    vals[binpatch.GA_AT] = binpatch.GA_JNE            # 未打
    body = bytes(vals)
    raw = b"\x00" * 64 + body + b"\x00" * 64
    open(path, "wb").write(raw)
    return len(raw)


def _fake_assets(path):
    url = binpatch.URL_OLD                            # 出厂 URL(未打)
    plat = b"steam"
    sub = b"steam-GL"
    svn = b"82743"
    d = bytearray(b"\x00" * 16)
    d += struct.pack("<i", len(url)) + _pack4(url)
    po = len(d) + 4
    d += struct.pack("<i", len(plat)) + _pack4(plat)
    so = len(d) + 4
    d += struct.pack("<i", len(sub)) + _pack4(sub)
    tail = len(d)
    d += struct.pack("<iiii", 1000, 1, 0, 2)          # gid, enc, IsOpenHot=0, verType
    d += struct.pack("<i", len(svn)) + _pack4(svn)
    d += b"\x00" * 32
    open(path, "wb").write(bytes(d))
    return {"plat_off": po, "sub_off": so, "tail": tail}


def make_client(tmp, n_wrappers=3):
    """造一份"像那么回事"的客户端。返回 (root, 记下来的关键偏移)。"""
    root = os.path.join(tmp, "client")
    os.makedirs(os.path.join(root, "环行旅舍_Data", "StreamingAssets"))
    os.makedirs(os.path.join(root, "Win", "lua"))
    _fake_ga(os.path.join(root, "GameAssembly.dll"))
    meta = _fake_assets(os.path.join(root, "环行旅舍_Data", "resources.assets"))
    open(os.path.join(root, "环行旅舍_Data", "StreamingAssets",
                      "DescriptionFile.json"), "w", encoding="utf-8").write("{}")

    # bk.zip: 放几个真 wrapper 对应的条目, 内容故意是"旧东西"
    targets = kleinspatcher.lua_targets()[:n_wrappers]
    names = ["/lua/" + rel for rel, _p in targets]
    blobs = [b"PRISTINE-" + rel.encode() for rel, _p in targets]
    names.append("/lua/some_other.lua")
    blobs.append(b"untouched")
    cap = 1024
    open(os.path.join(root, kleinspatcher.BKZIP), "wb").write(
        bkzip.build(names, blobs, cap))
    # ★★ 同一批模块**也放到 `Win\lua` 里**（原版内容）—— 国服版客户端走的是这条路，
    #   补丁器得就地换掉它们，而不是只改 bk.zip。见 kleinspatcher.step_lualive。
    for rel, _p in targets:
        p = os.path.join(root, kleinspatcher.LUAROOT, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b"PRISTINE-" + rel.encode())
    # 一个不该被碰的文件（防"glob 写太宽把整棵树都覆盖了"）
    open(os.path.join(root, kleinspatcher.LUAROOT, "keep_me.lua"), "wb").write(b"keep")
    meta["targets"] = [rel for rel, _p in targets]
    return root, meta


def snapshot(root):
    """整目录的 {相对路径: sha256}(跳过备份目录 —— 它不是客户端内容)。"""
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != kleinspatcher.BACKUP]
        for f in fn:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root)] = hashlib.sha256(
                open(p, "rb").read()).hexdigest()
    return out


# ── 驱动 TUI ─────────────────────────────────────────────────────────────
def drive(answers, pick=None, has_picker=True):
    """跑一次 `kleinspatcher_tui.main()`, `input()` 用脚本化回答。

    ★★ `ui.pick_folder` **永远**被换掉(换成"直接返回 `pick`")。
      换不得的后果实测过: 少换一次就弹出真的 Tk 文件夹对话框,
      **整个自检卡死在那儿**等人点(第一次跑就卡了 120 秒)。
      ▸ `pick=None` = 模拟"用户把选择框取消了"
      ▸ `pick=<路径>` = 模拟"用户选了这份客户端"
    """
    it = iter(list(answers))
    real_input = builtins.input
    real_pick = ui.pick_folder
    real_has = ui.has_folder_picker

    calls = [0]

    def fake_input(prompt=""):
        calls[0] += 1
        # ★★ 硬闸: 界面要是陷在死循环里, 它会**没完没了地要输入**。
        #   这里直接抛一个显眼的错, 让自检**当场失败**, 而不是像第一次那样
        #   挂在那儿刷 512KB 输出、看上去像"卡住"。(真踩过。)
        if calls[0] > 60:
            raise AssertionError(
                "★ 界面要了 %d 次输入 —— 几乎肯定在死循环(检查返回值/循环退出条件)"
                % calls[0])
        try:
            a = next(it)
        except StopIteration:
            raise EOFError("回答用完了")
        print("%s%s" % (prompt, a))
        return a

    builtins.input = fake_input
    ui.pick_folder = lambda initial=None, title=None: pick
    ui.has_folder_picker = lambda: has_picker
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = TUI.main()
    finally:
        builtins.input = real_input
        ui.pick_folder = real_pick
        ui.has_folder_picker = real_has
    return rc, buf.getvalue()


TMP = tempfile.mkdtemp(prefix="_kleins_tui_")

print("=== 1. 选目录屏: 直接退出 / 手动输入不存在的路径 / 取消选择框 ===")
rc, out = drive(["Q"], pick=None)
check("按 Q ⇒ 正常退出(0)", rc == 0, "rc=%s" % rc)

rc, out = drive(["2", "Z:\\绝对不存在的目录\\nope", "Q"])
check("手动输入不存在的路径 ⇒ 不崩, 回到选择屏再退",
      rc == 0 and "目录不存在" in out, "rc=%s" % rc)

rc, out = drive(["1", "Q"], pick=None)          # pick=None ⇒ 走 pick_folder, 返回 None
check("取消选择框(返回 None) ⇒ 停在选目录屏, 不崩",
      rc == 0 and "取消了选择框" in out, "rc=%s" % rc)

print()
print("=== 2. 不是客户端 ⇒ 提示缺什么 ===")
empty = os.path.join(TMP, "notaclient")
os.makedirs(empty, exist_ok=True)
rc, out = drive(["2", empty, "Q"])
check("★ 提示缺文件而不是崩", rc == 0 and "不是" in out and "GameAssembly.dll" in out,
      "rc=%s" % rc)
check("★ 而且不给「开始打补丁」这个选项", "开始打补丁" not in out)

print()
print("=== 3. ★★★ dry-run: 一个字节都不改 ===")
d3 = os.path.join(TMP, "dry")
os.makedirs(d3)
root3, meta3 = make_client(d3)
before3 = snapshot(root3)
rc, out = drive(["1", "D", "", "Q"], pick=root3)
after3 = snapshot(root3)
check("跑完了(rc=0)", rc == 0, "rc=%s" % rc)
check("★ 识别出渠道了", "steam-GL" in out and "Steam 版" in out)
check("★ 列出了预检(有「需处理」)", "预检" in out and "需处理" in out)
check("★★ dry-run 后**整目录哈希不变**（一个字节都没动）", before3 == after3,
      "变了: %s" % [k for k in set(before3) | set(after3)
                    if before3.get(k) != after3.get(k)])
check("★ 没有生成 _kleins_backup", not os.path.exists(
    os.path.join(root3, kleinspatcher.BACKUP)))

print()
print("=== 4. ★★★ 真打: 三处都到位 + 建了备份 ===")
d4 = os.path.join(TMP, "real")
os.makedirs(d4)
root4, meta4 = make_client(d4)
ga4 = os.path.join(root4, "GameAssembly.dll")
assets4 = os.path.join(root4, kleinspatcher.ASSETS)
before4 = snapshot(root4)
rc, out = drive(["1", "P", "y", "", "Q"], pick=root4)
check("跑完了(rc=0)", rc == 0, "rc=%s" % rc)
check("★ 提示了补丁完成", "补丁完成" in out)
check("★ 建了 _kleins_backup", os.path.exists(
    os.path.join(root4, kleinspatcher.BACKUP)))
ga_bytes = binpatch.gameassembly_state(ga4)
check("★ GameAssembly 判别位 0x75 -> 0xEB", ga_bytes[0] == "patched", str(ga_bytes))
st, err = binpatch.assets_state(assets4)
check("★ assets 三处都已是目标值", err is None and not any(n for n, _m in st),
      str(st) if err is None else err)
names4, blobs4, _c4 = bkzip.parse(open(os.path.join(root4, kleinspatcher.BKZIP), "rb").read())
idx4 = {n: i for i, n in enumerate(names4)}
ok_all = True
for rel in meta4["targets"]:
    key = "/lua/" + rel
    w = open(os.path.join(kleinspatcher.PATCH_LUA, rel), "rb").read()
    if idx4.get(key) is None or blobs4[idx4[key]] != w:
        ok_all = False
    ko = "/lua/" + rel[:-4] + "_orig.lua"
    if idx4.get(ko) is None:
        ok_all = False
check("★ bk.zip: wrapper 换进去了, `_orig` 也加上了", ok_all)
check("★ 不相关的条目没被动",
      blobs4[idx4["/lua/some_other.lua"]] == b"untouched")
check("★ 建出了 Win\\File_res\\DescriptionFile.json", os.path.exists(
    os.path.join(root4, kleinspatcher.FILE_RES, "DescriptionFile.json")))

# ★★★ 第五步: Win\lua 就地换 wrapper（国服版客户端只读这里, 不读 bk.zip）
ok_lua, ok_orig = True, True
for rel in meta4["targets"]:
    p = os.path.join(root4, kleinspatcher.LUAROOT, *rel.split("/"))
    o = p[:-4] + "_orig.lua"
    w = open(os.path.join(kleinspatcher.PATCH_LUA, rel), "rb").read()
    if open(p, "rb").read() != w:
        ok_lua = False
    # ★ `_orig` 必须是**原来那份原版的字节** —— 别把 wrapper 自己备成原版(那就永久丢原版了)
    if not os.path.exists(o) or open(o, "rb").read() != b"PRISTINE-" + rel.encode():
        ok_orig = False
check("★★ Win\\lua: 目标模块就地换成了 wrapper", ok_lua)
check("★★ Win\\lua: `_orig` 存的是**原版**字节（不是 wrapper）", ok_orig)
check("★ Win\\lua 里不相关的文件没被动",
      open(os.path.join(root4, kleinspatcher.LUAROOT, "keep_me.lua"),
           "rb").read() == b"keep")

print()
print("=== 5. ★ 打完再预检 ⇒ 0 项需处理(幂等) ===")
plan4 = kleinspatcher.build_plan(root4)
todo4 = [n for n, ch, _m in plan4 if ch]
check("★ 五项都变成「已就绪」", todo4 == [], str(todo4))

print()
print("=== 6. ★★★ 还原: 回到打过之前一模一样的字节 ===")
rc, out = drive(["1", "R", "y", "", "Q"], pick=root4)
check("跑完了(rc=0)", rc == 0, "rc=%s" % rc)
after6 = snapshot(root4)
check("★★ 整目录哈希 == 打补丁之前", before4 == after6,
      "差的: %s" % [k for k in set(before4) | set(after6)
                    if before4.get(k) != after6.get(k)])

print()
print("=== 7. ★ 没有文件夹选择框时, 敲**序号**也要能选中 ===")
# 模拟"这台机器没有 tkinter"。此时选项只剩 [2] 手动输入路径 / [Q] 退出 ——
# 序号 1 和键 '2' **不是一回事**, 正好用来验菜单真的认序号。
rc, out = drive(["1", root3, "Q"], has_picker=False)
check("★ 没选择框时不提供「选择客户端目录」", "选择客户端目录" not in out)
check("★ 敲序号 1 选中了「手动输入路径」", "手动输入路径" in out)
check("★ 而且真的走到识别那一步了", "预检" in out and "steam-GL" in out, "rc=%s" % rc)

print()
print("=== 8. ★ 和命令行共用同一套代码(不会各写一份) ===")
check("★ TUI 用的是 kleinspatcher.build_plan", TUI.kleinspatcher.build_plan
      is kleinspatcher.build_plan)
check("★ TUI 用的是 kleinspatcher.run_plan", TUI.kleinspatcher.run_plan
      is kleinspatcher.run_plan)
check("★ 补丁清单只有一份(STEPS)", TUI.kleinspatcher.STEPS is kleinspatcher.STEPS)

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 62)
print("通过 %d 项, 失败 %d 项" % (len(OK), len(BAD)))
for b in BAD:
    print("  [!!] " + b)
sys.exit(1 if BAD else 0)
