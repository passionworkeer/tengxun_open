"""
D31-01: Holding mutex, calling user callback, callback acquires same lock (C++)

Test harness:
1. Compiles and runs buggy_code.cpp  → expects DEADLOCK / TIMEOUT  → test FAILS
2. Compiles and runs gold_patch.cpp  → expects clean exit           → test PASSES
3. Static check: grep buggy_code.cpp for non-recursive std::mutex
                  used inside / after a locked section.

Path strategy:
  - Compile: use bash -c "..." (Unix-style paths; bash → g++ handles them)
  - Run binary: shell=False + Windows path (Windows CreateProcess needs \\ paths)
  - Both compilation and execution use /d/MinGW/bin/g++.exe as base
"""

import subprocess
import sys
import os
import shutil

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GXX = "/d/MinGW/bin/g++.exe"
TIMEOUT_SEC = 5          # deadlock should trigger well within 5 s
CXX_FLAGS = "-std=c++17 -pthread"

# Unix-style working directory
SRC_DIR = "/e/desktop/tengxun_open/testcases/D31-01-Cpp-Mutex-Callback-Reentry"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_win_path(unix_path: str) -> str:
    """
    Convert a Unix-style MSYS path to a Windows path.
    bash -c 'cygpath -w <path>' works for Unix-style input paths
    (e.g., /e/desktop/..., /d/MinGW/...).
    """
    bash_cmd = f"bash -c 'cygpath -w {unix_path}'"
    result = subprocess.run(bash_cmd, capture_output=True, text=True, shell=True)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"cygpath failed for: {unix_path!r}")


def compile(src: str, out: str) -> tuple[bool, str, str]:
    """
    Compile a C++ source file.
    Uses bash -c to run g++, passing Unix-style paths that bash expands.
    Returns (success, stdout, stderr).
    """
    # Build the g++ command as a bash string with Unix paths
    cmd = f'{GXX} {CXX_FLAGS} "{src}" -o "{out}"'
    result = subprocess.run(
        f'bash -c "{cmd}"',
        capture_output=True,
        text=True,
        shell=True,
    )
    return result.returncode == 0, result.stdout, result.stderr


def run_with_timeout(bin_unix: str, timeout: int = TIMEOUT_SEC) -> tuple[bool, str]:
    """
    Run the binary with a timeout using shell=False (Windows CreateProcess).
    Returns (timed_out, output) where timed_out=True means the process
    did not exit within the allotted time (deadlock).
    """
    # Get Windows path for the binary
    bin_win = _to_win_path(bin_unix + ".exe")
    try:
        result = subprocess.run(
            [bin_win],
            capture_output=True,
            text=True,
            timeout=timeout,
            # shell=False: Windows CreateProcess directly, timeout raises TimeoutExpired
        )
        return False, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return True, f"[TIMEOUT after {timeout}s — deadlock detected]"


# ---------------------------------------------------------------------------
# Static analysis: check buggy_code.cpp for the anti-pattern
# ---------------------------------------------------------------------------
def static_check_buggy() -> bool:
    """
    Detect the std::mutex + user-callback deadlock anti-pattern.

    The bug exists when ALL of these hold:
      1. std::mutex is used (not std::recursive_mutex)
      2. A function defined in the file tries to lock m (callback)
      3. Another function calls user_callback() while m is already locked
    """
    # Convert Unix-style path to Windows path for Python's open()
    buggy_src_unix = SRC_DIR + "/buggy_code.cpp"
    buggy_src_win  = _to_win_path(buggy_src_unix)
    with open(buggy_src_win, encoding="utf-8") as f:
        content = f.read()

    # More precise: check the actual mutex variable declaration, not comments.
    # The global is "std::mutex m;" (non-recursive); recursive would be "std::recursive_mutex m;"
    has_nonrecursive = "std::mutex m;" in content and "std::recursive_mutex m;" not in content
    has_callback_lock = (
        "callback_that_tries_lock" in content
        and ("lock_guard<std::mutex>" in content or "lock(" in content)
    )
    has_callback_call_in_locked = (
        "process_with_lock" in content
        and "user_callback()" in content
    )

    return has_nonrecursive and has_callback_lock and has_callback_call_in_locked


# ---------------------------------------------------------------------------
# Test cases (pytest discovers test_* functions automatically)
# ---------------------------------------------------------------------------
def test_gold_patch_compiles():
    """Gold patch must compile without errors."""
    ok, stdout, stderr = compile(
        f'"{SRC_DIR}/gold_patch.cpp"',
        f'"{SRC_DIR}/gold"'
    )
    assert ok, f"gold_patch.cpp failed to compile:\n{stdout}\n{stderr}"


def test_gold_patch_runs():
    """Gold patch must run to completion (no deadlock)."""
    ok, stdout, stderr = compile(
        f'"{SRC_DIR}/gold_patch.cpp"',
        f'"{SRC_DIR}/gold"'
    )
    assert ok, f"gold_patch.cpp failed to compile:\n{stderr}"

    timed_out, output = run_with_timeout(f"{SRC_DIR}/gold")
    assert not timed_out, f"gold_patch.cpp timed out (deadlocked). Output:\n{output}"
    assert "D31-01 FIXED test PASSED" in output, (
        f"gold_patch.cpp did not produce expected success marker.\n{output}"
    )
    print(f"[PASS] gold_patch ran successfully:\n{output}")


def test_buggy_code_deadlocks():
    """Buggy code must deadlock (or timeout) when run."""
    ok, stdout, stderr = compile(
        f'"{SRC_DIR}/buggy_code.cpp"',
        f'"{SRC_DIR}/buggy"'
    )
    assert ok, f"buggy_code.cpp failed to compile:\n{stderr}"

    timed_out, output = run_with_timeout(f"{SRC_DIR}/buggy")
    assert timed_out, (
        f"buggy_code.cpp did NOT deadlock/timeout — it completed unexpectedly.\n"
        f"This means the bug may not be present. Output:\n{output}"
    )
    print(f"[PASS] buggy_code.cpp correctly deadlocked (timeout):\n{output}")


def test_static_check_finds_bug():
    """Static analysis must detect the non-recursive mutex + callback anti-pattern."""
    bug_found = static_check_buggy()
    assert bug_found, (
        "Static check failed to detect the bug in buggy_code.cpp:\n"
        "  - std::mutex should be used (not recursive_mutex)\n"
        "  - callback_that_tries_lock should lock m\n"
        "  - process_with_lock should call user_callback() while holding the lock"
    )
    print("[PASS] Static check detected the bug pattern in buggy_code.cpp.")


# ---------------------------------------------------------------------------
# Manual invocation: python test_patch.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("D31-01: C++ Mutex Callback Reentry Test")
    print("=" * 60)

    # Kill any stale processes from previous runs
    for stale in ["buggy.exe", "gold.exe"]:
        stale_path = os.path.join(SRC_DIR, stale)
        if os.path.exists(stale_path):
            subprocess.run(f'taskkill //F //IM {stale} 2>nul', shell=True)

    # --- Step 1: compile gold_patch ---
    print("\n[1] Compiling gold_patch.cpp ...")
    ok, stdout, stderr = compile(
        f'"{SRC_DIR}/gold_patch.cpp"',
        f'"{SRC_DIR}/gold"'
    )
    if not ok:
        print(f"FAIL: gold_patch.cpp compilation error:\n{stdout}\n{stderr}")
        sys.exit(1)
    print("    OK")

    # --- Step 2: run gold_patch ---
    print("\n[2] Running gold_patch (expect: success) ...")
    timed_out, output = run_with_timeout(f"{SRC_DIR}/gold")
    if timed_out:
        print(f"FAIL: gold_patch deadlocked (unexpected):\n{output}")
        sys.exit(1)
    print(f"    OK — output:\n{output}")

    # --- Step 3: compile buggy_code ---
    print("\n[3] Compiling buggy_code.cpp ...")
    ok, stdout, stderr = compile(
        f'"{SRC_DIR}/buggy_code.cpp"',
        f'"{SRC_DIR}/buggy"'
    )
    if not ok:
        print(f"FAIL: buggy_code.cpp compilation error:\n{stdout}\n{stderr}")
        sys.exit(1)
    print("    OK")

    # --- Step 4: run buggy_code (expect deadlock) ---
    print("\n[4] Running buggy_code (expect: deadlock / timeout) ...")
    timed_out, output = run_with_timeout(f"{SRC_DIR}/buggy")
    if not timed_out:
        print(f"FAIL: buggy_code did NOT deadlock:\n{output}")
        sys.exit(1)
    print(f"    OK — deadlock confirmed:\n{output}")

    # --- Step 5: static check ---
    print("\n[5] Static check on buggy_code.cpp ...")
    if not static_check_buggy():
        print("FAIL: static check did not detect bug")
        sys.exit(1)
    print("    OK — bug pattern detected")

    # --- Cleanup ---
    subprocess.run(f'taskkill //F //IM buggy.exe 2>nul', shell=True)

    print("\n" + "=" * 60)
    print("All checks PASSED.")
    print("=" * 60)
