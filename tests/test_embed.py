import os
import tempfile
import unittest

from plc_st import STError
from plc_st.cli import main
from plc_st.embed import HashEmbedder, make_embedder, OpenAIEmbedder, OllamaEmbedder, GeminiEmbedder, cosine
from plc_st.rag import VectorStore

DOCS = [("a.md", "TON on-delay timer Q goes TRUE after PT elapses"), ("b.md", "CTU counts rising edges up to PV"),
        ("c.md", "馬達自鎖啟動保持電路")]


class TestEmbed(unittest.TestCase):
    def store(self, emb):
        s = VectorStore(emb)
        for src, t in DOCS:
            s.add_text(src, t)
        return s

    def test_hash_search(self):
        r = self.store(HashEmbedder()).search("on-delay timer TON", 1)
        self.assertEqual(r[0][1], "a.md")

    def test_remote_shapes(self):
        calls = []

        def tr(url, headers, payload):
            calls.append((url, payload))
            n = len(payload.get("input") or payload.get("requests"))
            vecs = [[1.0, float(i)] for i in range(n)]
            if "openai" in url:
                return {"data": [{"index": i, "embedding": v} for i, v in reversed(list(enumerate(vecs)))]}
            if "11434" in url:
                return {"embeddings": vecs}
            return {"embeddings": [{"values": v} for v in vecs]}
        for cls in (OpenAIEmbedder, OllamaEmbedder, GeminiEmbedder):
            e = cls(transport=tr)
            self.assertEqual(e.embed(["x", "y"]), [[1.0, 0.0], [1.0, 1.0]])
        self.assertTrue(calls[0][0].endswith("/embeddings"))

    def test_errors(self):
        with self.assertRaises(STError):
            make_embedder("nope")
        with self.assertRaises(STError):
            OpenAIEmbedder(api_key="")
        with self.assertRaises(STError):
            OllamaEmbedder(transport=lambda *a: {}).embed(["x"])

    def test_cosine(self):
        self.assertAlmostEqual(cosine([1, 0], [1, 0]), 1.0)
        self.assertEqual(cosine([0, 0], [1, 0]), 0.0)

    def test_persist_and_cli(self):
        with tempfile.TemporaryDirectory() as d:
            doc = os.path.join(d, "n.md")
            open(doc, "w").write("TON on-delay timer\n\n馬達自鎖")
            idx = os.path.join(d, "i.json")
            self.assertEqual(main(["index", doc, "-o", idx, "--embedder", "hash"]), 0)
            s = VectorStore.load(idx)
            self.assertIsInstance(s.embedder, HashEmbedder)
            self.assertTrue(s.search("TON timer", 1))
            self.assertEqual(main(["search", idx, "TON timer"]), 0)


if __name__ == "__main__":
    unittest.main()
