"""
Independent (second-programmer) derivation of SDTM DM and ADaM ADSL in plain Python.

The SAS programs in ../programs build DM and ADSL from data/raw/dm_raw.csv. This module
re-derives the same datasets from the written rules in the README (not by translating the SAS
line by line), so the two outputs can be compared. That is "double programming": two
independent implementations of one specification, any difference is investigated.

    python independent_adsl.py                      # writes adsl_python.csv
    python independent_adsl.py --raw ../data/raw/dm_raw.csv --out adsl_python.csv

Standard library only (Python 3.9+).
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import date
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DM = os.path.join(HERE, "..", "data", "raw", "dm_raw.csv")

STUDYID = "DEMO001"
ARMCD = {"Placebo": "PBO", "Drug 10 mg": "TRT10", "Screen Failure": "SCRNFAIL"}
TRT01PN = {"PBO": 1, "TRT10": 2}                       # screen failures get no numeric treatment
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# same variables, same order as the SAS ADSL (DM variables first, then the derived ones)
ADSL_COLUMNS = ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID", "AGE", "AGEU", "SEX", "RACE",
                "ARM", "ARMCD", "RFICDTC", "RFSTDTC", "RFENDTC", "TRT01P", "TRT01PN",
                "TRTSDT", "TRTEDT", "SAFFL", "AGEGR1", "TRTDURD"]


# --------------------------------------------------------------------------- helpers
def read_csv(path: str) -> List[Dict[str, str]]:
    """Read a CSV with every value kept as text (so subject id 0001 stays 0001)."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def iso_to_date(text: str) -> Optional[date]:
    """'2026-02-03' -> date; blank -> None (a missing date stays missing, never 'today')."""
    text = (text or "").strip()
    return date.fromisoformat(text) if text else None


def date9(d: Optional[date]) -> str:
    """SAS DATE9. style: 03FEB2026 (blank for missing)."""
    return f"{d.day:02d}{MONTHS[d.month - 1]}{d.year}" if d else ""


def write_csv(rows: List[dict], columns: List[str], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_fmt(row.get(c)) for c in columns])


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return date9(value)
    return str(value)


# --------------------------------------------------------------------------- derivations
def derive_dm(raw_rows: List[Dict[str, str]]) -> List[dict]:
    """Simplified SDTM DM: identifiers, planned arm, ISO 8601 reference dates."""
    dm = []
    for r in raw_rows:
        dm.append({
            "STUDYID": STUDYID,
            "DOMAIN": "DM",
            "USUBJID": f"{STUDYID}-{r['SITEID']}-{r['SUBJID']}",
            "SUBJID": r["SUBJID"],
            "SITEID": r["SITEID"],
            "AGE": int(r["AGE"]),
            "AGEU": "YEARS",
            "SEX": r["SEX"],
            "RACE": r["RACE"],
            "ARM": r["ARM"],
            "ARMCD": ARMCD.get(r["ARM"], ""),
            "RFICDTC": r["CONSENTDT"],
            "RFSTDTC": r["FIRSTDOSE"],
            "RFENDTC": r["LASTDOSE"],
        })
    return dm


def age_group(age: int) -> str:
    """>=65 -> '>=65'; 18 to 64 -> '<65'; under 18 stays blank (outside the defined groups)."""
    if age >= 65:
        return ">=65"
    if age >= 18:
        return "<65"
    return ""


def derive_adsl(dm_rows: List[dict]) -> List[dict]:
    """ADSL rules: see README. Dates are real `date` objects here and formatted on output."""
    adsl = []
    for d in dm_rows:
        trtsdt = iso_to_date(d["RFSTDTC"])
        trtedt = iso_to_date(d["RFENDTC"])
        row = dict(d)
        row.update({
            "TRT01P": d["ARM"],
            "TRT01PN": TRT01PN.get(d["ARMCD"]),
            "TRTSDT": trtsdt,
            "TRTEDT": trtedt,
            "SAFFL": "Y" if trtsdt else "N",                       # received at least one dose
            "AGEGR1": age_group(d["AGE"]),
            "TRTDURD": (trtedt - trtsdt).days + 1 if trtsdt and trtedt else None,   # inclusive
        })
        adsl.append(row)
    return adsl


def build_adsl(raw_path: str = RAW_DM) -> List[dict]:
    return derive_adsl(derive_dm(read_csv(raw_path)))


# --------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Independent ADSL derivation (double programming).")
    ap.add_argument("--raw", default=RAW_DM, help="raw demographics CSV")
    ap.add_argument("--out", default="adsl_python.csv", help="output CSV")
    args = ap.parse_args(argv)
    adsl = build_adsl(args.raw)
    write_csv(adsl, ADSL_COLUMNS, args.out)
    n_saf = sum(1 for r in adsl if r["SAFFL"] == "Y")
    print(f"{len(adsl)} subjects, {n_saf} in the safety population -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
