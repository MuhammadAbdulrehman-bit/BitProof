#!/usr/bin/env python3
"""
download_tenders.py - fetch and validate the RFP AI tender dataset.

Usage:
    pip install requests pdfplumber
    python download_tenders.py              # download anything missing
    python download_tenders.py --force      # re-download everything
    python download_tenders.py --insecure   # only if the portal's TLS cert fails

Output:
    tenders/tuning/<id>.pdf      (gitignored - never commit the PDFs)
    tenders/held_out/<id>.pdf    (gitignored)
    tenders_manifest.csv         (COMMIT this: ids, URLs, page counts, SHA-256)

Exit code is non-zero if any tender failed validation.
"""

import argparse
import csv
import hashlib
import sys
import time
from pathlib import Path

import requests

# --------------------------------------------------------------------------
# DATASET: edit this list to add/replace tenders. Keep ids stable.
# 'note' records the document version (corrigendum number) so later changes
# to the portal copy can be explained by a hash mismatch.
# --------------------------------------------------------------------------
TENDERS = [
    {
        "id": "t01", "split": "tuning", "category": "IT services (ERP)",
        "title": "PRAL P-79/2026 ERP System", "note": "EPADS SBD, QCBS 70/30, Rules 2026",
        "url": "https://epms.ppra.gov.pk/pdf?file=dGVuZGVyX2F0dGFjaG1lbnRzL0ZpbmFsX1RlbmRlcl9Eb2N1bWVudF8xLnBkZg==",
    },
    {
        "id": "t02", "split": "tuning", "category": "Goods / IT hardware",
        "title": "NUST GPU Servers P158775", "note": "EPADS SBD, QCBS 70/30, Rules 2026",
        "url": "https://epms.ppra.gov.pk/pdf?file=dGVuZGVyX2F0dGFjaG1lbnRzL2JpZGRpbmctZG9jdW1lbnRfNF8yMy5wZGY=",
    },
    {
        "id": "t03", "split": "tuning", "category": "Works / goods (RFQ)",
        "title": "PSO RFQ OP-19978AM Modbus Boosters", "note": "RFQ, 6 pages, closes 21 Oct 2026",
        "url": "https://epms.ppra.gov.pk/pdf?file=dGVuZGVyX2F0dGFjaG1lbnRzL1JGUV9Db3JycmVjdGVkXzE5OTc4LnBkZg==",
    },
    {
        "id": "t04", "split": "tuning", "category": "Consultancy (design & supervision)",
        "title": "PRIMACO/EOBI Plot 54 Gulberg design & supervision RFP", "note": "Older SRFP template, QCBS 80/20, Rules 2004, closed",
        "url": "https://epms.ppra.gov.pk/pdf?file=dGVuZGVyX2F0dGFjaG1lbnRzLzE3ODE3ODYxODdfNmEzM2U2NGI2MTZiNC5wZGY=",
    },
    {
        "id": "t05", "split": "held_out", "category": "IT hardware/software (data platform)",
        "title": "PRAL P-55/2026 Central Data Hub", "note": "Corrigendum #2, 198 pages, closes 21 Oct 2026",
        "url": "https://epms.ppra.gov.pk/pdf?file=dGVuZGVyX2F0dGFjaG1lbnRzL1AtNTVfQ29ycmlnZW5kdW1fVGVuZGVyX0RvY3VtZW50cy5wZGY=",
    },
    {
        "id": "t06", "split": "held_out", "category": "Goods / electrical (lots, LCBS)",
        "title": "SEPCO NCB-S-APMS-01/2026-27", "note": "Corrigendum #3, 193 pages, 3 lots",
        "url": "https://epms.ppra.gov.pk/pdf?file=dGVuZGVyX2F0dGFjaG1lbnRzL0FQTVNfQmlkZGluZ19Eb2N1bWVudF8yLnBkZg==",
    },
]

OUT_DIR = Path("tenders")
MANIFEST = Path("tenders_manifest.csv")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; rfp-ai-dataset/1.0)"}
MIN_TEXT_CHARS = 500      # chars across the first 5 pages; below this => likely scanned
MIN_BYTES = 1_000
RETRIES = 3
TIMEOUT = 90


def fetch(url, insecure=False):
    """GET with retries + backoff. Returns bytes. Raises on final failure."""
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=not insecure)
            r.raise_for_status()
            return r.content
        except requests.exceptions.SSLError:
            raise  # retrying will not fix a bad certificate
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code < 500:
                raise RuntimeError(f"HTTP {e.response.status_code} (not retrying)")
            last = e
            if attempt < RETRIES:
                time.sleep(2 * attempt)
        except requests.RequestException as e:
            last = e
            if attempt < RETRIES:
                time.sleep(2 * attempt)
    raise RuntimeError(f"download failed after {RETRIES} tries: {last}")


def inspect_pdf(path):
    """Return (pages, text_chars_first5). Raises if the PDF cannot be opened."""
    import pdfplumber  # imported lazily so --help works without it

    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        chars = sum(len(p.extract_text() or "") for p in pdf.pages[:5])
    return pages, chars


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def process(t, force=False, insecure=False):
    """Download + validate one tender. Returns a manifest row dict."""
    dest = OUT_DIR / t["split"] / f"{t['id']}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "id": t["id"], "split": t["split"], "category": t["category"],
        "title": t["title"], "note": t["note"], "url": t["url"],
        "bytes": "", "pages": "", "text_chars_first5": "", "sha256": "", "status": "",
    }
    try:
        if dest.exists() and not force:
            data = dest.read_bytes()
            origin = "cached"
        else:
            data = fetch(t["url"], insecure=insecure)
            origin = "downloaded"
            if not data.startswith(b"%PDF"):
                preview = data[:80].decode("utf-8", "replace").replace("\n", " ")
                raise ValueError(f"not a PDF (got: {preview!r})")
            if len(data) < MIN_BYTES:
                raise ValueError(f"suspiciously small file ({len(data)} bytes)")
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(dest)  # atomic: never leaves a half-written .pdf behind

        pages, chars = inspect_pdf(dest)
        row.update(bytes=len(data), pages=pages, text_chars_first5=chars, sha256=sha256(data))
        if chars < MIN_TEXT_CHARS:
            row["status"] = "LOW_TEXT (probably scanned - replace this tender)"
        else:
            row["status"] = f"OK ({origin})"
    except Exception as e:  # keep going so one bad tender doesn't hide the others
        row["status"] = f"FAIL: {e}"
    return row


def write_manifest(rows):
    fields = ["id", "split", "category", "title", "note", "url",
              "bytes", "pages", "text_chars_first5", "sha256", "status"]
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download and validate the RFP AI tender set.")
    ap.add_argument("--force", action="store_true", help="re-download even if the file exists")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (use only if the portal certificate fails)")
    args = ap.parse_args(argv)

    if args.insecure:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("[warn] TLS verification disabled")

    rows = []
    for t in TENDERS:
        print(f"[..] {t['id']} ({t['split']}) {t['title']}")
        row = process(t, force=args.force, insecure=args.insecure)
        rows.append(row)
        print(f"     -> {row['status']}  pages={row['pages']}  text={row['text_chars_first5']}  "
              f"sha256={str(row['sha256'])[:12]}")
        time.sleep(1)  # be polite to the portal

    write_manifest(rows)
    bad = [r for r in rows if not r["status"].startswith("OK")]
    print(f"\nWrote {MANIFEST}. {len(rows) - len(bad)}/{len(rows)} OK.")
    if bad:
        print("Needs attention: " + ", ".join(f"{r['id']} [{r['status'].split(':')[0].split(' ')[0]}]" for r in bad))
        return 1
    print("Reminder: add 'tenders/' to .gitignore - commit this script and the manifest, not the PDFs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
