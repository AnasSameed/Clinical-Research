"""Reusable data-quality rules. Each rule takes a list of row dicts and returns
a list of findings: (rule_name, subject_id, message). Standard library only."""
from datetime import date

def _d(s):
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None

def required(rows, cols, key="SUBJID"):
    return [("REQUIRED", r.get(key, "?"), f"{c} is missing")
            for r in rows for c in cols if not (r.get(c) or "").strip()]

def unique(rows, col):
    seen, out = {}, []
    for r in rows:
        seen[r[col]] = seen.get(r[col], 0) + 1
    return [("UNIQUE", k, f"{col} appears {n} times") for k, n in seen.items() if n > 1]

def allowed(rows, col, values, key="SUBJID"):
    return [("CT", r.get(key, "?"), f"{col}='{r[col]}' not in {sorted(values)}")
            for r in rows if (r.get(col) or "").strip() and r[col] not in values]

def iso_dates(rows, cols, key="SUBJID"):
    return [("ISO8601", r.get(key, "?"), f"{c}='{r[c]}' is not YYYY-MM-DD")
            for r in rows for c in cols if (r.get(c) or "").strip() and _d(r[c]) is None]

def date_order(rows, first, second, key="SUBJID"):
    out = []
    for r in rows:
        a, b = _d(r.get(first)), _d(r.get(second))
        if a and b and b < a:
            out.append(("DATE_ORDER", r.get(key, "?"), f"{second} ({b}) is before {first} ({a})"))
    return out

def numeric_range(rows, col, lo, hi, key="SUBJID"):
    out = []
    for r in rows:
        v = (r.get(col) or "").strip()
        if not v:
            continue
        try:
            n = float(v)
        except ValueError:
            out.append(("RANGE", r.get(key, "?"), f"{col}='{v}' is not numeric")); continue
        if not lo <= n <= hi:
            out.append(("RANGE", r.get(key, "?"), f"{col}={n:g} outside {lo}-{hi}"))
    return out

def orphans(child_rows, parent_rows, key="SUBJID"):
    ids = {r[key] for r in parent_rows}
    return [("ORPHAN", r[key], f"record has no matching subject in parent dataset")
            for r in child_rows if r[key] not in ids]
