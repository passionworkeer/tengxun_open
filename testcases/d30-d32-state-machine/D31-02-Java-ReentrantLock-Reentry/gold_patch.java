import java.util.concurrent.locks.*;

public class gold_patch {
    private final ReentrantLock lock = new ReentrantLock();
    private int balance = 1000;
    private int transactionCount = 0;

    public void deposit(int amount) {
        lock.lock();
        try {
            balance += amount;
            transactionCount++;  // record the deposit exactly once
            // FIX: do NOT call processFee() inside the lock scope that also locks.
            // Instead, call the fee logic directly without re-acquiring the lock,
            // or restructure so there is only ONE lock-holding region that
            // performs both operations atomically in a single step.
            processFeeDirect(amount);  // no extra lock needed; already holding lock
        } finally {
            lock.unlock();
        }
    }

    // New helper: no lock acquisition -- caller already holds the lock.
    // This avoids the reentrant double-count trap entirely.
    private void processFeeDirect(int amount) {
        // No lock here -- we are inside the outer deposit() critical section.
        // Only one increment of transactionCount occurs (done in deposit()).
        balance -= amount / 100;
    }

    public int getBalance() {
        return balance;
    }

    public int getTransactionCount() {
        return transactionCount;
    }

    public static void main(String[] args) {
        gold_patch b = new gold_patch();
        b.deposit(1000);  // deposit 1000, expect transactionCount == 1
        System.out.println("Balance: " + b.getBalance());
        System.out.println("TransactionCount: " + b.getTransactionCount());
        // CORRECT: transactionCount == 1, balance == 990 (1000 + 1000 - 10 fee)
    }
}
