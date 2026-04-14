/**
 * D30-03: Connection pool leak – FIX version.
 *
 * FIX: every getConnection() is paired with POOL.returnConnection(conn).
 * This ensures the connection is returned to the pool immediately after use,
 * keeping pool slots available for other threads.
 */

import java.sql.*;

// Pool interface: Pool.java
// Pool implementation: SimplePool.java
// Both are in the same directory and compiled together.

public class gold_patch {

    private static final Pool POOL;
    private static final int POOL_MAX = 2;
    private static final long TIMEOUT_MS = 3000; // 3 s

    static {
        try { DriverManager.registerDriver(new org.h2.Driver()); } catch (SQLException e) { throw new RuntimeException(e); }
        POOL = new SimplePool(POOL_MAX, TIMEOUT_MS);
    }

    /**
     * Worker that holds a connection for 2 seconds.
     * FIX: connection is always returned to the pool in the finally block.
     */
    public static void correctWork() throws Exception {
        Connection conn = POOL.getConnection();
        try {
            Thread.sleep(2000);
        } finally {
            // FIX: always return connection to pool
            POOL.returnConnection(conn);
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("[gold_patch] Pool max=" + POOL_MAX + ", timeout=" + TIMEOUT_MS + "ms");
        System.out.println("[gold_patch] Initial active: " + POOL.activeCount());

        // -- Start background worker that holds a connection for 2 s --
        Thread worker = new Thread(() -> {
            try {
                Connection conn = POOL.getConnection();
                System.out.println("[gold_patch] Worker acquired conn, active=" + POOL.activeCount());
                Thread.sleep(2000);
                // FIX: connection properly returned to pool
                POOL.returnConnection(conn);
                System.out.println("[gold_patch] Worker done (conn returned), active=" + POOL.activeCount());
            } catch (Exception e) {
                System.out.println("[gold_patch] Worker exception: " + e.getMessage());
            }
        });
        worker.start();

        Thread.sleep(500);
        System.out.println("[gold_patch] Active after worker start: " + POOL.activeCount());

        // -- Try to acquire a second connection while worker holds one --
        // FIX: worker returns its conn at ~2s, freeing a slot.
        // Main thread waits 3s – enough for worker to finish.
        try {
            Connection conn2 = POOL.getConnection();
            System.out.println("[gold_patch] Second conn acquired (pool had idle slot)");
            POOL.returnConnection(conn2);
        } catch (SQLTimeoutException e) {
            System.out.println("[gold_patch] UNEXPECTED timeout (should not happen with fix)");
        }

        worker.join();

        System.out.println("[gold_patch] Active after worker done: " + POOL.activeCount());

        // -- Verify: pool must be empty --
        boolean clean = (POOL.activeCount() == 0);
        System.out.println("[gold_patch] Pool clean: " + clean);

        if (!clean) {
            System.out.println("[gold_patch] UNEXPECTED: pool not empty after fix");
            System.out.println("FAIL: connection_pool_leak");
            POOL.shutdown();
            System.exit(1);
        } else {
            System.out.println("[gold_patch] PASS: connection properly returned to pool");
            POOL.shutdown();
            System.exit(0);
        }
    }
}
