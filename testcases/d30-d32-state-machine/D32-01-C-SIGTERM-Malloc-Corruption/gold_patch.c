/**
 * D32-01: SIGTERM handler - FIXED VERSION
 *
 * FIX: Signal handler only calls async-signal-safe functions.
 *
 * Per POSIX.1-2017 (Table 3-3), only these functions (and a few others)
 * are async-signal-safe and may be called from a signal handler:
 *   _exit(), _Exit(), abort(), alarm(), close(), dup(), dup2(), execl(),
 *   execle(), execv(), execve(), _exit(), fpathconf(), fstat(), fstatat(),
 *   fsync(), ftruncate(), getegid(), geteuid(), getgid(), getgroups(),
 *   getpeername(), getpgrp(), getpid(), getppid(), getsockname(),
 *   getsockopt(), getuid(), kill() [with caveats], link(), linkat(),
 *   longjmp() [with caveats], lseek(), lstat(), mkdir(), mkfifo(),
 *   open(), openat(), pause(), pipe(), poll(), pselect(), raise(),
 *   read(), readlink(), readlinkat(), recv(), recvfrom(), recvmsg(),
 *   rename(), renameat(), rmdir(), select(), send(), sendmsg(), sendto(),
 *   setsockopt(), shutdown(), sigaction(), sigaddset(), sigdelset(),
 *   sigemptyset(), sigfillset(), sigismember(), sigpending(), sigprocmask(),
 *   sigqueue(), sigsuspend(), sleep(), socket(), socketpair(), stat(),
 *   stpcpy(), stpncpy(), symlink(), symlinkat(), tcdrain(), tcflow(),
 *   tcflush(), tcgetattr(), tcgetpgrp(), tcsendbreak(), tcsetattr(),
 *   tcsetpgrp(), time(), times(), umask(), uname(), unlink(), unlinkat(),
 *   utime(), utimensat(), utimes(), wait(), waitpid(), write(), etc.
 *
 * KEY FORBIDDEN functions: malloc, free, realloc, calloc, printf, fprintf,
 * sprintf, snprintf, scanf, fscanf, strcpy, strncpy, memcpy, memset,
 * memmove, getpwnam, getgrnam, system, popen, etc.
 *
 * The correct pattern is: set a volatile flag and defer ALL unsafe work
 * to the main context (outside the signal handler).
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

/* Message lives in main context, not signal handler */
static const char* error_msg = "Received SIGTERM, shutting down gracefully";

/**
 * SIGTERM handler - FIXED VERSION
 *
 * FIX: only use async-signal-safe operations.
 * - write() is async-signal-safe (POSIX.1-2017 Table 3-3)
 * - Setting should_exit is safe (sig_atomic_t operations are safe)
 * - NO malloc(), free(), printf(), strcpy(), etc.
 */
void sigterm_handler(int sig) {
    /* SAFE: sig_atomic_t operations are async-signal-safe */
    should_exit = 1;

    /* SAFE: write() is async-signal-safe (unlike printf) */
    const char msg[] = "SIGTERM received, exiting...\n";
    write(STDOUT_FILENO, msg, sizeof(msg) - 1);

    (void)sig;  /* suppress unused parameter warning */
}

/**
 * Simulates work that allocates and frees memory.
 * All malloc/free happen in main context (not signal handler).
 */
void do_work(void) {
    char* buf = malloc(1024);
    if (buf) {
        memset(buf, 'A', 1024);
        free(buf);
    }
}

int main(void) {
    /* Install signal handler using portable signal() API */
    if (signal(SIGTERM, sigterm_handler) == SIG_ERR) {
        perror("signal");
        return 1;
    }

    printf("PID: %d\n", (int)getpid());
    printf("Send SIGTERM to test the fix...\n");

    /* Main loop defers all malloc/free to normal context */
    while (!should_exit) {
        do_work();
        usleep(100000);  /* 100ms */
    }

    /* Deferred message printing (main context = safe) */
    printf("Exit: %s\n", error_msg);
    return 0;
}
