"""文件文字擷取:純文字、docx(zip+XML)、PDF(有 pypdf 用 pypdf,否則 stdlib 簡易解析)。"""
import os
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOC_EXT = {".docx", ".pdf"}


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W + "p"):
        text = "".join(t.text or "" for t in p.iter(W + "t"))
        if text.strip():
            paras.append(text)
    return "\n\n".join(paras)


def _pdf_unescape(s):
    s = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 255]), s)
    return re.sub(rb"\\(.)", lambda m: {b"n": b"\n", b"t": b"\t"}.get(m.group(1), m.group(1)), s)


def read_pdf(path):
    try:
        from pypdf import PdfReader
        return "\n\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
    except ImportError:
        pass
    # stdlib fallback:解 FlateDecode 串流,抽 (..) Tj / [..] TJ 字串(僅支援簡單編碼的 PDF)
    with open(path, "rb") as f:
        data = f.read()
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        body = m.group(1)
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass
        if b"BT" not in body:
            continue
        for bt in re.findall(rb"BT(.*?)ET", body, re.S):
            line = []
            for s in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*(?:Tj|TJ|')|\[(.*?)\]\s*TJ", bt, re.S):
                if s[0]:
                    line.append(_pdf_unescape(s[0]))
                else:
                    line.extend(_pdf_unescape(x) for x in re.findall(rb"\(((?:\\.|[^\\)])*)\)", s[1]))
            if line:
                out.append(b"".join(line).decode("latin-1"))
    return "\n".join(out)


def read_document(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return read_docx(path)
    if ext == ".pdf":
        return read_pdf(path)
    raise ValueError(f"unsupported document type: {ext or path}")
