#!/usr/bin/env python3
r"""Standalone test for tools/check.py regex hardening (stages E..E-6A).

Verifies (against the LIVE functions from tools/check.py):
  1) the linear MARKER scan (find_ok_marker) matches the former regex
     "\b[A-Z][A-Z0-9_]*_OK\b" on normal/boundary inputs;
  2) the linear years scanner (camel_years_linear) replicates the former
     regex capture semantics (last 4 digits of a long digit run);
  3) the legacy pattern analyzer (rule_pattern_safe) accepts every
     pattern currently present in tools/canon_rules.json (legacy target:
     since E-6A rule enforcement runs on RE2 and this analyzer is not the
     enforcement gate anymore, but its pinned behavior is kept);
  4) the legacy analyzer rejects the ReDoS shapes found in E-3/E-4/E-5;
  5) linear scanners stay fast on pathological sizes (growth check);
  6) E-6A fail-secure and no-fallback: canon_lint runs rules through
     Google RE2 only - zero Python re.compile calls for rules, compile
     errors are reported as [ERROR] with the rule id;
  7) RE2 vs Python re semantic equivalence for all 15 canon rules on
     real project lines and synthetic Unicode edge cases (skipped when
     RE2 is unavailable in this interpreter);
  8) input limits: MAX_LINE_LENGTH (fail-secure stop proven by a spy on
     RE2 search over a MATCHING line), MAX_TOTAL_CHARS, MAX_RULES
     (skipped when RE2 is unavailable);
  9) RULE_TIME_BUDGET: deterministic FakeTime proof - one R-limit ERROR,
     later rules not compiled, years/json sections not run, budget fires
     inside the finditer() match loop (skipped when RE2 is unavailable);
 10) MAX_PATTERN_LENGTH enforced in compile_rule: 300 compiles, 301
     rejected in forbid/max_count/forbid_filenames with [ERROR] + rule id;
 11) Unicode IGNORECASE characterization: Python re vs RE2 on İ/ı/ſ/K
     (divergences recorded, impact on the 15 rules measured);
 12) camel_years_linear isdecimal: \d semantics (superscripts rejected,
     Arabic-Indic decimals accepted).

Run (RE2 venv):  %TEMP%\\re2-test-312\\Scripts\\python.exe -I tools/test_check_regex.py
Run (no RE2):    python -I tools/test_check_regex.py   # RE2 sections skip
Prints CHECK_REGEX_TEST_OK on success, exit 0; exit 1 on any failure.
"""
import contextlib
import importlib
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

MARKER = re.compile(r"\b[A-Z][A-Z0-9_]*_OK\b")
YEARS_RX = re.compile(r"(\d{3,4})\s+по\s+верблюду")

RULES_PATH = Path(__file__).resolve().parent / "canon_rules.json"


def _u(s: str) -> str:
    """Console-safe rendering of Unicode symbols (cp1251 consoles cannot
    print İ/ſ/K directly)."""
    return "+".join("U+%04X" % ord(c) for c in s) or "EMPTY"


def main() -> int:
    failures = 0

    # --- 1) MARKER equivalence on normal/boundary/Unicode inputs -------------
    marker_cases = [
        "PASS STATE_TESTS_OK (15 checks)",
        "no markers here",
        "X_OK is a prefix token",
        "_OK alone is not a marker",
        "lowercase state_ok no match",
        "STATE_TESTS_OK_EXTRA is one token, no _OK boundary",
        "",
        "STATE_TESTS_OK в начале строки",
        "маркер в конце: текст STATE_TESTS_OK",
        "рядом с пунктуацией: (STATE_TESTS_OK),",
        "рядом с кириллицей до: головаSTATE_TESTS_OK",
        "рядом с кириллицей после: живой тест STATE_TESTS_OKголова",
        "рядом с unicode-буквой до: ÉSTATE_TESTS_OK",
        "рядом с unicode-буквой после: STATE_TESTS_OKÉ",
        "рядом с цифрой до: 1STATE_TESTS_OK",
        "рядом с цифрой после: STATE_TESTS_OK1",
        "рядом с подчёркиванием до: _STATE_TESTS_OK",
        "несколько маркеров: STATE_TESTS_OK и X_OK",
        "частичный: STATE_TESTS_O",
        "некорректный хвост: STATE_TESTS_OK1",
        "STATE_TESTS_OK\u00a0после NBSP",
        "STATE_TESTS_OK после таба:\tконец",
    ]
    for text in marker_cases:
        got = check.find_ok_marker(text)
        ref = MARKER.search(text)
        ref_g = ref.group(0) if ref else None
        if got != ref_g:
            failures += 1
            print("FAIL marker: %r -> linear=%r regex=%r" % (text, got, ref_g))
    print("marker equivalence: %d cases checked" % len(marker_cases))

    # --- 2) years linear scanner equivalence ---------------------------------
    camel_cases = [
        ("год 601 по верблюду", ["601"]),
        ("год 612 по верблюду и 629 по верблюду", ["612", "629"]),
        ("нет дат", []),
        ("99999 по верблюду", ["9999"]),
        ("12345 по верблюду", ["2345"]),
        ("12 по верблюду", []),
        ("\t9999\tпо верблюду", ["9999"]),
        ("в 9999 по верблюду году", ["9999"]),
    ]
    for line, expected in camel_cases:
        got = check.camel_years_linear(line)
        ref = YEARS_RX.findall(line)
        if got != ref:
            failures += 1
            print("FAIL camel linear=%r regex=%r line=%r" % (got, ref, line))
    print("camel equivalence: %d cases checked" % len(camel_cases))

    # --- 3) validator accepts every current canon_rules.json pattern ---------
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    patterns = []
    for r in rules.get("forbid", []):
        patterns.append(r["pattern"])
    for r in rules.get("max_count", rules.get("forbid", []) and [] or []):
        patterns.append(r["pattern"])
    for r in rules.get("forbid_filenames", []):
        patterns.append(r["pattern"])
    # years_by_camel has no "pattern" field: its scanner is linear and is
    # covered separately by the camel cases above
    rejected = [p for p in patterns if not check.rule_pattern_safe(p)]
    if rejected:
        failures += 1
        print("FAIL: current rules rejected by validator: %r" % rejected)
    print("validator: %d current patterns accepted" % len(patterns))

    # --- 4) validator shapes: ReDoS rejected, linear accepted ----------------
    catastrophic = [
        # classic nested quantifiers
        "(a+)+b",
        "(a*)*b",
        "((a+)b)+c",
        "(a|aa)+b",
        "(a+){2,}b",
        "(?:a+)+b",
        ".*.*.*.*.*Z",
        "(a|aa)+$",
        "(a|a?)+$",
        "([a-z]+)+$",
        "(a+)+$",
        ".*.*",
        "..*.*",
        "(?:.*a)+X",
        # '?' is a bounded quantifier: a quantified atom inside a quantified
        # group makes partitions ambiguous
        "(a?)+Z",
        r"(\d{3,4})+Z",
        # composable literal alternatives
        "(ab|a|b)+Z",
        "(ab|c|de|abc)+Z",
        # duplicate alternatives: two ways to match the same text
        "(с|со|со)+Z",
        # empty alternative
        "(a|)+Z",
        # lazy quantifier
        ".*?x",
        "a?+",
        # class 2: adjacent repetitions of the same atom (empirically cubic)
        "a*a*Z",
        "a*a*a*a*Z",
        "a+a+a+a+Z",
        r"\s*\s*Z",
        # class 3: overlapping charsets in one flexible run
        "(.*)(.*)Z",
        "(a*)(a*)Z",
        r"(\d+)(\d+)Z",
        r"\w*\d*Z",
        # class 4: mixtures — unbounded unit overlapping another unit
        "(a*b)a*Z",
        ".*a*Z",
        "(a|aa)a*Z",
        # class 1/5: chains of ambiguous/bounded units above the budget
        "(a|aa)" * 8 + "Z",
        "(a|aa)" * 20 + "Z",
        r"(\d{3,4})" * 8 + "Z",
        r"(\d{3,4})" * 20 + "Z",
        "a{1,2}" * 8 + "Z",
        r"(\d{3,4}){7}",
        r"(\d{3,4}){20}",
        # group with an unbounded quantifier inside, itself quantified
        "(a+){2}",
        "(a+){2,3}",
        # conservative rejects: not provably safe with this analysis
        "(a|ab)" * 8 + "Z",
        # zero-consumption atoms must NOT act as a min-barrier between two
        # sliding unbounded units (stage E-3 regression: b*(?:a{0})b*Z)
        "b*(?:a{0})b*Z",
        "b*a{0}b*Z",
        "b*(?:[a]{0})b*Z",
        r"b*(?:\d{0})b*Z",
        "b*(?:.{0})b*Z",
        "b*(?:ab){0}b*Z",
        "a*(?:x{0}y{0})a*Z",
        "a*(?:(?:xy){0})a*Z",
        "a*(?:x{0})a*Z",
        "a*(?:[x]{0})a*Z",
        # stage E-4: a zero-consumption ALTERNATIVE BRANCH must give the
        # group min 0 even when other branches consume (running-minimum
        # model wrongly took the required atom of another branch)
        "a*(?:x{0}|b)a*Z",
        "a*(?:|b)a*Z",
        "a*(?:x{0}|b|c)a*Z",
        "a*(?:(?:x{0}|b))a*Z",
        "a*(?:b|x{0})a*Z",
        "a*(?:x{0}y{0})a*Z",
        "a*(?:(?:x{0}))a*Z",
        "a*(?:(?:(?:x{0})))a*Z",
        "b*(a|)b*Z",
        "b*(|a)b*Z",
        "b*(a||b)b*Z",
        "a*(?:x?)a*Z",
        "a*(?:)a*Z",
        "b*(?:a{0,0})b*Z",
        # stage E-5: a required fixed atom with an OVERLAPPING charset does
        # not split the flexible run (the match redistributes through it)
        "a*aa*Z",
        "a*aaa*Z",
        "a*a{1}a*Z",
        "a*(?:a)a*Z",
        "a*(?:a|b)a*Z",
        "a*[a]a*Z",           # loose class charset: conservative overlap
        r"a*\wa*Z",           # 'a' is a word char: \w overlaps a*
        "a*.a*Z",             # dot overlaps everything
        "a*(?:a{1})a*Z",
        "a*b*a*Z",            # empirically SLOW: the empty b* merges the a* runs
        "a*[b]a*Z",           # conservative reject: class charset not computed
        # stage E-5 verdict change (was accepted in E-4): '.*X.*' has the
        # same shape as '.*X.*Z', which explodes on texts with many X
        # (empirically 0.67 s at 10 KB, killed at 3 MB): the required X is
        # overlapped by the LEFT dot-star, so the partitions (start of .*X,
        # end of trailing .*) multiply — the model cannot prove a pin
        ".*X.*",
    ]
    for p in catastrophic:
        if not check.rule_pattern_safe(p):
            continue
        failures += 1
        print("FAIL: validator missed catastrophic pattern %r" % p)
    allowed = [
        r"\b(с|со)\s+Жеби\b",
        r"\b(в|из|к|за)\s+Жебь\b",
        r"(\d{3,4})\s+по\s+верблюду",
        r"\bигрок\w*",
        r"(?:https?://)?example\.(com|org)",
        r"^[A-Z]+$",
        r"(\d{3,4})",
        r"[a-z]+",
        r"foo|bar",
        r"(?:abc)+",
        r"a.*Z",
        r"601 по верблюду",
        r"(\b(?:foo|bar)\b)+",
        "a?",
        "colou?r",
        r"x{2,3}",
        r"хор\s+без\s+суда",
        r"оказывается\s+повсюду",
        # required literals pin the run: baseline-linear shapes
        "a*ba*Z",
        "a+aX",
        ".*X",
        r"\w*\s*Z",
        "(?:a|ab)+Z",
        "(?:со|с)*a*Z",
        "(a+)?(b+)?c",
        # short ambiguous chains inside the branching budget
        r"(\d{3,4})" * 3 + "Z",
        "(a|aa)(a|aa)(a|aa)Z",
        "(a|ab)(a|ab)(a|ab)Z",
        "a{1,2}b{1,2}" * 4 + "Z",
        "(с|со)(с|со)",
        r"(\d{3,4}){2}",
        r"(\d{3,4}){6}",
        r"(\d{3,4})\s*по\s*верблюду",
        r"ulitka|snail|улитк",
        r"злат\w*\s+чертог",
        # zero-consumption shapes that must NOT create false barriers or
        # unjustified rejects (stage E-3)
        "b*a{0}cb*Z",          # required 'c' pins the two b* runs apart
        "b*(?:a{0}c)b*Z",      # 'c' inside the group pins them apart
        "a*(?:xy{0})bZ",       # 'x' is required (the {0} binds to 'y' only)
        "(?:a{0})",
        "(?:ab){0}Z",
        "(?:x{0}y)Z",
        "x{0}y",
        "a{0,3}",
        "(?:a{0}|b)c",
        "a{2}",
        # stage E-4: a required atom pins the boundary even inside a group
        # whose OTHER branch is zero; branch order must not change verdicts
        "a*(?:x{0}y)a*Z",      # {0} binds to x only, y is required
        "a*(?:x{0}y{0}c)a*Z",  # required c inside the branch
        "(?:b|x{0})",
        "(?:c|b|x{0})",
        "(?:x{0}|b|c)",
        "a*(?:(?:(?:x{0})))Z",  # nested zero groups alone, pinned by Z
        "(?:((?:x{0})))",
        "(?:ab|c)",
        "(?:abc|b)",
        # stage E-5: required atoms WITHOUT charset overlap really pin the
        # run and stay accepted (baseline-linear cost only)
        "a*ba*Z",
        r"a*\da*Z",
        "a*c+a*Z",
        "a*b{1}a*Z",           # {1} on a non-overlapping literal: real pin
    ]
    for p in allowed:
        if check.rule_pattern_safe(p):
            continue
        failures += 1
        print("FAIL: validator rejected a linear pattern %r" % p)
    print("validator shapes: %d catastrophic rejected, %d linear accepted"
          % (len(catastrophic), len(allowed)))

    # --- 5) pathological input timing on the linear scanners -----------------
    timings = []
    for size in (100_000, 200_000, 400_000):
        pathological = "a" * size + " OK"
        t0 = time.perf_counter()
        check.find_ok_marker(pathological)
        dt = time.perf_counter() - t0
        timings.append((size, dt))
        if dt > 2.0:
            failures += 1
            print("FAIL: marker scan too slow at %d chars (%.4fs)" % (size, dt))
    camel_line = ("1" * 50000 + " по верблюду ") * 4
    t0 = time.perf_counter()
    got = check.camel_years_linear(camel_line)
    dt = time.perf_counter() - t0
    timings.append((len(camel_line), dt))
    if dt > 2.0:
        failures += 1
        print("FAIL: camel scan too slow (%.4fs)" % dt)
    if got != ["1111", "1111", "1111", "1111"]:
        failures += 1
        print("FAIL: camel pathological years %r" % (got,))
    print("timing table (size, seconds): %s" % timings)

    # --- 6) E-6A no-fallback proof: canon_lint never uses Python re ---------
    if not check._RE2_AVAILABLE:
        print("sec 6 skipped (RE2 unavailable in this interpreter)")
    else:
        orig_compile = re.compile
        orig_rules_path = check.RULES_PATH
        orig_root = check.ROOT
        compiled = []
        calls = {"n": 0}
        try:
            re.compile = lambda pattern, flags=0: _spy_compile(
                pattern, flags, orig_compile, compiled, calls)
            with tempfile.TemporaryDirectory(prefix="siriya_regex_test_") as td:
                tdp = Path(td)
                (tdp / "scan").mkdir()
                rules_obj = {
                    "scan_dirs": ["scan"],
                    "scan_ext": [".txt"],
                    "forbid": [
                        # classic ReDoS shapes are now COMPILED by RE2 and
                        # executed in linear time (E-6A architecture)
                        {"id": "R-danger", "pattern": "(a+)+Z", "severity": "error",
                         "message": "linear under RE2"},
                        {"id": "R-zero", "pattern": "b*(?:a{0})b*Z", "severity": "error",
                         "message": "linear under RE2"},
                        {"id": "R-safe", "pattern": "STATE_TESTS_OK", "severity": "error",
                         "message": "ordinary rule"},
                    ],
                }
                check.RULES_PATH = tdp / "canon_rules.json"
                check.RULES_PATH.write_text(json.dumps(rules_obj, ensure_ascii=False),
                                            encoding="utf-8")
                check.ROOT = tdp
                err_before = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                err_after = check.errors
                lint_out = buf.getvalue()
        finally:
            re.compile = orig_compile
            check.RULES_PATH = orig_rules_path
            check.ROOT = orig_root
        # Python re must NEVER compile a rule: rules go through RE2 only.
        # (The str re.compile calls that a spy may observe belong to the
        # stdlib itself, e.g. glob's lazy b'([*?[])' import.)
        py_rule_compiles = [c for c in compiled
                            if isinstance(c, str) and c in
                            ("(a+)+Z", "b*(?:a{0})b*Z", "STATE_TESTS_OK")]
        if py_rule_compiles:
            failures += 1
            print("FAIL: rule reached Python re.compile: %r" % py_rule_compiles)
        if err_after != err_before:
            failures += 1
            print("FAIL: valid rules reported errors under RE2 "
                  "(delta %d): %r" % (err_after - err_before, lint_out[:200]))
        if "R-danger" not in lint_out and "R-zero" not in lint_out:
            # nothing failed: both ReDoS-shaped rules scanned the lines
            # silently under RE2 - fine; the point is zero Python-re use
            pass
        print("sec 6 no-fallback proof: %d python-re.compile calls for rules "
              "(expect 0), RE2 executed all %d rules without errors "
              "(errors delta %d)" % (len(py_rule_compiles), 3,
                                     err_after - err_before))

        # 6b) invalid syntax -> comprehensible [ERROR], rule NOT enforced
        orig_rules_path = check.RULES_PATH
        orig_root = check.ROOT
        try:
            with tempfile.TemporaryDirectory(prefix="siriya_regex_test_") as td:
                tdp = Path(td)
                (tdp / "scan").mkdir()
                rules_obj = {
                    "scan_dirs": ["scan"],
                    "scan_ext": [".txt"],
                    "forbid": [
                        {"id": "R-badsyntax", "pattern": "(?:", "severity": "error",
                         "message": "must not compile"},
                    ],
                }
                check.RULES_PATH = tdp / "canon_rules.json"
                check.RULES_PATH.write_text(json.dumps(rules_obj, ensure_ascii=False),
                                            encoding="utf-8")
                check.ROOT = tdp
                err_before = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                err_after = check.errors
                lint_out = buf.getvalue()
        finally:
            check.RULES_PATH = orig_rules_path
            check.ROOT = orig_root
        if err_after - err_before < 1:
            failures += 1
            print("FAIL: invalid RE2 syntax was not reported as ERROR")
        if "R-badsyntax" not in lint_out or "rule not compiled (RE2)" not in \
                lint_out or "NOT enforced" not in lint_out:
            failures += 1
            print("FAIL: compile error is not comprehensible: %r"
                  % lint_out[:200])
        print("sec 6b compile-error proof: comprehensible [ERROR] with rule "
              "id reported (errors delta %d)" % (err_after - err_before))

    # --- 7) empirical backtracking probes in isolated subprocesses ----------
    # Each probe runs re.search on an adversarial input in a separate
    # subprocess with a hard 5 s timeout, so a hanging pattern cannot block
    # this test. A probe confirms (a) the DANGEROUS verdict of shapes the
    # validator rejects and (b) the FAST verdict of the accepted shapes.
    probe_code = (
        "import re, time, sys\n"
        "pat = sys.argv[1]\n"
        "text = sys.stdin.read()\n"
        "t0 = time.perf_counter()\n"
        "re.search(pat, text)\n"
        "print('%.3f' % (time.perf_counter() - t0))\n"
    )
    probes = [
        # (label, pattern, text, expect_slow, allow_conservative_reject)
        # allow_conservative_reject=True marks a shape that is empirically
        # linear but not provably safe with this analysis: the validator
        # MAY reject it (documented conservative policy), never accept a
        # slow shape.
        ("C1-small", "(a|aa)(a|aa)(a|aa)Z", "a" * 10 + "X", False, False),
        ("C1-big", "(a|aa)" * 30 + "Z", "a" * 61 + "X", True, False),
        ("C1ab-big", "(a|ab)" * 30 + "Z", "a" * 61 + "X", False, True),
        ("C2-4stars", "a*a*a*a*Z", "a" * 1500 + "X", True, False),
        ("C2-2stars", "a*a*Z", "a" * 3000 + "X", True, False),
        ("C3-dotdot", "(.*)(.*)Z", "a" * 3000 + "X", True, False),
        ("C3-aa", "(a*)(a*)Z", "a" * 3000 + "X", True, False),
        ("C3-digits", r"(\d+)(\d+)Z", "1" * 2000 + "X", True, False),
        ("C3-worddigit", r"\w*\d*Z", "1" * 3000 + "X", True, False),
        ("C3-wordspace", r"\w*\s*Z", "a" * 2500 + " " * 2500 + "X", False, False),
        ("C4-groupstar", "(a*b)a*Z", "ab" * 200000 + "a" * 200000 + "X", True, False),
        ("C4-dotastar", ".*a*Z", "a" * 3000 + "X", True, False),
        ("C4-clean-unb", "(?:со|с)*a*Z", "с" * 3000 + "aX", False, False),
        ("C4-pin", "a*ba*Z", "a" * 3000 + "X", False, False),
        ("C4-lit-after-unb", "a+aX", "a" * 4000 + "b", False, False),
        ("C4-dotlit", ".*X", "a" * 8000 + "b", False, False),
        ("C5-d34-20", r"(\d{3,4})" * 20 + "Z", "1" * 300 + "X", True, False),
        ("C5-d34-3", r"(\d{3,4})(\d{3,4})(\d{3,4})Z", "1" * 20 + "X", False, False),
        ("C5-a12", "a{1,2}" * 30 + "Z", "a" * 61 + "X", True, False),
        ("C5-disjoint", "a{1,2}b{1,2}" * 10 + "Z", "ab" * 15 + "X", False, False),
        # zero-consumption units between two sliding unbounded runs
        ("Z0-group", "b*(?:a{0})b*Z", "b" * 3000 + "X", True, False),
        ("Z0-top", "b*a{0}b*Z", "b" * 3000 + "X", True, False),
        ("Z0-class", "b*(?:[a]{0})b*Z", "b" * 3000 + "X", True, False),
        ("Z0-pinned", "b*a{0}cb*Z", "b" * 3000 + "X", False, False),
        ("Z1-alt", "a*(?:x{0}|b)a*Z", "a" * 3000 + "X", True, False),
        ("Z1-empty-alt", "a*(?:|b)a*Z", "a" * 3000 + "X", True, False),
        ("Z1-nested", "a*(?:(?:x{0}|b))a*Z", "a" * 3000 + "X", True, False),
        ("Z1-pinned", "a*(?:x{0}y)a*Z", "a" * 3000 + "X", False, False),
        # stage E-5: overlap-based partition explosion vs real pins
        ("E5-overlap", "a*aa*Z", "a" * 3000 + "X", True, False),
        ("E5-pin", "a*ba*Z", "a" * 3000 + "X", False, False),
        ("E5-bstar", "a*b*a*Z", "a" * 3000 + "X", True, False),
        ("E5-escape", r"a*\wa*Z", "a" * 3000 + "X", True, False),
        ("E5-dotx", ".*X.*Z", ("a" * 150 + "X") * 300 + "b", True, False),
    ]
    probe_failures = 0
    conservative = []
    for label, pat, text, expect_slow, allow_conservative in probes:
        t0 = time.perf_counter()
        try:
            r = subprocess.run([sys.executable, "-I", "-c", probe_code, pat],
                               input=text, capture_output=True, text=True,
                               timeout=5)
            out = (r.stdout or "").strip()
            got_slow = (not out) or float(out.splitlines()[-1]) > 2.0
            detail = out.splitlines()[-1] if out else "rc=%s" % r.returncode
        except subprocess.TimeoutExpired:
            got_slow = True
            detail = "killed by 5s timeout"
        if got_slow != expect_slow:
            failures += 1
            probe_failures += 1
            print("FAIL probe %s: expect slow=%s, got slow=%s (%s)"
                  % (label, expect_slow, got_slow, detail))
        # validator verdict must agree with the measured reality:
        # a slow shape must always be rejected; a fast shape may only be
        # rejected when marked as a documented conservative reject
        v_safe = check.rule_pattern_safe(pat)
        if expect_slow and v_safe:
            failures += 1
            probe_failures += 1
            print("FAIL probe %s: validator accepts a measured-slow shape" % label)
        if not expect_slow and not v_safe:
            if allow_conservative:
                conservative.append(label)
            else:
                failures += 1
                probe_failures += 1
                print("FAIL probe %s: validator rejects a measured-linear "
                      "shape without a conservative-reject mark" % label)
    if probe_failures:
        print("empirical probes: %d of %d failed" % (probe_failures, len(probes)))
    else:
        note = ("; conservative rejects: " + ", ".join(conservative)) \
            if conservative else ""
        print("empirical probes: %d/%d agree (slow shapes rejected, linear "
              "shapes accepted%s)" % (len(probes), len(probes), note))

    # --- 8) zero-consumption semantics audit matrix (stage E-4) --------------
    # Every construction that can create an empty match, across all atom
    # types the whitelist accepts. expect_safe=False means the shape leaves
    # two sliding unbounded units merged through a zero-consumption path
    # (empirically cubic in Python re); expect_safe=True means a required
    # atom pins the boundary or no second sliding run exists.
    matrix = [
        # {0} / {0,0} on every atom type, between two sliding runs
        ("b*(?:a{0})b*Z", False, "literal {0} in group"),
        ("b*a{0}b*Z", False, "literal {0} top-level"),
        ("b*(?:[a]{0})b*Z", False, "class {0}"),
        (r"b*(?:\d{0})b*Z", False, "escape {0}"),
        ("b*(?:.{0})b*Z", False, "dot {0}"),
        ("b*(?:a{0,0})b*Z", False, "literal {0,0}"),
        # '?' and empty groups
        ("a*(?:x?)a*Z", False, "x? zero branch"),
        ("a*(?:)a*Z", False, "empty group"),
        ("b*(a|)b*Z", False, "empty alternative last"),
        ("b*(|a)b*Z", False, "empty alternative first"),
        ("b*(a||b)b*Z", False, "empty alternative middle"),
        # alternatives where only SOME branches are empty
        ("a*(?:x{0}|b)a*Z", False, "E-4 counterexample"),
        ("a*(?:|b)a*Z", False, "empty first branch"),
        ("a*(?:x{0}|b|c)a*Z", False, "three branches, one zero"),
        ("a*(?:b|x{0})a*Z", False, "permutation of the counterexample"),
        ("a*(?:(?:x{0}|b))a*Z", False, "nested counterexample"),
        # nested zero groups
        ("a*(?:(?:x{0}))a*Z", False, "nested zero group"),
        ("a*(?:(?:(?:x{0})))a*Z", False, "double nested zero group"),
        ("(?:((?:x{0})))", True, "nested zero groups alone"),
        # zero and required atoms in sequence
        ("a*(?:x{0}y{0})a*Z", False, "two zero atoms"),
        ("a*(?:xy{0})a*Z", True, "required x pins ({0} binds y only)"),
        ("a*(?:x{0}y)a*Z", True, "required y pins ({0} binds x only)"),
        ("a*(?:x{0}y{0}c)a*Z", True, "required c pins inside the branch"),
        # branch order must not change the verdict
        ("(?:x{0}|b)", True, "perm base"),
        ("(?:b|x{0})", True, "perm swapped"),
        ("(?:x{0}|b|c)", True, "perm three branches"),
        ("(?:c|b|x{0})", True, "perm three branches swapped"),
        # real minimum lengths of alternatives
        ("(?:ab|c)", True, "branch mins 2 and 1 -> group min 1"),
        ("(?:abc|b)", True, "branch mins 3 and 1"),
        # quantifier interactions around {0}
        ("a{0}+", False, "nothing to repeat after {0}"),
        ("a{0}?", False, "lazy quantifier after {0}"),
        ("a{0}{2}", False, "double quantifier after {0}"),
        # safe shapes: pin or disjoint charset
        ("(?:a{0})", True, "zero group alone"),
        ("(?:(?:a{0}))", True, "nested zero group alone"),
        ("(?:a{0}|b)c", True, "required c pins"),
        ("(?:a{0}|b)c*", True, "c* has a disjoint charset"),
        ("a*(?:x{0}|b{0}c)", True, "second branch requires c, no second run"),
        ("a*(?:x{0}|b)c", True, "required c pins after the group"),
        ("b*(?:a{0}c)b*Z", True, "required c inside the group pins"),
    ]
    matrix_failures = 0
    for pat, want_safe, comment in matrix:
        got_safe = check.rule_pattern_safe(pat)
        if got_safe != want_safe:
            failures += 1
            matrix_failures += 1
            print("FAIL matrix %r: safe=%s, want=%s (%s)"
                  % (pat, got_safe, want_safe, comment))
    if matrix_failures:
        print("audit matrix: %d of %d failed" % (matrix_failures, len(matrix)))
    else:
        print("audit matrix: %d/%d verdicts correct (zero-consumption "
              "semantics across all accepted atom types)" % (len(matrix), len(matrix)))

    # --- 10) E-6A: RE2 vs Python re equivalence on all 15 canon rules -------
    if not check._RE2_AVAILABLE:
        print("sec 10 RE2-equivalence skipped (RE2 unavailable in this "
              "interpreter - expected for the main Python 3.15)")
    else:
        import re2 as re2_mod
        rules10 = json.loads(Path(check.RULES_PATH).read_text(encoding="utf-8"))
        opts_i = re2_mod.Options()
        opts_i.case_sensitive = False
        opts_s = re2_mod.Options()
        opts_s.case_sensitive = True
        real_lines = []
        for d in rules10["scan_dirs"]:
            for p in sorted((check.ROOT / d).rglob("*")):
                if p.is_file() and p.suffix.lower() in rules10["scan_ext"]:
                    real_lines.extend(p.read_text(encoding="utf-8",
                                                  errors="replace").splitlines())
        syn = ["в Жеби", "с Жеби", "с Жебью", "в Жебь", "Жебе", "Жебе.", "Жебем",
               "Абдуллъ", "Абдулла", "маджахед", "моджахед", "МоДжаХеД",
               "Хасан", "хасан", "трёхгорб", "трехгорб", "ТРЁХГОРБ",
               "злат чертог", "злат-солнце чертог", "ЗлатЧертог чертог",
               "хор без суда", "хоровод без суда", "ХОР  БЕЗ  СУДА",
               "оказывается повсюду", "игрок", "Игрок и игрок", "1игрок",
               "игрок.игрок", "в\u00a0Жеби", "с\u2003Жеби", "в Жебь\u00a0",
               "«в Жебь»", "(с Жеби)", "—в Жебь—", "", "в-Жебь", "вЖебь",
               "1в Жебь", "в Жебь1", "в Жебьх"]
        eq_fail = 0
        for sec in ("forbid", "max_count", "forbid_filenames"):
            for r in rules10.get(sec, []):
                fi = "i" in r.get("flags", "")
                rx_py = re.compile(r["pattern"], re.IGNORECASE if fi else 0)
                rx2 = check.compile_rule(r["pattern"], r.get("flags"))
                texts = real_lines + syn
                if sec == "forbid_filenames":
                    texts = [p.name for dd in r.get("dirs", [])
                             for p in sorted((check.ROOT / dd).rglob("*"))]
                diff = 0
                for t in texts:
                    a = bool(rx_py.search(t))
                    b = bool(rx2.search(t))
                    if sec == "max_count":
                        na = len(list(rx_py.finditer(t)))
                        nb = len(list(rx2.finditer(t)))
                        if na != nb:
                            diff += 1
                            if diff <= 3:
                                print("  10) count diff %s %r: py=%d re2=%d"
                                      % (r["id"], t[:40], na, nb))
                            continue
                    if a != b:
                        diff += 1
                        if diff <= 3:
                            print("  10) bool diff %s %r: py=%s re2=%s"
                                  % (r["id"], t[:60], a, b))
                if diff:
                    eq_fail += 1
                    print("FAIL 10: %s differs on %d inputs" % (r["id"], diff))
        # IGNORECASE ё/Ё + Unicode whitespace class identity (29 chars)
        import re2 as _re2
        ws_all = [c for c in map(chr, range(0x110000)) if re.match(r"\s", c)]
        ws_miss = [c for c in ws_all
                   if not _re2.match(check.PYTHON_WS_RE2_CLASS, c, opts_s)]
        if ws_miss:
            eq_fail += 1
            print("FAIL 10: whitespace class misses %d chars"
                  % len(ws_miss))
        word_probe = ["а", "ё", "é", "日", "_", "5", "٠", "‿", "̈", "Ⅰ"]
        w_bad = [c for c in word_probe
                 if bool(re.match(r"\w", c)) !=
                 bool(_re2.match(check.WORD_RE2_CLASS, c, opts_s))]
        if w_bad:
            eq_fail += 1
            print("FAIL 10: word class probe mismatch: %r" % w_bad)
        if eq_fail:
            failures += eq_fail
            print("sec 10 RE2-equivalence: %d failures" % eq_fail)
        else:
            print("sec 10 RE2-equivalence: 15/15 rules identical on %d real "
                  "lines + %d synthetic cases; \\s=%d chars, \\w probe clean"
                  % (len(real_lines), len(syn), len(ws_all)))

    # --- 11) input limits: each exceeded limit is an ERROR (fail-secure) ----
    if not check._RE2_AVAILABLE:
        print("sec 11 limits skipped (RE2 unavailable in this interpreter)")
    else:
        limit_fail = 0
        orig = {k: getattr(check, k) for k in
                ("MAX_LINE_LENGTH", "MAX_TOTAL_CHARS", "MAX_RULES",
                 "RULE_TIME_BUDGET", "RULES_PATH", "ROOT")}
        try:
            with tempfile.TemporaryDirectory(prefix="siriya_limits_") as td:
                tdp = Path(td)
                (tdp / "scan").mkdir()
                # the over-limit line CONTAINS a match for the rule ("STATE"):
                # a false pass is impossible - if the line were scanned,
                # R-x would fire
                long_line = "STATE" + "a" * 20
                (tdp / "scan" / "f.txt").write_text(long_line + "\n", encoding="utf-8")
                check.RULES_PATH = tdp / "canon_rules.json"
                check.ROOT = tdp

                # spy wrapper around compile_rule: counts RE2 compiles and
                # search()/finditer() calls, proving nothing ran
                spy = {"compile": 0, "search": 0, "finditer": 0}
                orig_cr = check.compile_rule

                def spy_cr(pattern, flags):
                    spy["compile"] += 1
                    rx = orig_cr(pattern, flags)
                    o_search = rx.search
                    o_finditer = rx.finditer

                    def sp_search(t):
                        spy["search"] += 1
                        return o_search(t)

                    def sp_finditer(t):
                        spy["finditer"] += 1
                        return o_finditer(t)

                    class SpiedRx:
                        def search(self, t):
                            return sp_search(t)

                        def finditer(self, t):
                            return sp_finditer(t)

                    return SpiedRx()

                check.MAX_LINE_LENGTH = 10
                check.MAX_TOTAL_CHARS = 10 ** 9
                check.MAX_RULES = 100
                check.RULE_TIME_BUDGET = 60.0
                check.compile_rule = spy_cr
                check.RULES_PATH.write_text(json.dumps({
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid": [{"id": "R-x", "pattern": "STATE",
                                "severity": "error", "message": "x"}],
                }), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                out = buf.getvalue()
                if check.errors - err0 < 1 or "MAX_LINE_LENGTH" not in out:
                    limit_fail += 1
                    print("FAIL 11: long line did not produce a MAX_LINE_LENGTH "
                          "ERROR: %r" % out[:150])
                if "R-x scan/f.txt:1" in out:
                    limit_fail += 1
                    print("FAIL 11: over-limit line produced a rule match "
                          "(the line WAS scanned)")
                if spy["compile"] != 0 or spy["search"] != 0 \
                        or spy["finditer"] != 0:
                    limit_fail += 1
                    print("FAIL 11: RE2 was invoked despite the line-limit "
                          "breach: %r" % spy)
                check.compile_rule = orig_cr
                check.MAX_LINE_LENGTH = 10 ** 6   # restore for later phases

                check.MAX_TOTAL_CHARS = 5
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                if check.errors - err0 < 1 or "MAX_TOTAL_CHARS" not in buf.getvalue():
                    limit_fail += 1
                    print("FAIL 11: MAX_TOTAL_CHARS did not produce an ERROR")
                check.MAX_TOTAL_CHARS = 10 ** 9

                check.MAX_RULES = 1
                check.RULES_PATH.write_text(json.dumps({
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid": [
                        {"id": "R-a", "pattern": "a", "severity": "error", "message": "x"},
                        {"id": "R-b", "pattern": "b", "severity": "error", "message": "x"},
                    ],
                }), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                if check.errors - err0 < 1 or "MAX_RULES" not in buf.getvalue():
                    limit_fail += 1
                    print("FAIL 11: MAX_RULES did not produce an ERROR")
                check.MAX_RULES = 100
        finally:
            for k, v in orig.items():
                setattr(check, k, v)
        if limit_fail:
            failures += limit_fail
            print("sec 11 limits: %d failures" % limit_fail)
        else:
            print("sec 11 limits: line-limit fail-secure proven by spy "
                  "(0 RE2 calls on a matching line) + MAX_TOTAL_CHARS/"
                  "MAX_RULES produce ERROR")

    # --- 11b) RULE_TIME_BUDGET: deterministic fail-secure stop --------------
    # A fake clock makes the budget expire at a chosen monotonic() call
    # index, so the test does not depend on machine speed.
    if not check._RE2_AVAILABLE:
        print("sec 11b budget skipped (RE2 unavailable in this interpreter)")
    else:
        budget_fail = 0
        orig_time = check.time
        orig_cr = check.compile_rule
        orig_camel = check.camel_years_linear
        orig = {k: getattr(check, k) for k in
                ("MAX_LINE_LENGTH", "MAX_TOTAL_CHARS", "MAX_RULES",
                 "RULE_TIME_BUDGET", "RULES_PATH", "ROOT")}

        class _FakeTime:
            """time module stand-in: monotonic() returns queued values, then
            holds the last one."""
            def __init__(self, values):
                self.values = list(values)

            def monotonic(self):
                if len(self.values) > 1:
                    return self.values.pop(0)
                return self.values[0]

        try:
            with tempfile.TemporaryDirectory(prefix="siriya_budget_") as td:
                tdp = Path(td)
                (tdp / "scan").mkdir()
                # line 1 contains a match for R-1 (must still be reported
                # BEFORE the stop), line 2 carries an out-of-allowlist year
                # (the years section must NOT run after the budget stop);
                # data/x.json lacks "src" (the json section must NOT run)
                (tdp / "scan" / "f.txt").write_text(
                    "STATE ok\n9999 по верблюду\n", encoding="utf-8")
                (tdp / "data").mkdir()
                (tdp / "data" / "x.json").write_text(
                    '{"text": "abc"}', encoding="utf-8")
                check.RULES_PATH = tdp / "canon_rules.json"
                check.ROOT = tdp
                check.MAX_LINE_LENGTH = 10 ** 6
                check.MAX_TOTAL_CHARS = 10 ** 9
                check.MAX_RULES = 100
                check.RULE_TIME_BUDGET = 60.0

                compiles = []
                camel_calls = []

                def spy_cr(pattern, flags):
                    compiles.append(pattern)
                    return orig_cr(pattern, flags)

                def spy_camel(line):
                    camel_calls.append(line)
                    return orig_camel(line)

                check.compile_rule = spy_cr
                check.camel_years_linear = spy_camel
                # monotonic call trace: 1 = deadline; 2 = forbid R-1 line 1
                # (0 -> scan continues, match reported); 3 = forbid R-1
                # line 2 (100 -> budget fires); later rules, years and json
                # sections must not run
                check.time = _FakeTime([0.0, 0.0, 100.0])

                check.RULES_PATH.write_text(json.dumps({
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid": [
                        {"id": "R-1", "pattern": "STATE", "severity": "warn",
                         "message": "m1"},
                        {"id": "R-2", "pattern": "zzz", "severity": "error",
                         "message": "m2"},
                    ],
                    "years_by_camel": {"id": "R-years", "severity": "error",
                                       "allowed": [601], "message": "y"},
                    "json_text_needs_src": {"id": "R-src", "severity": "warn",
                                            "dirs": ["data"], "allowed": ["к"],
                                            "message": "s"},
                }), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                out = buf.getvalue()
                if check.errors - err0 != 1:
                    budget_fail += 1
                    print("FAIL 11b: expected exactly one R-limit ERROR, "
                          "got delta %d: %r" % (check.errors - err0,
                                                out[:200]))
                if out.count("[ERROR] R-limit") != 1 \
                        or "RULE_TIME_BUDGET" not in out:
                    budget_fail += 1
                    print("FAIL 11b: budget ERROR missing/duplicated: %r"
                          % out[:200])
                if compiles != ["STATE"]:
                    budget_fail += 1
                    print("FAIL 11b: rules compiled after the budget stop: %r"
                          % compiles)
                if "R-1 scan/f.txt:1" not in out:
                    budget_fail += 1
                    print("FAIL 11b: the match on line 1 was lost before "
                          "the stop")
                if "R-years" in out or camel_calls:
                    budget_fail += 1
                    print("FAIL 11b: years section ran after the stop "
                          "(camel calls=%d)" % len(camel_calls))
                if "R-src" in out:
                    budget_fail += 1
                    print("FAIL 11b: json section ran after the stop")

                # 11b-2: the budget fires INSIDE the finditer() match loop of
                # a max_count rule: forbid matches nothing (monotonic stays
                # 0 for its two lines), max_count compiles, the 5th
                # monotonic call (inside finditer) returns 100 -> the loop
                # breaks at the first match
                fake2 = _FakeTime([0.0, 0.0, 0.0, 0.0, 100.0])
                check.time = fake2
                compiles.clear()
                camel_calls.clear()
                check.RULES_PATH.write_text(json.dumps({
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid": [
                        {"id": "R-z1", "pattern": "zzz", "severity": "error",
                         "message": "z1"},
                    ],
                    "max_count": [
                        {"id": "R-max", "pattern": "STATE", "severity": "warn",
                         "max": 1, "message": "mc"},
                    ],
                }), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                if check.errors - err0 != 1 \
                        or "RULE_TIME_BUDGET" not in buf.getvalue():
                    budget_fail += 1
                    print("FAIL 11b-finditer: budget did not fire during the "
                          "max_count phase: %r" % buf.getvalue()[:200])
                if "STATE" not in compiles:
                    budget_fail += 1
                    print("FAIL 11b-finditer: max_count rule never compiled")
                if len(compiles) != 2:
                    budget_fail += 1
                    print("FAIL 11b-finditer: rules compiled after the "
                          "budget stop: %r" % compiles)
                if camel_calls:
                    budget_fail += 1
                    print("FAIL 11b-finditer: years scanner ran after the stop")
        finally:
            check.time = orig_time
            check.compile_rule = orig_cr
            check.camel_years_linear = orig_camel
            for k, v in orig.items():
                setattr(check, k, v)
        if budget_fail:
            failures += budget_fail
            print("sec 11b budget: %d failures" % budget_fail)
        else:
            print("sec 11b budget: deterministic FakeTime proof - exactly "
                  "one R-limit, later rules not compiled, years/json "
                  "sections not run, finditer loop interrupted")

    # --- 11c) MAX_PATTERN_LENGTH enforced in compile_rule (production path) --
    if not check._RE2_AVAILABLE:
        print("sec 11c pattern-length skipped (RE2 unavailable)")
    else:
        pl_fail = 0
        p300 = "a" * 300
        p301 = "a" * 301
        try:
            rx = check.compile_rule(p300, "")
            rx.search("a" * 400)
        except Exception as e:
            pl_fail += 1
            print("FAIL 11c: 300-char pattern must compile, got: %s" % e)
        try:
            check.compile_rule(p301, "")
            pl_fail += 1
            print("FAIL 11c: 301-char pattern must NOT compile")
        except ValueError as e:
            if "MAX_PATTERN_LENGTH" not in str(e):
                pl_fail += 1
                print("FAIL 11c: 301-char error lacks the limit name: %s" % e)
        # all three rule sections report [ERROR] with the rule id
        orig_rules_path = check.RULES_PATH
        orig_root = check.ROOT
        try:
            with tempfile.TemporaryDirectory(prefix="siriya_plen_") as td:
                tdp = Path(td)
                (tdp / "scan").mkdir()
                (tdp / "scan" / "f.txt").write_text("x\n", encoding="utf-8")
                check.RULES_PATH = tdp / "canon_rules.json"
                check.ROOT = tdp
                rules_obj = {
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid": [{"id": "R-pl-f", "pattern": "a" * 301,
                                "severity": "error", "message": "x"}],
                    "max_count": [{"id": "R-pl-m", "pattern": "a" * 301,
                                   "severity": "error", "max": 1, "message": "x"}],
                }
                check.RULES_PATH.write_text(json.dumps(rules_obj), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                out = buf.getvalue()
                if "R-pl-f" not in out or "R-pl-m" not in out \
                        or out.count("MAX_PATTERN_LENGTH") != 2:
                    pl_fail += 1
                    print("FAIL 11c: forbid/max_count 301-char rules not "
                          "reported with their ids: %r" % out[:200])
                check.RULES_PATH.write_text(json.dumps({
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid_filenames": [{"id": "R-pl-n", "pattern": "a" * 301,
                                          "severity": "error", "dirs": ["scan"],
                                          "message": "x"}],
                }), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                out = buf.getvalue()
                if "R-pl-n" not in out or "MAX_PATTERN_LENGTH" not in out:
                    pl_fail += 1
                    print("FAIL 11c: forbid_filenames 301-char rule not "
                          "reported: %r" % out[:200])
        finally:
            check.RULES_PATH = orig_rules_path
            check.ROOT = orig_root
        if pl_fail:
            failures += pl_fail
            print("sec 11c pattern-length: %d failures" % pl_fail)
        else:
            print("sec 11c pattern-length: 300 compiles, 301 rejected in "
                  "forbid/max_count/forbid_filenames with [ERROR] + rule id")

    # --- 11d) RULE_TIME_BUDGET inside the json_text_needs_src section -------
    # Deterministic FakeTime: monotonic() returns 0.0 for the first 13 calls
    # (deadline + forbid line + json-before/after a.json + the first three
    # walk_json visits of a.json + json-before/after b.json + the first two
    # walk_json visits of b.json) and 100.0 on call 14 - issued INSIDE
    # walk_json on node "/n/m" of the SECOND json file. Traced empirically
    # (19 budget calls in total for this ruleset).
    if not check._RE2_AVAILABLE:
        print("sec 11d json budget skipped (RE2 unavailable)")
    else:
        json_fail = 0
        orig_time = check.time
        orig = {k: getattr(check, k) for k in
                ("MAX_LINE_LENGTH", "MAX_TOTAL_CHARS", "MAX_RULES",
                 "RULE_TIME_BUDGET", "RULES_PATH", "ROOT")}
        try:
            with tempfile.TemporaryDirectory(prefix="siriya_jsonbud_") as td:
                tdp = Path(td)
                (tdp / "scan").mkdir()
                (tdp / "data").mkdir()
                (tdp / "data" / "a.json").write_text(
                    '{"text": "ok", "n": {"text": "ok"}}', encoding="utf-8")
                (tdp / "data" / "b.json").write_text(
                    '{"text": "ok", "n": {"m": {"text": "ok"}}}',
                    encoding="utf-8")
                (tdp / "data" / "c.json").write_text(
                    '{"text": "never reached"}', encoding="utf-8")
                (tdp / "scan" / "f.txt").write_text("STATE ok\n", encoding="utf-8")
                check.RULES_PATH = tdp / "canon_rules.json"
                check.ROOT = tdp
                check.MAX_LINE_LENGTH = 10 ** 6
                check.MAX_TOTAL_CHARS = 10 ** 9
                check.MAX_RULES = 100
                check.RULE_TIME_BUDGET = 60.0
                check.time = _FakeTime([0.0] * 13 + [100.0])
                check.RULES_PATH.write_text(json.dumps({
                    "scan_dirs": ["scan"], "scan_ext": [".txt"],
                    "forbid": [{"id": "R-x", "pattern": "STATE",
                                "severity": "warn", "message": "x"}],
                    "json_text_needs_src": {"id": "R-src", "severity": "warn",
                                            "dirs": ["data"], "allowed": ["к"],
                                            "message": "s"},
                }), encoding="utf-8")
                err0 = check.errors
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check.canon_lint()
                out = buf.getvalue()
                # exactly one R-limit ERROR (fail-secure stop)
                if check.errors - err0 != 1:
                    json_fail += 1
                    print("FAIL 11d: expected exactly one ERROR (the R-limit), "
                          "got delta %d: %r" % (check.errors - err0,
                                                out[:200]))
                if out.count("[ERROR] R-limit") != 1 \
                        or "RULE_TIME_BUDGET" not in out:
                    json_fail += 1
                    print("FAIL 11d: budget ERROR missing/duplicated: %r"
                          % out[:200])
                # json traversal ran UNTIL the stop: only the FULLY walked
                # file (a.json: 2 text nodes) is reported; the budget fired
                # inside walk_json of b.json, so b.json and c.json report
                # nothing (no silent partial results)
                if out.count("R-src") != 2:
                    json_fail += 1
                    print("FAIL 11d: expected exactly 2 R-src nodes before the "
                          "stop, got %d: %r" % (out.count("R-src"), out[:300]))
                if "b.json" in out:
                    json_fail += 1
                    print("FAIL 11d: second json file was reported after the "
                          "budget stopped inside its traversal")
                if "c.json" in out:
                    json_fail += 1
                    print("FAIL 11d: third json file was processed after the "
                          "stop")
                # the forbid section ran BEFORE json (normal order) and did
                # not run again after the stop: exactly one R-x warning
                if out.count("R-x") != 1:
                    json_fail += 1
                    print("FAIL 11d: forbid rule scanned after the stop: %r"
                          % out[:200])
        finally:
            check.time = orig_time
            for k, v in orig.items():
                setattr(check, k, v)
        if json_fail:
            failures += json_fail
            print("sec 11d json budget: %d failures" % json_fail)
        else:
            print("sec 11d json budget: FakeTime proof - budget fires inside "
                  "walk_json (node /n/m of the second file), exactly one "
                  "R-limit, node after the stop and the third file are not "
                  "processed, no section reruns")

    # --- 12) fail-secure: missing RE2 binding -> explicit ERROR, rules not run
    orig_re2_avail = check._RE2_AVAILABLE
    sys.modules["re2"] = None   # blocks "import re2" inside reload
    try:
        importlib.reload(check)
        if check._RE2_AVAILABLE:
            failures += 1
            print("FAIL 12: reload with blocked re2 still sees RE2")
        err0 = check.errors
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            check.canon_lint()
        out = buf.getvalue()
        if check.errors - err0 < 1:
            failures += 1
            print("FAIL 12: missing RE2 did not produce an ERROR")
        if "RE2 binding not available" not in out or "fail-secure" not in out:
            failures += 1
            print("FAIL 12: missing-RE2 diagnostic is not comprehensible: %r"
                  % out[:200])
        if "scanned " in out:
            failures += 1
            print("FAIL 12: rules were scanned despite missing RE2 "
                  "(silent skip is forbidden)")
    finally:
        sys.modules.pop("re2", None)
        importlib.reload(check)
    # when RE2 was available before (RE2 venv run), the reload must restore
    # it; on the main 3.15 interpreter it stays False by design
    if orig_re2_avail and not check._RE2_AVAILABLE:
        failures += 1
        print("FAIL 12: RE2 availability not restored after reload")
    print("sec 12 fail-secure: missing RE2 -> explicit ERROR, no rules run")

    # --- 13) no-fallback: the module does not import Python re at all -------
    src13 = Path(check.__file__).read_text(encoding="utf-8")
    bad_src = []
    if "import re\n" in src13 or "import re;" in src13 or \
            src13.lstrip().startswith("import re"):
        bad_src.append("import re")
    for token in ("re.compile(", "re.search(", "re.finditer(", "re.match("):
        if token in src13:
            bad_src.append(token)
    if hasattr(check, "re"):
        bad_src.append("module attribute re")
    if not check._RE2_AVAILABLE:
        pass   # on 3.15 the RE2 import failed; still no Python re allowed
    if bad_src:
        failures += 1
        print("FAIL 13: Python re traces in check.py: %r" % bad_src)
    else:
        print("sec 13 no-fallback: check.py imports no Python re and calls "
              "no re.* functions; RE2 is the only engine")

    # --- 14) RE2 scaling on the known ReDoS shapes at 16k inputs ------------
    if not check._RE2_AVAILABLE:
        print("sec 14 scaling skipped (RE2 unavailable in this interpreter)")
    else:
        probe14 = (
            "import re2, time, sys\n"
            "opts = re2.Options()\n"
            "opts.case_sensitive = True\n"
            "shapes = ['a*aa*Z', 'a*aaa*Z', 'a*a{1}a*Z', 'a*(?:a)a*Z',\n"
            "          'a*(?:a|b)a*Z', 'a*.a*Z', 'a*b*a*Z', 'a*ba*Z',\n"
            "          r'a*\\da*Z', '.*X.*', 'a*a*a*a*Z', '(a+)+b',\n"
            "          '(a|aa)+b']\n"
            "txt = sys.stdin.read()\n"
            "for pat in shapes:\n"
            "    t0 = time.perf_counter()\n"
            "    rx = re2.compile(pat, opts)\n"
            "    rx.search(txt)\n"
            "    dt = time.perf_counter() - t0\n"
            "    print('%s %.4f' % (pat, dt))\n"
        )
        scal_fail = 0
        for suffix in ("X", "b", "!"):
            txt = "a" * 16000 + suffix
            try:
                r14 = subprocess.run(
                    [sys.executable, "-I", "-c", probe14],
                    input=txt, capture_output=True, text=True, timeout=30)
                worst = 0.0
                for ln in (r14.stdout or "").strip().splitlines():
                    _, dt = ln.rsplit(" ", 1)
                    worst = max(worst, float(dt))
                print("  14) suffix %r: worst RE2 search %.4fs (13 shapes, "
                      "16k chars)" % (suffix, worst))
                if worst > 2.0:
                    scal_fail += 1
                    print("  FAIL 14: RE2 not linear at %r" % suffix)
            except subprocess.TimeoutExpired:
                scal_fail += 1
                print("  FAIL 14: RE2 exceeded 30s at suffix %r" % suffix)
        if scal_fail:
            failures += scal_fail
            print("sec 14 scaling: %d failures" % scal_fail)
        else:
            print("sec 14 scaling: 3 suffixes x 13 shapes all linear (<2s "
                  "worst-case), 16k inputs")

    # --- 15) Unicode IGNORECASE: Python re vs RE2 characterization ----------
    # Known divergence symbols. This section CHARACTERIZES the differences
    # (exact recorded outcomes); it does NOT claim full equivalence.
    if not check._RE2_AVAILABLE:
        print("sec 15 IGNORECASE skipped (RE2 unavailable)")
    else:
        import re2 as _r15
        o15 = _r15.Options()
        o15.case_sensitive = False
        cases15 = [
            # (pattern, text, note) - both directions are covered
            (r"i", "\u0130", "I vs Turkish dotted I"),
            ("\u0130", "i", "Turkish dotted I vs i"),
            (r"I", "\u0130", "capital I vs Turkish dotted I"),
            ("\u0130", "I", "Turkish dotted I vs capital I"),
            (r"i", "\u0131", "i vs dotless i (U+0131)"),
            ("\u0131", "i", "dotless i (U+0131) vs i"),
            (r"I", "\u0131", "capital I vs dotless i (U+0131)"),
            (r"s", "\u017F", "s vs long s"),
            ("\u017F", "s", "long s vs s"),
            (r"S", "\u017F", "capital S vs long s"),
            (r"k", "\u212A", "k vs Kelvin sign (U+212A)"),
            ("\u212A", "k", "Kelvin sign (U+212A) vs k"),
            ("\u212A", "\u212A", "Kelvin sign vs itself"),
            (r"k", "K", "k vs capital K sanity"),
        ]
        known_diffs = []   # recorded divergences (characterization)
        for pat, txt, note in cases15:
            a = bool(re.search(pat, txt, re.IGNORECASE))
            b = bool(_r15.search(pat, txt, o15))
            tag = "SAME" if a == b else "DIFF"
            print("  15) %-4s pattern=%s text=%s py=%-5s re2=%-5s %s"
                  % (tag, _u(pat), _u(txt), a, b, note))
            if a != b:
                known_diffs.append((pat, txt, a, b))
        # impact on the 15 canon rules: none of the rule patterns contain
        # these symbols, and none of the scanned project texts contain them
        # (checked below on the real scan set)
        rules15 = json.loads(Path(check.RULES_PATH).read_text(encoding="utf-8"))
        all_patterns = ""
        for sec in ("forbid", "max_count", "forbid_filenames"):
            for r in rules15.get(sec, []):
                all_patterns += r["pattern"]
        sym_in_patterns = [c for c in ("\u0130", "\u0131", "\u017F", "\u212A")
                           if c in all_patterns]
        texts15 = []
        for d in rules15["scan_dirs"]:
            for p in sorted((check.ROOT / d).rglob("*")):
                if p.is_file() and p.suffix.lower() in rules15["scan_ext"]:
                    texts15.append(p.read_text(encoding="utf-8",
                                               errors="replace"))
        sym_in_texts = [c for c in ("\u0130", "\u0131", "\u017F", "\u212A")
                        if any(c in t for t in texts15)]
        print("  15) divergence symbols in canon patterns: %s; in scanned "
              "texts: %s"
              % ([_u(c) for c in sym_in_patterns] or "none",
                 [_u(c) for c in sym_in_texts] or "none"))
        if sym_in_patterns:
            failures += 1
            print("FAIL 15: divergence symbols appear in canon patterns - "
                  "RE2 vs re outcomes could differ on real rules")
        print("sec 15 IGNORECASE characterization: %d divergences recorded "
              "(%s); impact on the 15 rules: %s"
              % (len(known_diffs),
                 ", ".join("%s/%s py=%s re2=%s"
                           % (_u(p), _u(t), a, b)
                           for p, t, a, b in known_diffs)
                 if known_diffs else "none",
                 "none" if not sym_in_patterns and not sym_in_texts
                 else "PRESENT - see above"))

    # --- 16) camel_years_linear uses isdecimal (matches \d semantics) -------
    cam_cases = [
        ("год 601 по верблюду", ["601"]),                 # plain ASCII
        ("9999 по верблюду", ["9999"]),                   # long run -> last 4
        ("٢٥٥ по верблюду", ["٢٥٥"]),                     # Arabic-Indic decimals
        ("١٢٣٤٥ по верблюду", ["٢٣٤٥"]),                  # long run -> last 4
        ("² по верблюду", []),                            # superscript: NOT \d
        ("⁰¹²³ по верблюду", []),                         # superscripts: NOT \d
        ("12 по верблюду", []),                           # shorter than 3
        ("год 640 по верблюду и 629 по верблюду", ["640", "629"]),
    ]
    cam_fail = 0
    for line, want in cam_cases:
        got = check.camel_years_linear(line)
        if got != want:
            cam_fail += 1
            print("FAIL 16 camel %s: got %s, want %s"
                  % (_u(line), [_u(x) for x in got], [_u(x) for x in want]))
    # int() must only ever see decimal strings; verify on the samples
    for line, _ in cam_cases:
        for y in check.camel_years_linear(line):
            try:
                int(y)
            except ValueError:
                cam_fail += 1
                print("FAIL 16: int() cannot parse %r" % y)
    if cam_fail:
        failures += cam_fail
        print("sec 16 camel isdecimal: %d failures" % cam_fail)
    else:
        print("sec 16 camel isdecimal: %d/%d cases correct; superscripts "
              "rejected, Arabic-Indic decimals accepted, int() safe"
              % (len(cam_cases), len(cam_cases)))

    if failures:
        print("TEST: FAIL - %d checks failed" % failures)
        return 1
    print("CHECK_REGEX_TEST_OK")
    return 0


def _spy_compile(pattern, flags, orig_compile, compiled, calls):
    calls["n"] += 1
    compiled.append(pattern)
    return orig_compile(pattern, flags)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("TEST: FAIL - unhandled exception")
        sys.exit(1)
