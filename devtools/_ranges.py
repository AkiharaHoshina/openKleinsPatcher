import json
sj = json.load(open(r"D:\openKleinsPatcher\devtools\il2cpp_steam\script.json", encoding="utf-8"))
for k in ("ScriptString", "ScriptMethod"):
    a = [e["Address"] for e in sj[k]]
    print(k, len(a), "min=%#x max=%#x" % (min(a), max(a)))
    print("  样例:", json.dumps(sj[k][:2], ensure_ascii=False)[:300])
# 看 ScriptString 里有没有我们关心的键名
keys = {e["Value"] for e in sj["ScriptString"]}
for want in ("updateList", "parts", "Version", "UpdateFlag", "resName", "ResName", "md5", "Md5",
             "size", "Size", "resUrl", "bin", "updateType", "name"):
    print("%-12s %s" % (want, want in keys))
