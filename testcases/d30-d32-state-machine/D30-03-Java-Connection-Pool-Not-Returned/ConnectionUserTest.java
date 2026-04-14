/**
 * ConnectionUserTest – JUnit-style manual test runner for ConnectionUser.
 *
 * Demonstrates:
 *   - BUGGY: ConnectionUser.doWork() leaks the connection (no returnConnection)
 *   - After leak, pool has stale active connections
 *
 * Run directly: java -cp h2*.jar;. ConnectionUserTest
 */

import java.sql.*;

public class ConnectionUserTest {

    private static Pool POOL;

    public static void main(String[] args) throws Exception {
        // Register H2 driver
        try { DriverManager.registerDriver(new org.h2.Driver()); } catch (SQLException e) { throw new RuntimeException(e); }

        POOL = new SimplePool(2, 3000); // pool size=2, timeout=3s

        int passed = 0;
        int failed = 0;

        // -- Test 1: doWork leaks a connection --
        System.out.println("\n=== Test 1: doWork() leaks connection ===");
        ConnectionUser user = new ConnectionUser(POOL);
        int before = POOL.activeCount();
        user.doWork();
        Thread.sleep(200); // allow to settle
        int after = POOL.activeCount();
        System.out.println("Active before: " + before + "  after: " + after);
        if (after == 0) {
            System.out.println("PASS: connection was returned to pool");
            passed++;
        } else {
            System.out.println("FAIL: connection leaked (still " + after + " active)");
            failed++;
        }

        // Detect leak: if pool is exhausted, subsequent connections will timeout
        if (after > 0) {
            System.out.println("Detected leak: pool has " + after + " leaked connection(s) – "
                + "subsequent acquires will block/timeout");
        }

        // -- Test 2: verify pool is empty after use --
        System.out.println("\n=== Test 2: verify pool empty after use ===");
        boolean clean = (POOL.activeCount() == 0);
        System.out.println("Pool clean: " + clean);
        if (clean) {
            System.out.println("PASS: pool empty");
            passed++;
        } else {
            System.out.println("FAIL: pool not empty");
            failed++;
        }

        // -- Summary --
        System.out.println("\n=== Results: " + passed + " passed, " + failed + " failed ===");
        POOL.shutdown();
        System.exit(failed > 0 ? 1 : 0);
    }
}
