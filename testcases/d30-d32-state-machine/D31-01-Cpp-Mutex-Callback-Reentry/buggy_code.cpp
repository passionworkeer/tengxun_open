/**
 * D31-01: Holding mutex, calling user callback, callback acquires same lock (C++)
 *
 * BUG: std::mutex is non-recursive. When process_with_lock() holds m and
 * invokes user_callback(), if user_callback also tries to lock m, the program
 * deadlocks. The correct fix is either std::recursive_mutex OR restructuring so
 * the callback does not need the lock.
 */

#include <mutex>
#include <functional>
#include <thread>
#include <iostream>
#include <vector>

// Using non-recursive std::mutex — deadlock waiting to happen
std::mutex m;
int shared_counter = 0;

/**
 * Process work while holding the mutex.
 * Calls user-provided callback INSIDE the locked section.
 */
void process_with_lock(std::function<void()> user_callback) {
    std::lock_guard<std::mutex> lock(m);   // acquires m
    shared_counter = 1;
    std::cout << "[process_with_lock] locked, calling user callback..." << std::endl;
    // BUG: calling user callback while holding the lock.
    // If user_callback also locks m, deadlock with std::mutex.
    user_callback();
    shared_counter = 2;
    std::cout << "[process_with_lock] releasing lock." << std::endl;
}

/**
 * Callback that attempts to lock the same mutex.
 * With std::mutex: DEADLOCK.
 * With std::recursive_mutex: would not deadlock, but shared state is
 * being double-modified which is a logic bug / broken invariant.
 */
void callback_that_tries_lock() {
    std::cout << "[callback] attempting to lock m..." << std::endl;
    std::lock_guard<std::mutex> lock(m);   // DEADLOCK here with std::mutex
    std::cout << "[callback] acquired lock, modifying shared state." << std::endl;
    shared_counter += 10;
}

int main() {
    std::cout << "Starting D31-01 test (buggy version)..." << std::endl;
    std::cout << "Expected: deadlock with std::mutex." << std::endl;

    // Demonstrate the deadlock scenario
    process_with_lock(callback_that_tries_lock);

    std::cout << "shared_counter=" << shared_counter << std::endl;
    std::cout << "D31-01 test PASSED (this line should NOT be reached)." << std::endl;
    return 0;
}
