#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**临时**测试驱动：把现有 inject_*.py 重定向到另一份客户端，产出一个候选补丁版本。

    python build_test_build.py <目标客户端根> --workdir <临时工作目录>
                               [--only a.py,b.py] [--skip-binary] [--dry-run]

存在的意义
----------
正式补丁器（openKleinsPatcher/patchlib）走"预编译字节码 blob"路线，还没写完。
但「Steam 版到底需要哪些补丁」这个问题必须**先实跑**才有定论，不能等。
现有 inject 脚本是按**模块名**包装的，天然与版本无关 —— 只要把里面的两族路径
重定向过去，就能直接产出一个可跑的候选版本，用来做实验。

★★ 重定向要改的只有两族路径
  ① 客户端目标：`D:\\KleinsPatch\\Win\\lua`  →  `<目标>\\Win\\lua`
     （还有 inject2.py 里的 `D:\\hxls\\Win\\lua`，那是它的 PRISTINE 来源）
  ② **备份落点**：`D:\\KleinsPatch\\_re\\_lua_` →  `<workdir>\\_lua_`
     ★ 这个必须改！脚本的逻辑是「备份已存在就不重做」，而 `_re` 里躺着的是
       **老客户端**的 pristine 备份。不改的话它会把老版文件当成目标客户端的
       原版备份写进 `_orig.lua` —— 27/28 个目标两版恰好相同所以看不出来，
       但 `view_game_main_ui` 就会错。

  其余 `_re` 路径（`client_*.log` / `disabled_ui.txt` / `cfg/` / 各种 flag）**故意不改** ——
  它们是运行期状态，指向开发目录反而方便观察。

产物
----
  <目标> 被就地修改（所以务必先备份！调用方负责准备干净副本）。
  <workdir>\\build_report.txt  记录本次跑了哪些脚本、各自结果。
"""
import io
import os
import struct
import sys
import traceback

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INJECT_DIR = r"D:\KleinsPatch\_re"          # 现有 inject 脚本所在

# 产品级补丁集（按依赖顺序，cfg-dump 先上）
DEFAULT_SCRIPTS = [
    "inject_cfgdump.py",     # config_data_center  ← 必需：补丁器靠它产配置表
    "inject2.py",            # logic_login_main    ← 修登录崩溃（不属于 inject_*.py 命名）
    "inject_btns.py",        # view_game_main_ui
    "inject_login.py",       # view_login_ui
    "inject_logout.py",      # net_error_handler
    "inject_noticeback.py",  # view_normal_notice_ui
    "inject_taskunlock.py",  # logic_task_main
    "inject_newrole.py",     # logic_role_data
    "inject_skin.py",        # logic_role / logic_role_skin / view_role_skin_base
    "inject_uiblock.py",     # uimgr
    "inject_settingblock.py",# view_setting_ui
    # ★★ 2026-10-17: view_home_ui —— 拦「**先切场景再开界面**」的入口(贸区)。
    #   uiblock 拦的是 uimgr.ShowView, 但 ClickMaoYiBtn 在那之前就 Play("anim_home_out")
    #   把主页收走了 ⇒ ShowView 那层拦住也只剩空白屏。必须在按钮回调这一层拦。
    #   ★ 它和 inject_homeprobe.py 打的是**同一个文件**, 别同时上。
    "inject_homeblock.py",
    # ★★ 2026-10-17: view_common_get_items_ui —— 「获得物品」弹窗护栏。
    #   SetItem 里 `cfg.quality` 对"查不到配置的道具"**没有 nil 检查** ⇒ 弹窗整窗崩
    #   (用户报的「选中确定无法领取」)。服务端 build_gamedata 会下发整个背包,
    #   所以背包里只要有一件客户端没有的道具就必崩。
    "inject_itemsfix.py",
    "inject_mailclear.py",   # logic_mail
    "inject_scene.py",       # logic_change_scene
    "inject_queue.py",       # view_role_queue_base / view_role_select_base
    "inject_recruit.py",     # view_recruit_pay_ui
    "inject_share.py",       # view_recruit_share_ui
    "inject_shop.py",        # logic_shop / view_pop_buy_item_ui / view_pop_buy_month_card_ui
    "inject_gift.py",        # sub_shop ×3
    "inject_storefix.py",    # logic_store ← 护栏: 摘掉客户端查不到配置的道具 id
    "inject_pcfix.py",       # logic_personal_center ← 护栏: 摘掉查不到配置的头像/头像框
    "inject_curprobe.py",    # lua_data_center ← 探针: 记录顶栏三种货币的读写
    "inject_atlasfix.py",    # logic_role_atlas ← 护栏: 吞掉 CheckRoleByMap 的 nil 异常
]

# 二进制补丁
GA_SIG = ("45 33 c0 48 8b d0 48 8b cb e8 ?? ?? ?? ?? 84 c0 75 2f 4c 8b 47 20 4d 85 c0", 16)
URL_OLD = b"https://base-product.bingkolo.com:10300/"
URL_NEW = b"http://127.0.0.1:10300/kleins/origin/v1/"
ASSETS_REL = r"环行旅舍_Data\resources.assets"


def rewrite(src, target_root, workdir):
    """把脚本里的两族路径重定向。"""
    out = src
    tgt_fwd = target_root.replace("\\", "/")
    wd_fwd = workdir.replace("\\", "/")
    pairs = [
        # ① 客户端目标（反斜杠 + 正斜杠两种写法都覆盖）
        ("D:\\KleinsPatch\\Win\\lua", target_root + r"\Win\lua"),
        ("D:/KleinsPatch/Win/lua", tgt_fwd + "/Win/lua"),
        ("D:\\hxls\\Win\\lua", target_root + r"\Win\lua"),
        ("D:/hxls/Win/lua", tgt_fwd + "/Win/lua"),
        ("D:\\hxls\\Win", target_root + r"\Win"),
        # ② 备份落点
        ("D:\\KleinsPatch\\_re\\_lua_", workdir + r"\_lua_"),
        ("D:/KleinsPatch/_re/_lua_", wd_fwd + "/_lua_"),
    ]
    for a, b in pairs:
        out = out.replace(a, b)
    return out


def run_script(name, target_root, workdir):
    path = os.path.join(INJECT_DIR, name)
    if not os.path.exists(path):
        return name, False, "脚本不存在: %s" % path
    src = io.open(path, encoding="utf-8").read()
    new = rewrite(src, target_root, workdir)
    # 安全检查：确保没有残留的老客户端目标路径
    if "D:\\KleinsPatch\\Win" in new or "D:/KleinsPatch/Win" in new:
        return name, False, "重定向不干净，仍有 D:\\KleinsPatch\\Win"
    g = {"__name__": "__main__", "__file__": path}
    old_argv = sys.argv
    sys.argv = [path]
    try:
        exec(compile(new, path, "exec"), g)
    except SystemExit:
        pass
    except Exception:
        return name, False, traceback.format_exc(limit=3)
    finally:
        sys.argv = old_argv
    return name, True, "ok"


def patch_gameassembly(target_root):
    """把完整性校验的 JNE 改成 JMP。返回 (ok, 说明)。"""
    path = os.path.join(target_root, "GameAssembly.dll")
    sig, off_in_sig = GA_SIG
    vals = []
    for i in range(0, len(sig.replace(" ", "")), 2):
        p = sig.replace(" ", "")[i:i + 2]
        vals.append(None if p == "??" else int(p, 16))
    raw = open(path, "rb").read()
    hits = []
    for i in range(len(raw) - len(vals)):
        for j, v in enumerate(vals):
            if v is not None and raw[i + j] != v:
                break
        else:
            hits.append(i)
    if len(hits) != 1:
        return False, "★ 特征码命中 %d 处（要求恰好 1 处）" % len(hits)
    off = hits[0] + off_in_sig
    cur = raw[off]
    if cur == 0xEB:
        return True, "已经是 EB（已打过），跳过"
    if cur != 0x75:
        return False, "偏移 0x%X 处是 0x%02X，期望 0x75" % (off, cur)
    data = bytearray(raw)
    data[off] = 0xEB
    open(path, "wb").write(bytes(data))
    return True, "命中 1 处 @ 0x%X，0x75 -> 0xEB" % off


def patch_assets(target_root):
    """把平台 URL 换成指向本机假服的等长串。返回 (ok, 说明)。"""
    path = os.path.join(target_root, ASSETS_REL)
    raw = open(path, "rb").read()
    if raw.count(URL_NEW) == 1 and raw.count(URL_OLD) == 0:
        return True, "已经是新串（已打过），跳过"
    hits = []
    s = 0
    while True:
        k = raw.find(URL_OLD, s)
        if k < 0:
            break
        hits.append(k)
        s = k + 1
    if len(hits) != 1:
        return False, "★ URL 命中 %d 处（要求恰好 1 处）" % len(hits)
    off = hits[0]
    prefix = struct.unpack_from("<i", raw, off - 4)[0]
    if prefix != 40:
        return False, "★ 长度前缀 = %d，期望 40" % prefix
    if len(URL_OLD) != len(URL_NEW):
        return False, "★ 新旧串不等长"
    data = bytearray(raw)
    data[off:off + len(URL_NEW)] = URL_NEW
    open(path, "wb").write(bytes(data))
    return True, "命中 1 处 @ 0x%X，URL 等长替换" % off


def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0].startswith("-"):
        print(__doc__)
        return 2
    target = os.path.abspath(args[0])
    workdir = None
    only = None
    do_binary = True
    dry = False
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--workdir":
            workdir = os.path.abspath(args[i + 1]); i += 2; continue
        if a == "--only":
            only = [x.strip() for x in args[i + 1].split(",") if x.strip()]; i += 2; continue
        if a == "--skip-binary":
            do_binary = False; i += 1; continue
        if a == "--dry-run":
            dry = True; i += 1; continue
        print("未知参数: %s" % a)
        return 2

    if not os.path.isdir(target):
        print("目标目录不存在: %s" % target)
        return 2
    if not workdir:
        workdir = os.path.join(HERE, "_work")
    os.makedirs(workdir, exist_ok=True)

    scripts = only if only else DEFAULT_SCRIPTS
    print("目标客户端 : %s" % target)
    print("工作目录   : %s" % workdir)
    print("补丁脚本   : %d 个" % len(scripts))
    print("二进制补丁 : %s" % ("跳过" if not do_binary else "打"))
    print("dry-run    : %s" % dry)
    print()

    report = []
    if do_binary and not dry:
        ok, msg = patch_gameassembly(target)
        report.append(("GameAssembly.dll", ok, msg))
        print("  [%s] GameAssembly.dll  %s" % ("OK" if ok else "!!", msg))
        ok, msg = patch_assets(target)
        report.append(("resources.assets", ok, msg))
        print("  [%s] resources.assets  %s" % ("OK" if ok else "!!", msg))
    elif do_binary:
        print("  (dry-run) 跳过二进制补丁")

    print()
    for name in scripts:
        if dry:
            # dry-run 也要过一遍重写逻辑 —— 这是最容易出错的一步，必须能静态验证
            p = os.path.join(INJECT_DIR, name)
            if not os.path.exists(p):
                report.append((name, False, "脚本不存在"))
                print("  [!!] %s  脚本不存在" % name)
                continue
            new = rewrite(io.open(p, encoding="utf-8").read(), target, workdir)
            bad = [s for s in ("D:\\KleinsPatch\\Win", "D:/KleinsPatch/Win",
                               "D:\\hxls\\Win", "D:/hxls/Win",
                               "D:\\KleinsPatch\\_re\\_lua_", "D:/KleinsPatch/_re/_lua_")
                   if s in new]
            if bad:
                report.append((name, False, "残留: %s" % bad))
                print("  [!!] %-24s 重写后仍有残留: %s" % (name, bad))
            else:
                # 顺便数一数重定向了几处，便于确认真的命中
                n_t = new.count(target + r"\Win\lua") + \
                      new.count(target.replace("\\", "/") + "/Win/lua")
                n_b = new.count(workdir + r"\_lua_") + \
                      new.count(workdir.replace("\\", "/") + "/_lua_")
                report.append((name, True, "重写 OK (目标 %d 处, 备份 %d 处)" % (n_t, n_b)))
                print("  [OK] %-24s 重写 OK (目标路径 %d 处, 备份路径 %d 处)"
                      % (name, n_t, n_b))
            continue
        n, ok, msg = run_script(name, target, workdir)
        report.append((name, ok, msg))
        print("  [%s] %s" % ("OK" if ok else "!!", n))
        if not ok:
            print("       " + msg.replace("\n", "\n       "))

    rp = os.path.join(workdir, "build_report.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("目标: %s\n\n" % target)
        for n, ok, msg in report:
            f.write("[%s] %s\n" % ("OK" if ok else "!!", n))
            if not ok:
                f.write("    " + msg + "\n")
        f.write("\n失败 %d / %d\n" % (sum(1 for _, ok, _ in report if not ok), len(report)))
    print()
    print("报告: %s" % rp)
    bad = sum(1 for _, ok, _ in report if not ok)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
