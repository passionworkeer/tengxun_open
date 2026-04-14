// client_buggy_test.go — D30-02 tests for the BUGGY version.
//
//go:build buggy

// This file is compiled only when:  go test -tags=buggy
//
// The bug: resp.Body is never closed → connection cannot be returned to pool.
// This test verifies that buggy_code.go is MISSING resp.Body.Close(),
// causing the assertion to FAIL — the intended outcome for the buggy version.
package D30_02_GO_RESPONSE_BODY_LEAK

import (
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"testing"
)

// TestBuggyCodeMissingBodyClose is a SOURCE-LEVEL check that reads
// buggy_code.go and verifies that resp.Body.Close() is NOT called.
// Since this is the BUGGY version, we EXPECT this to be true (body close missing).
// We assert the FIXED behaviour (body IS closed), so the test FAILS.
//
// The test FAIL is the correct outcome for the buggy version.
func TestBuggyCodeMissingBodyClose(t *testing.T) {
	src, err := os.ReadFile("buggy_code.go")
	if err != nil {
		t.Fatalf("could not read buggy_code.go: %v", err)
	}
	content := string(src)

	// Detect "defer resp.Body.Close()" — the definitive fixed pattern.
	// The comment "BUG: resp.Body.Close() is missing" is just text (no parentheses).
	deferRespBodyClose := regexp.MustCompile(`(?m)^\s*defer\s+resp\.Body\.Close\s*\(`)
	ioCopyCall := regexp.MustCompile(`\bio\.Copy\b`)

	hasDeferBodyClose := deferRespBodyClose.MatchString(content)
	hasIoCopy := ioCopyCall.MatchString(content)

	if hasDeferBodyClose || hasIoCopy {
		t.Errorf("UNEXPECTED: buggy_code.go appears to close resp.Body. " +
			"This test expects buggy code to MISS the close call. " +
			"If buggy_code.go has defer resp.Body.Close(), it is not the buggy version.")
	} else {
		t.Errorf("BUGGY detected: buggy_code.go does NOT call defer resp.Body.Close(). " +
			"Connection will not be returned to pool. " +
			"FAIL (expected: buggy version should fail this test)")
	}
}

// TestBuggyFunctionRunsSuccessfully verifies that BodyNotClosed() can make
// requests (it just doesn't close the body properly).
func TestBuggyFunctionRunsSuccessfully(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"test":true}`))
	}))
	defer srv.Close()

	// BodyNotClosed uses http.Get() internally.
	result, err := BodyNotClosed(srv.URL)
	if err != nil {
		t.Errorf("BodyNotClosed returned error: %v", err)
	}
	if result == "" {
		t.Errorf("BodyNotClosed returned empty result")
	}
}
