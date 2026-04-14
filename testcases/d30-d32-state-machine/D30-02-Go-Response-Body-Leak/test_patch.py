"""
D30-02: Go Response.Body leak (Go)

Validates that:
- buggy_code.go: missing defer resp.Body.Close() → Go tests FAIL
- gold_patch.go: has     defer resp.Body.Close() → Go tests PASS
"""

import subprocess
import pathlib
import pytest
import re

CASE_DIR = pathlib.Path(__file__).parent.resolve()

# Path to Go binary (installed at D:/go/go/bin/go.exe)
GO_EXE = pathlib.Path("D:/go/go/bin/go.exe")
if not GO_EXE.exists():
    GO_EXE = pathlib.Path("go")  # fallback to PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_go_test(tag: str) -> dict:
    """Run 'go test' with the given build tag and return result."""
    cmd = [str(GO_EXE), "test", "-tags=" + tag, "-v", "./..."]
    proc = subprocess.run(
        cmd,
        cwd=CASE_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "tag": tag,
    }


def read_source(filename: str) -> str:
    return (CASE_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Go binary presence
# ---------------------------------------------------------------------------

class TestGoEnvironment:
    def test_go_available(self):
        result = subprocess.run(
            [str(GO_EXE), "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"Go not found at {GO_EXE}. "
            "Install Go 1.22+ from https://go.dev/dl/ and set D:/go/go/bin/go.exe"
        )


# ---------------------------------------------------------------------------
# Buggy version tests — expected to FAIL
# ---------------------------------------------------------------------------

class TestBuggyCode:
    """Tests for the buggy implementation (buggy_code.go)."""

    def test_buggy_code_exists(self):
        assert (CASE_DIR / "buggy_code.go").exists(), "buggy_code.go not found"

    def test_buggy_code_compiles(self):
        """buggy_code.go should compile successfully (no syntax errors)."""
        result = subprocess.run(
            [str(GO_EXE), "build", str(CASE_DIR / "buggy_code.go")],
            cwd=CASE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # build with //go:build ignore is skipped, but check package compiles
        # We use 'go vet' on the package instead
        result = subprocess.run(
            [str(GO_EXE), "vet", "./..."],
            cwd=CASE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # vet should pass (the bug is a logic issue, not a vet error)
        assert result.returncode == 0, f"go vet failed:\n{result.stderr}"

    def test_buggy_code_source_missing_body_close(self):
        """
        BUGGY: buggy_code.go does NOT contain 'defer resp.Body.Close()'.

        This test checks the source for the fixed pattern.
        On buggy code: this should NOT be found → test PASSES.
        (But we invert: we expect the Go test to FAIL, not this Python check.)
        """
        src = read_source("buggy_code.go")

        # Pattern: "defer resp.Body.Close(" — the fixed pattern
        has_fixed_pattern = bool(re.search(r'defer\s+resp\.Body\.Close\s*\(', src))

        assert not has_fixed_pattern, (
            "buggy_code.go should NOT contain 'defer resp.Body.Close()'. "
            "If it does, it is not the buggy version."
        )

    def test_buggy_go_tests_fail(self):
        """
        EXPECTED: go test -tags=buggy should FAIL.

        The buggy version's TestBuggyCodeMissingBodyClose asserts that
        defer resp.Body.Close() IS present (fixed behaviour), which fails
        because the buggy code is missing it. This is the correct outcome.
        """
        result = run_go_test("buggy")
        assert result["returncode"] != 0, (
            f"BUGGY version: expected tests to FAIL (missing resp.Body.Close()), "
            f"but got returncode={result['returncode']}. "
            f"stdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"
        )
        # Also confirm the specific failure message
        combined = result["stdout"] + result["stderr"]
        assert "BUGGY detected" in combined or "FAIL" in combined, (
            f"Expected failure message not found in output:\n{combined}"
        )


# ---------------------------------------------------------------------------
# Fixed version tests — expected to PASS
# ---------------------------------------------------------------------------

class TestGoldPatch:
    """Tests for the fixed implementation (gold_patch.go)."""

    def test_gold_patch_exists(self):
        assert (CASE_DIR / "gold_patch.go").exists(), "gold_patch.go not found"

    def test_gold_patch_source_has_body_close(self):
        """
        FIXED: gold_patch.go DOES contain 'defer resp.Body.Close()'.

        This confirms the fix is present in the source.
        """
        src = read_source("gold_patch.go")

        # Pattern: "defer resp.Body.Close(" — the fixed pattern
        has_fixed_pattern = bool(re.search(r'defer\s+resp\.Body\.Close\s*\(', src))

        assert has_fixed_pattern, (
            "gold_patch.go should contain 'defer resp.Body.Close()'. "
            "If it is missing, the fix is not correctly applied."
        )

    def test_gold_go_tests_pass(self):
        """
        EXPECTED: go test -tags=fixed should PASS.

        The fixed version's TestFixedCodeHasBodyClose verifies that
        defer resp.Body.Close() is present and the test should pass.
        """
        result = run_go_test("fixed")
        assert result["returncode"] == 0, (
            f"FIXED version: expected tests to PASS, but got returncode={result['returncode']}. "
            f"stdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"
        )
        assert "PASS" in result["stdout"], (
            f"Expected 'PASS' not found in test output:\n{result['stdout']}"
        )


# ---------------------------------------------------------------------------
# Integration: overall verdict
# ---------------------------------------------------------------------------

class TestOverallVerdict:
    def test_buggy_fails_fixed_passes(self):
        """
        The definitive end-to-end check:
        - buggy version: go test → FAIL
        - fixed version: go test → PASS
        """
        buggy_result = run_go_test("buggy")
        fixed_result = run_go_test("fixed")

        assert buggy_result["returncode"] != 0, (
            "BUGGY version should FAIL but it PASSED"
        )
        assert fixed_result["returncode"] == 0, (
            f"FIXED version should PASS but it FAILED (rc={fixed_result['returncode']}). "
            f"stderr:\n{fixed_result['stderr']}"
        )
