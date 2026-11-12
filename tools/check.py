#!/usr/bin/env python3
"""One command to check the project: canon lint + Godot headless tests.

    python tools/check.py              # everything
    python tools/check.py --canon-only # only text/canon rules (fast)
    python tools/check.py --tests-only # only Godot tests

Exit codes: 0 = all good, 1 = errors found, 3 = incomplete (tests could not run,
for example Godot was not found). Warnings never fail the check, but read them.

Godot executable: environment variable GODOT_BIN, or the first line of
tools/godot_path.txt (this file is git-ignored). Use the *console* build on Windows.

Tests: every file tests/test_*.gd is run as
    godot --headless --path <root> --script res://tests/<file>
A test passes when it exits with code 0 and prints a marker like STATE_TESTS_OK,
and prints no "SCRIPT ERROR" / "Parse Error".

Needs only the Python standard library. Works on Windows, macOS and Linux.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "tools" / "canon_rules.json"
TEST_TIMEOUT = 90
MARKER = re.compile(r"\b[A-Z][A-Z0-9_]*_OK\b")
BAD_OUTPUT = ("SCRIPT ERROR", "Parse Error", "Failed to load script")

errors = 0
warnings = 0


def report(severity, rule_id, where, message):
    global errors, warnings
    if severity == "error":
        errors += 1
        tag = "ERROR"
    else:
        warnings += 1
        tag = "warn "
    print(f"[{tag}] {rule_id} {where}: {message}")


def re_flags(flags):
    return re.IGNORECASE if "i" in (flags or "") else 0


def iter_text_files(rules):
    exts = set(rules.get("scan_ext", []))
    for d in rules.get("scan_dirs", []):
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in exts:
                yield p


def read_lines(path):
    """Return lines to scan. JSON is normalized so \\uXXXX escapes are visible as text."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            raw = json.dumps(json.loads(raw), ensure_ascii=False, indent=1)
        except ValueError as e:
            report("error", "R-json", rel(path), f"invalid JSON: {e}")
    return raw.splitlines()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def walk_json(node, path, out):
    if isinstance(node, dict):
        if isinstance(node.get("text"), str) and node["text"].strip():
            out.append((path, node))
        for k, v in node.items():
            walk_json(v, f"{path}/{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_json(v, f"{path}[{i}]", out)


def canon_lint():
    print("== Canon lint ==")
    if not RULES_PATH.exists():
        report("error", "R-setup", "tools/canon_rules.json", "rules file missing")
        return
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    files = list(iter_text_files(rules))
    print(f"scanned {len(files)} files in {', '.join(rules.get('scan_dirs', []))}")

    cache = {p: read_lines(p) for p in files}

    for r in rules.get("forbid", []):
        rx = re.compile(r["pattern"], re_flags(r.get("flags")))
        for p, lines in cache.items():
            for n, line in enumerate(lines, 1):
                if rx.search(line):
                    report(r["severity"], r["id"], f"{rel(p)}:{n}", r["message"])

    for r in rules.get("max_count", []):
        rx = re.compile(r["pattern"], re_flags(r.get("flags")))
        hits = []
        for p, lines in cache.items():
            for n, line in enumerate(lines, 1):
                for _ in rx.finditer(line):
                    hits.append(f"{rel(p)}:{n}")
        if len(hits) > r["max"]:
            report(r["severity"], r["id"], ", ".join(hits[:6]),
                   f'{len(hits)} occurrences (max {r["max"]}). {r["message"]}')

    y = rules.get("years_by_camel")
    if y:
        rx = re.compile(r"(\d{3,4})\s+по\s+верблюду")
        for p, lines in cache.items():
            for n, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    if int(m.group(1)) not in y["allowed"]:
                        report(y["severity"], y["id"], f"{rel(p)}:{n}",
                               f'{m.group(0)}: {y["message"]}')

    for r in rules.get("forbid_filenames", []):
        rx = re.compile(r["pattern"], re_flags(r.get("flags")))
        for d in r.get("dirs", []):
            base = ROOT / d
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if p.is_file() and rx.search(p.name):
                    report(r["severity"], r["id"], rel(p), r["message"])

    s = rules.get("json_text_needs_src")
    if s:
        for d in s.get("dirs", []):
            base = ROOT / d
            if not base.exists():
                continue
            for p in sorted(base.rglob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                found = []
                walk_json(data, "", found)
                for jpath, node in found:
                    if node.get("src") not in s["allowed"]:
                        report(s["severity"], s["id"], f"{rel(p)}{jpath}", s["message"])


def find_godot():
    env = os.environ.get("GODOT_BIN")
    if env and Path(env).exists():
        return env
    cfg = ROOT / "tools" / "godot_path.txt"
    if cfg.exists():
        first = cfg.read_text(encoding="utf-8").strip().splitlines()
        if first and Path(first[0].strip()).exists():
            return first[0].strip()
    return None


def godot_tests():
    print("== Godot tests ==")
    tests = sorted((ROOT / "tests").glob("test_*.gd")) if (ROOT / "tests").exists() else []
    if not tests:
        print("no tests yet (tests/test_*.gd)")
        return 0
    godot = find_godot()
    if not godot:
        print("INCOMPLETE: Godot not found. Set GODOT_BIN or put the path in tools/godot_path.txt")
        return 3
    failed = 0
    for t in tests:
        cmd = [godot, "--headless", "--path", str(ROOT), "--script", f"res://tests/{t.name}"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=TEST_TIMEOUT)
            out = (res.stdout or "") + (res.stderr or "")
            ok = res.returncode == 0 and MARKER.search(out) and not any(b in out for b in BAD_OUTPUT)
        except subprocess.TimeoutExpired:
            out, ok = f"timeout after {TEST_TIMEOUT}s (scripts that wait for frames must run windowed)", False
        if ok:
            print(f"PASS {t.name}: {MARKER.search(out).group(0)}")
        else:
            failed += 1
            tail = "\n    ".join(out.strip().splitlines()[-8:])
            print(f"FAIL {t.name}\n    {tail}")
    print(f"tests: {len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canon-only", action="store_true")
    ap.add_argument("--tests-only", action="store_true")
    a = ap.parse_args()
    code = 0
    if not a.tests_only:
        canon_lint()
        print(f"canon: {errors} errors, {warnings} warnings")
        if errors:
            code = 1
    if not a.canon_only:
        t = godot_tests()
        if t == 1:
            code = 1
        elif t == 3 and code == 0:
            code = 3
    print({0: "RESULT: OK", 1: "RESULT: FAIL", 3: "RESULT: INCOMPLETE (not green)"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
