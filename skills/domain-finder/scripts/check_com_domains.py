#!/usr/bin/env python3
"""Bulk-screen exact .com registrations through Verisign RDAP.

A 404 means no current registry record. It is a strong screening signal, not a
registrar purchase guarantee or trademark clearance.

Invalid labels are recorded as `invalid` and do not abort the batch.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://rdap.verisign.com/com/v1/domain/{domain}"
LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}
VERSION = "1.1.0"


def prepare(value: str) -> str | None:
    """Strip comments, URLs, and a trailing .com. None means skip."""
    value = value.strip().lower()
    if not value or value.startswith("#"):
        return None
    value = re.sub(r"^https?://", "", value)
    value = value.split("/", 1)[0]
    if value.startswith("www."):
        value = value[4:]
    if value.endswith(".com"):
        value = value[:-4]
    return value.strip(".")


def normalize(value: str) -> str | None:
    """Normalize a name or URL to one valid .com label."""
    prepared = prepare(value)
    if prepared is None:
        return None
    if not LABEL_RE.fullmatch(prepared):
        raise ValueError(f"Invalid .com label: {prepared!r}")
    return prepared


def invalid_result(label: str, error: str) -> dict[str, object]:
    """Build a result row for a name that cannot be queried."""
    return {
        "name": label,
        "domain": f"{label}.com",
        "status": "invalid",
        "http": None,
        "error": error,
    }


def check_name(name: str, attempts: int = 3) -> dict[str, object]:
    """Query Verisign RDAP and classify one exact .com candidate."""
    domain = f"{name}.com"
    url = ENDPOINT.format(domain=domain)
    headers = {
        "Accept": "application/rdap+json, application/json",
        "User-Agent": f"domain-finder-skill/{VERSION}",
    }

    for attempt in range(1, max(1, attempts) + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                code = response.status
                response.read(1)
            if code == 200:
                return {
                    "name": name,
                    "domain": domain,
                    "status": "registered",
                    "http": code,
                }
            return {
                "name": name,
                "domain": domain,
                "status": "unknown",
                "http": code,
                "error": f"unexpected HTTP {code}",
            }
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {
                    "name": name,
                    "domain": domain,
                    "status": "no_rdap_record",
                    "http": 404,
                }
            if error.code in TRANSIENT_HTTP and attempt < max(1, attempts):
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            return {
                "name": name,
                "domain": domain,
                "status": "unknown",
                "http": error.code,
                "error": f"HTTP {error.code}",
            }
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt < max(1, attempts):
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            return {
                "name": name,
                "domain": domain,
                "status": "unknown",
                "http": None,
                "error": str(error),
            }

    raise AssertionError("retry loop exhausted unexpectedly")


def load_names(
    positional: list[str], file_path: str | None
) -> tuple[list[str], list[dict[str, object]]]:
    """Load candidates; record invalid labels without aborting the batch."""
    raw = list(positional)
    if file_path:
        raw.extend(Path(file_path).read_text(encoding="utf-8").splitlines())
    if not raw and not sys.stdin.isatty():
        raw.extend(sys.stdin.read().splitlines())

    names: list[str] = []
    invalids: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_invalid: set[str] = set()
    for value in raw:
        try:
            name = normalize(value)
        except ValueError as error:
            label = prepare(value) or value.strip().lower()
            if label not in seen_invalid:
                seen_invalid.add(label)
                invalids.append(invalid_result(label, str(error)))
            continue
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    if not names:
        raise SystemExit("No valid candidates supplied")
    return names, invalids


def build_payload(results: list[dict[str, object]], available_only: bool) -> dict[str, object]:
    """Build the stable JSON result schema."""
    counts = {
        "checked": len(results),
        "no_rdap_record": sum(r["status"] == "no_rdap_record" for r in results),
        "registered": sum(r["status"] == "registered" for r in results),
        "unknown": sum(r["status"] == "unknown" for r in results),
        "invalid": sum(r["status"] == "invalid" for r in results),
    }
    shown = (
        [r for r in results if r["status"] == "no_rdap_record"]
        if available_only
        else results
    )
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        **counts,
        "results": shown,
        "warning": (
            "A Verisign 404 is a strong no-record signal. Confirm registrability at "
            "a registrar and check trademarks before committing."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk-screen exact .com domains with Verisign RDAP"
    )
    parser.add_argument("names", nargs="*", help="candidate names or .com domains")
    parser.add_argument("--file", help="newline-delimited candidate file")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--available-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", help="optional JSON output path")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    names, invalids = load_names(args.names, args.file)
    workers = max(1, min(args.workers, 16))
    attempts = max(1, args.attempts)

    ordered: dict[str, dict[str, object]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_name, name, attempts): name for name in names}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                ordered[name] = future.result()
            except Exception as error:  # preserve failed candidates as unknown
                ordered[name] = {
                    "name": name,
                    "domain": f"{name}.com",
                    "status": "unknown",
                    "http": None,
                    "error": repr(error),
                }

    results = [ordered[name] for name in names]
    results.extend(invalids)
    payload = build_payload(results, args.available_only)
    encoded = json.dumps(payload, indent=2)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        for result in payload["results"]:
            print(f"{result['status']:16} {result['domain']}")
        print(
            f"checked={payload['checked']} "
            f"no_record={payload['no_rdap_record']} "
            f"registered={payload['registered']} "
            f"unknown={payload['unknown']} "
            f"invalid={payload['invalid']}",
            file=sys.stderr,
        )

    return 2 if payload["unknown"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
