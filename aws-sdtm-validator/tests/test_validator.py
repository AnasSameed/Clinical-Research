"""Unit tests for the validator. Run with:  python -m pytest -q"""

import json
import pathlib
import sys
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validator import validate_csv  # noqa: E402

SAMPLES = ROOT / "sample_data"


def run(name):
    return validate_csv((SAMPLES / name).read_text(), name)


def rules(report):
    return {r["rule"] for r in report["rules_triggered"]}


def test_clean_dm_passes():
    r = run("dm_clean.csv")
    assert r["domain"] == "DM"
    assert r["status"] == "PASS", r["findings"]
    assert r["summary"]["subjects"] == 8


def test_clean_vs_passes():
    r = run("vs_clean.csv")
    assert r["status"] == "PASS", r["findings"]


def test_dm_errors_are_caught():
    r = run("dm_with_errors.csv")
    assert r["status"] == "FAIL"
    expected = {
        "DUPLICATE_SUBJECT", "INVALID_ISO8601", "CODELIST_VIOLATION",
        "END_BEFORE_START", "AGE_NEGATIVE", "AGE_NOT_NUMERIC", "AGEU_MISSING",
        "AGE_IMPLAUSIBLE", "CODELIST_CASE", "MULTIPLE_STUDYID", "MISSING_VALUE",
        "EXPECTED_VARIABLE_MISSING",
    }
    assert expected <= rules(r), expected - rules(r)


def test_ae_errors_are_caught():
    r = run("ae_with_errors.csv")
    assert r["status"] == "FAIL"
    expected = {
        "DUPLICATE_SEQ", "END_BEFORE_START", "AEDECOD_MISSING",
        "CODELIST_VIOLATION", "FATAL_NOT_SERIOUS", "SEQ_NOT_INTEGER",
        "INVALID_ISO8601",
    }
    assert expected <= rules(r), expected - rules(r)


def test_missing_required_variable():
    r = validate_csv("STUDYID,DOMAIN,USUBJID\nS1,DM,S1-001\n", "dm.csv")
    missing = {f["variable"] for f in r["findings"] if f["rule"] == "REQUIRED_VARIABLE_MISSING"}
    assert {"SEX", "AGE", "SITEID"} <= missing


def test_partial_iso_dates_allowed():
    csv_text = ("STUDYID,DOMAIN,USUBJID,AESEQ,AETERM,AEDECOD,AESTDTC\n"
                "S1,AE,S1-1,1,HEADACHE,Headache,2024-03\n"
                "S1,AE,S1-1,2,NAUSEA,Nausea,2024\n")
    r = validate_csv(csv_text, "ae.csv")
    assert "INVALID_ISO8601" not in rules(r)


def test_empty_and_header_only_files():
    assert validate_csv("", "x.csv")["status"] == "FAIL"
    assert "NO_RECORDS" in rules(validate_csv("STUDYID,DOMAIN\n", "dm.csv"))


def test_bom_is_tolerated():
    text = "﻿" + (SAMPLES / "dm_clean.csv").read_text()
    assert validate_csv(text, "dm.csv")["status"] == "PASS"


def test_domain_from_filename_when_no_domain_column():
    r = validate_csv("STUDYID,USUBJID\nS1,S1-1\n", "ae_extract.csv")
    assert r["domain"] == "AE"


def test_lambda_handler_writes_reports():
    with mock.patch("boto3.client") as client:
        s3 = client.return_value
        body = (SAMPLES / "dm_with_errors.csv").read_bytes()
        s3.get_object.return_value = {"Body": mock.Mock(read=lambda: body)}
        import importlib
        import lambda_function
        importlib.reload(lambda_function)

        event = {"Records": [{"s3": {"bucket": {"name": "b"},
                                     "object": {"key": "incoming/dm_with_errors.csv", "size": len(body)}}}]}
        out = lambda_function.lambda_handler(event, None)

    assert out["processed"] == 1 and out["results"][0]["status"] == "FAIL"
    keys = [c.kwargs["Key"] for c in s3.put_object.call_args_list]
    assert keys == ["reports/dm_with_errors.qc.json", "reports/dm_with_errors.qc.html"]
    report = json.loads(s3.put_object.call_args_list[0].kwargs["Body"])
    assert report["source"] == "s3://b/incoming/dm_with_errors.csv"
    assert "<table>" in s3.put_object.call_args_list[1].kwargs["Body"].decode()
