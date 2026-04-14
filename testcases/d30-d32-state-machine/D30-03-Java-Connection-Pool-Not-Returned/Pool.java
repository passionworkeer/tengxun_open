/**
 * Pool – minimal connection pool interface (self-contained, no javax.sql needed).
 * Shared by buggy_code, gold_patch, and ConnectionUser test files.
 */
import java.sql.*;

public interface Pool {
    /** Acquire a connection from the pool. May block or timeout. */
    Connection getConnection() throws SQLException;
    /** Return a connection to the pool. */
    void returnConnection(Connection c);
    /** Number of currently checked-out (active) connections. */
    int activeCount();
    /** Shutdown the pool. */
    void shutdown();
}
