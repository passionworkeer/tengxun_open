/*
 * D32-02: Fixed version of SIGUSR1 handler
 *
 * FIX: Signal handler now uses ONLY async-signal-safe functions.
 * write() is async-signal-safe; fprintf/printf/fflush are NOT.
 *
 * Rule: In a signal handler, only use functions from the
 *       async-signal-safe list in POSIX.1-2001.
 *       See: man 7 signal-safety
 */

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <time.h>

volatile sig_atomic_t sigusr1_count = 0;

void sigusr1_handler(int sig) {
    /* FIX: use write() - the only reliable async-signal-safe output function.
     * write() operates on raw file descriptors without buffering or locks.
     * time() is also async-signal-safe (SUSv4).
     */
    char buf[128];
    int len = snprintf(buf, sizeof(buf), "[SIGUSR1 received at %ld]\n",
                       (long)time(NULL));
    if (len > 0 && (size_t)len < sizeof(buf)) {
        write(STDOUT_FILENO, buf, (size_t)len);
    } else {
        const char fallback[] = "[SIGUSR1]\n";
        write(STDOUT_FILENO, fallback, sizeof(fallback) - 1);
    }
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

    printf("PID: %d - send SIGUSR1 to test fix\n", getpid());
    fflush(stdout);

    main_loop();

    printf("Total SIGUSR1 count: %d\n", (int)sigusr1_count);
    return 0;
}
