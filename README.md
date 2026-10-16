<p align="center">
  <img alt="自由旅舍 FreeKleins —— Patcher" src="assets/banner.png" width="100%">
</p>

# openKleinsPatcher

把**你自己合法持有**的一份《环行旅舍》客户端，改成能连本地假服务端的版本。

这是 [openKleinsServer](../openKleinsServer) 的配套工具：服务端负责"说协议"，本工具负责让
客户端"愿意跟它说话"（把平台 URL 指到本机、把完整性校验放过、把 Lua 补丁铺进去）。

> **本仓库不含任何游戏内容。** 它只改了客户端**自己那几个文件**，且所有改动都能一键还原。
> 见下面的「关于游戏内容」。

---

## 它是什么 / 它不做什么

**做**：给一份干净客户端打五处补丁（见下表），改完就能连 `127.0.0.1:10300`。

**不做**：

* 不带客户端 —— 你得自己有。
* 不带配置表 —— 那是打过补丁的客户端在运行时自己导出来的（服务端会用）。
* 不改游戏逻辑 —— 只在少数几个 Lua 模块外面**包一层**（见「Lua 补丁怎么打的」）。

---

## 快速开始

### 0. 前置

* 一份**干净**的《环行旅舍》客户端（国服版或 Steam 版都行，会自动识别）
* **先关掉游戏** —— 它占着 `bk.zip`，开着游戏打补丁会失败
* 服务端已经准备好了（[openKleinsServer](../openKleinsServer)）

### 1. 打补丁

双击 `kleinspatcher.exe`，按提示走：

```
[1] 选择客户端目录      ← 弹出系统文件夹选择框
[2] 手动输入路径        ← 直接敲/粘一个目录
```

选完会**先预检**（只看不改），列出哪几项需要处理。然后：

| 键 | 干什么 | 安全吗 |
|---|---|---|
| `P` | 开始打补丁（**先备份再动手**） | 备份在 `<客户端>\_kleins_backup\` |
| `D` | 只看不写 | 一个字节都不动 |
| `R` | 还原 | 从备份恢复，回到打补丁之前 |
| `C` | 重新识别 | 改完文件后刷新 |
| `B` | 换一个客户端 | |

也可以走命令行（同一个 exe）：

```
kleinspatcher.exe <客户端目录>            # 打补丁
kleinspatcher.exe <客户端目录> --dry-run   # 只看会做什么
kleinspatcher.exe <客户端目录> --list      # 列各项状态，只读
kleinspatcher.exe <客户端目录> --revert    # 还原
```

### 2. 启动顺序

> ★★★ **先打补丁 → 再开服 → 最后起游戏。**

* **先打补丁**：补丁要把客户端里的服务端地址改成 `127.0.0.1`。
  **顺序反了**（服务端先开着、拿**没打过补丁**的客户端去连）客户端可能提示**网络问题** ——
  它手里的地址还是官方那个，早就没了。这是**已知问题**；补丁过之后就不用担心了。
* **再开服**：客户端建不了目录，`resources\cfg\<渠道>\` 得由服务端先建出来。
* **最后起游戏**。

服务端那边的细节见它的 README。

第一次启动会**慢一阵**：客户端要把配置表全量导出一次（约 190MB）。这是预期内的，
每个「渠道 + 版本」只付一次，之后就直接跳过。

---

## 打的五件事

| # | 目标 | 干什么 |
|---|---|---|
| 1 | `Win\File_res\DescriptionFile.json` | **Steam 版出厂没有这个目录**，不补上客户端会 `CheckVersion_LocalFile_NotExists` → `Hotfix.Reset()`（删目录）→ 重启 → 无限循环。从 `StreamingAssets\DescriptionFile.json` 复制一份。 |
| 2 | `GameAssembly.dll` | 资源完整性校验 `0x75`(JNE) → `0xEB`(JMP) |
| 3 | `环行旅舍_Data\resources.assets` | 平台 URL 指向本机；`IsOpenHot`→1；`PlatType` `steam`→`bingkolo` |
| 4 | `环行旅舍_Data\StreamingAssets\bk.zip` | **Steam 版的 Lua 补丁走这里**：把 wrapper 换进去、把原版另存为 `_orig` |
| 5 | `Win\lua\...` | **国服版的 Lua 补丁走这里**：同上，但是**就地写文件** |

### ★★★ 为什么 Lua 要打**两**条路

Steam 版每次启动都执行 HotUpdate 的 Decompress，把 `bk.zip` 整包解开覆盖 `Win\lua`
⇒ 直接改 `Win\lua` 活不过一次启动，只能改源包。

但**国服版不解压** —— 它直接读 `Win\lua`。只打 `bk.zip` 的话，国服客户端跑的还是原版 Lua。
（实测踩过：拿国服客户端打补丁，`bk.zip` 里 31/31 wrapper 都在，可 `Win\lua` 一个都没变
⇒ 白屏在 `logic_login_main.InitServerList` 的原版 bug 上。）

⇒ 两条路都打，谁生效看客户端；打重了也没关系（幂等）。

---

## Lua 补丁怎么打的

### wrapper 形态

不修改原模块，而是在它外面**包一层**：

```lua
-- 明文长这样（编译成字节码后放进 patches\lua\）
local M = require("logic/login_ui/view_login_ui_orig")   -- 原模块（已经另存为 _orig）
local orig = M.InitData
M.InitData = function(...)
    if orig then pcall(orig, ...) end
    ...                                                   -- 我们加的东西
end
return M
```

原模块备份成同目录的 `xxx_orig.lua`，所以我们永远能**回退到原逻辑**，
也能在别人改动过逻辑时**不覆盖**它（只在外面包）。

### 补丁集

`patches\lua\` 下 31 个条目，路径与客户端 `Win\lua\` 一一对应。
判定"这是 wrapper 不是游戏原文件"的依据：**每一个都 `require` 它的 `_orig` 兄弟**。

客户端版本差异不用管：目标模块在**这个版本里不存在**，就自动跳过
（国服/Steam 各有专有模块，不需要维护 N 套清单）。

---

## 幂等 / 可逆

* **重复运行**：内容已经是 wrapper 就跳过，不重复动刀。`--dry-run` 可以先看。
* **`--revert`**：从 `<客户端>\_kleins_backup\` 还原所有被改过的文件（含 `bk.zip`、
  `Win\lua` 里的每一个），并删掉当初是我们新建的东西。
* **先全量预检、再动手**：任何一步前置条件不满足就整体中止，一个字节都不改。

> ⚠️ `Win\lua` 里的补丁要等客户端**再启动一次**才复原（解压步骤会按还原后的 `bk.zip` 覆盖）。

---

## 目录结构

```
kleinspatcher.py        命令行入口（也负责全部实际逻辑）
kleinspatcher_tui.py    交互式外壳（双击 exe 走这个）；带参数时转给上面那份
patchlib/               两个仓库无关的通用件，**只用标准库**
    binpatch.py         GameAssembly / resources.assets 的特征码定位与改写
    bkzip.py            bk.zip 的解析与重打包
    clientinfo.py       认这是不是客户端、是哪个版本
    lz4block.py         LZ4 块解压（分析资源包用）
    ui.py               编号菜单 / 文件夹选择框 / 输入清洗
patches/lua/            补丁集（wrapper，编译后的字节码）
devtools/               开发期工具与自检，**不参与打包**
```

## 自己打包 exe

```
python -m PyInstaller --distpath . --workpath devtools\_build_patcher ^
    --noconfirm --log-level ERROR devtools\kleinspatcher.spec
```

## 自检

改完之后跑这几个（都在 `devtools\`）：

| 脚本 | 查什么 |
|---|---|
| `_selftest_tui.py` | 拿一个**临时造出来的假客户端**把整个 TUI 流程真跑一遍：dry-run 一个字节不改 / 真打（含 `Win\lua` 就地换、`_orig` 存的是原版字节）/ 还原回**一模一样**的字节 / 幂等 |
| `_check_tui_smoke.py` | 把**打好的 exe** 真跑起来，用管道喂几种输入 —— 含一个**必须失败**的对照组，防止"判据永远为真"的假绿 |
| `_check_junk.py` | `ui.clean()` 对 BOM / 零宽字符 / NUL 等脏输入的处理 |
| `_check_patched_bkzip.py <客户端>` | 打完的 `bk.zip` 里 wrapper 是否 31/31 就位、`_orig` 是否齐全 |
| `_gameconf.py <客户端>` | 看客户端会自报的 `PlatType` / `SubPlatType` / URL / `IsOpenHot` |

---

## 已知限制

* 补丁集是**按模块逐个包**的，不是全量替换 —— 客户端里没动过的模块保持原样。
* 服务端那边的功能覆盖情况（哪些界面能用、哪些禁用了）见服务端仓库的文档。
* `devtools\` 下的 IL2CPP 反编译产物、游戏原版 Lua 副本等**刻意不进版本控制**
  （见 `.gitignore`），但它们是排查问题时的关键证据。

---

## 关于游戏内容

《环行旅舍》(Kleins) 及其全部内容的一切权利归其原权利人所有。本项目与游戏的开发方、
运营方**无任何关联**，也**未获得其授权或认可**。项目目的是**互操作性研究**与**数字保存**
（游戏已于 2024 年前后停止运营）。

**本仓库刻意不含**：游戏二进制、`*.assets`、`*.dll`、游戏原版 Lua（`*.orig`）、
IL2CPP 反编译产物、配置表、`bk.zip` 及其解包内容。

**仓库里有、但可能涉及第三方的**，为透明起见逐条列出：

* `patches\lua\` 下的 wrapper —— 作者自己写的 Lua（编译后的字节码），不含游戏代码。
* `base\*.json` —— 客户端文件的 `{文件名: [大小, sha256]}` **哈希清单**，用于比对
  打补丁前后的字节级差异；只有哈希，没有内容。

如果你在本仓库里发现了任何游戏内容，那是**误提交**，请提 issue。

---

## 许可

**AGPL-3.0** —— 见 [LICENSE](LICENSE)。

★ 该许可**只覆盖本仓库的原创源码**，不覆盖《环行旅舍》及其任何资源。
★ AGPL 允许商用，但要求：改动必须以同样许可开源；
  **通过网络提供服务时，也必须向使用者提供源码**。
