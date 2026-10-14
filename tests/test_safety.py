import tempfile
import unittest
from pathlib import Path
from tools.verificar_seguranca import scan

class TestSafety(unittest.TestCase):
    def test_finds_fake_token_without_revealing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            fake="sk-" + "proj-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
            (p/"demo.py").write_text('api_key="' + fake + '"',encoding="utf-8")
            issues,_=scan(p)
            self.assertTrue(issues)
            self.assertNotIn(fake,str(issues))

    def test_simple_code_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/"demo.py").write_text('print("ola")',encoding="utf-8")
            issues,_=scan(p)
            self.assertEqual(issues,[])

if __name__=="__main__":
    unittest.main()
