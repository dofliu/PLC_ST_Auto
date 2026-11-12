"""LLM provider 抽象(Gemini / OpenAI / Claude / Ollama),僅用標準庫 HTTP。
transport 可注入(測試用):transport(url, headers, payload) -> dict"""
import json
import os
import re
import urllib.request

from .checker import check, Issue
from .interpreter import STError

DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o",
    "claude": "claude-sonnet-5-5",
    "ollama": "llama3.1",
    "mock": "demo",
}
KEY_ENV = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY"}


def http_post_json(url, headers, payload, timeout=120):
    req = urllib.request.Request(url, json.dumps(payload).encode("utf-8"),
                                 {"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # URLError / HTTPError / JSON
        raise STError(f"LLM request failed: {e}")


class Provider:
    name = ""

    def __init__(self, model=None, api_key=None, base_url=None, transport=None):
        self.model = model or DEFAULT_MODELS[self.name]
        self.api_key = api_key or os.environ.get(KEY_ENV.get(self.name, ""), "")
        self.base_url = base_url
        self.transport = transport or http_post_json
        if self.name in KEY_ENV and not self.api_key and transport is None:
            raise STError(f"missing API key for {self.name} (set {KEY_ENV[self.name]})")

    def complete(self, system, user):
        raise NotImplementedError


class OpenAI(Provider):
    name = "openai"

    def complete(self, system, user):
        url = (self.base_url or "https://api.openai.com/v1") + "/chat/completions"
        d = self.transport(url, {"Authorization": f"Bearer {self.api_key}"}, {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        try:
            return d["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise STError(f"unexpected OpenAI response: {str(d)[:200]}")


class Claude(Provider):
    name = "claude"

    def complete(self, system, user):
        url = (self.base_url or "https://api.anthropic.com") + "/v1/messages"
        d = self.transport(url, {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, {
            "model": self.model, "max_tokens": 4096, "system": system,
            "messages": [{"role": "user", "content": user}]})
        try:
            return "".join(b.get("text", "") for b in d["content"])
        except (KeyError, TypeError, AttributeError):
            raise STError(f"unexpected Claude response: {str(d)[:200]}")


class Gemini(Provider):
    name = "gemini"

    def complete(self, system, user):
        base = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{self.model}:generateContent"
        d = self.transport(url, {"x-goog-api-key": self.api_key}, {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}]})
        try:
            return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            raise STError(f"unexpected Gemini response: {str(d)[:200]}")


class Ollama(Provider):
    name = "ollama"

    def complete(self, system, user):
        url = (self.base_url or "http://localhost:11434") + "/api/chat"
        d = self.transport(url, {}, {
            "model": self.model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        try:
            return d["message"]["content"]
        except (KeyError, TypeError):
            raise STError(f"unexpected Ollama response: {str(d)[:200]}")


class Mock(Provider):
    """離線示範 provider(不連網、不需金鑰):依 prompt 的點位表產生自保持程式。
    初稿故意引用一個未宣告的輸出 alarm_lamp,修正輪補上宣告,用來展示「產生 → 檢查 → 修正」流程。"""
    name = "mock"
    DEFAULT_DECL = [("VAR_INPUT", "start", "BOOL"), ("VAR_INPUT", "stop", "BOOL"), ("VAR_OUTPUT", "motor", "BOOL")]

    @staticmethod
    def _decls(user):
        m = re.search(r"Tag table \(declare these exactly\):\n(.*?)(?:\n\n|\Z)", user, re.S)
        if not m:
            return None
        out, sec = [], None
        for line in m.group(1).splitlines():
            t = line.strip()
            if re.fullmatch(r"VAR(_INPUT|_OUTPUT|_IN_OUT)?", t):
                sec = t
            elif sec and (d := re.match(r"(\w+)\s*:\s*([^;:=]+?)\s*(?::=|;)", t)):
                out.append((sec, d.group(1), d.group(2).strip().upper()))
        return out or None

    def complete(self, system, user):
        repair = "Your previous answer:" in user
        decls = self._decls(user.split("\n\nYour previous answer:")[0]) or self.DEFAULT_DECL
        bins = [n for s, n, t in decls if s == "VAR_INPUT" and t == "BOOL"]
        bouts = [n for s, n, t in decls if s == "VAR_OUTPUT" and t == "BOOL"]
        out_name = bouts[0] if bouts else "motor"
        extra = [] if bouts else [("VAR_OUTPUT", out_name, "BOOL")]
        if repair:
            extra.append(("VAR_OUTPUT", "alarm_lamp", "BOOL"))
        lines = ["(* mock provider: offline demo, not a real LLM *)", "PROGRAM Main"]
        for sec in ("VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR"):
            sel = [(n, t) for s, n, t in decls + extra if s == sec]
            if sel:
                lines.append(sec)
                lines += [f"  {n} : {t};" for n, t in sel]
                lines.append("END_VAR")
        if len(bins) >= 2:
            lines.append(f"{out_name} := ({bins[0]} OR {out_name}) AND NOT {bins[1]};")
        elif bins:
            lines.append(f"{out_name} := {bins[0]};")
        lines.append(f"alarm_lamp := NOT {out_name};")
        lines.append("END_PROGRAM")
        return "```st\n" + "\n".join(lines) + "\n```"


PROVIDERS = {c.name: c for c in (OpenAI, Claude, Gemini, Ollama, Mock)}
PROVIDERS["gpt"] = OpenAI
PROVIDERS["anthropic"] = Claude


def get_provider(name, **kw):
    try:
        return PROVIDERS[name.lower()](**kw)
    except KeyError:
        raise STError(f"unknown provider {name!r}; choose from {sorted(set(PROVIDERS))}")


SYSTEM_PROMPT = """You are an expert IEC 61131-3 Structured Text (ST) programmer.
Output exactly one complete PROGRAM ... END_PROGRAM in a single ```st code block, then nothing else.
Rules:
- Declare every variable in VAR_INPUT / VAR_OUTPUT / VAR sections before use; never write to VAR_INPUT.
- Use only standard IEC types and function blocks (TON, TOF, CTU, R_TRIG, F_TRIG) unless told otherwise.
- Do not invent functions, libraries or instructions. If the requirement is ambiguous, state the assumption in a (* comment *).
- Target vendor: {vendor}."""


def build_prompt(requirement, tags_text="", vendor="iec", context=None):
    """回傳 (system, user)。context 為 RAG 檢索片段列表(M6 使用)。"""
    parts = []
    if context:
        parts.append("Reference documentation (use only what is documented here):\n"
                     + "\n---\n".join(context))
    if tags_text.strip():
        parts.append("Tag table (declare these exactly):\n" + tags_text.strip())
    parts.append("Requirement:\n" + requirement.strip())
    return SYSTEM_PROMPT.format(vendor=vendor), "\n\n".join(parts)


def extract_st(text):
    """從 LLM 回覆取出 ST 程式碼(優先 ```st 區塊,否則 PROGRAM..END_PROGRAM)。"""
    m = re.search(r"```(?:st|iecst|pascal|structured-?text)?[ \t]*\n(.*?)```", text, re.S | re.I)
    if m:
        return m.group(1).strip() + "\n"
    m = re.search(r"\b(PROGRAM\b.*?END_PROGRAM)", text, re.S | re.I)
    if m:
        return m.group(1).strip() + "\n"
    raise STError("no ST code found in LLM response")


def generate(provider, requirement, tags_text="", vendor="iec", context=None):
    system, user = build_prompt(requirement, tags_text, vendor, context)
    return extract_st(provider.complete(system, user))


def build_repair_prompt(user, code, issues):
    """把上一輪程式碼與檢查錯誤附在原 prompt 後,要求修正。"""
    errs = "\n".join(f"- {i}" for i in issues)
    return (f"{user}\n\nYour previous answer:\n```st\n{code.strip()}\n```\n"
            f"The static checker / test scenario reported these errors:\n{errs}\n"
            "Fix all of them and output the complete corrected PROGRAM in one ```st block.")


def _scenario_issues(code, scenario, vendor):
    """以情境在虛擬 PLC 執行,不符/執行錯誤轉成 error Issue。"""
    from .scenario import run_scenario
    try:
        fails = run_scenario(code, scenario, profile=vendor)
    except STError as e:
        return [Issue("error", 0, f"scenario could not run: {e}")]
    return [Issue("error", 0, f"scenario step {f['step']}: {f['var']} expected {f['expected']!r} "
                              f"but program produced {f['actual']!r}") for f in fails]


def generate_checked(provider, requirement, tags_text="", vendor="iec", context=None, max_rounds=3,
                     scenario=None, on_round=None):
    """產生 → check(+情境驗證)→ 把 error 回饋 LLM 修正,最多 max_rounds 次修正。
    scenario 為 JSON 字串/dict(見 scenario.py);靜態檢查通過後才執行情境。
    on_round(round_no, code, issues) 於每一輪(含第 0 輪)評估後呼叫,供評測記錄每輪錯誤。
    回傳 (code, issues, rounds);issues 為最後一輪結果(含 warning)。"""
    system, user = build_prompt(requirement, tags_text, vendor, context)

    def evaluate(code):
        issues = check(code, vendor)
        if scenario is not None and not any(i.severity == "error" for i in issues):
            issues = issues + _scenario_issues(code, scenario, vendor)
        return issues

    code = extract_st(provider.complete(system, user))
    issues = evaluate(code)
    rounds = 0
    if on_round:
        on_round(rounds, code, issues)
    while rounds < max_rounds and any(i.severity == "error" for i in issues):
        rounds += 1
        errors = [i for i in issues if i.severity == "error"]
        code = extract_st(provider.complete(system, build_repair_prompt(user, code, errors)))
        issues = evaluate(code)
        if on_round:
            on_round(rounds, code, issues)
    return code, issues, rounds
