"""
AWS Lambda entry point.

Triggered by S3 ObjectCreated events on the  incoming/  prefix.
For every uploaded .csv it:
  1. downloads the file,
  2. runs the SDTM checks in validator.py,
  3. writes  reports/<name>.qc.json  and  reports/<name>.qc.html  back to the bucket.
"""

import html
import json
import logging
import os
import urllib.parse

import boto3

from validator import validate_csv

log = logging.getLogger()
log.setLevel(logging.INFO)

s3 = boto3.client("s3")
REPORT_PREFIX = os.environ.get("REPORT_PREFIX", "reports/")
MAX_BYTES = int(os.environ.get("MAX_FILE_BYTES", str(20 * 1024 * 1024)))


def lambda_handler(event, context):
    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        size = record["s3"]["object"].get("size", 0)

        if not key.lower().endswith(".csv"):
            log.info("Skipping non-CSV object %s", key)
            continue

        name = key.rsplit("/", 1)[-1]
        if size > MAX_BYTES:
            report = _too_big_report(name, size)
        else:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                text = body.decode("latin-1")
            report = validate_csv(text, name)

        report["source"] = f"s3://{bucket}/{key}"
        stem = name[:-4]
        json_key = f"{REPORT_PREFIX}{stem}.qc.json"
        html_key = f"{REPORT_PREFIX}{stem}.qc.html"

        s3.put_object(Bucket=bucket, Key=json_key,
                      Body=json.dumps(report, indent=2).encode(),
                      ContentType="application/json")
        s3.put_object(Bucket=bucket, Key=html_key,
                      Body=render_html(report).encode(),
                      ContentType="text/html; charset=utf-8")

        # One structured line per file makes CloudWatch Logs Insights queries easy.
        log.info(json.dumps({"file": key, "domain": report["domain"],
                             "status": report["status"], **report["summary"]}))
        results.append({"file": key, "status": report["status"], "report": json_key})

    return {"processed": len(results), "results": results}


def _too_big_report(name, size):
    return {
        "file": name, "domain": None, "domain_label": None, "status": "FAIL",
        "summary": {"records": 0, "subjects": 0, "variables": 0, "errors": 1, "warnings": 0},
        "rules_triggered": [{"severity": "ERROR", "rule": "FILE_TOO_LARGE", "count": 1}],
        "findings": [{"severity": "ERROR", "rule": "FILE_TOO_LARGE",
                      "message": f"File is {size} bytes; limit is {MAX_BYTES}.",
                      "row": None, "variable": None, "value": None}],
    }


def render_html(r: dict) -> str:
    e = html.escape
    colour = {"PASS": "#1a7f37", "PASS_WITH_WARNINGS": "#9a6700", "FAIL": "#cf222e"}[r["status"]]
    s = r["summary"]
    rows = "".join(
        f"<tr class='{e(f['severity'].lower())}'><td>{e(f['severity'])}</td>"
        f"<td>{e(f['rule'])}</td><td>{'' if f['row'] is None else f['row']}</td>"
        f"<td>{e(f['variable'] or '')}</td><td>{e(f['value'] or '')}</td>"
        f"<td>{e(f['message'])}</td></tr>"
        for f in r["findings"]
    ) or "<tr><td colspan='6'>No findings. The dataset passed every check.</td></tr>"
    rules = "".join(f"<li><b>{e(x['rule'])}</b> ({e(x['severity'])}): {x['count']}</li>"
                    for x in r["rules_triggered"])
    domain = f"{r['domain'] or '?'}" + (f" ({r['domain_label']})" if r.get("domain_label") else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QC report: {e(r['file'])}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;color:#1f2328;max-width:1100px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:999px;color:#fff;background:{colour};font-weight:600}}
.grid{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.card{{border:1px solid #d0d7de;border-radius:8px;padding:10px 16px;min-width:110px}}
.card b{{display:block;font-size:22px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{border-bottom:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#f6f8fa}} tr.error td:first-child{{color:#cf222e;font-weight:600}}
tr.warning td:first-child{{color:#9a6700;font-weight:600}}
</style></head><body>
<h1>SDTM QC report</h1>
<p><b>File:</b> {e(r['file'])}<br><b>Domain:</b> {e(domain)}<br>
<b>Source:</b> {e(r.get('source', ''))}<br><b>Validated:</b> {e(r.get('validated_at', ''))}</p>
<span class="badge">{e(r['status'])}</span>
<div class="grid">
<div class="card"><b>{s['records']}</b>records</div>
<div class="card"><b>{s['subjects']}</b>subjects</div>
<div class="card"><b>{s['variables']}</b>variables</div>
<div class="card"><b>{s['errors']}</b>errors</div>
<div class="card"><b>{s['warnings']}</b>warnings</div></div>
<h2>Rules triggered</h2><ul>{rules or '<li>None</li>'}</ul>
<h2>Findings</h2>
<table><tr><th>Severity</th><th>Rule</th><th>Row</th><th>Variable</th><th>Value</th><th>Message</th></tr>
{rows}</table></body></html>"""
