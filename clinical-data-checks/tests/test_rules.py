import unittest
from checks import rules as R

class T(unittest.TestCase):
    def test_required(self):
        self.assertEqual(len(R.required([{"SUBJID": "1", "SEX": ""}], ["SEX"])), 1)
    def test_unique(self):
        self.assertEqual(len(R.unique([{"SUBJID": "1"}, {"SUBJID": "1"}], "SUBJID")), 1)
    def test_allowed(self):
        self.assertEqual(len(R.allowed([{"SUBJID": "1", "SEX": "X"}], "SEX", {"M", "F"})), 1)
        self.assertEqual(R.allowed([{"SUBJID": "1", "SEX": "M"}], "SEX", {"M", "F"}), [])
    def test_iso(self):
        self.assertEqual(len(R.iso_dates([{"SUBJID": "1", "D": "03/04/2026"}], ["D"])), 1)
        self.assertEqual(R.iso_dates([{"SUBJID": "1", "D": "2026-03-04"}], ["D"]), [])
    def test_date_order(self):
        r = [{"SUBJID": "1", "A": "2026-02-01", "B": "2026-01-01"}]
        self.assertEqual(len(R.date_order(r, "A", "B")), 1)
    def test_range(self):
        self.assertEqual(len(R.numeric_range([{"SUBJID": "1", "AGE": "150"}], "AGE", 18, 90)), 1)
    def test_orphans(self):
        self.assertEqual(len(R.orphans([{"SUBJID": "9"}], [{"SUBJID": "1"}])), 1)

if __name__ == "__main__":
    unittest.main()
