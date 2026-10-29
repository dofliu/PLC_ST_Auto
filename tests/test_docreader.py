import os
import tempfile
import unittest
import zipfile
import zlib

from plc_st.docreader import read_docx, read_pdf, read_document
from plc_st.rag import VectorStore

DOCX_XML = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>TON timer</w:t></w:r><w:r><w:t> PT usage</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>馬達自鎖</w:t></w:r></w:p></w:body></w:document>')


def make_docx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", DOCX_XML)


def make_pdf(path, text):
    content = f"BT /F1 12 Tf ({text}) Tj ET".encode()
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Filter /FlatDecode >>\nstream\n" + zlib.compress(content) + b"\nendstream\nendobj\n%%EOF")


class TestDocReader(unittest.TestCase):
    def test_docx(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.docx")
            make_docx(p)
            t = read_docx(p)
            self.assertIn("TON timer PT usage", t)
            self.assertIn("馬達自鎖", t)

    def test_pdf_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.pdf")
            make_pdf(p, r"CTU counts \(rising\) edges")
            self.assertIn("CTU counts (rising) edges", read_pdf(p))

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            read_document("x.bin")

    def test_rag_indexes_docs(self):
        with tempfile.TemporaryDirectory() as d:
            make_docx(os.path.join(d, "a.docx"))
            make_pdf(os.path.join(d, "b.pdf"), "R_TRIG rising edge detector")
            s = VectorStore()
            s.add_path(d)
            self.assertIn("TON", s.search("TON timer")[0][2])
            self.assertIn("R_TRIG", s.search("rising edge detector")[0][2])
