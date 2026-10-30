"""
Independent ADAE derivation, the AE summary table, and a maximum-severity table.

    python independent_adae.py                                   # writes the CSVs and tables to ./out
    python independent_adae.py --check ../docs/expected_ae_summary.txt   # also verifies the AE table

Rules (same as the SAS program 03_ae_summary.sas)
  * only the safety population (SAFFL = Y); AEs of screen failures are dropped
  * treatment-emergent (TRTEMFL = Y): AE start date on or after the first dose date
  * a subject is counted once per preferred term; percentages use the safety-population N per arm
New here: AESEVN (1/2/3) and a "subjects by maximum severity" table.
"""
from __future__ import annotations

import argparse
import difflib
import os
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Tuple

from independent_adsl import (ADSL_COLUMNS, RAW_DM, build_adsl, date9, iso_to_date, read_csv,
                              write_csv)

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_AE = os.path.join(HERE, "..", "data", "raw", "ae_raw.csv")
SEV_N = {"MILD": 1, "MODERATE": 2, "SEVERE": 3}
SEV_LABEL = {1: "Mild", 2: "Moderate", 3: "Severe"}
ADAE_COLUMNS = ["SUBJID", "AETERM", "AEBODSYS", "AESEV", "AESEVN", "AESTDTC", "AESER",
                "USUBJID", "TRT01P", "TRT01PN", "TRTSDT", "AESTDT", "TRTEMFL"]

# column widths measured from docs/expected_ae_summary.txt
W_SOC, W_PT, W_ARM = 56, 36, 18


# --------------------------------------------------------------------------- ADAE
def derive_adae(ae_rows: List[Dict[str, str]], adsl_rows: List[dict]) -> List[dict]:
    by_subject = {r["SUBJID"]: r for r in adsl_rows}
    adae = []
    for ae in ae_rows:
        sl = by_subject.get(ae["SUBJID"])
        if sl is None or sl["SAFFL"] != "Y":
            continue                                        # not in the safety population
        start = iso_to_date(ae["AESTDTC"])
        row = dict(ae)
        row.update({
            "AESEVN": SEV_N.get(ae["AESEV"]),
            "USUBJID": sl["USUBJID"],
            "TRT01P": sl["TRT01P"],
            "TRT01PN": sl["TRT01PN"],
            "TRTSDT": sl["TRTSDT"],
            "AESTDT": start,
            "TRTEMFL": "Y" if start and start >= sl["TRTSDT"] else "N",
        })
        adae.append(row)
    return adae


# --------------------------------------------------------------------------- tables
def pct(n: int, total: int) -> str:
    """One decimal, halves rounded up like SAS (Python's round() would round half to even)."""
    return str((Decimal(100 * n) / Decimal(total)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def cell(n: int, total: int) -> str:
    return f"{n} ({pct(n, total)}%)" if n else "0"


def arm_info(adsl_rows: List[dict]) -> Dict[int, Tuple[str, int]]:
    """{TRT01PN: (arm label, safety-population N)}."""
    info: Dict[int, List] = {}
    for r in adsl_rows:
        if r["SAFFL"] == "Y" and r["TRT01PN"] is not None:
            label, n = info.setdefault(r["TRT01PN"], [r["TRT01P"], 0])
            info[r["TRT01PN"]][1] = n + 1
    return {k: (v[0], v[1]) for k, v in sorted(info.items())}


def ae_table(adae: List[dict], adsl_rows: List[dict]) -> str:
    arms = arm_info(adsl_rows)
    subjects = defaultdict(set)                             # (soc, term, arm) -> subject ids
    for r in adae:
        if r["TRTEMFL"] == "Y":
            subjects[(r["AEBODSYS"], r["AETERM"], r["TRT01PN"])].add(r["USUBJID"])
    header = (f"{'System Organ Class':<{W_SOC}}{'Preferred Term':<{W_PT}}"
              + "".join(f"{f'{lab} (N={n})':<{W_ARM}}" for lab, n in arms.values()).rstrip())
    lines = ["Subjects with Treatment-Emergent Adverse Events (Safety Population)", header]
    for soc, term in sorted({(s, t) for s, t, _ in subjects}):
        cells = [cell(len(subjects.get((soc, term, a), ())), arms[a][1]) for a in arms]
        lines.append(f"{soc:<{W_SOC}}{term:<{W_PT}}"
                     + "".join(f"{c:<{W_ARM}}" for c in cells[:-1]) + cells[-1])
    return "\n".join(lines) + "\n"


def severity_table(adae: List[dict], adsl_rows: List[dict]) -> str:
    """Subjects with at least one TEAE, counted once at their worst severity."""
    arms = arm_info(adsl_rows)
    worst: Dict[Tuple[int, str], int] = {}
    for r in adae:
        if r["TRTEMFL"] == "Y" and r["AESEVN"]:
            k = (r["TRT01PN"], r["USUBJID"])
            worst[k] = max(worst.get(k, 0), r["AESEVN"])
    count = lambda a, sev=None: sum(1 for (arm, _), s in worst.items()                  # noqa: E731
                                    if arm == a and (sev is None or s == sev))
    label_w = 30
    lines = ["Subjects with Treatment-Emergent Adverse Events by Maximum Severity (Safety Population)",
             f"{'':<{label_w}}" + "".join(f"{f'{lab} (N={n})':<{W_ARM}}" for lab, n in arms.values()).rstrip()]
    rows = [("Any TEAE", None)] + [(SEV_LABEL[s], s) for s in (1, 2, 3)]
    for label, sev in rows:
        cells = [cell(count(a, sev), arms[a][1]) for a in arms]
        lines.append(f"{label:<{label_w}}" + "".join(f"{c:<{W_ARM}}" for c in cells[:-1]) + cells[-1])
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Independent ADAE + AE tables (double programming).")
    ap.add_argument("--dm-raw", default=RAW_DM)
    ap.add_argument("--ae-raw", default=RAW_AE)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--check", help="expected AE summary text; exit 1 if the table differs")
    args = ap.parse_args(argv)

    adsl = build_adsl(args.dm_raw)
    adae = derive_adae(read_csv(args.ae_raw), adsl)
    os.makedirs(args.out_dir, exist_ok=True)
    write_csv(adsl, ADSL_COLUMNS, os.path.join(args.out_dir, "adsl_python.csv"))
    write_csv(adae, ADAE_COLUMNS, os.path.join(args.out_dir, "adae_python.csv"))
    summary, severity = ae_table(adae, adsl), severity_table(adae, adsl)
    for name, text in (("ae_summary_python.txt", summary), ("ae_severity_python.txt", severity)):
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    print(summary)
    print(severity)
    n_te = sum(1 for r in adae if r["TRTEMFL"] == "Y")
    print(f"ADAE: {len(adae)} records in the safety population, {n_te} treatment-emergent")

    if args.check:
        with open(args.check, encoding="utf-8") as fh:
            expected = fh.read()
        if expected != summary:
            print("\nAE summary DIFFERS from the expected file:")
            print("".join(difflib.unified_diff(expected.splitlines(True), summary.splitlines(True),
                                                "expected", "python")))
            return 1
        print("AE summary matches the expected file exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
