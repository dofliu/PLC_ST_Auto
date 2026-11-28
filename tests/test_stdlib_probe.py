"""A1:標準函式庫探測的回歸保護 —— 已標示 OK 的項目不得退步,覆蓋率只能上升。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import stdlib_probe  # noqa: E402

BASELINE_OK = 60  # 2026-11-28 A1 盤點;A2 完成後調高


class TestStdlibProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = stdlib_probe.probe()

    def test_count_and_categories(self):
        self.assertGreaterEqual(len(self.rows), 112)
        self.assertEqual({r[0] for r in self.rows} >= {"型別轉換", "字串", "時間日期", "標準 FB", "位移"}, True)

    def test_no_regression(self):
        ok = sum(1 for r in self.rows if r[2] == "OK")
        self.assertGreaterEqual(ok, BASELINE_OK, [r[:4] for r in self.rows if r[2] != "OK"])

    def test_core_items_ok(self):
        must = {"TON", "TOF", "TP", "CTU", "CTD", "CTUD", "R_TRIG", "F_TRIG", "SR", "RS", "SEL", "LIMIT",
                "MAX(多引數)", "MIN(多引數)", "ROL WORD", "SHL WORD", "TIME + TIME", "MOD 運算子(負數)"}
        status = {r[1]: r[2] for r in self.rows}
        self.assertEqual({m: status[m] for m in must if status[m] != "OK"}, {})

    def test_doc_matches_probe(self):
        doc = open(os.path.join(os.path.dirname(__file__), "..", "docs", "stdlib_coverage.md"), encoding="utf-8").read()
        for r in self.rows:
            self.assertIn(f"| {r[1]} |", doc)


if __name__ == "__main__":
    unittest.main()
