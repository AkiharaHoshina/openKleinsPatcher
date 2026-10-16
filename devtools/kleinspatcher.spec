# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec —— 《环行旅舍》客户端补丁器
#
# 构建（和 openKleinsServer/tools/*.spec 一个布局）:
#     cd D:\openKleinsPatcher
#     python -m PyInstaller --distpath . --workpath devtools\_build_patcher ^
#         --noconfirm --log-level ERROR devtools\kleinspatcher.spec
#
# 产物: <distpath>\kleinspatcher.exe   （distpath 给 `.` 就落在仓库根）
#
# ★ 入口是 **TUI**（kleinspatcher_tui.py）；带参数时会转给命令行那份
#   （`kleinspatcher.exe <目录> --list / --dry-run / --revert`）。
#   两条路共用 kleinspatcher.build_plan / run_plan ⇒ 不会各写一份逻辑。
#
# ★★ `tkinter` **必须**写进 hiddenimports:
#   `patchlib/ui.py` 是**懒导入**它的（在函数体里才 import），PyInstaller 的静态
#   分析看不见 ⇒ 不写的话，打出来的 exe 里**没有目录选择框**，而界面上只是
#   [1] 那一项不见了 —— 不报错、不崩，最难查的那种。
#
# ★ `patches\lua` 打进包里（单文件就能用）；运行时**exe 旁边那份优先**
#   （作者想换补丁集不用重新打包），逻辑在 kleinspatcher.PATCH_LUA。
#
# ★ 路径用 SPECPATH 解析, 不要依赖调用时的当前目录。

import os

# ★ `SPECPATH` **本身就是 spec 所在的目录**(= devtools/) —— 只用一次 dirname。
#   (第一版多套了一层, 结果仓库根算成了 `D:\`, 报 "script 'D:\...py' not found"。)
_ROOT = os.path.dirname(os.path.abspath(SPECPATH))    # 仓库根

block_cipher = None

a = Analysis([os.path.join(_ROOT, 'kleinspatcher_tui.py')],
             pathex=[_ROOT],
             binaries=[],
             datas=[(os.path.join(_ROOT, 'patches', 'lua'), 'patches/lua')],
             hiddenimports=['tkinter', 'tkinter.filedialog'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='kleinspatcher',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )
