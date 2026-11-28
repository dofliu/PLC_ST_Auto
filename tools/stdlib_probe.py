"""Probe the virtual PLC + checker against IEC 61131-3 (3rd ed.) standard functions / FBs.

Each case: (category, name, declarations, statement, variable, expected value).
Status: OK = runs and gives the expected value and the checker has no error;
WRONG = runs but the value differs; CHECKER = runs correctly but the checker reports an error;
MISSING = parse/runtime error (not implemented).

    python tools/stdlib_probe.py            # markdown table
    python tools/stdlib_probe.py --summary  # counts only
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plc_st.checker import check  # noqa: E402
from plc_st.interpreter import VirtualPLC  # noqa: E402

C = []


def case(cat, name, decl, stmt, var, exp, note=""):
    C.append((cat, name, decl, stmt, var, exp, note))


# --- 2.5.1.5.1 type conversion
case("型別轉換", "INT_TO_REAL 等 *_TO_*", "r:REAL;", "r := INT_TO_REAL(3);", "r", 3.0)
case("型別轉換", "REAL_TO_INT(2.5) 捨入", "i:INT;", "i := REAL_TO_INT(2.5);", "i", 3, "IEC:四捨五入(CODESYS 同)")
case("型別轉換", "DINT_TO_INT 截斷溢位", "i:INT;", "i := DINT_TO_INT(70000);", "i", 4464)
case("型別轉換", "TRUNC", "i:DINT;", "i := TRUNC(-2.7);", "i", -2)
case("型別轉換", "TRUNC_INT(型別化)", "i:INT;", "i := TRUNC_INT(2.7);", "i", 2)
case("型別轉換", "STRING_TO_INT", "i:INT;", "i := STRING_TO_INT('42');", "i", 42)
case("型別轉換", "INT_TO_STRING", "s:STRING;", "s := INT_TO_STRING(42);", "s", "42")
case("型別轉換", "REAL_TO_STRING", "s:STRING;", "s := REAL_TO_STRING(1.5);", "s", "1.5")
case("型別轉換", "BOOL_TO_STRING", "s:STRING;", "s := BOOL_TO_STRING(TRUE);", "s", "TRUE")
case("型別轉換", "INT_TO_BCD", "w:WORD;", "w := INT_TO_BCD(12);", "w", 0x12)
case("型別轉換", "BCD_TO_INT", "i:INT;", "i := BCD_TO_INT(16#12);", "i", 12)
case("型別轉換", "TIME_TO_DINT", "d:DINT;", "d := TIME_TO_DINT(T#1s500ms);", "d", 1500)
case("型別轉換", "DINT_TO_TIME", "t:TIME;", "t := DINT_TO_TIME(250);", "t", 250)
case("型別轉換", "TO_INT(通用,CODESYS)", "i:INT;", "i := TO_INT(3.6);", "i", 4)
case("型別轉換", "TO_REAL(通用,CODESYS)", "r:REAL;", "r := TO_REAL(3);", "r", 3.0)
case("型別轉換", "BYTE_TO_WORD", "w:WORD;", "w := BYTE_TO_WORD(16#FF);", "w", 255)
case("型別轉換", "INT_TO_UINT(-1)", "u:UINT;", "u := INT_TO_UINT(-1);", "u", 65535)
case("型別轉換", "LREAL_TO_REAL", "r:REAL;", "r := LREAL_TO_REAL(2.25);", "r", 2.25)
# --- numerical
case("數值", "ABS", "i:INT;", "i := ABS(-5);", "i", 5)
case("數值", "SQRT", "r:REAL;", "r := SQRT(16.0);", "r", 4.0)
case("數值", "LN", "r:REAL;", "r := LN(1.0);", "r", 0.0)
case("數值", "LOG", "r:REAL;", "r := LOG(100.0);", "r", 2.0)
case("數值", "EXP", "r:REAL;", "r := EXP(0.0);", "r", 1.0)
case("數值", "SIN", "r:REAL;", "r := SIN(0.0);", "r", 0.0)
case("數值", "COS", "r:REAL;", "r := COS(0.0);", "r", 1.0)
case("數值", "TAN", "r:REAL;", "r := TAN(0.0);", "r", 0.0)
case("數值", "ASIN", "r:REAL;", "r := ASIN(0.0);", "r", 0.0)
case("數值", "ACOS", "r:REAL;", "r := ACOS(1.0);", "r", 0.0)
case("數值", "ATAN", "r:REAL;", "r := ATAN(0.0);", "r", 0.0)
case("數值", "ATAN2(第 3 版附加)", "r:REAL;", "r := ATAN2(1.0, 1.0);", "r", math.atan2(1, 1))
# --- arithmetic
case("算術", "ADD(函式形式)", "i:INT;", "i := ADD(1, 2, 3);", "i", 6)
case("算術", "SUB", "i:INT;", "i := SUB(5, 2);", "i", 3)
case("算術", "MUL", "i:INT;", "i := MUL(2, 3, 4);", "i", 24)
case("算術", "DIV(整數截斷)", "i:INT;", "i := DIV(-7, 2);", "i", -3)
case("算術", "MOD(函式形式)", "i:INT;", "i := MOD(7, 3);", "i", 1)
case("算術", "MOD 運算子(負數)", "i:INT;", "i := -7 MOD 3;", "i", -1)
case("算術", "EXPT", "r:REAL;", "r := EXPT(2.0, 3);", "r", 8.0)
case("算術", "** 運算子", "r:REAL;", "r := 2.0 ** 3;", "r", 8.0)
case("算術", "MOVE", "i:INT;", "i := MOVE(5);", "i", 5)
case("算術", "INT 溢位繞回", "i:INT := 32767;", "i := i + 1;", "i", -32768)
# --- bit shift
case("位移", "SHL WORD", "w:WORD := 16#8001;", "w := SHL(w, 1);", "w", 0x0002)
case("位移", "SHL 中間值依型別截斷", "w:WORD := 16#8000; b:BOOL;", "b := SHL(w, 1) = 0;", "b", True)
case("位移", "SHR WORD", "w:WORD := 16#8000;", "w := SHR(w, 15);", "w", 1)
case("位移", "ROL WORD", "w:WORD := 16#8001;", "w := ROL(w, 1);", "w", 0x0003)
case("位移", "ROL BYTE", "b:BYTE := 16#81;", "b := ROL(b, 1);", "b", 0x03)
case("位移", "ROR BYTE", "b:BYTE := 16#81;", "b := ROR(b, 1);", "b", 0xC0)
case("位移", "ROL DWORD", "d:DWORD := 16#80000001;", "d := ROL(d, 1);", "d", 3)
case("位移", "ROR DWORD", "d:DWORD := 16#00000001;", "d := ROR(d, 1);", "d", 0x80000000)
case("位移", "ROL n ≥ 寬度", "w:WORD := 16#0001;", "w := ROL(w, 17);", "w", 0x0002)
# --- bitwise
case("位元邏輯", "AND WORD", "w:WORD;", "w := 16#F0F0 AND 16#FF00;", "w", 0xF000)
case("位元邏輯", "OR / XOR WORD", "w:WORD;", "w := 16#F0F0 XOR 16#FF00;", "w", 0x0FF0)
case("位元邏輯", "NOT BYTE", "b:BYTE := 1;", "b := NOT b;", "b", 254)
case("位元邏輯", "NOT 中間值依型別截斷", "b:BYTE := 16#0F; x:BOOL;", "x := (NOT b) = 16#F0;", "x", True)
case("位元邏輯", "AND(函式形式)", "w:WORD;", "w := AND(16#FF, 16#0F);", "w", 0x0F)
case("位元邏輯", "NOT(函式形式)", "x:BOOL;", "x := NOT(FALSE);", "x", True)
# --- selection
case("選擇", "SEL", "i:INT;", "i := SEL(TRUE, 1, 2);", "i", 2)
case("選擇", "MAX(多引數)", "i:INT;", "i := MAX(3, 9, 2);", "i", 9)
case("選擇", "MIN(多引數)", "i:INT;", "i := MIN(3, 1, 2);", "i", 1)
case("選擇", "LIMIT", "i:INT;", "i := LIMIT(0, 120, 100);", "i", 100)
case("選擇", "MUX", "i:INT;", "i := MUX(1, 10, 20, 30);", "i", 20)
# --- comparison
case("比較", "運算子 > >= = <> <= <", "x:BOOL;", "x := (2 > 1) AND (1 <= 1) AND (1 <> 2);", "x", True)
case("比較", "GT(函式形式,可多引數)", "x:BOOL;", "x := GT(3, 2, 1);", "x", True)
case("比較", "EQ(函式形式)", "x:BOOL;", "x := EQ(2, 2);", "x", True)
case("比較", "GE/LE/LT/NE(函式形式)", "x:BOOL;", "x := NE(1, 2);", "x", True)
case("比較", "字串比較", "x:BOOL;", "x := 'ABC' < 'ABD';", "x", True)
# --- string
case("字串", "LEN", "i:INT;", "i := LEN('ABCDE');", "i", 5)
case("字串", "LEFT", "s:STRING;", "s := LEFT('ABCDE', 2);", "s", "AB")
case("字串", "RIGHT", "s:STRING;", "s := RIGHT('ABCDE', 2);", "s", "DE")
case("字串", "MID", "s:STRING;", "s := MID('ABCDE', 2, 2);", "s", "BC")
case("字串", "CONCAT(2 引數)", "s:STRING;", "s := CONCAT('AB', 'CD');", "s", "ABCD")
case("字串", "CONCAT(多引數)", "s:STRING;", "s := CONCAT('A', 'B', 'C');", "s", "ABC")
case("字串", "INSERT", "s:STRING;", "s := INSERT('ABCD', 'XY', 2);", "s", "ABXYCD")
case("字串", "DELETE", "s:STRING;", "s := DELETE('ABCDE', 2, 2);", "s", "ADE")
case("字串", "REPLACE", "s:STRING;", "s := REPLACE('ABCDE', 'XY', 2, 2);", "s", "AXYDE")
case("字串", "FIND", "i:INT;", "i := FIND('ABCDE', 'CD');", "i", 3)
case("字串", "STRING 長度上限 STRING(n)", "s:STRING(3);", "s := 'ABCDE';", "s", "ABC")
# --- time / date
case("時間日期", "TIME + TIME", "t:TIME;", "t := T#1s + T#500ms;", "t", 1500)
case("時間日期", "TIME * INT", "t:TIME;", "t := T#1s * 3;", "t", 3000)
case("時間日期", "TIME / INT", "t:TIME;", "t := T#1s / 4;", "t", 250)
case("時間日期", "ADD_TIME / SUB_TIME", "t:TIME;", "t := SUB_TIME(T#2s, T#500ms);", "t", 1500)
case("時間日期", "MUL_TIME / DIV_TIME", "t:TIME;", "t := MUL_TIME(T#1s, 2);", "t", 2000)
case("時間日期", "TIME 比較", "x:BOOL;", "x := T#1s > T#999ms;", "x", True)
case("時間日期", "TOD# 常數", "t:TOD;", "t := TOD#12:00:00;", "t", 43200000)
case("時間日期", "TIME_OF_DAY# 常數", "t:TIME_OF_DAY;", "t := TIME_OF_DAY#00:00:01;", "t", 1000)
case("時間日期", "D# 常數", "d:DATE;", "d := D#1970-01-02;", "d", 86400000)
case("時間日期", "DT# 常數", "d:DT;", "d := DT#1970-01-01-00:00:01;", "d", 1000)
case("時間日期", "ADD_TOD_TIME", "t:TOD;", "t := ADD_TOD_TIME(TOD#12:00:00, T#1h);", "t", 46800000)
case("時間日期", "SUB_TOD_TOD", "t:TIME;", "t := SUB_TOD_TOD(TOD#12:00:00, TOD#11:00:00);", "t", 3600000)
case("時間日期", "SUB_DATE_DATE", "t:TIME;", "t := SUB_DATE_DATE(D#1970-01-03, D#1970-01-02);", "t", 86400000)
case("時間日期", "ADD_DT_TIME", "d:DT;", "d := ADD_DT_TIME(DT#1970-01-01-00:00:00, T#1s);", "d", 1000)
case("時間日期", "CONCAT_DATE_TOD", "d:DT;", "d := CONCAT_DATE_TOD(D#1970-01-02, TOD#00:00:01);", "d", 86401000)
case("時間日期", "DT_TO_TOD / DT_TO_DATE", "t:TOD;", "t := DT_TO_TOD(DT#1970-01-02-00:00:05);", "t", 5000)
case("時間日期", "LTIME# 常數", "t:LTIME;", "t := LTIME#1s;", "t", 1000)
# --- types
case("基本型別", "LREAL / LINT", "r:LREAL; i:LINT;", "i := 9000000000; r := 1.0E300;", "i", 9000000000)
case("基本型別", "USINT / UDINT / ULINT", "u:USINT := 255;", "u := u + 1;", "u", 0)
case("基本型別", "LWORD", "w:LWORD;", "w := 16#FFFFFFFFFFFFFFFF;", "w", 2**64 - 1)
case("基本型別", "CHAR", "c:CHAR;", "c := 'a';", "c", "a")
case("基本型別", "WSTRING", "s:WSTRING;", 's := "ab";', "s", "ab")
case("基本型別", "REAL 32 位元精度", "r:REAL; x:BOOL;", "r := 0.1; x := r = 0.1;", "x", True, "IEC REAL 為 32 位元;兩邊皆轉為 REAL 時相等")

# --- standard FBs
FB = [
    ("標準 FB", "TON", "t:TON; q:BOOL;", "t(IN := TRUE, PT := T#20ms); q := t.Q;", "q", True, 3),
    ("標準 FB", "TOF", "t:TOF; q:BOOL;", "t(IN := FALSE, PT := T#20ms); q := t.Q;", "q", False, 3),
    ("標準 FB", "TP", "t:TP; q:BOOL;", "t(IN := TRUE, PT := T#100ms); q := t.Q;", "q", True, 2),
    ("標準 FB", "CTU", "c:CTU; v:INT;", "c(CU := NOT c.CU, PV := 5); v := c.CV;", "v", 2, 4),
    ("標準 FB", "CTD", "c:CTD; v:INT;", "c(CD := FALSE, LD := TRUE, PV := 5); v := c.CV;", "v", 5, 1),
    ("標準 FB", "CTUD", "c:CTUD; v:INT;", "c(CU := TRUE, PV := 5); v := c.CV;", "v", 1, 3),
    ("標準 FB", "CTU_DINT / CTU_UDINT(型別化)", "c:CTU_DINT; v:DINT;", "c(CU := TRUE, PV := 5); v := c.CV;", "v", 1, 1),
    ("標準 FB", "R_TRIG", "r:R_TRIG; n:INT;", "r(CLK := TRUE); IF r.Q THEN n := n + 1; END_IF;", "n", 1, 3),
    ("標準 FB", "F_TRIG", "f:F_TRIG; n:INT; s:BOOL := TRUE;", "f(CLK := s); s := FALSE; IF f.Q THEN n := n + 1; END_IF;", "n", 1, 3),
    ("標準 FB", "SR", "s:SR; q:BOOL;", "s(SET1 := TRUE, RESET := TRUE); q := s.Q1;", "q", True, 1),
    ("標準 FB", "RS", "s:RS; q:BOOL;", "s(SET := TRUE, RESET1 := TRUE); q := s.Q1;", "q", False, 1),
    ("標準 FB", "TON 經過時間 ET", "t:TON; e:TIME;", "t(IN := TRUE, PT := T#1s); e := t.ET;", "e", 20, 3),
    ("標準 FB", "LTON / TON_LTIME(第 3 版)", "t:LTON; q:BOOL;", "t(IN := TRUE, PT := T#20ms); q := t.Q;", "q", True, 3),
]


def run(decl, stmt, var, scans=1):
    src = f"PROGRAM P\nVAR\n{decl}\nEND_VAR\n{stmt}\nEND_PROGRAM\n"
    p = VirtualPLC(src, scan_ms=10)
    for _ in range(scans):
        p.scan()
    errs = [d.msg for d in check(src) if d.severity == "error"]
    return p.vars[var], errs


def same(a, b):
    if isinstance(b, float) and isinstance(a, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)
    return a == b and type(a) is type(b) if isinstance(b, (bool, str)) else a == b


def probe():
    rows = []
    for cat, name, decl, stmt, var, exp, note in C:
        rows.append((cat, name, *status(decl, stmt, var, exp, 1), note))
    for cat, name, decl, stmt, var, exp, scans in FB:
        rows.append((cat, name, *status(decl, stmt, var, exp, scans), ""))
    return rows


def status(decl, stmt, var, exp, scans):
    try:
        got, errs = run(decl, stmt, var, scans)
    except Exception as e:  # noqa: BLE001
        return "MISSING", f"{type(e).__name__}: {e}"[:90]
    if not same(got, exp):
        return "WRONG", f"得到 {got!r},應為 {exp!r}"
    if errs:
        return "CHECKER", errs[0][:90]
    return "OK", ""


if __name__ == "__main__":
    rows = probe()
    cnt = {}
    for r in rows:
        cnt[r[2]] = cnt.get(r[2], 0) + 1
    if "--summary" not in sys.argv:
        print("| 類別 | 項目 | 狀態 | 說明 |\n|---|---|---|---|")
        for cat, name, st, detail, note in rows:
            print(f"| {cat} | {name} | {st} | {(detail + ' ' + note).strip().replace('|', '/')} |")
    print(f"\n總計 {len(rows)} 項:", ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
