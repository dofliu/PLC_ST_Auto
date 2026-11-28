"""M37:直接位址共用記憶體(process image)。

同一區域(I/Q/M)中位址重疊的變數共用位元組,例如 `w AT %MW0 : WORD` 與 `b AT %MX0.0 : BOOL`:
寫入其中一個,另一個立即反映。定址與位元組順序依 profile:
- IEC / CODESYS(預設):%MW1 = 第 1 個 word(位元組 2..3),little-endian,%MX0.0 = %MW0 的最低位元
- Siemens S7:%MW1 = 位元組 1..2,big-endian,%M0.0 = %MW0 的 bit 8(高位元組在前)
只有位址真的重疊的變數才會被追蹤,沒有重疊時行為與以前完全相同。
"""
import struct

from .parser import parse_addr

_BITS = {"BOOL": 1, "SINT": 8, "USINT": 8, "BYTE": 8, "INT": 16, "UINT": 16, "WORD": 16,
         "DINT": 32, "UDINT": 32, "DWORD": 32, "REAL": 32, "TIME": 32,
         "LINT": 64, "ULINT": 64, "LWORD": 64, "LREAL": 64}

_SIGNED = {"SINT", "INT", "DINT", "LINT", "TIME"}


def layout(addr, siemens):
    """位址 → (區域, 起始位元組, 位元組數, 位元 or None)。"""
    a = parse_addr(addr)
    if a["size"] == "X":
        return a["area"], a["index"], 1, a["bit"] or 0
    nbytes = a["bits"] // 8
    start = a["index"] if siemens else a["index"] * nbytes
    return a["area"], start, nbytes, None


class ProcessImage:
    def __init__(self, decls, types, siemens):
        self.big = siemens
        self.mem = {}       # area -> bytearray
        self.loc = {}       # var key -> (area, start, nbytes, bit, type)
        cand = []
        for d in decls:
            t = d["type"]
            if not d.get("addr") or d.get("array") or t not in _BITS or types.get(d["name"].lower()) != t:
                continue
            area, start, n, bit = layout(d["addr"], siemens)
            if bit is None and _BITS[t] != n * 8:
                continue  # 大小不符:檢查器會報錯,模擬時不連動
            cand.append((d["name"].lower(), area, start, n, bit, t))
        # 只保留與其他變數真正重疊的
        self.peers = {}
        for k, area, s, n, bit, t in cand:
            for k2, area2, s2, n2, bit2, _ in cand:
                if k2 == k or area2 != area or not (s < s2 + n2 and s2 < s + n):
                    continue
                if bit is not None and bit2 is not None and bit != bit2:
                    continue  # 同一位元組的不同位元互不影響
                self.peers.setdefault(k, []).append(k2)
        for k, area, s, n, bit, t in cand:
            if k in self.peers:
                self.loc[k] = (area, s, n, bit, t)
                buf = self.mem.setdefault(area, bytearray())
                if len(buf) < s + n:
                    buf.extend(bytes(s + n - len(buf)))

    def __bool__(self):
        return bool(self.loc)

    # -- encode / decode
    def _fmt(self, t, n):
        e = ">" if self.big else "<"
        if t == "REAL":
            return e + "f"
        if t == "LREAL":
            return e + "d"
        c = {1: "b", 2: "h", 4: "i", 8: "q"}[n]
        return e + (c if t in _SIGNED else c.upper())

    def store(self, key, value):
        area, s, n, bit, t = self.loc[key]
        buf = self.mem[area]
        if bit is not None:
            if value:
                buf[s] |= 1 << bit
            else:
                buf[s] &= ~(1 << bit) & 0xFF
            return
        if t in ("REAL", "LREAL"):
            raw = struct.pack(self._fmt(t, n), float(value))
        else:
            v = int(value) & ((1 << (8 * n)) - 1)  # 依位元寬截斷(二補數)
            if t in _SIGNED and v >= 1 << (8 * n - 1):
                v -= 1 << (8 * n)
            raw = struct.pack(self._fmt(t, n), v)
        buf[s:s + n] = raw

    def load(self, key):
        area, s, n, bit, t = self.loc[key]
        buf = self.mem[area]
        if bit is not None:
            return bool(buf[s] >> bit & 1)
        v = struct.unpack(self._fmt(t, n), bytes(buf[s:s + n]))[0]
        return float(v) if t in ("REAL", "LREAL") else int(v)


class LocatedVars(dict):
    """變數表:寫入有重疊位址的變數時,同步更新共用記憶體並刷新其他重疊變數。"""

    def __init__(self, data, image):
        super().__init__(data)
        self.image = image
        for k in image.loc:  # 依宣告順序寫入初值,後宣告者覆蓋重疊位元組
            if k in self:
                image.store(k, dict.__getitem__(self, k))
        for k in image.loc:
            if k in self:
                dict.__setitem__(self, k, image.load(k))

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if key in self.image.loc:
            self.image.store(key, value)
            # 寫入者自己也從共用記憶體讀回:REAL 依 32 位元精度捨入、整數依位元寬截斷,
            # 與同位址的其他變數讀到完全相同的值(M37 審查:同位址 REAL 不可出現兩種精度)
            dict.__setitem__(self, key, self.image.load(key))
            for k in self.image.peers[key]:
                dict.__setitem__(self, k, self.image.load(k))
