"""Tests for the double-programming toolkit. Run: pytest -q  (no SAS needed)."""
import csv
import os
import subprocess
import sys
from datetime import date

import pytest

import compare_datasets as cmp
import independent_adae as adae
import independent_adsl as adsl

HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED = os.path.join(HERE, "..", "docs", "expected_ae_summary.txt")


# ------------------------------------------------------------------ ADSL
@pytest.fixture(scope="module")
def adsl_rows():
    return adsl.build_adsl()


def by_id(rows, subjid):
    return next(r for r in rows if r["SUBJID"] == subjid)


def test_subject_counts(adsl_rows):
    assert len(adsl_rows) == 24
    assert sum(r["SAFFL"] == "Y" for r in adsl_rows) == 22
    assert {r["SUBJID"] for r in adsl_rows if r["SAFFL"] == "N"} == {"0005", "0020"}


def test_usubjid_keeps_leading_zeros(adsl_rows):
    assert by_id(adsl_rows, "0001")["USUBJID"].startswith("DEMO001-")
    assert by_id(adsl_rows, "0001")["USUBJID"].endswith("-0001")


def test_screen_failures_have_no_treatment_number(adsl_rows):
    sf = by_id(adsl_rows, "0005")
    assert sf["ARMCD"] == "SCRNFAIL" and sf["TRT01PN"] is None and sf["TRTSDT"] is None


def test_missing_last_dose_keeps_duration_missing(adsl_rows):
    r = by_id(adsl_rows, "0004")
    assert r["TRTSDT"] is not None and r["TRTEDT"] is None and r["TRTDURD"] is None


def test_duration_is_inclusive():
    row = adsl.derive_adsl([{"ARM": "Placebo", "ARMCD": "PBO", "AGE": 40,
                             "RFSTDTC": "2026-02-01", "RFENDTC": "2026-02-01"}])[0]
    assert row["TRTDURD"] == 1


@pytest.mark.parametrize("age,expected", [(17, ""), (18, "<65"), (64, "<65"), (65, ">=65"), (90, ">=65")])
def test_age_groups(age, expected):
    assert adsl.age_group(age) == expected


def test_date9_is_locale_independent():
    assert adsl.date9(date(2026, 2, 3)) == "03FEB2026"
    assert adsl.date9(None) == ""


# ------------------------------------------------------------------ ADAE and tables
def test_ae_table_matches_expected_file_exactly(adsl_rows):
    ae = adae.derive_adae(adsl.read_csv(adae.RAW_AE), adsl_rows)
    with open(EXPECTED, encoding="utf-8") as fh:
        assert adae.ae_table(ae, adsl_rows) == fh.read()


def test_pre_dose_and_screen_failure_aes_are_excluded(adsl_rows):
    ae = adae.derive_adae(adsl.read_csv(adae.RAW_AE), adsl_rows)
    assert not any(r["SUBJID"] == "0005" for r in ae)                    # screen failure dropped
    pre = [r for r in ae if r["SUBJID"] == "0001" and r["AESTDTC"] == "2026-01-30"]
    assert pre and pre[0]["TRTEMFL"] == "N"                              # before first dose


def test_severity_counts_use_worst_event_per_subject(adsl_rows):
    ae = adae.derive_adae(adsl.read_csv(adae.RAW_AE), adsl_rows)
    text = adae.severity_table(ae, adsl_rows)
    table = {l[:30].strip(): l[30:] for l in text.splitlines()[2:]}
    # cells are "n (pct%)" or "0"; Placebo column is 18 wide
    cell = lambda label, col: table[label][:18].strip() if col == 0 else table[label][18:].strip()
    assert [cell("Any TEAE", 0), cell("Any TEAE", 1)] == ["5 (45.5%)", "10 (90.9%)"]
    assert [cell("Mild", 0), cell("Mild", 1)] == ["0", "4 (36.4%)"]
    assert [cell("Moderate", 0), cell("Moderate", 1)] == ["2 (18.2%)", "6 (54.5%)"]
    assert [cell("Severe", 0), cell("Severe", 1)] == ["3 (27.3%)", "0"]


def test_percentages_round_half_up_not_half_even():
    assert adae.pct(1, 8) == "12.5"
    assert adae.pct(1, 16) == "6.3"       # 6.25 -> 6.3 (Python round() would give 6.2)
    assert adae.pct(1, 3) == "33.3"


def test_subject_counted_once_per_term():
    sl = [{"SUBJID": "1", "USUBJID": "S-1", "SAFFL": "Y", "TRT01P": "Placebo", "TRT01PN": 1,
           "TRTSDT": date(2026, 1, 1)}]
    ae_raw = [{"SUBJID": "1", "AETERM": "Headache", "AEBODSYS": "Nervous", "AESEV": "MILD",
               "AESTDTC": "2026-01-05", "AESER": "N"},
              {"SUBJID": "1", "AETERM": "Headache", "AEBODSYS": "Nervous", "AESEV": "SEVERE",
               "AESTDTC": "2026-01-09", "AESER": "N"}]
    out = adae.derive_adae(ae_raw, sl)
    assert "Headache" in adae.ae_table(out, sl) and "1 (100.0%)" in adae.ae_table(out, sl)
    severe = [l for l in adae.severity_table(out, sl).splitlines() if l.startswith("Severe")][0]
    assert severe.split(None, 1)[1] == "1 (100.0%)"            # counted once, at the worst severity


# ------------------------------------------------------------------ compare_datasets
BASE_COLS = ["USUBJID", "AGE", "SAFFL"]


def rows(*triples):
    return [dict(zip(BASE_COLS, t)) for t in triples]


def run(base, comp, **kw):
    return cmp.compare(BASE_COLS, base, BASE_COLS, comp, ["USUBJID"], **kw)


def test_identical_datasets_match():
    data = rows(("A", "40", "Y"), ("B", "50", "N"))
    assert run(data, [dict(r) for r in data]).matches


def test_value_difference_is_reported():
    res = run(rows(("A", "40", "Y")), rows(("A", "41", "Y")))
    assert not res.matches and res.diffs == [
        {"key": ("A",), "column": "AGE", "base": "40", "compare": "41"}]


def test_numeric_tolerance_and_text_equality():
    assert cmp.values_equal("62", "62.0")
    assert cmp.values_equal("0.1", "0.10000000001")
    assert not cmp.values_equal("Y", "y")                 # text is case-sensitive
    assert not cmp.values_equal("", "0")                  # missing is not zero


def test_missing_rows_and_columns_detected():
    res = cmp.compare(BASE_COLS, rows(("A", "1", "Y"), ("B", "2", "Y")),
                      ["USUBJID", "AGE", "EXTRA"], [{"USUBJID": "A", "AGE": "1", "EXTRA": "x"}],
                      ["USUBJID"])
    assert res.only_base_keys == [("B",)] and res.only_base_columns == ["SAFFL"]
    assert res.only_compare_columns == ["EXTRA"] and not res.matches


def test_duplicate_keys_are_an_error():
    with pytest.raises(ValueError, match="duplicate key"):
        run(rows(("A", "1", "Y"), ("A", "2", "Y")), rows(("A", "1", "Y")))


def test_cli_exit_codes(tmp_path):
    def write(name, body):
        p = tmp_path / name
        p.write_text(body)
        return str(p)
    a = write("a.csv", "usubjid,age\nA,40\n")
    b = write("b.csv", "USUBJID,AGE\nA,40.0\n")           # case + 40 vs 40.0 -> still a match
    c = write("c.csv", "USUBJID,AGE\nA,41\n")
    cmd = [sys.executable, os.path.join(HERE, "compare_datasets.py")]
    assert subprocess.run(cmd + [a, b, "--key", "USUBJID"], capture_output=True).returncode == 0
    assert subprocess.run(cmd + [a, c, "--key", "USUBJID"], capture_output=True).returncode == 1
    assert subprocess.run(cmd + [a, c, "--key", "NOPE"], capture_output=True).returncode == 2


# ------------------------------------------------------------------ end to end: injected error is caught
def test_injected_programming_error_is_found(tmp_path, adsl_rows):
    good = tmp_path / "good.csv"
    bad = tmp_path / "bad.csv"
    adsl.write_csv(adsl_rows, adsl.ADSL_COLUMNS, str(good))
    broken = [dict(r) for r in adsl_rows]
    by_id(broken, "0002")["TRTDURD"] = by_id(broken, "0002")["TRTDURD"] + 1     # off-by-one duration
    adsl.write_csv(broken, adsl.ADSL_COLUMNS, str(bad))
    b_cols, b_rows = cmp.read_table(str(good))
    c_cols, c_rows = cmp.read_table(str(bad))
    res = cmp.compare(b_cols, b_rows, c_cols, c_rows, ["USUBJID"])
    assert [(d["column"], d["key"][0].endswith("0002")) for d in res.diffs] == [("TRTDURD", True)]
