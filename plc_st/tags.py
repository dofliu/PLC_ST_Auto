"""CSV 點位表 → ST 變數宣告。欄位: name,type,direction,init,comment"""
import csv
import io

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
