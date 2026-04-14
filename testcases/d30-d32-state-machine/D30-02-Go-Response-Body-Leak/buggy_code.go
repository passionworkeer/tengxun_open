// Package D30_02_GO_RESPONSE_BODY_LEAK — buggy implementation.
//
// BUG: resp.Body is never closed, so the TCP connection is never returned
// to the transport's idle-connection pool.
package D30_02_GO_RESPONSE_BODY_LEAK

import (
	"fmt"
	"io"
	"net/http"
	"time"
)

// BodyNotClosed fetches a URL and reads the response body WITHOUT closing it.
// This is the BUGGY pattern: the connection stays pinned to the client.
func BodyNotClosed(url string) (string, error) {
	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("GET %s: %w", url, err)
	}
	// BUG: resp.Body.Close() is missing.
	// The TCP connection is never returned to http.DefaultClient's idle pool.
	defer func() {}()

	n, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("read %d bytes, status %s", n, resp.Status), nil
}

// BuggySmokeTest runs a quick manual verification against httpbin.org.
func BuggySmokeTest() {
	for i := 0; i < 3; i++ {
		r, err := BodyNotClosed("https://httpbin.org/get")
		if err != nil {
			fmt.Printf("request %d error: %v\n", i, err)
		} else {
			fmt.Printf("request %d ok: %s\n", i, r)
		}
		time.Sleep(100 * time.Millisecond)
	}
}
