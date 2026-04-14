import java.util.concurrent.locks.*;

public class buggy_code {
    private final ReentrantLock lock = new ReentrantLock();
    private int balance = 1000;
    private int transactionCount = 0;

    public void deposit(int amount) {
        lock.lock();
        try {
            balance += amount;
            transactionCount++;  // first increment: recording the deposit itself
            // BUG: reentrant call while holding lock modifies the same shared state
            // processFee() also locks (reentrant) and increments transactionCount again
            // The caller expects ONE transaction record, but gets TWO due to reentrancy
            processFee(amount);   // reentrant lock entry -> transactionCount++ again!
        } finally {
            lock.unlock();
        }
    }

    private void processFee(int amount) {
        lock.lock();  // reentrant: same thread re-acquires the lock
        try {
            // BUG: transactionCount was already incremented above.
            // Reentering here causes a second, unintended increment.
            // The invariant "one deposit == one transactionCount increment" is broken.
            transactionCount++;   // double-counted! Should be 1, actually becomes 2
            balance -= amount / 100;  // deduct 1% fee from balance
        } finally {
            lock.unlock();
        }
    }

    public int getBalance() {
        return balance;
    }

    public int getTransactionCount() {
        return transactionCount;
    }

    public static void main(String[] args) {
        buggy_code b = new buggy_code();
        b.deposit(1000);  // deposit 1000, expect transactionCount == 1
        System.out.println("Balance: " + b.getBalance());
        System.out.println("TransactionCount: " + b.getTransactionCount());
        // BUG: transactionCount will be 2 instead of 1
        // balance will be 990 (1000 + 1000 - 10 fee) -- also confusing naming
    }
}
