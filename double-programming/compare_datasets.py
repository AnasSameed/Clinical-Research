"""
Compare two datasets (CSV exports), the way PROC COMPARE does for double programming.

    python compare_datasets.py adsl_sas.csv adsl_python.csv --key USUBJID
    python compare_datasets.py adae_sas.csv adae_python.csv --key USUBJID AETERM AESTDTC --tol 1e-8

Reports rows and columns present in only one file and every cell whose value differs.
Exit code 0 = datasets match, 1 = differences found, 2 = unusable input (for example duplicate keys).

Comparison rules
  * column names are matched case-insensitively; column order does not matter
  * leading/trailing spaces are ignored; blank means missing; blank vs blank matches
  * values that are both numbers are compared numerically within --tol (so 62 equals 62.0)
  * everything else is compared as exact, case-sensitive text
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- reading
def read_table(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        columns = [c.strip().upper() for c in (reader.fieldnames or [])]
        rows = [{c.strip().upper(): (v or "").strip() for c, v in r.items() if c is not None}
                for r in reader]
    return columns, rows


# --------------------------------------------------------------------------- comparison
def values_equal(a: str, b: str, tol: float = 1e-8) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if a == b:
        return True
    if not a or not b:
        return False                       # one missing, one present
    try:
        return abs(float(a) - float(b)) <= tol
    except ValueError:
        return False


@dataclass
class CompareResult:
    base_rows: int = 0
    compare_rows: int = 0
    common_rows: int = 0
    common_columns: List[str] = field(default_factory=list)
    only_base_columns: List[str] = field(default_factory=list)
    only_compare_columns: List[str] = field(default_factory=list)
    only_base_keys: List[tuple] = field(default_factory=list)
    only_compare_keys: List[tuple] = field(default_factory=list)
    diffs: List[dict] = field(default_factory=list)      # {key, column, base, compare}

    @property
    def n_diff_rows(self) -> int:
        return len({d["key"] for d in self.diffs})

    @property
    def matches(self) -> bool:
        return not (self.diffs or self.only_base_keys or self.only_compare_keys
                    or self.only_base_columns or self.only_compare_columns)


def _index(rows: List[Dict[str, str]], key: List[str], label: str) -> Dict[tuple, Dict[str, str]]:
    index: Dict[tuple, Dict[str, str]] = {}
    for r in rows:
        k = tuple(r.get(c, "") for c in key)
        if k in index:
            raise ValueError(f"duplicate key {k} in {label}: the key columns are not unique")
        index[k] = r
    return index


def compare(base_cols, base_rows, comp_cols, comp_rows, key: List[str], tol: float = 1e-8,
            ignore: Optional[List[str]] = None) -> CompareResult:
    key = [k.upper() for k in key]
    ignore_set = {c.upper() for c in (ignore or [])}
    for k in key:
        for label, cols in (("base", base_cols), ("compare", comp_cols)):
            if k not in cols:
                raise ValueError(f"key column {k} is not in the {label} file")

    res = CompareResult(base_rows=len(base_rows), compare_rows=len(comp_rows))
    res.common_columns = [c for c in base_cols if c in comp_cols and c not in ignore_set]
    res.only_base_columns = [c for c in base_cols if c not in comp_cols and c not in ignore_set]
    res.only_compare_columns = [c for c in comp_cols if c not in base_cols and c not in ignore_set]

    bi, ci = _index(base_rows, key, "base"), _index(comp_rows, key, "compare")
    res.only_base_keys = sorted(set(bi) - set(ci))
    res.only_compare_keys = sorted(set(ci) - set(bi))
    common = sorted(set(bi) & set(ci))
    res.common_rows = len(common)
    for k in common:
        for col in res.common_columns:
            if not values_equal(bi[k].get(col, ""), ci[k].get(col, ""), tol):
                res.diffs.append({"key": k, "column": col,
                                  "base": bi[k].get(col, ""), "compare": ci[k].get(col, "")})
    return res


# --------------------------------------------------------------------------- report
def format_report(res: CompareResult, base_name: str, compare_name: str, key: List[str],
                  max_diffs: int = 25) -> str:
    dash = lambda items: ", ".join(items) if items else "-"          # noqa: E731
    lines = [f"Dataset comparison   base: {base_name}   compare: {compare_name}",
             f"Key: {', '.join(k.upper() for k in key)}",
             f"Rows    base {res.base_rows} | compare {res.compare_rows} | in both {res.common_rows} "
             f"| only in base {len(res.only_base_keys)} | only in compare {len(res.only_compare_keys)}",
             f"Columns in both {len(res.common_columns)} | only in base: {dash(res.only_base_columns)} "
             f"| only in compare: {dash(res.only_compare_columns)}",
             f"Value differences: {len(res.diffs)} cell(s) in {res.n_diff_rows} row(s)"]
    for k in res.only_base_keys[:max_diffs]:
        lines.append(f"  row only in base:    {k}")
    for k in res.only_compare_keys[:max_diffs]:
        lines.append(f"  row only in compare: {k}")
    for d in res.diffs[:max_diffs]:
        lines.append(f"  {d['key']} {d['column']}: base='{d['base']}' compare='{d['compare']}'")
    if len(res.diffs) > max_diffs:
        lines.append(f"  ... {len(res.diffs) - max_diffs} more")
    lines.append("RESULT: MATCH" if res.matches else "RESULT: DIFFERENCES FOUND")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare two CSV datasets (double programming QC).")
    ap.add_argument("base", help="e.g. the SAS export")
    ap.add_argument("compare", help="e.g. the independent Python output")
    ap.add_argument("--key", nargs="+", required=True, help="key column(s) that identify a row")
    ap.add_argument("--tol", type=float, default=1e-8, help="numeric tolerance (default 1e-8)")
    ap.add_argument("--ignore", nargs="*", default=[], help="columns to leave out of the comparison")
    args = ap.parse_args(argv)
    try:
        bc, br = read_table(args.base)
        cc, cr = read_table(args.compare)
        res = compare(bc, br, cc, cr, args.key, args.tol, args.ignore)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(format_report(res, args.base, args.compare, args.key))
    return 0 if res.matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
