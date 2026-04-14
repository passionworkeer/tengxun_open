/**
 * D32-01: SIGTERM handler calls malloc causing heap corruption
 *
 * BUG: The signal handler sigterm_handler() calls malloc(), which is NOT
 * an async-signal-safe function (POSIX.1-2017). When a signal arrives while
 * the main program is executing malloc/free, calling malloc in the handler
 * can cause:
 *   1. Deadlock (recursive mutex on heap)
 *   2. Heap structure corruption
 *   3. Double-free / use-after-free
 *   4. Segmentation fault
 *
 * A proper fix uses only async-signal-safe functions in the handler, or
 * defers unsafe work to the main context via a volatile flag.
 *
 * Platform note: this file uses signal() which is available on both
 * POSIX and Windows (MinGW). The async-signal-safety issue is universal.
 */

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

/* Volatile flag to signal main loop to exit */
volatile sig_atomic_t should_exit = 0;

/* Error message buffer allocated INSIDE signal handler (BUG) */
char* error_msg = NULL;

/**
 * SIGTERM handler - BUGGY VERSION
 *
 * This handler calls malloc() which is NOT async-signal-safe.
 * POSIX.1-2017 Table 3-3 lists functions that may be called safely
 * in signal handlers. malloc is NOT in that table.
 *
 * Consequences:
 * - If main thread is inside malloc(): deadlock or heap corruption
 * - If main thread is inside free(): double-free or heap corruption
 * - ASan (AddressSanitizer) will report heap-buffer-overflow on signal
 */
void sigterm_handler(int sig) {
    /* BUG: malloc is NOT async-signal-safe (POSIX) */
    /* Calling malloc in a signal handler while another malloc is in
     * progress (or while the heap is being accessed from main code)
     * causes heap corruption and undefined behavior. */
    error_msg = malloc(256);   /* NOT async-signal-safe! */
    if (error_msg) {
        strcpy(error_msg, "Received SIGTERM, shutting down gracefully");
    }
    should_exit = 1;
    (void)sig;  /* suppress unused parameter warning */
}

/**
 * Simulates work that allocates and frees memory.
 * Represents a typical program that uses the heap.
 */
void do_work(void) {
    char* buf = malloc(1024);
    if (buf) {
        memset(buf, 'A', 1024);
        free(buf);  /* Also not async-signal-safe in handler context */
    }
}

int main(void) {
    /* Install signal handler using portable signal() API */
    if (signal(SIGTERM, sigterm_handler) == SIG_ERR) {
        perror("signal");
        return 1;
    }

    printf("PID: %d\n", (int)getpid());
    printf("Send SIGTERM (kill or Ctrl+C) to trigger the bug...\n");

    /* Main loop: simulate ongoing work with heap activity */
    while (!should_exit) {
        do_work();
        usleep(100000);  /* 100ms */
    }

    printf("Exit: %s\n", error_msg ? error_msg : "no message");
    if (error_msg) {
        free(error_msg);  /* This free() is after the signal handler returns */
    }
    return 0;
}
