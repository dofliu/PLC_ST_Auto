"""可替換 embedding provider(local hash / OpenAI / Ollama / Gemini),僅用標準庫 HTTP。
transport 可注入(測試用):transport(url, headers, payload) -> dict"""
import hashlib
import math
import os

from .interpreter import STError
from .llm import http_post_json
from .rag import tokenize


class Embedder:
    name = ""
    default_model = ""

    def __init__(self, model=None, api_key=None, base_url=None, transport=None):
        self.model = model or self.default_model
        self.api_key = api_key or os.environ.get({"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}.get(self.name, ""), "")
        self.base_url = base_url
        self.transport = transport or http_post_json
        if self.name in ("openai", "gemini") and not self.api_key and transport is None:
            raise STError(f"missing API key for {self.name} embeddings")

    def embed(self, texts):
        raise NotImplementedError

    def spec(self):
        return {"name": self.name, "model": self.model, "base_url": self.base_url}


class HashEmbedder(Embedder):
    """離線雜湊詞袋向量(無需網路/金鑰;可驗證 dense 管線)。"""
    name = "hash"
    dim = 256

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in tokenize(t):
                h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
                v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
            out.append(v)
        return out


class OpenAIEmbedder(Embedder):
    name = "openai"
    default_model = "text-embedding-3-small"

    def embed(self, texts):
        url = (self.base_url or "https://api.openai.com/v1") + "/embeddings"
        d = self.transport(url, {"Authorization": f"Bearer {self.api_key}"}, {"model": self.model, "input": texts})
        try:
            return [x["embedding"] for x in sorted(d["data"], key=lambda x: x.get("index", 0))]
        except (KeyError, TypeError):
            raise STError(f"unexpected OpenAI embeddings response: {str(d)[:200]}")


class OllamaEmbedder(Embedder):
    name = "ollama"
    default_model = "nomic-embed-text"

    def embed(self, texts):
        url = (self.base_url or "http://localhost:11434") + "/api/embed"
        d = self.transport(url, {}, {"model": self.model, "input": texts})
        try:
            return d["embeddings"]
        except (KeyError, TypeError):
            raise STError(f"unexpected Ollama embeddings response: {str(d)[:200]}")


class GeminiEmbedder(Embedder):
    name = "gemini"
    default_model = "text-embedding-004"

    def embed(self, texts):
        base = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        reqs = [{"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}} for t in texts]
        d = self.transport(f"{base}/models/{self.model}:batchEmbedContents", {"x-goog-api-key": self.api_key}, {"requests": reqs})
        try:
            return [e["values"] for e in d["embeddings"]]
        except (KeyError, TypeError):
            raise STError(f"unexpected Gemini embeddings response: {str(d)[:200]}")


EMBEDDERS = {c.name: c for c in (HashEmbedder, OpenAIEmbedder, OllamaEmbedder, GeminiEmbedder)}


def make_embedder(name, **kw):
    try:
        return EMBEDDERS[name](**kw)
    except KeyError:
        raise STError(f"unknown embedder {name!r}; available: {', '.join(EMBEDDERS)}") from None


def cosine(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0
