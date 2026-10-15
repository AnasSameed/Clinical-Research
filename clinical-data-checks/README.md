# Clinical Data Checks (Python)

A small, dependency-free tool that runs **data-quality checks on clinical datasets** (DM and AE, SDTM-style) before they go into programming or review. It mirrors what a clinical programmer does in practice: edit checks, controlled-terminology checks and cross-dataset checks.

All data here is **synthetic**. No real patient data.

## Checks

| Rule | What it catches |
|---|---|
| REQUIRED | Missing values in mandatory variables |
| UNIQUE | Duplicate subject IDs |
| CT | Values outside controlled terminology (SEX, AESEV, AESER) |
| RANGE | Non-numeric or implausible AGE |
| ISO8601 | Dates not in YYYY-MM-DD |
| DATE_ORDER | Dosing before consent; last dose before first dose |
| ORPHAN | AE records whose subject is not in DM |

## Run it

```
python check_data.py                                   # clean sample data -> no findings
python check_data.py data/dm_dirty.csv data/ae_dirty.csv   # deliberately broken data -> 11 findings
python -m unittest discover -s tests -t .              # unit tests
```

Requires Python 3.9+ only. Exit code is 1 when findings exist, so it can be used in a CI step.
Expected output for the dirty files is in `data/expected_dirty_report.txt`.

## Structure

```
check_data.py     runs all rules, prints a grouped report
checks/rules.py   one small function per rule, easy to add more
tests/            unit tests for each rule
data/             clean and dirty synthetic samples
```

## Ideas to extend

- Read rules from a YAML config instead of code
- Add LB / VS domains and a check that AE dates fall within the study period
- Export the report to CSV or HTML
- Run it automatically on every push with GitHub Actions
- Run it on files in an S3 bucket (ties in with the AWS notes)
