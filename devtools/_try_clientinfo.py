#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动看一眼 `patchlib.clientinfo` 对真实客户端读到什么(只读)。

    python devtools\\_try_clientinfo.py <客户端根> [<客户端根> ...]
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from patchlib import clientinfo                      # noqa: E402

for root in sys.argv[1:]:
    print("=" * 70)
    print("客户端: %s" % root)
    print("-" * 70)
    for line in clientinfo.describe(clientinfo.identify(root)):
        print("  " + line)
print("=" * 70)
