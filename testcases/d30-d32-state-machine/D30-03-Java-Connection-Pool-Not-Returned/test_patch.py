"""
D30-03 Test Patch: Connection pool leak detection (Java)

Fail-to-Pass logic:
  BUG version (buggy_code.java):
    - Connection acquired, POOL.returnConnection() missing in finally block
    - Pool active-connection count stays > 0 after worker finishes
    - Process exits with code 1 (bug detected)

  FIX version (gold_patch.java):
    - Every getConnection() paired with POOL.returnConnection()
    - Pool active-connection count returns to 0 after worker finishes
    - Process exits with code 0 (pass)

Evaluation: End-to-end Fail-to-Pass
  - buggy_code.java  -> FAIL (connection leaked, pool exhausted)
  - gold_patch.java  -> PASS (connection properly returned)
"""

import os
import subprocess
import sys
import urllib.request

import pytest

CASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── JAR downloads ──────────────────────────────────────────────────────────────

JAR_DIR = os.path.join(CASE_DIR, "_jars")
H2_JAR  = os.path.join(JAR_DIR, "h2.jar")

MAVEN_H2 = "https://repo1.maven.org/maven2/com/h2database/h2/2.2.224/h2-2.2.224.jar"


def ensure_jars():
    """Download H2 JAR from Maven Central if not already present."""
    os.makedirs(JAR_DIR, exist_ok=True)
    if not os.path.exists(H2_JAR):
        print(f"[download] {MAVEN_H2}")
        urllib.request.urlretrieve(MAVEN_H2, H2_JAR)
        print(f"[download] saved -> {H2_JAR}")
    else:
        print(f"[cache] {H2_JAR}")


def classpath():
    """Return classpath: H2 JAR + current dir (for compiled .class files)."""
    ensure_jars()
    return f"{H2_JAR}{os.pathsep}{CASE_DIR}"


# ── Compilation helpers ────────────────────────────────────────────────────────

def compile_java(source: str, cp: str) -> tuple[bool, str]:
    """Compile a Java source file (UTF-8 encoding). Returns (success, stderr)."""
    result = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-cp", cp, source],
        capture_output=True,
        text=True,
        cwd=CASE_DIR,
    )
    return result.returncode == 0, result.stderr


def run_java(class_name: str, cp: str, timeout: int = 20) -> tuple[int, str, str]:
    """Run a compiled Java class. Returns (exit_code, stdout, stderr)."""
    result = subprocess.run(
        ["java", "-cp", cp, class_name],
        capture_output=True,
        text=True,
        cwd=CASE_DIR,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cp():
    """Module-scoped classpath – JARs are downloaded once."""
    return classpath()


# ── Tests ─────────────────────────────────────────────────────────────────────

BUGGY   = os.path.join(CASE_DIR, "buggy_code.java")
GOLD    = os.path.join(CASE_DIR, "gold_patch.java")


def _extract_method_body(src: str, method_signature: str) -> str:
    """Extract the body of a method by scanning for matching braces."""
    start = src.find(method_signature)
    if start == -1:
        return ""
    brace = src.find("{", start)
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    return src[start:]


def _strip_java_comments(src: str) -> str:
    """Remove all // and /* */ comments from Java source (keeps code intact)."""
    result = []
    i = 0
    n = len(src)
    while i < n:
        if src[i:i+2] == '//':
            # Single-line comment: skip to end of line
            eol = src.find('\n', i)
            if eol == -1: break
            i = eol + 1
        elif src[i:i+2] == '/*':
            # Multi-line comment: skip to closing */
            end = src.find('*/', i+2)
            if end == -1: break
            i = end + 2
        else:
            result.append(src[i])
            i += 1
    return ''.join(result)


def test_buggy_code_compiles(cp):
    """buggy_code.java must compile without errors."""
    ok, err = compile_java(BUGGY, cp)
    assert ok, f"buggy_code.java failed to compile:\n{err}"


def test_gold_patch_compiles(cp):
    """gold_patch.java must compile without errors."""
    ok, err = compile_java(GOLD, cp)
    assert ok, f"gold_patch.java failed to compile:\n{err}"


def test_buggy_code_has_connection_leak(cp):
    """
    BUG version: connection is never returned to pool.
    After worker finishes the pool should still have 1 active connection.
    The process exits with code 1 (bug detected).
    """
    exit_code, stdout, stderr = run_java("buggy_code", cp, timeout=15)
    combined = stdout + stderr
    print(f"\n[buggy_code stdout]\n{stdout}")
    print(f"[buggy_code stderr]\n{stderr}")

    # The bug is detected: pool not clean
    assert "FAIL: connection_pool_leak" in combined, (
        f"buggy_code.java should detect connection leak and exit with FAIL.\n"
        f"Output:\n{combined}"
    )
    assert exit_code == 1, (
        f"buggy_code.java should exit with code 1 (bug detected), got {exit_code}"
    )


def test_gold_patch_no_leak(cp):
    """
    FIX version: connection is properly returned to pool.
    The pool returns to 0 active connections, process exits with code 0.
    """
    exit_code, stdout, stderr = run_java("gold_patch", cp, timeout=15)
    combined = stdout + stderr
    print(f"\n[gold_patch stdout]\n{stdout}")
    print(f"[gold_patch stderr]\n{stderr}")

    # The fix works: pool is clean
    assert "PASS: connection properly returned to pool" in combined, (
        f"gold_patch.java should pass (connection returned).\n"
        f"Output:\n{combined}"
    )
    assert exit_code == 0, (
        f"gold_patch.java should exit with code 0 (pass), got {exit_code}"
    )


def test_static_no_returnconnection_in_buggy():
    """
    Static check: buggy_code.java must NOT call POOL.returnConnection(conn)
    in the buggyWork method (that's the intentional bug).
    Comments are stripped so // FIX: POOL.returnConnection does not affect this.
    """
    with open(BUGGY, "r", encoding="utf-8") as f:
        raw = f.read()

    src = _strip_java_comments(raw)
    method_body = _extract_method_body(src, "public static void buggyWork()")
    assert "returnConnection(conn)" not in method_body, (
        "buggy_code.java: buggyWork() must NOT call POOL.returnConnection(conn) – that's the bug"
    )


def test_static_has_returnconnection_in_gold():
    """
    Static check: gold_patch.java must call POOL.returnConnection(conn)
    in the correctWork method (the fix).
    """
    with open(GOLD, "r", encoding="utf-8") as f:
        raw = f.read()

    src = _strip_java_comments(raw)
    method_body = _extract_method_body(src, "public static void correctWork()")
    assert "returnConnection(conn)" in method_body, (
        "gold_patch.java: correctWork() must call POOL.returnConnection(conn) (the fix)"
    )


def test_connectionuser_test_class_compiles(cp):
    """
    ConnectionUser.java and ConnectionUserTest.java must both compile together.
    """
    cu  = os.path.join(CASE_DIR, "ConnectionUser.java")
    cut = os.path.join(CASE_DIR, "ConnectionUserTest.java")
    ok, err = compile_java(cu, cp)
    assert ok, f"ConnectionUser.java failed to compile:\n{err}"
    ok, err = compile_java(cut, cp)
    assert ok, f"ConnectionUserTest.java failed to compile:\n{err}"


def test_connectionuser_buggy_detected(cp):
    """
    Run ConnectionUserTest against the BUGGY ConnectionUser.java.
    The doWork() method leaks a connection -> at least one test fails.
    """
    exit_code, stdout, stderr = run_java("ConnectionUserTest", cp, timeout=15)
    combined = stdout + stderr
    print(f"\n[ConnectionUserTest stdout]\n{stdout}")
    print(f"[ConnectionUserTest stderr]\n{stderr}")

    # BUGGY ConnectionUser leaks the connection -> at least one test fails
    assert "1 passed, 1 failed" in combined or "0 passed, 2 failed" in combined, (
        f"ConnectionUserTest with buggy ConnectionUser should report failures.\n"
        f"Output:\n{combined}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
