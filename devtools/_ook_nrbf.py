# -*- coding: utf-8 -*-
"""把 bk.zip 里的 ZipInfo NRBF 记录流逐条打印出来，用来照抄结构写重建器。"""
import struct
import sys

import lz4.block

sys.stdout.reconfigure(errors="replace")
P = sys.argv[1] if len(sys.argv) > 1 else r"F:\originKleinsSteam\环行旅舍_Data\StreamingAssets\bk.zip"
d = open(P, "rb").read()


def rdvarint(b, o):
    v = sh = 0
    while True:
        x = b[o]
        o += 1
        v |= (x & 0x7F) << sh
        if not (x & 0x80):
            return v, o
        sh += 7


raw = bytearray()
o = 0
while o < len(d):
    o += 1
    unc, o = rdvarint(d, o)
    cpr, o = rdvarint(d, o)
    raw += lz4.block.decompress(d[o:o + cpr], uncompressed_size=unc)
    o += cpr

hdr_len = struct.unpack_from("<i", raw, 0)[0]
print("头块长度 = %d" % hdr_len)
b = raw[4:4 + hdr_len]

R = {0: "SerializedStreamHeader", 1: "ClassWithId", 2: "SystemClassWithMembers",
     3: "ClassWithMembers", 4: "SystemClassWithMembersAndTypes",
     5: "ClassWithMembersAndTypes", 6: "BinaryObjectString", 7: "BinaryArray",
     8: "MemberPrimitiveTyped", 9: "MemberReference", 10: "ObjectNull",
     11: "MessageEnd", 12: "BinaryLibrary", 13: "ObjectNullMultiple256",
     14: "ObjectNullMultiple", 15: "ArraySinglePrimitive", 16: "ArraySingleObject",
     17: "ArraySingleString", 21: "MethodCall", 22: "MethodReturn"}


def rdstr(o):
    n, o = rdvarint(b, o)
    return b[o:o + n].decode("utf-8", "replace"), o + n


o = 0
n = 0
while o < len(b) and n < 60:
    t = b[o]
    start = o
    o += 1
    if t == 0:
        print("%6d %-28s RootId=%d HeaderId=%d Maj=%d Min=%d"
              % (start, R[t], *struct.unpack_from("<iiii", b, o)))
        o += 16
    elif t == 12:
        libid = struct.unpack_from("<i", b, o)[0]
        o += 4
        s, o = rdstr(o)
        print("%6d %-28s LibraryId=%d name=%r" % (start, R[t], libid, s))
    elif t in (4, 5):
        oid = struct.unpack_from("<i", b, o)[0]
        o += 4
        cname, o = rdstr(o)
        mc = struct.unpack_from("<i", b, o)[0]
        o += 4
        names = []
        for _ in range(mc):
            s, o = rdstr(o)
            names.append(s)
        types = list(b[o:o + mc])
        o += mc
        print("%6d %-28s ObjectId=%d Class=%r Members=%s Types=%s"
              % (start, R[t], oid, cname, names, types))
        # ★ ClassWithMembersAndTypes 末尾还有个 LibraryId（int32）—— 漏了它后面全串位
        got_lib = False
        # 附加类型信息
        for ty in types:
            if ty == 0:      # Primitive
                print("            primType=%d" % b[o]); o += 1
            elif ty == 4:    # Class
                s, o = rdstr(o)
                print("            classType=%r" % s)
            elif ty in (3,):  # SystemClass
                s, o = rdstr(o)
                print("            systemClass=%r" % s)
            elif ty == 7:
                print("            primArrayType=%d" % b[o]); o += 1
            # 1(String)/2(Object)/5(ObjectArray)/6(StringArray) 无附加
        # ★ 只有 ClassWithMembersAndTypes(5) 有尾部 LibraryId；
        #   SystemClassWithMembersAndTypes(4) **没有**（它是系统类）
        if t == 5:
            lib = struct.unpack_from("<i", b, o)[0]
            o += 4
            print("            LibraryId=%d" % lib)
    elif t == 6:
        oid = struct.unpack_from("<i", b, o)[0]
        o += 4
        s, o = rdstr(o)
        print("%6d %-28s ObjectId=%d value=%r" % (start, R[t], oid, s[:70]))
    elif t == 7:
        oid = struct.unpack_from("<i", b, o)[0]
        o += 4
        length = struct.unpack_from("<i", b, o)[0]
        o += 4
        print("%6d %-28s ObjectId=%d ArrayLength=%d elems=" % (start, R[t], oid, length), end="")
        for i in range(min(4, length)):
            v = struct.unpack_from("<i", b, o + 4 * i)[0]
            print(v, end=" ")
        print("..." if length > 4 else "")
        o += 4 * length
    elif t == 1:
        oid, mid = struct.unpack_from("<ii", b, o)
        o += 8
        print("%6d %-28s ObjectId=%d MetadataId=%d" % (start, R[t], oid, mid))
    elif t in (2, 3):
        oid = struct.unpack_from("<i", b, o)[0]
        o += 4
        cname, o = rdstr(o)
        mc = struct.unpack_from("<i", b, o)[0]
        o += 4
        names = []
        for _ in range(mc):
            s, o = rdstr(o)
            names.append(s)
        print("%6d %-28s ObjectId=%d Class=%r Members=%s" % (start, R[t], oid, cname, names))
    elif t in (16, 17):
        oid, length = struct.unpack_from("<ii", b, o)
        o += 8
        print("%6d %-28s ObjectId=%d Length=%d" % (start, R[t], oid, length))
    elif t == 15:
        oid, length = struct.unpack_from("<ii", b, o)
        pt = b[o + 8]
        o += 9
        print("%6d %-28s ObjectId=%d Length=%d primType=%d elems=" % (start, R[t], oid, length, pt), end="")
        for i in range(min(4, length)):
            print(struct.unpack_from("<i", b, o + 4 * i)[0], end=" ")
        print("..." if length > 4 else "")
        o += 4 * length
    elif t == 9:
        print("%6d %-28s IdRef=%d" % (start, R[t], struct.unpack_from("<i", b, o)[0]))
        o += 4
    elif t == 13:
        print("%6d %-28s count=%d" % (start, R[t], b[o]))
        o += 1
    elif t == 14:
        print("%6d %-28s count=%d" % (start, R[t], struct.unpack_from("<i", b, o)[0]))
        o += 4
    elif t == 8:
        pt = b[o]
        o += 1
        print("%6d %-28s type=%d value=%d" % (start, R[t], pt, struct.unpack_from("<i", b, o)[0]))
        o += 4
    elif t == 10:
        print("%6d %-28s" % (start, R[t]))
    else:
        print("%6d %-28s  <未解析，停>" % (start, R.get(t, t)))
        break
    n += 1
