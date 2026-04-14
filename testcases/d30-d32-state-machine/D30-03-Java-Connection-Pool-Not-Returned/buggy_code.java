/**
 * D30-03: Connection pool leak – connection never returned to pool.
 *
 * BUG: acquire Connection from pool and never call returnConnection().
 * This causes:
 *   - Pool exhaustion (all connections checked out, never returned)
 *   - Subsequent threads block waiting for a connection
 *   - Pool-level timeout or complete deadlock
 *
 * FIX: always call pool.returnConnection(conn) in finally block.
 */

import java.sql.*;

// Pool interface: Pool.java
// Pool implementation: SimplePool.java
// Both are in the same directory and compiled together.

public class buggy_code {

    private static final Pool POOL;
    private static final int POOL_MAX = 2;
    private static final long TIMEOUT_MS = 3000; // 3 s – exposes the bug

    static {
        try { DriverManager.registerDriver(new org.h2.Driver()); } catch (SQLException e) { throw new RuntimeException(e); }
        POOL = new SimplePool(POOL_MAX, TIMEOUT_MS);
    }

    /**
     * Worker that holds a connection for 2 seconds – simulating a long DB operation.
     * BUG: the connection is never returned to the pool.
     */
    public static void buggyWork() throws Exception {
        Connection conn = POOL.getConnection();
        try {
            Thread.sleep(2000);
        } finally {
            // BUG: missing POOL.returnConnection(conn);
            // Correct fix: POOL.returnConnection(conn);
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("[buggy_code] Pool max=" + POOL_MAX + ", timeout=" + TIMEOUT_MS + "ms");
        System.out.println("[buggy_code] Initial active: " + POOL.activeCount());

        // -- Start background worker that holds a connection for 2 s --
        Thread worker = new Thread(() -> {
            try {
                Connection conn = POOL.getConnection();
                System.out.println("[buggy_code] Worker acquired conn, active=" + POOL.activeCount());
                Thread.sleep(2000);
                // BUG: conn never returned – connection leaks!
                System.out.println("[buggy_code] Worker done (conn NOT returned), active=" + POOL.activeCount());
            } catch (Exception e) {
                System.out.println("[buggy_code] Worker exception: " + e.getMessage());
            }
        });
        worker.start();

        Thread.sleep(500);
        System.out.println("[buggy_code] Active after worker start: " + POOL.activeCount());

        // -- Try to acquire a second connection while worker holds one --
        try {
            Connection conn2 = POOL.getConnection();
            System.out.println("[buggy_code] Second conn acquired (worker still holds first)");
            // conn2 will be returned but worker's conn is leaked
            POOL.returnConnection(conn2);
        } catch (SQLTimeoutException e) {
            System.out.println("[buggy_code] TIMEOUT – pool exhausted (bug reproduced)");
        }

        worker.join();

        System.out.println("[buggy_code] Active after worker done: " + POOL.activeCount());

        // -- Verify: pool must be empty --
        boolean clean = (POOL.activeCount() == 0);
        System.out.println("[buggy_code] Pool clean: " + clean);

        if (!clean) {
            System.out.println("[buggy_code] BUG DETECTED: " + POOL.activeCount() + " connection(s) leaked");
            System.out.println("FAIL: connection_pool_leak");
            POOL.shutdown();
            System.exit(1);
        } else {
            System.out.println("[buggy_code] PASS");
            POOL.shutdown();
            System.exit(0);
        }
    }
}
