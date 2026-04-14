/**
 * SimplePool – minimal connection pool implementation.
 * Shared by buggy_code and gold_patch (compiled into a single directory).
 */
import java.sql.*;
import java.util.*;

public class SimplePool implements Pool {
    private final int maxSize;
    private final long timeoutMs;
    private final Queue<Connection> idle = new ArrayDeque<>();
    private final Set<Connection> active = new HashSet<>();
    private volatile boolean shutdown = false;

    public SimplePool(int maxSize, long timeoutMs) {
        this.maxSize = maxSize;
        this.timeoutMs = timeoutMs;
    }

    private Connection makeReal() throws SQLException {
        return DriverManager.getConnection(
            "jdbc:h2:mem:testdb_" + System.identityHashCode(this) + ";DB_CLOSE_DELAY=-1");
    }

    @Override
    public synchronized Connection getConnection() throws SQLException {
        if (shutdown) throw new SQLException("Pool shutdown");
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (true) {
            // Always prefer returning idle connections first
            if (!idle.isEmpty()) {
                Connection c = idle.poll();
                active.add(c);
                return c;
            }
            // Only create new connection if below max
            if (active.size() < maxSize) {
                Connection c = makeReal();
                active.add(c);
                return c;
            }
            // Pool exhausted: wait for a returned connection
            long wait = deadline - System.currentTimeMillis();
            if (wait <= 0) throw new SQLTimeoutException("Connection pool exhausted – timeout");
            try { wait(wait); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new SQLException("interrupted");
            }
        }
    }

    @Override
    public synchronized void returnConnection(Connection c) {
        if (active.remove(c) && !shutdown) { idle.add(c); notifyAll(); }
    }

    @Override
    public synchronized int activeCount() { return active.size(); }

    @Override
    public synchronized void shutdown() {
        shutdown = true;
        idle.clear();
        active.clear();
    }
}
