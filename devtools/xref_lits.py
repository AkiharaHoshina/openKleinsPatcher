#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反汇编 IL2CPP 里某个函数，并把**字符串字面量**和**调用目标**解析成人名。

    python xref_lits.py <rva十六进制> [--len 1200] [--dll <路径>] [--script <script.json>]
      e.g.  python xref_lits.py 0x11BFAE0 --len 2000

## 为什么需要它

IL2CPP 把 C# 编译成原生 x64，`JsonData["updateList"]` 这种下标访问会变成
「加载字符串字面量 → call JsonData.get_Item」。字面量本身**不在 DLL 里**
（在 global-metadata.dat），所以直接搜字节永远搜不到 —— 只能反汇编看它引用了哪个地址，
再用 Il2CppDumper 的 `script.json` 把地址还原成字符串。

`script.json` 里有两张表正好够用：
    ScriptString : [{Address, Value}]      → 地址 -> 字符串字面量
    ScriptMethod : [{Address, Name, ...}]  → 地址 -> 方法名

★ 输出的每一行都会把 `lea rX,[rip+d]`（算成绝对地址）和 `call rel32` 解析出来，
  所以能直接读出「它在查哪个键」「它调了哪个方法」。
"""
import argparse
import json
import struct
import sys

sys.stdout.reconfigure(errors="replace")

DEFAULT_DLL = r"F:\originKleinsSteam\GameAssembly.dll"
DEFAULT_SCRIPT = r"D:\openKleinsPatcher\devtools\il2cpp_steam\script.json"


def pe_sections(path):
    """极简 PE 解析：返回 [(VirtualAddress, VirtualSize, PointerToRawData, SizeOfRawData)]。"""
    d = open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
    assert d[e_lfanew:e_lfanew + 4] == b"PE\0\0", "不是 PE 文件"
    coff = e_lfanew + 4
    nsect = struct.unpack_from("<H", d, coff + 2)[0]
    opt_size = struct.unpack_from("<H", d, coff + 16)[0]
    sect = coff + 20 + opt_size
    out = []
    for i in range(nsect):
        b = sect + i * 40
        name = d[b:b + 8].rstrip(b"\0").decode("latin-1")
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", d, b + 8)
        out.append((name, va, vsize, rawptr, rawsize))
    return d, out


def rva_to_off(sections, rva):
    for _n, va, vsize, rawptr, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return rawptr + (rva - va)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rva", help="函数 RVA，十六进制（如 0x11BFAE0）")
    ap.add_argument("--len", type=int, default=1200, help="反汇编字节数")
    ap.add_argument("--dll", default=DEFAULT_DLL)
    ap.add_argument("--script", default=DEFAULT_SCRIPT)
    ap.add_argument("--image-base", type=lambda x: int(x, 0), default=0x180000000)
    a = ap.parse_args()

    rva = int(a.rva, 0)
    data, sections = pe_sections(a.dll)
    off = rva_to_off(sections, rva)
    if off is None:
        print("RVA %#x 不落在任何节里" % rva)
        return 2

    sj = json.load(open(a.script, encoding="utf-8"))
    # ★ ScriptString / ScriptMethod 的 Address 是 **RVA**（不是 VA）——
    #   实测 ScriptString 范围 0x2a97818..0x2b26bb8，而 DLL ImageBase = 0x180000000。
    #   所以查表前必须把算出来的 VA 减掉 ImageBase。踩过。
    strings = {e["Address"]: e["Value"] for e in sj.get("ScriptString", [])}
    methods = {e["Address"]: e["Name"] for e in sj.get("ScriptMethod", [])}
    print("字面量表 %d 条 / 方法表 %d 条" % (len(strings), len(methods)))
    print("RVA %#x -> 文件偏移 %#X" % (rva, off))
    print()

    try:
        import capstone
    except ImportError:
        print("缺 capstone：pip install capstone")
        return 2
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    code = data[off:off + a.len]
    base = a.image_base + rva

    def lookup(va):
        """VA -> 名字（查表前减 ImageBase，因为 script.json 存的是 RVA）。"""
        r = va - a.image_base
        if r in strings:
            return "STR %r" % strings[r]
        if r in methods:
            return methods[r]
        return None

    for ins in md.disasm(code, base):
        extra = ""
        # 1) lea reg, [rip+d] / mov reg, [rip+d] → 绝对地址，查是不是字符串字面量
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                r = lookup(ins.address + ins.size + op.mem.disp)
                if r:
                    extra += "   ; " + r
            if op.type == capstone.x86.X86_OP_IMM:
                r = lookup(op.imm)
                if r:
                    extra += "   ; " + r
        # 2) call rel32 → 方法名
        if ins.mnemonic == "call" and ins.operands and ins.operands[0].type == capstone.x86.X86_OP_IMM:
            r = lookup(ins.operands[0].imm)
            if r and not r.startswith("STR "):
                extra += "   ; -> " + r
        print("  %08X  %-34s %s%s" % (ins.address, ins.mnemonic + " " + ins.op_str, "", extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
