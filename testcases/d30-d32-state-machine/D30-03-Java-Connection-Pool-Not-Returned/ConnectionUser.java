/**
 * ConnectionUser – demonstrates the leak with a simple class-based API.
 *
 * BUGGY version: doWork() never returns the connection to the pool.
 */

import java.sql.*;

public class ConnectionUser {

    private final Pool pool;

    public ConnectionUser(Pool pool) { this.pool = pool; }

    /**
     * Execute a SELECT query.
     * BUG VERSION: Connection is never returned to the pool.
     */
    public void doWork() throws SQLException {
        Connection conn = pool.getConnection();
        try (ResultSet rs = conn.prepareStatement("SELECT 1 AS a").executeQuery()) {
            rs.next();
            int val = rs.getInt("a");
        } // BUG: pool.returnConnection(conn) is missing!
        // Note: try-with-resources closes the ResultSet but NOT the Connection.
    }
}
