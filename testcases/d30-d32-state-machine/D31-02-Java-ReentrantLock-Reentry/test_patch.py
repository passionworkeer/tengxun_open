"""
D31-02: ReentrantLock reentry with data inconsistency (Java)

Validates that:
- buggy_code.java produces transactionCount == 2 (wrong) after one deposit()
- gold_patch.java produces transactionCount == 1 (correct) after one deposit()
"""

import subprocess
import os
import sys
import re
import pathlib
import pytest


CASE_DIR = pathlib.Path(__file__).parent.resolve()


def run_java_class(class_name: str) -> dict:
    """Compile and run a Java class, returning stdout, stderr, and parsed values."""
    # Compile
    compile_proc = subprocess.run(
        ["javac", f"{class_name}.java"],
        cwd=CASE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if compile_proc.returncode != 0:
        return {
            "stdout": "",
            "stderr": compile_proc.stderr,
            "compile_error": True,
            "transaction_count": None,
            "balance": None,
        }

    # Run
    run_proc = subprocess.run(
        ["java", "-cp", CASE_DIR, class_name],
        capture_output=True,
        text=True,
        timeout=30,
    )
    stdout = run_proc.stdout
    stderr = run_proc.stderr

    txn_match = re.search(r"TransactionCount:\s*(\d+)", stdout)
    bal_match = re.search(r"Balance:\s*(-?\d+)", stdout)

    return {
        "stdout": stdout,
        "stderr": stderr,
        "compile_error": False,
        "returncode": run_proc.returncode,
        "transaction_count": int(txn_match.group(1)) if txn_match else None,
        "balance": int(bal_match.group(1)) if bal_match else None,
    }


class TestBuggyCode:
    """Tests for the buggy implementation."""

    def test_buggy_code_compiles(self):
        result = run_java_class("buggy_code")
        assert not result["compile_error"], f"Compilation failed:\n{result['stderr']}"

    def test_buggy_code_runs(self):
        result = run_java_class("buggy_code")
        assert result["returncode"] == 0, f"Runtime error:\n{result['stderr']}"

    def test_buggy_code_transaction_count_is_wrong(self):
        """
        EXPECTED FAIL (this is the bug):
        After one deposit() call, transactionCount should be 1.
        Due to the reentrant processFee() also incrementing transactionCount,
        the buggy version produces transactionCount == 2.
        The test PASSES when it detects the bug (wrong count == 2).
        """
        result = run_java_class("buggy_code")
        assert result["transaction_count"] is not None, "Could not parse transactionCount"
        assert result["transaction_count"] == 2, (
            f"Expected buggy transactionCount == 2 (double-count due to reentrancy), "
            f"but got {result['transaction_count']}"
        )

    def test_buggy_code_no_negative_balance(self):
        """The buggy code should not have a negative balance after a single deposit."""
        result = run_java_class("buggy_code")
        assert result["balance"] is not None
        assert result["balance"] >= 0, f"Balance went negative: {result['balance']}"


class TestGoldPatch:
    """Tests for the fixed implementation."""

    def test_gold_patch_compiles(self):
        result = run_java_class("gold_patch")
        assert not result["compile_error"], f"Compilation failed:\n{result['stderr']}"

    def test_gold_patch_runs(self):
        result = run_java_class("gold_patch")
        assert result["returncode"] == 0, f"Runtime error:\n{result['stderr']}"

    def test_gold_patch_transaction_count_is_correct(self):
        """
        EXPECTED PASS (this is the fix):
        After one deposit() call, transactionCount should be exactly 1.
        The gold patch avoids the reentrant double-increment.
        """
        result = run_java_class("gold_patch")
        assert result["transaction_count"] is not None, "Could not parse transactionCount"
        assert result["transaction_count"] == 1, (
            f"Expected gold transactionCount == 1, but got {result['transaction_count']}"
        )

    def test_gold_patch_balance_correct(self):
        """
        Balance after deposit(1000):
        - deposit adds 1000  -> balance = 2000
        - fee deducts 1%      -> balance = 2000 - 10 = 1990
        """
        result = run_java_class("gold_patch")
        assert result["balance"] == 1990, (
            f"Expected balance == 1990, but got {result['balance']}"
        )


class TestStaticAnalysis:
    """Static checks for the reentrant lock pattern."""

    def test_buggy_code_has_reentrant_lock(self):
        """Verify buggy_code uses ReentrantLock."""
        src = (CASE_DIR / "buggy_code.java").read_text(encoding="utf-8")
        assert "ReentrantLock" in src, "buggy_code should use ReentrantLock"
        assert "lock.lock()" in src, "buggy_code should call lock.lock()"
        assert "lock.unlock()" in src, "buggy_code should call lock.unlock()"

    def test_gold_patch_has_reentrant_lock(self):
        """Verify gold_patch uses ReentrantLock."""
        src = (CASE_DIR / "gold_patch.java").read_text(encoding="utf-8")
        assert "ReentrantLock" in src, "gold_patch should use ReentrantLock"

    def test_buggy_code_reentrant_method_calls_lock(self):
        """
        In buggy_code, processFee() calls lock.lock() again while the outer
        deposit() already holds the lock -- this is the source of the double-count.
        """
        src = (CASE_DIR / "buggy_code.java").read_text(encoding="utf-8")
        # Check that processFee contains lock.lock() (reentrant acquisition)
        assert "lock.lock()" in src, "buggy_code should have a reentrant lock call"
        # The reentrancy is the bug; the test above confirms the bad pattern exists

    def test_gold_patch_no_double_lock(self):
        """
        In gold_patch, processFeeDirect() does NOT call lock.lock().
        The reentrant double-lock pattern is eliminated.
        """
        src = (CASE_DIR / "gold_patch.java").read_text(encoding="utf-8")
        # Count lock.lock() occurrences -- should be exactly 1 (only in deposit)
        count = src.count("lock.lock()")
        assert count == 1, (
            f"gold_patch should have exactly 1 lock.lock() call (in deposit), "
            f"but found {count}"
        )
