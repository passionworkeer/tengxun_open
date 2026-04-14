// Package fixed — D30-02 patched implementation.
//
// FIX: resp.Body is always closed (defer resp.Body.Close()), so the
// TCP connection is returned to the transport's idle-connection pool.
package D30_02_GO_RESPONSE_BODY_LEAK

import (
	"fmt"
	"io"
	"net/http"
	"time"
)

// BodyIsClosed fetches a URL, reads the body, and PROPERLY closes it.
// This is the CORRECT pattern: the connection is returned to the pool.
func BodyIsClosed(url string) (string, error) {
	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("GET %s: %w", url, err)
	}
	// FIX: defer resp.Body.Close() ensures the connection is always returned.
	defer resp.Body.Close()

	n, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("read %d bytes, status %s", n, resp.Status), nil
}

// FixedSmokeTest runs a quick manual verification against httpbin.org.
func FixedSmokeTest() {
	for i := 0; i < 3; i++ {
		r, err := BodyIsClosed("https://httpbin.org/get")
		if err != nil {
			fmt.Printf("request %d error: %v\n", i, err)
		} else {
			fmt.Printf("request %d ok: %s\n", i, r)
		}
		time.Sleep(100 * time.Millisecond)
	}
}
