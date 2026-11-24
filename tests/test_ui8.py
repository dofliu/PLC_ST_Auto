"""UI8 靜態回歸:寬螢幕雙頁籤的標記、CSS 斷點、快捷鍵與記憶鍵存在。互動行為由 tests/ui_ui8.js 驗證。"""
import os
import unittest

HTML = os.path.join(os.path.dirname(__file__), "..", "plc_st", "web", "index.html")


class Ui8Static(unittest.TestCase):
    def setUp(self):
        with open(HTML, encoding="utf-8") as f:
            self.html = f.read()

    def test_toggle_button_only_on_wide_screens(self):
        self.assertIn('id="dualbtn" onclick="dualToggle()" aria-pressed="false"', self.html)
        self.assertIn("@media(min-width:1600px){#dualbtn{display:inline-flex}}", self.html)
        self.assertIn("const WIDE='(min-width:1600px)'", self.html)

    def test_secondary_select_lists_all_tabs(self):
        for t in ("gen", "sim", "test", "exp", "rag", "set"):
            self.assertIn(f'<option value="{t}">', self.html.split('id="tab2sel"')[1].split("</select>")[0])

    def test_dual_layout_css(self):
        self.assertIn("body.dual .tab.on2{grid-column:2", self.html)
        self.assertIn("nav button.on2{", self.html)

    def test_memory_and_split_keys(self):
        self.assertIn("mem.set('tab2',tab2)", self.html)
        self.assertIn("mem.set('dual',", self.html)
        self.assertIn("dualOn()?'split2':'split'", self.html)

    def test_export_refresh_also_when_secondary(self):
        self.assertIn("$('tab_exp').matches('.on,.on2')", self.html)


if __name__ == "__main__":
    unittest.main()
