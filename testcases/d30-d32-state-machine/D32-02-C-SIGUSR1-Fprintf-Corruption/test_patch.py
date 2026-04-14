"""
D32-02: SIGUSR1 handler calls fprintf to stdout causing corruption

Tests that:
  1. buggy_code.c uses NON-async-signal-safe functions (fprintf/printf/fflush)
     in the signal handler  -> should FAIL (buggy)
  2. gold_patch.c uses ONLY async-signal-safe functions (write) in signal handler
     -> should PASS (fixed)

Evaluation method: Fail-to-Pass
  - buggy: test FAILS  (finds the bug = correct detection)
  - gold:  test PASSES  (no bug found = correct fix)
"""

import subprocess
import sys
import os
import re
import tempfile
import time
import signal
import pytest

CASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUGGY_SRC = os.path.join(CASE_DIR, "buggy_code.c")
GOLD_SRC = os.path.join(CASE_DIR, "gold_patch.c")

# Async-signal-safe output functions (subset relevant here)
ASYNC_SAFE_OUTPUT = {"write"}
# Non-async-signal-safe output/buffer functions (MUST NOT appear in signal handlers)
NON_SAFE_OUTPUT = {"fprintf", "printf", "fflush", "vprintf", "vfprintf", "fputs", "fwrite"}


def extract_signal_handler_functions(c_src: str) -> list[str]:
    """
    Extract all function calls that appear INSIDE the sigusr1_handler function
    (or any function assigned to sa.sa_handler).
    Returns list of function names called within the handler scope.
    """
    with open(c_src, encoding="utf-8") as f:
        source = f.read()

    # Find the signal handler function body
    # Match: void sigusr1_handler(...) { ... }
    handler_pattern = re.compile(
        r'(?:void|static\s+void)\s+sigusr1_handler\s*\([^)]*\)\s*\{',
        re.MULTILINE | re.DOTALL,
    )
    m = handler_pattern.search(source)
    if not m:
        return []

    # Count braces to find the end of the function body
    start = m.end()
    brace_level = 1
    end = start
    for i, ch in enumerate(source[start:], start):
        if ch == "{":
            brace_level += 1
        elif ch == "}":
            brace_level -= 1
            if brace_level == 0:
                end = i
                break

    handler_body = source[start:end]

    # Find all function calls: identifier followed by '('
    # Exclude keywords, types, and preprocessor
    calls = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', handler_body)
    return calls


def has_gcc() -> bool:
    """Check if gcc is available in PATH."""
    try:
        return subprocess.call(
            ["gcc", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0
    except FileNotFoundError:
        return False


def compile_src(src_path: str, binary_path: str, sanitizer: str = "") -> bool:
    """Compile a C source file. Returns True on success."""
    flags = ["-Wall", "-Wextra", "-O0"]
    if sanitizer:
        flags.append(sanitizer)
    cmd = ["gcc", "-o", binary_path, src_path] + flags
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


class TestBuggyCode:
    """
    Tests against buggy_code.c.
    The signal handler uses fprintf/fflush which are NOT async-signal-safe.
    These tests should FAIL (detect the bug).
    """

    def test_buggy_uses_fprintf_in_handler(self):
        """FAIL: buggy_code.c uses fprintf (non-async-signal-safe) in handler."""
        calls = extract_signal_handler_functions(BUGGY_SRC)
        found = [c for c in calls if c in NON_SAFE_OUTPUT]
        assert len(found) == 0, (
            f"BUGGY: signal handler calls non-async-signal-safe function(s): {found}. "
            f"These must be replaced with async-signal-safe alternatives like write()."
        )

    def test_buggy_compilation_warnings(self):
        """Compile buggy_code.c - may succeed but the bug is at runtime."""
        if not has_gcc():
            pytest.skip("gcc not available")
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            binary = f.name
        try:
            ok = compile_src(BUGGY_SRC, binary)
            assert ok, "buggy_code.c failed to compile"
        finally:
            if os.path.exists(binary):
                os.unlink(binary)

    def test_buggy_runtime_signal_safety(self):
        """
        Send SIGUSR1 to running process and verify no corruption / deadlock.
        This is a runtime check: if the handler uses non-safe functions,
        output may be interleaved or the process may deadlock.
        """
        if not has_gcc():
            pytest.skip("gcc not available")

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            binary = f.name
        try:
            ok = compile_src(BUGGY_SRC, binary)
            if not ok:
                pytest.skip("compilation failed")

            # Run the program
            proc = subprocess.Popen(
                [binary],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.2)

            # Send SIGUSR1 while main loop is running
            proc.send_signal(signal.SIGUSR1)
            time.sleep(0.3)
            proc.send_signal(signal.SIGUSR1)
            time.sleep(0.3)
            proc.send_signal(signal.SIGUSR1)

            stdout, stderr = proc.communicate(timeout=5)

            # If handler is safe, output should be clean.
            # If buggy (uses fprintf), output may be interleaved or garbled.
            # We check that output is not corrupted (not empty, has expected patterns).
            assert "[SIGUSR1" in stdout or "iteration" in stdout, (
                f"No output from buggy program. stdout={stdout!r} stderr={stderr!r}"
            )
            # The test passes on compilation/launch; the bug is in the source code check.
        finally:
            if os.path.exists(binary):
                os.unlink(binary)


class TestGoldPatch:
    """
    Tests against gold_patch.c.
    The signal handler uses ONLY write() (async-signal-safe).
    These tests should PASS.
    """

    def test_gold_uses_only_async_safe_in_handler(self):
        """PASS: gold_patch.c signal handler uses only async-signal-safe functions."""
        calls = extract_signal_handler_functions(GOLD_SRC)
        non_safe_found = [c for c in calls if c in NON_SAFE_OUTPUT]
        assert len(non_safe_found) == 0, (
            f"FIX: signal handler still contains non-async-signal-safe "
            f"function(s): {non_safe_found}"
        )

    def test_gold_uses_write_in_handler(self):
        """PASS: gold_patch.c uses write() (async-signal-safe) in handler."""
        calls = extract_signal_handler_functions(GOLD_SRC)
        assert "write" in calls, (
            f"FIX: signal handler does not call write(). "
            f"Found calls: {calls}"
        )

    def test_gold_compilation(self):
        """Compile gold_patch.c - should succeed cleanly."""
        if not has_gcc():
            pytest.skip("gcc not available")
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            binary = f.name
        try:
            ok = compile_src(GOLD_SRC, binary)
            assert ok, "gold_patch.c failed to compile"
        finally:
            if os.path.exists(binary):
                os.unlink(binary)

    def test_gold_runtime_signal_safety(self):
        """
        Send SIGUSR1 to gold_patch process - output should be clean.
        """
        if not has_gcc():
            pytest.skip("gcc not available")

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            binary = f.name
        try:
            ok = compile_src(GOLD_SRC, binary)
            if not ok:
                pytest.skip("compilation failed")

            proc = subprocess.Popen(
                [binary],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.2)
            proc.send_signal(signal.SIGUSR1)
            time.sleep(0.3)
            proc.send_signal(signal.SIGUSR1)

            stdout, stderr = proc.communicate(timeout=5)

            # Gold fix should produce clean output without interleaving
            assert "iteration" in stdout or "[SIGUSR1" in stdout, (
                f"gold_patch produced no output: stdout={stdout!r} stderr={stderr!r}"
            )
            # No crash / corruption expected
            assert proc.returncode == 0, f"gold_patch crashed: {stderr}"
        finally:
            if os.path.exists(binary):
                os.unlink(binary)


class TestStaticAnalysis:
    """
    Pure static analysis tests - no gcc required.
    Uses regex to extract function calls from the signal handler in source.
    """

    def test_buggy_fprintf_detected(self):
        """Buggy code must be detected as having fprintf in handler."""
        calls = extract_signal_handler_functions(BUGGY_SRC)
        assert "fprintf" in calls, (
            f"Expected fprintf in buggy handler, got: {calls}"
        )

    def test_buggy_fflush_detected(self):
        """Buggy code must be detected as having fflush in handler."""
        calls = extract_signal_handler_functions(BUGGY_SRC)
        assert "fflush" in calls, (
            f"Expected fflush in buggy handler, got: {calls}"
        )

    def test_gold_no_fprintf(self):
        """Gold patch must NOT have fprintf in handler."""
        calls = extract_signal_handler_functions(GOLD_SRC)
        assert "fprintf" not in calls, (
            f"Gold patch should not have fprintf, found: {calls}"
        )

    def test_gold_no_fflush(self):
        """Gold patch must NOT have fflush in handler."""
        calls = extract_signal_handler_functions(GOLD_SRC)
        assert "fflush" not in calls, (
            f"Gold patch should not have fflush, found: {calls}"
        )

    def test_gold_uses_write(self):
        """Gold patch MUST use write() in handler."""
        calls = extract_signal_handler_functions(GOLD_SRC)
        assert "write" in calls, (
            f"Gold patch must call write(), found: {calls}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
