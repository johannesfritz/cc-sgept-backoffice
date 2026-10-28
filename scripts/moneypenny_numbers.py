"""Moneypenny's back-office invoice numbers, read for the generator and the Drive upload.

Moneypenny reserves an invoice's number when Lina drafts it and keeps the
numbers it issued or cancelled. The generator and every Drive upload refuse
those numbers. The read uses MNP_API_URL and the CEO's token,
MNP_API_TOKEN_CEO, falling back to MNP_API_TOKEN: the generator issues for
the CEO. When the service cannot be read, a number counts as held.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import urllib.request


def series(year: int) -> dict:
    """Return Moneypenny's back-office series report for a four-digit year.

    Its `last_number` is the counter Lina's invoice drafts raise, its
    `reserved` lists the numbers open drafts hold, its `issued` lists the
    numbers Moneypenny records as issued or cancelled, its `cancelled` lists
    the cancelled ones among them, and its `pre_engine` lists the issued
    numbers recorded before Moneypenny numbered invoices, such as the
    generator's own invoices from the stocktake. Raises RuntimeError when MNP_API_URL or the
    token is unset or the service cannot be read.
    """
    base = os.environ.get("MNP_API_URL", "").rstrip("/")
    token = os.environ.get("MNP_API_TOKEN_CEO") or os.environ.get("MNP_API_TOKEN", "")
    if not base or not token:
        raise RuntimeError(
            "MNP_API_URL and MNP_API_TOKEN_CEO (or MNP_API_TOKEN) must be set to read Moneypenny's invoice counter"
        )
    request = urllib.request.Request(
        f"{base}/v1/documents/series/?series=backoffice&year={year}",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            report = json.load(response)
        return {
            "last_number": int(report["last_number"]),
            "reserved": [str(n) for n in report.get("reserved", [])],
            "issued": [str(n) for n in report.get("issued", [])],
            "cancelled": [str(n) for n in report.get("cancelled", [])],
            "pre_engine": [str(n) for n in report["pre_engine"]],
        }
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError) as err:
        raise RuntimeError(f"Cannot read Moneypenny's invoice counter: {err}") from err


def holder(number: str, report: dict) -> str | None:
    """Return a one-line reason when the series report holds the number's sequence, None when it does not.

    A number counts as held when an open Lina draft reserves it, when
    Moneypenny keeps it as a cancelled draft's void number, or when Moneypenny
    issued it. A number recorded before Moneypenny numbered invoices
    (`pre_engine`) is the generator's own, issued or cancelled, and does not
    count. Both `YYNNN` and `YYNNN-NNNNNN`
    compare by their sequence.
    """
    sequence = number.split("-")[0]
    held = [n for n in report["reserved"] if n.split("-")[0] == sequence]
    if held:
        return f"Invoice number {sequence} is held by a Lina draft in Moneypenny as {held[0]}"
    recorded = [n for n in report["issued"] if n.split("-")[0] == sequence and n not in report["pre_engine"]]
    void = [n for n in recorded if n in report["cancelled"]]
    if void:
        return f"Invoice number {sequence} belongs to a cancelled Lina draft that Moneypenny keeps as {void[0]}"
    if recorded:
        return f"Invoice number {sequence} was issued by Moneypenny as {recorded[0]}"
    return None


def refusal(number: str) -> str | None:
    """Read Moneypenny now and return why the number may not be uploaded, None when it may.

    A number Moneypenny holds, or one it cannot check, is refused.
    """
    match = re.match(r"\d{5}", str(number))
    if not match:
        return f"Invoice number {number!r} does not start with a five-digit sequence"
    sequence = match.group(0)
    try:
        report = series(2000 + int(sequence[:2]))
    except RuntimeError as err:
        return f"Invoice number {sequence} cannot be checked against Moneypenny's drafts: {err}"
    return holder(sequence, report)
