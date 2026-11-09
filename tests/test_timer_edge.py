"""計時器在邊緣那次呼叫 ET=0(IEC 語意)。舊版在邊緣那次就先加了一個掃描週期,
使計時器提早一個週期觸發,PT ≤ 掃描週期時延時完全消失(例:星三角 100ms 換相死區)。"""
import unittest

from plc_st.interpreter import VirtualPLC


def plc(decl, body, scan=100):
    return VirtualPLC(f"PROGRAM P VAR i : BOOL; {decl} END_VAR {body} END_PROGRAM", scan_ms=scan)


class TimerEdge(unittest.TestCase):
    def test_ton_short_pt_not_instant(self):
        p = plc("t : TON;", "t(IN := i, PT := T#100ms);")
        p.set_input("i", True)
        p.scan(1)
        self.assertFalse(p.get("t.Q"))
        self.assertEqual(p.get("t.ET"), 0)
        p.scan(1)
        self.assertTrue(p.get("t.Q"))
        self.assertEqual(p.get("t.ET"), 100)

    def test_ton_zero_pt_immediate(self):
        p = plc("t : TON;", "t(IN := i, PT := T#0ms);")
        p.set_input("i", True)
        p.scan(1)
        self.assertTrue(p.get("t.Q"))

    def test_ton_exact_timing(self):
        p = plc("t : TON;", "t(IN := i, PT := T#500ms);")
        p.set_input("i", True)
        p.scan(5)  # 呼叫於 0..400 ms
        self.assertFalse(p.get("t.Q"))
        p.scan(1)  # 500 ms
        self.assertTrue(p.get("t.Q"))

    def test_ton_restart_after_drop(self):
        p = plc("t : TON;", "t(IN := i, PT := T#200ms);")
        p.set_input("i", True)
        p.scan(3)
        self.assertTrue(p.get("t.Q"))
        p.set_input("i", False)
        p.scan(1)
        p.set_input("i", True)
        p.scan(1)
        self.assertFalse(p.get("t.Q"))
        self.assertEqual(p.get("t.ET"), 0)

    def test_tof_falling_edge(self):
        p = plc("t : TOF;", "t(IN := i, PT := T#100ms);")
        p.set_input("i", True)
        p.scan(1)
        p.set_input("i", False)
        p.scan(1)  # 下降緣那次:ET=0,Q 仍 TRUE
        self.assertTrue(p.get("t.Q"))
        p.scan(1)
        self.assertFalse(p.get("t.Q"))

    def test_tp_pulse_width(self):
        p = plc("t : TP;", "t(IN := i, PT := T#300ms);")
        p.set_input("i", True)
        highs = 0
        for _ in range(6):
            p.scan(1)
            highs += bool(p.get("t.Q"))
        self.assertEqual(highs, 3)  # 呼叫於 0,100,200 ms 為 TRUE,300 ms 結束

    def test_star_delta_dead_time_visible(self):
        src = """PROGRAM P VAR run : BOOL := TRUE; ts, td : TON; star, delta : BOOL; END_VAR
ts(IN := run, PT := T#500ms);
td(IN := run AND ts.Q, PT := T#100ms);
star := run AND NOT ts.Q;
delta := run AND td.Q AND NOT star;
END_PROGRAM"""
        p = VirtualPLC(src, scan_ms=100)
        trace = []
        for _ in range(8):
            p.scan(1)
            trace.append((p.get("star"), p.get("delta")))
        off = trace.index((False, False))
        self.assertEqual(trace[off + 1], (False, True))  # 先全斷一個週期,再投入三角形


if __name__ == "__main__":
    unittest.main()
