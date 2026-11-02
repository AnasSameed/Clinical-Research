# Clinical SAS Practice: SDTM DM, ADaM ADSL and an AE Summary Table

A small, end-to-end practice project in SAS using **synthetic** trial data (no real patients). It follows the usual clinical programming flow:

```
raw CSV  ->  SDTM DM  ->  ADaM ADSL  ->  adverse-event summary table (PROC REPORT)
```

> **Scope:** a simplified learning project. It uses CDISC-style names and derivations, but it is not a full SDTM/ADaM Implementation Guide-compliant submission package.

## What it demonstrates
| Skill | Where |
|---|---|
| DATA step: reading CSV with `INFILE`/`INPUT`, explicit lengths, `SELECT/WHEN`, derived variables | `01_sdtm_dm.sas`, `02_adsl.sas` |
| SDTM DM: `USUBJID`, `ARM/ARMCD`, ISO 8601 reference dates | `01_sdtm_dm.sas` |
| ADaM ADSL: `TRT01P/TRT01PN`, `TRTSDT/TRTEDT`, `SAFFL`, `AGEGR1`, `TRTDURD` | `02_adsl.sas` |
| PROC SQL joins and `COUNT(DISTINCT ...)` for subject counts | `03_ae_summary.sas` |
| PROC TRANSPOSE, PROC REPORT, PROC FREQ, PROC MEANS | `02_adsl.sas`, `03_ae_summary.sas` |
| Macros: reusable QC checks (unique keys, missing values) | `macros/qc_checks.sas` |
| Handling messy data: screen failures, a missing last-dose date, an AE before first dose | `data/generate_synthetic_data.py` |

## Project layout
```
data/
  generate_synthetic_data.py    reproducible synthetic data (fixed seed)
  raw/dm_raw.csv                24 subjects (11 placebo, 11 active, 2 screen failures)
  raw/ae_raw.csv                30 adverse event records
macros/
  qc_checks.sas                 %check_unique, %check_missing
programs/
  00_setup.sas                  set the project path, library and macros (run first)
  01_sdtm_dm.sas                raw -> SDTM DM
  02_adsl.sas                   DM -> ADSL
  03_ae_summary.sas             ADSL + AE -> AE summary table
docs/
  expected_ae_summary.txt       the numbers the table should show
```

## How to run
1. Copy this folder to a place your SAS can read (for example SAS OnDemand for Academics or SAS Viya for Learners).
2. Open `programs/00_setup.sas` and change the `root` path to your folder.
3. In one SAS session, run the programs in order: `00`, `01`, `02`, `03`.
4. Compare the table from `03_ae_summary.sas` with `docs/expected_ae_summary.txt`.

## Derivation rules
- **USUBJID** = `STUDYID-SITEID-SUBJID`
- **SAFFL** = `Y` if the subject has a first dose date, otherwise `N`
- **TRTDURD** = `TRTEDT - TRTSDT + 1`, left missing if either date is missing
- **Treatment-emergent AE** = AE start date on or after the first dose date
- A subject is counted **once** per preferred term; percentages use the safety-population N per arm

## Data checks built in
- Duplicate `USUBJID` check on DM and ADSL
- Missing-date counts: 2 screen failures have no first dose, and 3 subjects have no last dose (2 screen failures plus 1 dosed subject with a missing end date)
- The AE of a screen failure is dropped by the safety-population join
- One AE that starts before the first dose is excluded as not treatment-emergent

## Expected results
See `docs/expected_ae_summary.txt`. These numbers were computed independently in Python from the same raw files, so they can be used to check the SAS output.

## Notes and next steps
- [ ] Add a screenshot of the final report to `docs/`
- [ ] Add a `PROC COMPARE` step against a second, independently programmed ADSL (double programming)
- [ ] Extend to ADAE and a severity table
- [ ] Add the VS (vital signs) domain
