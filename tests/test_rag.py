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

    def test_invalid_chunk_params(self):
        # 回歸:size == overlap 時舊版硬切迴圈不會前進
        for size, overlap in [(100, 100), (100, 150), (0, 0), (100, -1)]:
            with self.assertRaises(ValueError):
                chunk_text("x" * 500, size=size, overlap=overlap)
        self.assertEqual(main(["index", "examples/docs", "-o", os.devnull]), 0)

    def test_reindex_excludes_output_in_input_dir(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "doc.md"), "w", encoding="utf-8") as f:
                f.write("TON on-delay timer.\n\nCTU counter.")
            out = os.path.join(d, "idx.json")
            self.assertEqual(main(["index", d, "-o", out]), 0)
            first = VectorStore.load(out).docs
            self.assertEqual(main(["index", d, "-o", out]), 0)
            second = VectorStore.load(out).docs
            self.assertEqual(first, second)
            self.assertTrue(all(doc["source"].endswith("doc.md") for doc in second))

    def test_add_path_indexes_once(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(5):
                with open(os.path.join(d, f"{i}.md"), "w", encoding="utf-8") as f:
                    f.write(f"document {i} about timers")
            s = VectorStore()
            calls = []
            orig = s._index
            s._index = lambda: (calls.append(1), orig())
            s.add_path(d)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(s.docs), 5)
            self.assertTrue(s.search("timers"))

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            VectorStore().add_file("x.bin")


if __name__ == "__main__":
    unittest.main()
