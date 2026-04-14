/**
 * D31-01: Fixed version — use std::recursive_mutex to allow reentry.
 *
 * FIX: Replace std::mutex with std::recursive_mutex.
 * A recursive mutex allows the same thread to lock it multiple times.
 * The lock count is tracked; the mutex is only fully released when the
 * outermost lock_guard goes out of scope.
 *
 * Alternative fix: restructure so the callback does NOT need the lock
 * (pass data in/out, or use a different synchronisation primitive).
 * Here we demonstrate the recursive_mutex approach.
 */

#include <mutex>
#include <functional>
#include <thread>
#include <iostream>
#include <vector>

// FIX: use recursive_mutex so reentry from the same thread is safe
std::recursive_mutex m;
int shared_counter = 0;

/**
 * Process work while holding the recursive mutex.
 * Calls user-provided callback INSIDE the locked section.
 */
void process_with_lock(std::function<void()> user_callback) {
    std::lock_guard<std::recursive_mutex> lock(m);   // acquires m
    shared_counter = 1;
    std::cout << "[process_with_lock] locked (count=1), calling user callback..." << std::endl;
    // FIXED: recursive_mutex allows the same thread to re-enter safely.
    user_callback();
    shared_counter = 2;
    std::cout << "[process_with_lock] releasing lock (count=0)." << std::endl;
}

/**
 * Callback that also locks the same recursive mutex.
 * With std::recursive_mutex: safe reentry, no deadlock.
 * The lock count goes from 1 → 2 → 1 → 0 as scopes unwind.
 */
void callback_that_tries_lock() {
    std::cout << "[callback] attempting to lock m..." << std::endl;
    std::lock_guard<std::recursive_mutex> lock(m);   // re-acquires m (count=2)
    std::cout << "[callback] acquired lock (count=2), modifying shared state." << std::endl;
    shared_counter += 10;
}

int main() {
    std::cout << "Starting D31-01 fixed version..." << std::endl;
    std::cout << "Expected: completes successfully with recursive_mutex." << std::endl;

    process_with_lock(callback_that_tries_lock);

    std::cout << "shared_counter=" << shared_counter << std::endl;
    std::cout << "D31-01 FIXED test PASSED." << std::endl;
    return 0;
}
