"""RAG:文件切塊 + TF-IDF 向量庫(stdlib,可持久化為 JSON)。"""
import json
import math
import os
import re
from collections import Counter

TEXT_EXT = {".txt", ".md", ".st", ".csv", ".xml", ".json", ".rst"}


def tokenize(text):
    """英數詞 + CJK 單字/雙字(bigram),不分大小寫。"""
    text = text.lower()
    toks = re.findall(r"[a-z0-9_]+", text)
    for run in re.findall(r"[一-鿿]+", text):
        toks.extend(run)
        toks.extend(run[i:i + 2] for i in range(len(run) - 1))
    return toks


def chunk_text(text, size=800, overlap=100):
    """依段落累積切塊;超長段落以固定視窗硬切(含重疊)。"""
    chunks, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        while len(para) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(para[:size])
            para = para[size - overlap:]
        if cur and len(cur) + len(para) + 2 > size:
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return chunks


class VectorStore:
    def __init__(self):
        self.docs = []  # {"source", "text"}
        self._tf = []
        self._idf = {}

    def add_text(self, source, text, size=800, overlap=100):
        for c in chunk_text(text, size, overlap):
            self.docs.append({"source": source, "text": c})
        self._index()

    def add_file(self, path, **kw):
        ext = os.path.splitext(path)[1].lower()
        if ext not in TEXT_EXT:
            raise ValueError(f"unsupported document type: {ext or path}")
        with open(path, encoding="utf-8", errors="replace") as f:
            self.add_text(path, f.read(), **kw)

    def add_path(self, path, **kw):
        if os.path.isdir(path):
            for root, _, files in sorted(os.walk(path)):
                for n in sorted(files):
                    if os.path.splitext(n)[1].lower() in TEXT_EXT:
                        self.add_file(os.path.join(root, n), **kw)
        else:
            self.add_file(path, **kw)

    def _index(self):
        self._tf = [Counter(tokenize(d["text"])) for d in self.docs]
        df = Counter(t for tf in self._tf for t in tf)
        n = len(self.docs)
        self._idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}

    def _vec(self, tf):
        v = {t: (1 + math.log(c)) * self._idf[t] for t, c in tf.items() if t in self._idf}
        norm = math.sqrt(sum(x * x for x in v.values()))
        return v, norm

    def search(self, query, k=4, min_score=0.05):
        q, qn = self._vec(Counter(tokenize(query)))
        if not qn:
            return []
        out = []
        for d, tf in zip(self.docs, self._tf):
            v, vn = self._vec(tf)
            if not vn:
                continue
            s = sum(w * v.get(t, 0) for t, w in q.items()) / (qn * vn)
            if s >= min_score:
                out.append((s, d))
        out.sort(key=lambda x: -x[0])
        return [(s, d["source"], d["text"]) for s, d in out[:k]]

    def context(self, query, k=4):
        """回傳可直接傳給 build_prompt(context=) 的片段列表。"""
        return [f"[{src}]\n{text}" for _, src, text in self.search(query, k)]

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"docs": self.docs}, f, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        s = cls()
        s.docs = data["docs"]
        s._index()
        return s
