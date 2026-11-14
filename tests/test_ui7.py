"""UI7 靜態回歸:設定記憶不得包含 API Key;分欄/手機導覽/無障礙標記存在。互動行為由 tests/ui_e2e.js 72–83 驗證。"""
import os
import re
import unittest

HTML = os.path.join(os.path.dirname(__file__), "..", "plc_st", "web", "index.html")


class Ui7Static(unittest.TestCase):
    def setUp(self):
        with open(HTML, encoding="utf-8") as f:
            self.html = f.read()

    def mem_ids(self):
        m = re.search(r"const MEM_IDS=\[([^\]]*)\]", self.html)
        self.assertIsNotNone(m)
        return re.findall(r"'([^']+)'", m.group(1))

    def test_api_keys_never_persisted(self):
        ids = self.mem_ids()
        self.assertNotIn("key", ids)
        self.assertNotIn("embkey", ids)
        self.assertIn("MEM_NEVER=['key','embkey']", self.html)

    def test_persisted_ids_exist(self):
        for i in self.mem_ids():
            self.assertIn(f'id="{i}"', self.html, i)

    def test_splitter_is_accessible(self):
        self.assertRegex(self.html, r'id="split" role="separator"[^>]*tabindex="0"[^>]*aria-valuenow="50"')

    def test_mobile_nav_and_skip_link(self):
        self.assertIn('data-t="code" class="mcode"', self.html)
        self.assertIn('class="skip" href="#code"', self.html)
        self.assertIn("body:not(.mv-code) #codepane{display:none}", self.html)

    def test_drawer_toggle_keyboard(self):
        self.assertIn('role="button" tabindex="0" aria-controls="chkout" aria-expanded="false"', self.html)


if __name__ == "__main__":
    unittest.main()
