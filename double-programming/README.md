# Double programming toolkit (Python)

In clinical programming, important datasets and tables are built **twice, independently**: a production programmer writes one program, a QC programmer writes another from the same specification, and the outputs are compared (in SAS, `PROC COMPARE`). Any difference is investigated and fixed.

This folder is the **QC side** for the SAS programs in `../programs`:

| File | What it does |
|---|---|
| `independent_adsl.py` | Re-derives SDTM `DM` and ADaM `ADSL` from `../data/raw/dm_raw.csv` using the rules in the spec (not a line-by-line translation of the SAS) |
| `independent_adae.py` | Builds `ADAE` (`TRTEMFL`, `AESEVN`), the AE summary table and a new max-severity table |
| `compare_datasets.py` | A small `PROC COMPARE`: keys, missing rows/columns, cell differences, numeric tolerance, exit codes |
| `test_double_programming.py` | 23 tests, including an injected off-by-one error that the comparison must catch |

Standard library only for the programs (Python 3.9+); `pytest` for the tests.

## Run it

```bash
cd double-programming
python independent_adae.py --check ../docs/expected_ae_summary.txt   # builds everything into ./out
pytest -q
```

The AE summary produced here matches `docs/expected_ae_summary.txt` **character for character**, and the severity table matches counts derived by hand from the raw data (Placebo 5 subjects with a TEAE: 0 mild / 2 moderate / 3 severe; Drug 10 mg 10 subjects: 4 / 6 / 0).

## Derivation rules implemented

- `USUBJID = DEMO001-<SITEID>-<SUBJID>`; subject ids are read as text so `0001` keeps its zeros
- `ARMCD`: Placebo `PBO`, Drug 10 mg `TRT10`, Screen Failure `SCRNFAIL`; `TRT01PN` 1 / 2 / missing
- `SAFFL = Y` when a first-dose date exists; `TRTDURD = TRTEDT - TRTSDT + 1`, left missing if either date is missing
- `AGEGR1`: `>=65` or `<65` (adults only)
- Dates are written as `DATE9.` text (`03FEB2026`) with an explicit month list, so the output does not depend on locale
- `TRTEMFL = Y` when the AE starts on or after `TRTSDT`; AEs of subjects outside the safety population are dropped
- Subjects are counted once per preferred term; percentages use the arm's safety N and **round half up like SAS** (Python's built-in `round()` rounds half to even: 6.25 would print 6.2)

## Compare against the SAS output

On the SAS side, export the datasets (the SAS programs themselves are unchanged):

```sas
proc export data=adam.adsl outfile="adsl_sas.csv" dbms=csv replace; run;
proc export data=adam.adae outfile="adae_sas.csv" dbms=csv replace; run;
```

Then:

```bash
python independent_adsl.py --out adsl_python.csv
python compare_datasets.py adsl_sas.csv adsl_python.csv --key USUBJID
python compare_datasets.py adae_sas.csv out/adae_python.csv --key USUBJID AETERM AESTDTC
```

Exit code 0 = match, 1 = differences, 2 = unusable input (for example duplicate keys). Column names are matched case-insensitively and numbers are compared within a tolerance, so `62` equals `62.0`. If an export writes dates differently from `DATE9.`, use `--ignore` for those columns or add a format to the export.

## Status and limits

- Everything above is tested on the Python side, using the repository's own data.
- **The SAS export and comparison step was not run**, because no SAS installation was available. The SAS `ADSL`/`ADAE` datasets have therefore not been compared with the Python ones yet; the only SAS-derived reference used is the committed `docs/expected_ae_summary.txt`.
- This is a small teaching dataset (24 subjects). A real study would also compare labels, types and lengths against the define-xml.
