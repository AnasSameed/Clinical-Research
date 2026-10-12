"""Generates SYNTHETIC trial data for the practice project. No real patients.
Run:  python generate_synthetic_data.py   (writes dm_raw.csv and ae_raw.csv into data/raw/)
A fixed random seed keeps the files reproducible.
"""
import csv, random
from datetime import date, timedelta
from pathlib import Path

random.seed(2026)
out = Path(__file__).parent / "raw"
out.mkdir(exist_ok=True)

races = ["WHITE", "ASIAN", "BLACK OR AFRICAN AMERICAN", "OTHER"]
sites = ["101", "102", "103"]

# 24 subjects: 11 placebo, 11 active, 2 screen failures (never dosed)
arms = ["Placebo"] * 11 + ["Drug 10 mg"] * 11 + ["Screen Failure"] * 2
random.shuffle(arms)

dm_rows = []
for i, arm in enumerate(arms, start=1):
    subjid = f"{i:04d}"
    consent = date(2026, 1, 5) + timedelta(days=random.randint(0, 25))
    if arm == "Screen Failure":
        first = last = ""
    else:
        first_d = consent + timedelta(days=random.randint(3, 10))
        last_d = first_d + timedelta(days=random.randint(55, 85))
        first, last = first_d.isoformat(), last_d.isoformat()
    dm_rows.append([subjid, random.choice(sites), random.randint(19, 78),
                    random.choice(["M", "F"]), random.choice(races), arm,
                    consent.isoformat(), first, last])

# one dosed subject has no recorded last dose date (a deliberate data-cleaning case)
dosed = [r for r in dm_rows if r[7]]
dosed[3][8] = ""

terms = [
    ("Headache", "Nervous system disorders"),
    ("Dizziness", "Nervous system disorders"),
    ("Nausea", "Gastrointestinal disorders"),
    ("Diarrhoea", "Gastrointestinal disorders"),
    ("Fatigue", "General disorders and administration site conditions"),
    ("Rash", "Skin and subcutaneous tissue disorders"),
    ("Upper respiratory tract infection", "Infections and infestations"),
]
sev = ["MILD", "MILD", "MILD", "MODERATE", "MODERATE", "SEVERE"]

ae_rows = []
for r in dm_rows:
    subjid, arm, first = r[0], r[5], r[7]
    if arm == "Screen Failure":
        continue
    n_ae = random.choice([0, 1, 1, 2, 3]) if arm == "Drug 10 mg" else random.choice([0, 0, 1, 1, 2])
    chosen = random.sample(terms, k=n_ae)
    for term, soc in chosen:
        start = date.fromisoformat(first) + timedelta(days=random.randint(1, 50))
        ae_rows.append([subjid, term, soc, random.choice(sev), start.isoformat(),
                        "Y" if random.random() < 0.08 else "N"])

# deliberate edge cases: an AE BEFORE first dose (not treatment-emergent) and an AE for a screen failure
first_dosed = dosed[0]
ae_rows.append([first_dosed[0], "Headache", "Nervous system disorders", "MILD",
                (date.fromisoformat(first_dosed[7]) - timedelta(days=4)).isoformat(), "N"])
sf = next(r for r in dm_rows if r[5] == "Screen Failure")
ae_rows.append([sf[0], "Nausea", "Gastrointestinal disorders", "MILD", "2026-02-01", "N"])

with open(out / "dm_raw.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["SUBJID", "SITEID", "AGE", "SEX", "RACE", "ARM", "CONSENTDT", "FIRSTDOSE", "LASTDOSE"])
    w.writerows(dm_rows)
with open(out / "ae_raw.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["SUBJID", "AETERM", "AEBODSYS", "AESEV", "AESTDTC", "AESER"])
    w.writerows(ae_rows)
print(len(dm_rows), "subjects;", len(ae_rows), "adverse events")
