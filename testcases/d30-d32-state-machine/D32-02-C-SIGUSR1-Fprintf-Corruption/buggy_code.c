/*
 * D32-02: SIGUSR1 handler calls fprintf to stdout causing corruption
 *
 * BUG: Signal handler uses fprintf() which is NOT async-signal-safe.
 * fprintf() uses internal buffering and stdio locks that can:
 *   1. Deadlock if signal arrives while main holds the lock
 *   2. Corrupt the stdout buffer if interrupted during write
 *   3. Leave stdout in an inconsistent state
 *
 * Async-signal-safe functions (POSIX): _exit, write, kill, signal, etc.
 * Non-safe (MUST NOT use in signal handlers): fprintf, printf, fflush,
 *                                               malloc, free, exit, etc.
 */

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <time.h>

volatile sig_atomic_t sigusr1_count = 0;

void sigusr1_handler(int sig) {
    /* BUG: fprintf is NOT async-signal-safe
     * It uses internal buffering and locks that can corrupt stdout
     * or cause deadlock when signal arrives during another fprintf.
     *
     * Correct async-signal-safe replacement: write(STDOUT_FILENO, msg, len)
     */
    fprintf(stdout, "[SIGUSR1 received at %ld]\n", (long)time(NULL));
    fflush(stdout);  /* also NOT async-signal-safe */
    sigusr1_count++;
}

void main_loop(void) {
    for (int i = 0; i < 5; i++) {
        printf("Main loop iteration %d\n", i);
        fflush(stdout);
        usleep(500000);
    }
}

int main(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigusr1_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGUSR1, &sa, NULL);

    printf("PID: %d - send SIGUSR1 to trigger bug\n", getpid());
    fflush(stdout);

    main_loop();

    printf("Total SIGUSR1 count: %d\n", (int)sigusr1_count);
    return 0;
}
