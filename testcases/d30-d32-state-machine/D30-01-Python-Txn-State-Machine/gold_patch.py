"""
D30-01 Gold Patch: Correct transfer implementation

Fix:
  - Remove isolation_level=None (disables connection management)
  - Use 'with conn:' context manager for automatic begin/commit/rollback
  - Transaction lifecycle is now properly managed per DB-API 2.0
"""

import sqlite3
import tempfile
import os


def make_transfer(db_path: str, from_id: int, to_id: int, amount: int) -> None:
    """
    Transfer: debit then credit, maintaining balance invariant.
    FIXED VERSION: uses with conn: context manager for safe transaction.
    """
    conn = sqlite3.connect(db_path)  # isolation_level='DEFERRED' by default
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
            cursor.close()
    finally:
        conn.close()


def setup_db(db_path: str) -> None:
    """Create accounts table with initial data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)")
    cursor.execute("DELETE FROM accounts")
    cursor.execute("INSERT INTO accounts (id, name, balance) VALUES (1, 'Alice', 1000)")
    cursor.execute("INSERT INTO accounts (id, name, balance) VALUES (2, 'Bob',   500)")
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    try:
        setup_db(db_path)
        make_transfer(db_path, from_id=1, to_id=2, amount=200)
        print("Transfer completed.")
    finally:
        os.unlink(db_path)
