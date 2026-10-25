import os
import tempfile
import unittest

from plc_st.cli import main
from plc_st.llm import build_prompt
from plc_st.rag import VectorStore, chunk_text


class TestRAG(unittest.TestCase):
    def setUp(self):
        self.s = VectorStore()
        self.s.add_text("a.md", "TON on-delay timer: Q goes TRUE after PT elapses.\n\nCTU counts rising edges of CU up to PV.")
        self.s.add_text("b.md", "馬達啟動保持電路使用自鎖,按下停止鈕解除。\n\n溫度控制使用 PID 迴路。")

    def test_chunking(self):
        cs = chunk_text("x" * 2000, size=800, overlap=100)
        self.assertTrue(all(len(c) <= 800 for c in cs))
        self.assertEqual(chunk_text("a\n\nb", size=800), ["a\n\nb"])

    def test_search_en_and_cjk(self):
        self.assertIn("TON", self.s.search("on-delay timer TON")[0][2])
        self.assertIn("自鎖", self.s.search("馬達自鎖")[0][2])
        self.assertEqual(self.s.search("zzzz qqqq"), [])

    def test_persist_and_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "i.json")
            self.s.save(p)
            ctx = VectorStore.load(p).context("count rising edges")
            self.assertTrue(ctx and "CTU" in ctx[0])
            self.assertIn("Reference documentation", build_prompt("r", context=ctx)[1])

    def test_cli_index_search(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "i.json")
            self.assertEqual(main(["index", "examples/docs", "-o", p]), 0)
            self.assertEqual(main(["search", p, "TON timer PT"]), 0)
            self.assertEqual(main(["index", "README.md", "-o", p]), 0)

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            VectorStore().add_file("x.pdf")


if __name__ == "__main__":
    unittest.main()
