"""CSV 點位表 → ST 變數宣告。欄位: name,type,direction,init,comment"""
import csv
import io
import re

from .interpreter import STError

SECTIONS = {"IN": "VAR_INPUT", "OUT": "VAR_OUTPUT", "INOUT": "VAR_IN_OUT", "VAR": "VAR"}
ORDER = ["VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR"]


def parse_tags(text):
    rows = []
    for i, r in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        if not r.get("name"):
            continue
        d = (r.get("direction") or "VAR").upper()
        if d not in SECTIONS:
            raise STError(f"tag table line {i}: bad direction {d!r}")
        if not r.get("type"):
            raise STError(f"tag table line {i}: missing type")
        rows.append({"name": r["name"], "type": r["type"].upper(), "section": SECTIONS[d],
                     "init": r.get("init", ""), "comment": r.get("comment", "")})
    return rows


def tags_to_var_blocks(text):
    rows = parse_tags(text)
    out = []
    for sec in ORDER:
        sel = [r for r in rows if r["section"] == sec]
        if not sel:
            continue
        out.append(sec)
        for r in sel:
            line = f"  {r['name']} : {r['type']}"
            if r["init"]:
                line += f" := {r['init']}"
            line += ";"
            if r["comment"]:
                line += f" (* {r['comment'].replace('*)', '* )')} *)"
            out.append(line)
        out.append("END_VAR")
    return "\n".join(out) + "\n"


IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


def preview_tags(text):
    """點位表預覽(不中斷):每列附 line、section 與 error;回傳 {"rows": [...], "errors": n}。
    與 parse_tags 同樣的規則,另外檢查識別字格式與重複名稱(不分大小寫)。"""
    rows, seen = [], {}
    try:
        reader = csv.DictReader(io.StringIO(text))
        for i, r in enumerate(reader, start=2):
            r = {(k or "").strip().lower(): (v or "").strip() if isinstance(v, str) else "" for k, v in r.items()}
            if not any(r.values()):
                continue
            d = (r.get("direction") or "VAR").upper()
            row = {"line": i, "name": r.get("name", ""), "type": (r.get("type") or "").upper(),
                   "direction": d, "section": SECTIONS.get(d, ""), "init": r.get("init", ""),
                   "comment": r.get("comment", ""), "error": None}
            if not row["name"]:
                row["error"] = "缺少 name"
            elif not IDENT.match(row["name"]):
                row["error"] = f"name {row['name']!r} 不是合法識別字"
            elif row["name"].lower() in seen:
                row["error"] = f"與第 {seen[row['name'].lower()]} 行名稱重複"
            elif d not in SECTIONS:
                row["error"] = f"direction {d!r} 應為 IN / OUT / INOUT / VAR"
            elif not row["type"]:
                row["error"] = "缺少 type"
            if row["name"]:
                seen.setdefault(row["name"].lower(), i)
            rows.append(row)
    except csv.Error as e:
        return {"rows": rows, "errors": len([r for r in rows if r["error"]]) + 1, "fatal": f"CSV 格式錯誤:{e}"}
    return {"rows": rows, "errors": len([r for r in rows if r["error"]]), "fatal": None}
