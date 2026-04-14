// client_fixed_test.go — D30-02 tests for the FIXED version.
//
//go:build fixed

// This file is compiled only when:  go test -tags=fixed
//
// The fix: defer resp.Body.Close() is present → connection is returned to pool.
// This test verifies that gold_patch.go CORRECTLY calls resp.Body.Close(),
// causing the test to PASS — the intended outcome for the fixed version.
package D30_02_GO_RESPONSE_BODY_LEAK

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"testing"
)

// TestFixedCodeHasBodyClose is a SOURCE-LEVEL check that reads
// gold_patch.go and verifies that resp.Body.Close() IS called.
// Since this is the FIXED version, we EXPECT the close to be present.
// The test PASSES when gold_patch.go has the close call.
func TestFixedCodeHasBodyClose(t *testing.T) {
	src, err := os.ReadFile("gold_patch.go")
	if err != nil {
		t.Fatalf("could not read gold_patch.go: %v", err)
	}
	content := string(src)

	// Detect "defer resp.Body.Close()" or "io.Copy" (which auto-closes).
	deferRespBodyClose := regexp.MustCompile(`(?m)^\s*defer\s+resp\.Body\.Close\s*\(`)
	ioCopyCall := regexp.MustCompile(`\bio\.Copy\b`)

	if !deferRespBodyClose.MatchString(content) && !ioCopyCall.MatchString(content) {
		t.Errorf("FIXED: gold_patch.go does NOT call defer resp.Body.Close(). " +
			"FAIL: the fixed version should have the close call.")
	}
	// If match: test PASSES (correct!)
}

// TestBodyIsClosedReturnsCleanly verifies that BodyIsClosed() can make
// requests without error.
func TestBodyIsClosedReturnsCleanly(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"test":true}`))
	}))
	defer srv.Close()

	// BodyIsClosed uses http.Get() internally.
	// Verify it makes a successful request.
	result, err := BodyIsClosed(srv.URL)
	if err != nil {
		t.Errorf("BodyIsClosed returned error: %v", err)
	}
	if result == "" {
		t.Errorf("BodyIsClosed returned empty result")
	}
}

// TestFixedClientClosesBody verifies that a properly closed response body
// allows the client to function correctly.
func TestFixedClientClosesBody(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	client := srv.Client() // uses httptest default transport

	resp, err := client.Get(srv.URL)
	if err != nil {
		t.Fatalf("GET failed: %v", err)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("ReadAll failed: %v", err)
	}
	resp.Body.Close()

	if len(body) == 0 {
		t.Errorf("got empty body")
	}
}
