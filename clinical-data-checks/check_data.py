"""Run data-quality checks on the DM and AE CSVs and write a report.
Usage:  python check_data.py [dm.csv] [ae.csv]      (exit code 1 if findings)"""
import csv, sys
from checks import rules as R

def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def run(dm, ae):
    f = []
    f += R.required(dm, ["SUBJID", "SITEID", "AGE", "SEX", "ARM", "CONSENTDT"])
    f += R.unique(dm, "SUBJID")
    f += R.allowed(dm, "SEX", {"M", "F", "U"})
    f += R.numeric_range(dm, "AGE", 18, 90)
    f += R.iso_dates(dm, ["CONSENTDT", "FIRSTDOSE", "LASTDOSE"])
    f += R.date_order(dm, "CONSENTDT", "FIRSTDOSE")
    f += R.date_order(dm, "FIRSTDOSE", "LASTDOSE")
    f += R.allowed(ae, "AESEV", {"MILD", "MODERATE", "SEVERE"})
    f += R.allowed(ae, "AESER", {"Y", "N"})
    f += R.iso_dates(ae, ["AESTDTC"])
    f += R.orphans(ae, dm)
    return f

def report(findings):
    if not findings:
        return "No findings. All checks passed."
    by = {}
    for rule, sid, msg in findings:
        by.setdefault(rule, []).append((sid, msg))
    lines = [f"{len(findings)} finding(s)\n"]
    for rule in sorted(by):
        lines.append(f"[{rule}] {len(by[rule])}")
        lines += [f"   subject {s}: {m}" for s, m in by[rule]]
    return "\n".join(lines)

if __name__ == "__main__":
    dm_path = sys.argv[1] if len(sys.argv) > 1 else "data/dm_raw.csv"
    ae_path = sys.argv[2] if len(sys.argv) > 2 else "data/ae_raw.csv"
    out = report(run(load(dm_path), load(ae_path)))
    print(out)
    sys.exit(0 if out.startswith("No findings") else 1)
