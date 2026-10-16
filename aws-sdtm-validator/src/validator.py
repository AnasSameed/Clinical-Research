"""
SDTM-style CSV validator.

Pure Python (standard library only) so the same logic runs locally, in unit
tests and inside AWS Lambda. Each check produces a Finding with a severity:

    ERROR   - the dataset breaks an SDTM rule and should not be used as-is
    WARNING - the data is legal but suspicious and worth a human look

Supported domains: DM (Demographics), AE (Adverse Events), VS (Vital Signs).
Any other domain still gets the generic checks.
"""

import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

ERROR = "ERROR"
WARNING = "WARNING"

# ISO 8601 as used in SDTM --DTC variables. Partial dates are allowed
# (e.g. "2024", "2024-03") because SDTM permits them for unknown parts.
ISO8601 = re.compile(
    r"^\d{4}"
    r"(-(0[1-9]|1[0-2])"
    r"(-(0[1-9]|[12]\d|3[01])"
    r"(T([01]\d|2[0-3])(:[0-5]\d(:[0-5]\d(\.\d+)?)?)?)?"
    r")?)?$"
)

DOMAIN_RULES = {
    "DM": {
        "label": "Demographics",
        "required": ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID",
                     "SEX", "AGE", "AGEU", "ARMCD", "ARM", "COUNTRY"],
        "expected": ["RFSTDTC", "RFENDTC", "RACE", "ETHNIC"],
        "codelists": {
            "SEX": {"M", "F", "U", "UNDIFFERENTIATED"},
            "AGEU": {"YEARS", "MONTHS", "WEEKS", "DAYS", "HOURS"},
        },
        "one_record_per_subject": True,
        "seq_var": None,
    },
    "AE": {
        "label": "Adverse Events",
        "required": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM",
                     "AEDECOD", "AESTDTC"],
        "expected": ["AEENDTC", "AESEV", "AESER", "AEREL", "AEOUT"],
        "codelists": {
            "AESEV": {"MILD", "MODERATE", "SEVERE"},
            "AESER": {"Y", "N"},
            "AEOUT": {"RECOVERED/RESOLVED", "RECOVERING/RESOLVING",
                      "NOT RECOVERED/NOT RESOLVED",
                      "RECOVERED/RESOLVED WITH SEQUELAE", "FATAL", "UNKNOWN"},
        },
        "one_record_per_subject": False,
        "seq_var": "AESEQ",
    },
    "VS": {
        "label": "Vital Signs",
        "required": ["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD",
                     "VSTEST", "VSORRES", "VSORRESU"],
        "expected": ["VSSTRESN", "VSSTRESU", "VISITNUM", "VSDTC"],
        "codelists": {
            "VSTESTCD": {"SYSBP", "DIABP", "PULSE", "RESP", "TEMP",
                         "HEIGHT", "WEIGHT", "BMI"},
        },
        "one_record_per_subject": False,
        "seq_var": "VSSEQ",
    },
}

# Plausibility ranges for VS standard results (warning only).
VS_RANGES = {
    "SYSBP": (60, 250), "DIABP": (30, 150), "PULSE": (30, 220),
    "RESP": (6, 60), "TEMP": (34, 42), "HEIGHT": (40, 230),
    "WEIGHT": (2, 300), "BMI": (10, 80),
}

MAX_FINDINGS_PER_RULE = 25  # keep reports readable for big files


@dataclass
class Finding:
    severity: str
    rule: str
    message: str
    row: int | None = None       # 1-based data row (header excluded)
    variable: str | None = None
    value: str | None = None


class _Collector:
    """Collects findings, capping how many are kept per rule."""

    def __init__(self):
        self.findings: list[Finding] = []
        self.counts: Counter = Counter()

    def add(self, severity, rule, message, row=None, variable=None, value=None):
        self.counts[(severity, rule)] += 1
        if self.counts[(severity, rule)] <= MAX_FINDINGS_PER_RULE:
            self.findings.append(Finding(severity, rule, message, row, variable,
                                         None if value is None else str(value)[:100]))


def _parse_iso(value: str):
    """Return a comparable datetime for complete dates, None for partial ones."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def detect_domain(rows: list[dict], filename: str) -> str | None:
    for r in rows:
        d = (r.get("DOMAIN") or "").strip().upper()
        if d:
            return d
    stem = filename.rsplit("/", 1)[-1].split(".")[0].upper()
    for d in DOMAIN_RULES:
        if stem == d or stem.startswith(d + "_"):
            return d
    return None


def validate_csv(text: str, filename: str = "dataset.csv") -> dict:
    """Validate CSV text and return a JSON-serialisable report."""
    out = _Collector()
    text = text.lstrip("﻿")  # tolerate Excel's UTF-8 BOM

    if not text.strip():
        out.add(ERROR, "FILE_EMPTY", "File is empty.")
        return _report(filename, None, [], [], out)

    reader = csv.reader(io.StringIO(text))
    raw_header = next(reader)
    header = [h.strip().upper() for h in raw_header]
    data = [r for r in reader if any(c.strip() for c in r)]

    dupes = [h for h, n in Counter(header).items() if n > 1]
    for h in dupes:
        out.add(ERROR, "DUPLICATE_COLUMN", f"Column '{h}' appears more than once.", variable=h)

    rows = []
    for i, r in enumerate(data, start=1):
        if len(r) != len(header):
            out.add(ERROR, "ROW_LENGTH",
                    f"Row has {len(r)} fields but header has {len(header)}.", row=i)
        rows.append({h: (r[j].strip() if j < len(r) else "") for j, h in enumerate(header)})

    for h in header:
        if len(h) > 8:
            out.add(WARNING, "VARNAME_LENGTH",
                    f"Variable name '{h}' is longer than 8 characters (SAS XPT limit).", variable=h)

    domain = detect_domain(rows, filename)
    rules = DOMAIN_RULES.get(domain or "")

    if not rows:
        out.add(ERROR, "NO_RECORDS", "File has a header but no data rows.")
        return _report(filename, domain, header, rows, out)

    if rules is None:
        out.add(WARNING, "UNKNOWN_DOMAIN",
                f"Domain '{domain or '?'}' has no specific rules; only generic checks ran.")
    else:
        for v in rules["required"]:
            if v not in header:
                out.add(ERROR, "REQUIRED_VARIABLE_MISSING",
                        f"Required variable {v} is missing.", variable=v)
        for v in rules["expected"]:
            if v not in header:
                out.add(WARNING, "EXPECTED_VARIABLE_MISSING",
                        f"Expected variable {v} is missing.", variable=v)

    _generic_checks(rows, header, domain, out)
    if rules:
        _codelist_checks(rows, rules, out)
        _subject_checks(rows, rules, out)
    if domain == "DM":
        _dm_checks(rows, out)
    elif domain == "AE":
        _ae_checks(rows, out)
    elif domain == "VS":
        _vs_checks(rows, out)

    return _report(filename, domain, header, rows, out)


def _generic_checks(rows, header, domain, out):
    if "DOMAIN" in header and domain:
        for i, r in enumerate(rows, 1):
            if r["DOMAIN"].upper() != domain:
                out.add(ERROR, "DOMAIN_MISMATCH",
                        f"DOMAIN is '{r['DOMAIN']}' but file is {domain}.",
                        row=i, variable="DOMAIN", value=r["DOMAIN"])

    if "STUDYID" in header:
        studies = {r["STUDYID"] for r in rows if r["STUDYID"]}
        if len(studies) > 1:
            out.add(ERROR, "MULTIPLE_STUDYID",
                    f"File contains {len(studies)} different STUDYID values: "
                    f"{', '.join(sorted(studies)[:5])}.", variable="STUDYID")
        for i, r in enumerate(rows, 1):
            if not r["STUDYID"]:
                out.add(ERROR, "MISSING_VALUE", "STUDYID is blank.", row=i, variable="STUDYID")

    if "USUBJID" in header:
        for i, r in enumerate(rows, 1):
            if not r["USUBJID"]:
                out.add(ERROR, "MISSING_VALUE", "USUBJID is blank.", row=i, variable="USUBJID")

    for v in (h for h in header if h.endswith("DTC")):
        for i, r in enumerate(rows, 1):
            val = r.get(v, "")
            if val and not ISO8601.match(val):
                out.add(ERROR, "INVALID_ISO8601",
                        f"{v} '{val}' is not an ISO 8601 date/time.",
                        row=i, variable=v, value=val)


def _codelist_checks(rows, rules, out):
    for var, allowed in rules["codelists"].items():
        for i, r in enumerate(rows, 1):
            val = r.get(var, "")
            if val and val.upper() not in allowed:
                out.add(ERROR, "CODELIST_VIOLATION",
                        f"{var} '{val}' is not in the controlled terminology "
                        f"({', '.join(sorted(allowed))}).",
                        row=i, variable=var, value=val)
            elif val and val != val.upper():
                out.add(WARNING, "CODELIST_CASE",
                        f"{var} '{val}' should be upper case.", row=i, variable=var, value=val)


def _subject_checks(rows, rules, out):
    if rules["one_record_per_subject"]:
        seen = {}
        for i, r in enumerate(rows, 1):
            u = r.get("USUBJID", "")
            if u and u in seen:
                out.add(ERROR, "DUPLICATE_SUBJECT",
                        f"USUBJID '{u}' appears more than once (first at row {seen[u]}).",
                        row=i, variable="USUBJID", value=u)
            seen.setdefault(u, i)

    seq = rules["seq_var"]
    if seq:
        per_subject = defaultdict(set)
        for i, r in enumerate(rows, 1):
            val = r.get(seq, "")
            if not val:
                out.add(ERROR, "MISSING_VALUE", f"{seq} is blank.", row=i, variable=seq)
                continue
            if not re.fullmatch(r"\d+", val):
                out.add(ERROR, "SEQ_NOT_INTEGER", f"{seq} '{val}' is not a positive integer.",
                        row=i, variable=seq, value=val)
                continue
            key = r.get("USUBJID", "")
            if val in per_subject[key]:
                out.add(ERROR, "DUPLICATE_SEQ",
                        f"{seq} {val} is repeated for USUBJID '{key}'.",
                        row=i, variable=seq, value=val)
            per_subject[key].add(val)


def _check_date_order(rows, start, end, out):
    for i, r in enumerate(rows, 1):
        s, e = _parse_iso(r.get(start, "")), _parse_iso(r.get(end, ""))
        if s and e and e < s:
            out.add(ERROR, "END_BEFORE_START",
                    f"{end} ({r[end]}) is before {start} ({r[start]}).",
                    row=i, variable=end, value=r[end])


def _dm_checks(rows, out):
    for i, r in enumerate(rows, 1):
        age, ageu = r.get("AGE", ""), r.get("AGEU", "")
        if age:
            try:
                a = float(age)
            except ValueError:
                a = None
                out.add(ERROR, "AGE_NOT_NUMERIC", f"AGE '{age}' is not numeric.",
                        row=i, variable="AGE", value=age)
            if a is not None and a < 0:
                out.add(ERROR, "AGE_NEGATIVE", f"AGE {age} is negative.",
                        row=i, variable="AGE", value=age)
            elif a is not None and a > 120 and ageu.upper() in ("", "YEARS"):
                out.add(WARNING, "AGE_IMPLAUSIBLE", f"AGE {age} years is implausible.",
                        row=i, variable="AGE", value=age)
            if not ageu:
                out.add(ERROR, "AGEU_MISSING", "AGE is populated but AGEU is blank.",
                        row=i, variable="AGEU")
        u, sub, site = r.get("USUBJID", ""), r.get("SUBJID", ""), r.get("SITEID", "")
        if u and sub and not u.endswith(sub):
            out.add(WARNING, "USUBJID_SUBJID_MISMATCH",
                    f"USUBJID '{u}' does not end with SUBJID '{sub}'.",
                    row=i, variable="USUBJID", value=u)
        if r.get("ARMCD") and len(r["ARMCD"]) > 20:
            out.add(ERROR, "ARMCD_LENGTH", "ARMCD is longer than 20 characters.",
                    row=i, variable="ARMCD", value=r["ARMCD"])
    _check_date_order(rows, "RFSTDTC", "RFENDTC", out)


def _ae_checks(rows, out):
    _check_date_order(rows, "AESTDTC", "AEENDTC", out)
    for i, r in enumerate(rows, 1):
        if r.get("AETERM") == "":
            out.add(ERROR, "MISSING_VALUE", "AETERM is blank.", row=i, variable="AETERM")
        if r.get("AETERM") and r.get("AEDECOD") == "":
            out.add(WARNING, "AEDECOD_MISSING",
                    f"AETERM '{r['AETERM']}' has no MedDRA preferred term (AEDECOD).",
                    row=i, variable="AEDECOD")
        if r.get("AEOUT", "").upper() == "FATAL" and r.get("AESER", "").upper() == "N":
            out.add(ERROR, "FATAL_NOT_SERIOUS",
                    "AEOUT is FATAL but AESER is N; a fatal event is always serious.",
                    row=i, variable="AESER", value=r["AESER"])


def _vs_checks(rows, out):
    for i, r in enumerate(rows, 1):
        val = r.get("VSSTRESN", "") or r.get("VSORRES", "")
        if not val:
            continue
        try:
            num = float(val)
        except ValueError:
            if "VSSTRESN" in r and r["VSSTRESN"]:
                out.add(ERROR, "VSSTRESN_NOT_NUMERIC", f"VSSTRESN '{val}' is not numeric.",
                        row=i, variable="VSSTRESN", value=val)
            continue
        rng = VS_RANGES.get(r.get("VSTESTCD", "").upper())
        if rng and not (rng[0] <= num <= rng[1]):
            out.add(WARNING, "VS_OUT_OF_RANGE",
                    f"{r['VSTESTCD']} result {val} is outside the plausible range "
                    f"{rng[0]}-{rng[1]}.", row=i, variable="VSSTRESN", value=val)


def _report(filename, domain, header, rows, out: _Collector) -> dict:
    errors = sum(n for (sev, _), n in out.counts.items() if sev == ERROR)
    warnings = sum(n for (sev, _), n in out.counts.items() if sev == WARNING)
    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    subjects = {r.get("USUBJID") for r in rows if r.get("USUBJID")}
    by_rule = [
        {"severity": sev, "rule": rule, "count": n}
        for (sev, rule), n in sorted(out.counts.items(),
                                     key=lambda kv: (kv[0][0] != ERROR, -kv[1]))
    ]
    return {
        "file": filename,
        "domain": domain,
        "domain_label": DOMAIN_RULES.get(domain or "", {}).get("label"),
        "status": status,
        "summary": {
            "records": len(rows),
            "subjects": len(subjects),
            "variables": len(header),
            "errors": errors,
            "warnings": warnings,
        },
        "rules_triggered": by_rule,
        "findings": [asdict(f) for f in out.findings],
        "validated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
