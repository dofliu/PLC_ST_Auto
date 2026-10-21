import unittest

from plc_st import VirtualPLC, STError
from plc_st.cli import main

SRC = """PROGRAM p
VAR x : INT := 32767; END_VAR
x := x + 1;
END_PROGRAM"""


class TestProfiles(unittest.TestCase):
    def test_overflow_modes(self):
        for prof, want in (("iec", -32768), ("saturate", 32767)):
            plc = VirtualPLC(SRC, profile=prof)
            plc.scan()
            self.assertEqual(plc.get("x"), want, prof)
        with self.assertRaises(STError):
            VirtualPLC(SRC, profile="strict").scan()

    def test_type_support(self):
        src = "PROGRAM p VAR a : UINT; END_VAR a := 1; END_PROGRAM"
        VirtualPLC(src, profile="codesys")
        with self.assertRaises(STError):
            VirtualPLC(src, profile="rockwell")
        with self.assertRaises(STError):
            VirtualPLC("PROGRAM p VAR a : LINT; END_VAR a := 1; END_PROGRAM", profile="siemens-s7-1200")

    def test_unknown_profile_and_list(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC, profile="nope")
        self.assertEqual(main(["profiles"]), 0)


if __name__ == "__main__":
    unittest.main()
