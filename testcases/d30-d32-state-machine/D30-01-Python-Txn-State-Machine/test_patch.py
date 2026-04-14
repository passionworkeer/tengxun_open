"""
D30-01 Test Patch: Transaction atomicity & state machine compliance

Fail-to-Pass logic:
  BUG version (isolation_level=None + direct commit):
    - No explicit begin() before commit() -> violates DB-API 2.0 state machine
    - Test: detect presence of isolation_level=None in code

  FIX version (with conn: context manager):
    - with block auto-begins transaction, auto-commits on exit
    - Auto-rollbacks on exception
    - Test: verify atomic rollback on exception
"""

import os
import sqlite3

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_balances(db_path: str) -> tuple[int, int]:
    """Return (alice_balance, bob_balance)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, balance FROM accounts ORDER BY id")
    rows = dict(cur.fetchall())
    cur.close()
    conn.close()
    return rows[1], rows[2]


def setup_db(db_path: str) -> None:
    """Initialise accounts table."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS accounts "
        "(id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)"
    )
    cur.execute("DELETE FROM accounts")
    cur.execute("INSERT INTO accounts (id, name, balance) VALUES (1, 'Alice', 1000)")
    cur.execute("INSERT INTO accounts (id, name, balance) VALUES (2, 'Bob',   500)")
    conn.commit()
    cur.close()
    conn.close()


def code_only(source: str) -> str:
    """Strip docstrings and comments, return executable code."""
    lines = []
    in_docstring = False
    for raw in source.splitlines():
        s = raw.strip()
        if '"""' in s or "'''" in s:
            in_docstring = not in_docstring
            continue
        if in_docstring or s.startswith("#"):
            continue
        if s:
            lines.append(s)
    return "\n".join(lines)


# ── Fixtures ──────────────────────────────────────────────────────────────────

CASE_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(params=[
    "buggy_code.py",   # BUG version: isolation_level=None + direct commit
    "gold_patch.py",   # FIX version: with conn: context manager
])
def target_module(request, tmp_path) -> tuple[str, str]:
    """Return (module_path, db_path) for each parameterised version."""
    module_path = os.path.join(CASE_DIR, request.param)
    db_path = str(tmp_path / "test.db")
    return module_path, db_path


# ── Core tests ───────────────────────────────────────────────────────────────

def test_transfer_atomicity_on_success(target_module):
    """
    Transfer succeeds -> balances conserved.
    PASS for both BUG and FIX versions.
    """
    module_path, db_path = target_module
    setup_db(db_path)

    import importlib.util
    spec = importlib.util.spec_from_file_location("transfer_mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.make_transfer(db_path, from_id=1, to_id=2, amount=200)

    alice, bob = get_balances(db_path)
    assert alice == 800, f"Alice balance should be 800, got {alice}"
    assert bob   == 700, f"Bob   balance should be 700, got {bob}"


def test_transfer_atomicity_on_exception(target_module):
    """
    Exception mid-transfer -> entire transaction rolls back, balances unchanged.

    BUG version  (isolation_level=None, no explicit transaction)
      -> first UPDATE auto-commits before exception
      -> balances: Alice=800, Bob=500  -> FAIL

    FIX version  (with conn: context manager)
      -> exception triggers auto-rollback
      -> balances: Alice=1000, Bob=500 -> PASS
    """
    module_path, db_path = target_module
    setup_db(db_path)

    # Write a sabotage module that raises after first DML
    sabotaged_source = """
import sqlite3

def make_transfer(db_path, from_id, to_id, amount):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE accounts SET balance = balance - ? WHERE id = ?",
            (amount, from_id))
        raise RuntimeError("Simulated failure during transfer")
    finally:
        conn.close()
"""
    sabotaged_path = db_path + "_sabotaged.py"
    with open(sabotaged_path, "w", encoding="utf-8") as f:
        f.write(sabotaged_source)

    try:
        import importlib.util
        spec2 = importlib.util.spec_from_file_location("sab", sabotaged_path)
        mod2 = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod2)

        with pytest.raises(RuntimeError, match="Simulated failure"):
            mod2.make_transfer(db_path, from_id=1, to_id=2, amount=200)

        alice, bob = get_balances(db_path)
        assert alice == 1000, f"Atomicity violated: Alice={alice}, expected 1000"
        assert bob   == 500,  f"Atomicity violated: Bob={bob}, expected 500"
    finally:
        os.unlink(sabotaged_path)


def test_no_isolation_level_none(target_module):
    """
    Static check: source code must NOT contain isolation_level=None.

    BUG version  -> FAIL
    FIX version  -> PASS
    """
    module_path, _ = target_module
    with open(module_path, "r", encoding="utf-8") as f:
        source = f.read()

    code = code_only(source)
    assert "isolation_level=None" not in code and "isolation_level = None" not in code, (
        "Code uses isolation_level=None, bypassing transaction state machine. "
        "Use 'with conn:' context manager or explicit begin()/commit()."
    )


def test_transaction_context_manager_used(target_module):
    """
    Static check: source code must use 'with conn:' context manager.

    BUG version  -> FAIL (no with conn:)
    FIX version  -> PASS (has with conn:)
    """
    module_path, _ = target_module
    with open(module_path, "r", encoding="utf-8") as f:
        source = f.read()

    code = code_only(source)
    assert "with conn:" in code, (
        "Code does not use 'with conn:' context manager for transaction safety."
    )


# ── Direct (non-parameterised) smoke tests ───────────────────────────────────

def test_buggy_code_contains_bug():
    """Verify buggy_code.py exists and contains the intentional bug."""
    buggy_path = os.path.join(CASE_DIR, "buggy_code.py")
    assert os.path.exists(buggy_path)

    with open(buggy_path, "r", encoding="utf-8") as f:
        source = f.read()

    code = code_only(source)
    assert "isolation_level=None" in code, (
        "buggy_code.py must contain 'isolation_level=None' as the bug"
    )


def test_gold_patch_has_no_bug():
    """Verify gold_patch.py is clean and uses the correct pattern."""
    gold_path = os.path.join(CASE_DIR, "gold_patch.py")
    assert os.path.exists(gold_path)

    with open(gold_path, "r", encoding="utf-8") as f:
        source = f.read()

    code = code_only(source)
    assert "isolation_level=None" not in code, "gold_patch.py must not contain bug"
    assert "with conn:" in code,        "gold_patch.py must use 'with conn:'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
