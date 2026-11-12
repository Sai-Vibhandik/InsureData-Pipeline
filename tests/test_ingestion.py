import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import _path  # noqa: F401
from insuredata import ingestion as ing


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_csv_json_and_lineage(self):
        (self.tmp / "a.csv").write_text("id,v\n1,x\n2,\n")
        (self.tmp / "b.json").write_text(json.dumps({"records": [{"id": 1, "v": None}]}))
        a, b = ing.read_any(self.tmp / "a.csv"), ing.read_any(self.tmp / "b.json")
        self.assertEqual(a["source_file"].iloc[0], "a.csv")
        self.assertTrue(pd.isna(a["v"].iloc[1]))
        self.assertEqual(len(b), 1)

    def test_excel_roundtrip(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl not installed")
        pd.DataFrame({"id": ["1"], "v": ["z"]}).to_excel(self.tmp / "x.xlsx", index=False)
        self.assertEqual(ing.read_any(self.tmp / "x.xlsx")["v"].iloc[0], "z")

    def test_errors(self):
        with self.assertRaises(ing.IngestionError): ing.read_any(self.tmp / "missing.csv")
        (self.tmp / "t.txt").write_text("x")
        with self.assertRaises(ing.IngestionError): ing.read_any(self.tmp / "t.txt")
        (self.tmp / "bad.json").write_text("{nope")
        with self.assertRaises(ing.IngestionError): ing.read_any(self.tmp / "bad.json")
        (self.tmp / "e.csv").write_text("")
        with self.assertRaises(ing.IngestionError): ing.read_any(self.tmp / "e.csv")
        with self.assertRaises(ing.IngestionError): ing.read_many([])

    def test_parallel_read_equals_serial(self):
        paths = []
        for i in range(4):
            p = self.tmp / f"f{i}.csv"; p.write_text(f"id\n{i}\n{i}b\n"); paths.append(p)
        pd.testing.assert_frame_equal(ing.read_many(paths), ing.read_many(paths, parallel=True))

    def test_check_columns(self):
        with self.assertRaises(ing.IngestionError):
            ing.check_columns(pd.DataFrame({"a": []}), ["a", "b"], "t")


if __name__ == "__main__":
    unittest.main()
