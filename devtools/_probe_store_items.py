# -*- coding: utf-8 -*-
"""找出「存档里发了、但客户端 dataconfig_itembase 里没有」的道具 id。

客户端 `logic_store.CreateItem` 是：
    item.Config = config_data_center.getConfigDataByID("dataconfig_itembase","id", item.ID)
而服务端 `build_store` 把存档里**所有**道具原样下发 ⇒ 只要有一个 id 查不到配置，
客户端刷新商店时就 `attempt to index field 'Config' (a nil value)` 崩掉。
"""
import ast
import json
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

CFG = r"D:\KleinsPatch\_re\cfg\dataconfig_itembase.txt"
for cand in (r"D:\openKleinsServer\cfg\dataconfig_itembase.txt", CFG):
    if os.path.exists(cand):
        CFG = cand
        break
SAVES = [r"D:\openKleinsServer\player.json", r"D:\KleinsPatch\_re\player.json",
         r"D:\openKleinsServer\baseline.json", r"D:\KleinsPatch\_re\baseline.json"]


def load_cfg_ids(path):
    """dump 是**多行缩进**的 Lua 表：行头是 `N => `（序号），字段缩进 4 空格、嵌套 8 空格。
    ⇒ 只认**正好 4 空格缩进**的 `id = N`，就是这一行的主键。"""
    ids = set()
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^ {4}id = (-?\d+),?\s*$", line)
            if m:
                ids.add(int(m.group(1)))
    return ids, bad


print("配置表: %s (%d 字节)" % (CFG, os.path.getsize(CFG)))
ids, bad = load_cfg_ids(CFG)
print("  解析出 %d 个 id（%d 行解不开）" % (len(ids), bad))
if ids:
    print("  id 范围 %d .. %d" % (min(ids), max(ids)))

for sp in SAVES:
    if not os.path.exists(sp):
        continue
    try:
        d = json.load(open(sp, encoding="utf-8"))
    except Exception as e:
        print("%s: 读不了 %s" % (sp, e))
        continue
    items = d.get("items")
    if not isinstance(items, dict):
        continue
    have = sorted(int(k) for k in items)
    miss = [i for i in have if ids and i not in ids]
    print()
    print("=== %s ===" % sp)
    print("  存档道具 %d 种: %s%s" % (len(have), have[:20], " ..." if len(have) > 20 else ""))
    if not ids:
        print("  （没有配置表可比）")
    elif miss:
        print("  ★★ 客户端配置里没有的 id: %s" % miss)
        for i in miss:
            print("      id=%d 数量=%s" % (i, items[str(i)] if str(i) in items else items.get(i)))
    else:
        print("  ✓ 全部都能在配置表里找到")
