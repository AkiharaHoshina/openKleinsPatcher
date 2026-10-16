# -*- coding: utf-8 -*-
"""按名字/地址在 script.json 里互查。 用法:
    python _findmethod.py name DownloadCondition
    python _findmethod.py rva 0x11BFAE0
"""
import json
import sys

sys.stdout.reconfigure(errors="replace")
sj = json.load(open(r"D:\openKleinsPatcher\devtools\il2cpp_steam\script.json", encoding="utf-8"))

mode, arg = sys.argv[1], sys.argv[2]

if mode == "name":
    hits = [e for e in sj["ScriptMethod"] if arg.lower() in e["Name"].lower()]
    print("命中 %d 条" % len(hits))
    seen = set()
    for e in hits:
        k = (e["Address"], e["Name"])
        if k in seen:
            continue
        seen.add(k)
        print("  %#010x  %s" % (e["Address"], e["Name"]))
        if len(seen) > 60:
            print("  ...(截断)")
            break
elif mode == "rva":
    a = int(arg, 0)
    for e in sj["ScriptMethod"]:
        if e["Address"] == a:
            print("  %#010x  %s" % (e["Address"], e["Name"]))
            print("     sig: %s" % e.get("Signature", "")[:300])
    for e in sj.get("ScriptMetadata", []):
        if e["Address"] == a:
            print("  [MD] %#010x  %s" % (e["Address"], e.get("Name", "")))
else:
    print(__doc__)
