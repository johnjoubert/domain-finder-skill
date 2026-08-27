from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/domain-finder/scripts/check_com_domains.py"
SPEC = importlib.util.spec_from_file_location("check_com_domains", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, status: int = 200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size: int = -1) -> bytes:
        return b"{"


class NormalizeTests(unittest.TestCase):
    def test_normalizes_urls_www_and_dot_com(self):
        self.assertEqual(MODULE.normalize("HTTPS://www.Example-Brand.com/path"), "example-brand")

    def test_skips_blanks_and_comments(self):
        self.assertIsNone(MODULE.normalize("  "))
        self.assertIsNone(MODULE.normalize("# candidate family"))

    def test_rejects_invalid_labels(self):
        for value in ["-bad", "bad-", "two words", "bad_name", "x" * 64]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.normalize(value)

    def test_load_names_deduplicates_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "names.txt"
            source.write_text("Candidate-One.com\ncandidate-two\ncandidate-one\n", encoding="utf-8")
            names, invalids = MODULE.load_names(
                ["Candidate-Two.com", "candidate-three"], str(source)
            )
        self.assertEqual(names, ["candidate-two", "candidate-three", "candidate-one"])
        self.assertEqual(invalids, [])

    def test_load_names_records_invalid_labels_without_dropping_valid_ones(self):
        names, invalids = MODULE.load_names(
            ["good-name", "bad_name", "also-good", "bad_name", "-bad", "# ignore"],
            None,
        )
        self.assertEqual(names, ["good-name", "also-good"])
        self.assertEqual([row["name"] for row in invalids], ["bad_name", "-bad"])
        self.assertTrue(all(row["status"] == "invalid" for row in invalids))
        self.assertTrue(all(row["http"] is None for row in invalids))

    def test_only_invalid_labels_still_exits(self):
        with self.assertRaises(SystemExit):
            MODULE.load_names(["bad_name", "-bad"], None)


class CheckTests(unittest.TestCase):
    @patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse(200))
    def test_http_200_is_registered(self, _urlopen):
        result = MODULE.check_name("example")
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["http"], 200)

    @patch.object(MODULE.urllib.request, "urlopen")
    def test_http_404_is_no_record(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError("url", 404, "not found", {}, None)
        result = MODULE.check_name("unlikely-name")
        self.assertEqual(result["status"], "no_rdap_record")
        self.assertEqual(result["http"], 404)

    @patch.object(MODULE.time, "sleep", return_value=None)
    @patch.object(MODULE.urllib.request, "urlopen")
    def test_transient_error_retries_without_claiming_availability(self, urlopen, _sleep):
        urlopen.side_effect = [
            urllib.error.HTTPError("url", 503, "unavailable", {}, None),
            urllib.error.HTTPError("url", 404, "not found", {}, None),
        ]
        result = MODULE.check_name("retry-name", attempts=2)
        self.assertEqual(result["status"], "no_rdap_record")
        self.assertEqual(urlopen.call_count, 2)

    @patch.object(MODULE.time, "sleep", return_value=None)
    @patch.object(MODULE.urllib.request, "urlopen")
    def test_exhausted_transport_failure_is_unknown(self, urlopen, _sleep):
        urlopen.side_effect = urllib.error.URLError("offline")
        result = MODULE.check_name("network-failure", attempts=2)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["http"])
        self.assertEqual(urlopen.call_count, 2)


class PayloadAndCliTests(unittest.TestCase):
    def test_available_only_filters_results_but_preserves_counts(self):
        results = [
            {"status": "registered", "domain": "a.com"},
            {"status": "no_rdap_record", "domain": "b.com"},
            {"status": "unknown", "domain": "c.com"},
        ]
        payload = MODULE.build_payload(results, available_only=True)
        self.assertEqual(payload["checked"], 3)
        self.assertEqual(payload["no_rdap_record"], 1)
        self.assertEqual(payload["registered"], 1)
        self.assertEqual(payload["unknown"], 1)
        self.assertEqual(payload["invalid"], 0)
        self.assertEqual([item["domain"] for item in payload["results"]], ["b.com"])
        self.assertIn("checked_at_utc", payload)

    def test_available_only_hides_invalid_but_preserves_count(self):
        results = [
            {"status": "invalid", "domain": "bad_name.com"},
            {"status": "no_rdap_record", "domain": "b.com"},
            {"status": "registered", "domain": "a.com"},
        ]
        payload = MODULE.build_payload(results, available_only=True)
        self.assertEqual(payload["checked"], 3)
        self.assertEqual(payload["invalid"], 1)
        self.assertEqual([item["domain"] for item in payload["results"]], ["b.com"])

    @patch.object(MODULE, "check_name")
    def test_json_cli_and_output_file(self, check_name):
        check_name.side_effect = lambda name, _attempts: {
            "name": name,
            "domain": f"{name}.com",
            "status": "registered",
            "http": 200,
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested/results.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = MODULE.main(["--json", "--output", str(output), "example.com"])
            printed = json.loads(stdout.getvalue())
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(printed["registered"], 1)
        self.assertEqual(saved["results"][0]["domain"], "example.com")

    @patch.object(MODULE, "check_name")
    def test_unknown_result_returns_exit_two(self, check_name):
        check_name.return_value = {
            "name": "maybe",
            "domain": "maybe.com",
            "status": "unknown",
            "http": None,
            "error": "offline",
        }
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = MODULE.main(["maybe"])
        self.assertEqual(code, 2)

    @patch.object(MODULE, "check_name")
    def test_invalid_label_does_not_abort_or_use_unknown_exit(self, check_name):
        check_name.side_effect = lambda name, _attempts: {
            "name": name,
            "domain": f"{name}.com",
            "status": "no_rdap_record",
            "http": 404,
        }
        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            code = MODULE.main(["--json", "good-name", "bad_name"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["checked"], 2)
        self.assertEqual(payload["invalid"], 1)
        self.assertEqual(payload["no_rdap_record"], 1)
        self.assertEqual(payload["unknown"], 0)
        self.assertEqual(check_name.call_count, 1)
        by_name = {row["name"]: row["status"] for row in payload["results"]}
        self.assertEqual(by_name["good-name"], "no_rdap_record")
        self.assertEqual(by_name["bad_name"], "invalid")


if __name__ == "__main__":
    unittest.main()
