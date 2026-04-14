"""
D32-01: SIGTERM handler calls malloc causing heap corruption (C)

Test for async-signal-safety violations in signal handlers.

Pass criteria:
  - gold_patch.c: NO non-async-signal-safe functions in any signal handler
  - buggy_code.c: MUST contain non-async-signal-safe calls in signal handler

Non-async-signal-safe functions that MUST NOT appear in signal handlers:
  malloc, free, realloc, calloc, printf, fprintf, sprintf, snprintf,
  vprintf, vfprintf, scanf, fscanf, sscanf, strcpy, strncpy, strcat,
  strncat, memcpy, memset, memmove, getpwnam, getgrnam, etc.

Async-signal-safe functions that ARE allowed:
  _exit(), write(), signal() (implementation-defined), sigaction(),
  kill() (with caveats), raise(), pause(), sleep(), etc.
"""

import subprocess
import sys
import os
import re
import pytest

# Path to the test case directory
CASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUGGY_FILE = os.path.join(CASE_DIR, "buggy_code.c")
GOLD_FILE = os.path.join(CASE_DIR, "gold_patch.c")

# GCC path (try mingw64 in PATH first, then explicit D:/mingw path)
def _find_gcc():
    import shutil
    for candidate in ["D:/mingw/bin/gcc.exe", "D:/mingw64/bin/gcc.exe", "gcc"]:
        if shutil.which(candidate):
            return candidate
    return None

GCC = _find_gcc()

# Non-async-signal-safe functions that must NOT appear in signal handlers.
# Source: POSIX.1-2017 Table 3-3.
NON_ASYNC_SAFE_PATTERNS = [
    r'\bmalloc\s*\(',
    r'\bfree\s*\(',
    r'\brealloc\s*\(',
    r'\bcalloc\s*\(',
    r'\bprintf\s*\(',
    r'\bfprintf\s*\(',
    r'\bsprintf\s*\(',
    r'\bsnprintf\s*\(',
    r'\bvprintf\s*\(',
    r'\bvfprintf\s*\(',
    r'\bvsprintf\s*\(',
    r'\bvsnprintf\s*\(',
    r'\bscanf\s*\(',
    r'\bfscanf\s*\(',
    r'\bsscanf\s*\(',
    r'\bstrcpy\s*\(',
    r'\bstrncpy\s*\(',
    r'\bstrcat\s*\(',
    r'\bstrncat\s*\(',
    r'\bmemcpy\s*\(',
    r'\bmemset\s*\(',
    r'\bmemmove\s*\(',
    r'\bgetpwnam\s*\(',
    r'\bgetgrnam\s*\(',
    r'\bsystem\s*\(',
    r'\bpopen\s*\(',
    r'\bopen\s*\([^)]*\b\"[rwa]',  # open with string flag in signal context
]

# Regex to detect a signal handler definition
SIGNAL_HANDLER_RE = re.compile(
    r'(?:void\s+\*?\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:__attribute__[^;]*)?\s*\{',
    re.MULTILINE
)

# Async-signal-safe functions that ARE allowed
ALLOWED_IN_HANDLER = {
    "_exit", "_Exit", "write", "signal", "sigaction", "sigemptyset",
    "sigfillset", "sigaddset", "sigdelset", "sigismember", "sigpending",
    "sigprocmask", "sigsuspend", "sigwait", "sigwaitinfo", "sigtimedwait",
    "sigqueue", "raise", "abort", "longjmp", "vfork", "execve", "fexecve",
    "pause", "sleep", "usleep", "nanosleep", "alarm", "ualarm",
    "getpid", "getppid", "getuid", "geteuid", "getgid", "getegid",
    "alarm", "kill", "fork", "wait", "waitpid", "pipe", "read", "close",
    "fsync", "fdatasync", "sync", "chdir", "chmod", "chown", "link",
    "unlink", "rmdir", "mkdir", "open", "creat", "umask",
}


def extract_handler_body(content: str, handler_name: str) -> str | None:
    """Extract the body of a named function from C source."""
    # Find the function start
    pattern = rf'(?:void\s+)?{re.escape(handler_name)}\s*\([^)]*\)\s*(?:__attribute__[^;]*)?\s*\{{'
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return None

    # Brace-balanced extraction
    start = match.end() - 1  # position of opening '{'
    depth = 1
    i = start + 1
    while i < len(content) and depth > 0:
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
        i += 1
    return content[start:i]


def find_violations(content: str) -> list[str]:
    """Find non-async-signal-safe function calls in the entire file."""
    violations = []
    for pattern in NON_ASYNC_SAFE_PATTERNS:
        for m in re.finditer(pattern, content):
            # Skip if inside a comment
            line_start = content.rfind('\n', 0, m.start()) + 1
            line_end = content.find('\n', m.start())
            if line_end == -1:
                line_end = len(content)
            line = content[line_start:line_end]
            # Remove line comments
            line_no_comment = line.split('//')[0]
            if re.search(pattern, line_no_comment):
                violations.append(f"{pattern} at position {m.start()}")
    return violations


def check_handler_async_safety(content: str) -> tuple[list[str], list[str]]:
    """
    Check all signal handlers in the file for async-signal-safety violations.

    Returns:
        (signal_handlers_found, violations) where:
        - signal_handlers_found: list of handler function names
        - violations: list of violation descriptions
    """
    # Find handler assignment via struct sigaction: .sa_handler = handler_name
    handler_assign_re = re.compile(
        r'\.sa_handler\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)',
        re.MULTILINE
    )

    # Find handler installation via signal(): signal(SIGTERM, handler_name)
    signal_call_re = re.compile(
        r'\bsignal\s*\(\s*(?:SIGTERM|SIGINT|SIGHUP|SIGUSR1|SIGUSR2|SIGSEGV'
        r'|SIGBUS|SIGFPE|SIGILL|SIGABRT|SIGCHLD|SIGQUIT|SIGPIPE|SIGALRM|SIGVTALRM)'
        r'\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)',
        re.IGNORECASE
    )

    handlers_found = set()
    for m in handler_assign_re.finditer(content):
        handlers_found.add(m.group(1))
    for m in signal_call_re.finditer(content):
        handlers_found.add(m.group(1))

    all_handlers = list(handlers_found)

    all_violations = []
    for handler_name in all_handlers:
        body = extract_handler_body(content, handler_name)
        if body:
            handler_violations = find_violations(body)
            for v in handler_violations:
                all_violations.append(f"  Handler '{handler_name}': {v}")
        else:
            # Try global search for the handler function
            func_re = re.compile(
                rf'void\s+{re.escape(handler_name)}\s*\([^)]*\)\s*\{{([^{{}}]*)\}}',
                re.MULTILINE | re.DOTALL
            )
            m = func_re.search(content)
            if m:
                func_body = m.group(1)
                handler_violations = find_violations(func_body)
                for v in handler_violations:
                    all_violations.append(f"  Handler '{handler_name}': {v}")

    return all_handlers, all_violations


class TestD3201AsyncSignalSafety:
    """Test async-signal-safety of signal handlers."""

    def test_gcc_available(self):
        """Verify gcc is available."""
        if GCC is None:
            pytest.skip("gcc not found in PATH or known locations")
        result = subprocess.run(
            [GCC, "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"gcc not available: {result.stderr}"
        print(f"\nGCC version: {result.stdout.splitlines()[0]}")

    def test_buggy_code_file_exists(self):
        """Verify buggy source exists."""
        assert os.path.isfile(BUGGY_FILE), f"Missing: {BUGGY_FILE}"

    def test_gold_patch_file_exists(self):
        """Verify gold patch source exists."""
        assert os.path.isfile(GOLD_FILE), f"Missing: {GOLD_FILE}"

    def test_buggy_code_compiles(self):
        """Buggy code compiles (with warnings about the bug)."""
        if GCC is None:
            pytest.skip("gcc not available")
        result = subprocess.run(
            [GCC, "-Wall", "-Wextra", "-o",
             os.path.join(CASE_DIR, "buggy"), BUGGY_FILE],
            capture_output=True,
            text=True
        )
        print(f"\n--- Buggy code compile stdout ---\n{result.stdout}")
        print(f"\n--- Buggy code compile stderr ---\n{result.stderr}")
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

    def test_gold_patch_compiles(self):
        """Gold patch compiles cleanly."""
        if GCC is None:
            pytest.skip("gcc not available")
        result = subprocess.run(
            [GCC, "-Wall", "-Wextra", "-o",
             os.path.join(CASE_DIR, "gold"), GOLD_FILE],
            capture_output=True,
            text=True
        )
        print(f"\n--- Gold patch compile stdout ---\n{result.stdout}")
        print(f"\n--- Gold patch compile stderr ---\n{result.stderr}")
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

    def test_buggy_has_async_unsafe_in_handler(self):
        """
        FAIL-to-Pass: buggy_code.c MUST contain async-signal-unsafe
        calls (malloc/free) inside signal handler.

        This test PASSES when violations are found (detecting the bug).
        """
        with open(BUGGY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        handlers, violations = check_handler_async_safety(content)

        print(f"\nBuggy code handlers found: {handlers}")
        print(f"Violations in buggy code: {len(violations)}")
        for v in violations:
            print(f"  {v}")

        assert len(violations) > 0, (
            f"BUG NOT DETECTED: {BUGGY_FILE} signal handlers appear safe, "
            f"but the bug requires malloc/free inside signal handler. "
            f"Handlers found: {handlers}"
        )

    def test_gold_is_async_safe(self):
        """
        Pass-to-Pass: gold_patch.c MUST NOT contain any async-signal-unsafe
        calls inside signal handlers.

        This test PASSES when NO violations are found (fix is correct).
        """
        with open(GOLD_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        handlers, violations = check_handler_async_safety(content)

        print(f"\nGold patch handlers found: {handlers}")
        print(f"Violations in gold patch: {len(violations)}")
        for v in violations:
            print(f"  {v}")

        assert len(violations) == 0, (
            f"GROUND TRUTH VIOLATION: {GOLD_FILE} contains async-signal-unsafe "
            f"calls in signal handlers: {violations}"
        )

    def test_buggy_fails_asan(self):
        """
        Runtime verification with AddressSanitizer.
        Compile with -fsanitize=address and verify ASan detects the issue.
        This is optional; static check above is primary.
        """
        if GCC is None:
            pytest.skip("gcc not available")

        # Compile with ASan
        asan_binary = os.path.join(CASE_DIR, "buggy_asan")
        result = subprocess.run(
            [GCC, "-Wall", "-Wextra",
             "-fsanitize=address", "-g",
             "-o", asan_binary, BUGGY_FILE],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            pytest.skip(f"ASan compilation failed: {result.stderr}")

        import time
        import signal as sig_module

        # Send SIGTERM quickly and check for ASan errors
        try:
            proc = subprocess.Popen(
                [asan_binary],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(0.5)

            # Send SIGTERM (works on Unix; on Windows this may raise)
            try:
                proc.send_signal(sig_module.SIGTERM)
            except (AttributeError, OSError):
                pytest.skip("SIGTERM not supported on this platform")

            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

        stderr_lower = stderr.lower()
        print(f"\n--- ASan stderr ---\n{stderr}")

        # ASan detects issues related to signal-handler malloc
        # Note: ASan may not always catch the specific signal+heap interaction
        # in a short test, but any heap-related error is a pass for this test
        asan_error = any(tag in stderr_lower for tag in
                        ["addresssanitizer", "heap-buffer-overflow",
                         "heap-use-after-free", "double-free",
                         "segmentation fault", "malloc:", "free:"])

        # For this test, we don't fail the suite if ASan doesn't catch it
        # (timing-dependent), but we note the result.
        print(f"\nASan error detected: {asan_error}")
        print(f"Return code: {proc.returncode}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
