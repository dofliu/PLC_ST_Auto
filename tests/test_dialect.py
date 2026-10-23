import unittest

from plc_st.checker import check


def warns(src, profile):
    return [str(i) for i in check(src, profile) if "dialect:" in str(i)]


class TestDialect(unittest.TestCase):
    def test_generic_clean(self):
        with open("examples/motor.st", encoding="utf-8") as f:
            src = f.read()
        self.assertEqual(warns(src, "iec"), [])
        self.assertEqual(warns(src, "codesys"), [])

    def test_shadow_name(self):
        src = "PROGRAM p\nVAR abs : INT; END_VAR\nabs := 1;\nEND_PROGRAM"
        self.assertTrue(warns(src, "iec"))

    def test_reserved_per_vendor(self):
        src = "PROGRAM p\nVAR this : INT; END_VAR\nthis := 1;\nEND_PROGRAM"
        self.assertTrue(warns(src, "codesys"))
        self.assertEqual(warns(src, "omron"), [])

    def test_mitsubishi_device_label(self):
        src = "PROGRAM p\nVAR X0 : BOOL; run : BOOL; END_VAR\nrun := X0;\nEND_PROGRAM"
        w = warns(src, "mitsubishi")
        self.assertEqual(len(w), 1)
        self.assertIn("X0", w[0])

    def test_rockwell(self):
        with open("examples/motor.st", encoding="utf-8") as f:
            w = warns(f.read(), "rockwell")
        self.assertTrue(any("T#" in m for m in w))
        self.assertTrue(any("TIMER" in m for m in w))

    def test_never_error(self):
        src = "PROGRAM p\nVAR X0 : BOOL; END_VAR\nX0 := TRUE;\nEND_PROGRAM"
        self.assertTrue(all(i.severity == "warning" for i in check(src, "mitsubishi")))


if __name__ == "__main__":
    unittest.main()
