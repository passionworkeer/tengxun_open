// client_test.go — D30-02 shared helpers (no build tag, always compiled).
//
// Test strategy:
//   When resp.Body is closed (fixed): connection is returned to pool → subsequent
//   requests REUSE the same TCP connection → connCount stays at 1.
//   When resp.Body is NOT closed (buggy): connection stays pinned → next request
//   opens a NEW TCP connection → connCount grows to 2.
//
// The connCountListener tracks distinct TCP connections accepted by the server,
// letting us assert that exactly 1 connection was used after 2 sequential requests.
package D30_02_GO_RESPONSE_BODY_LEAK

import (
	"net"
	"net/http"
	"net/http/httptest"
	"sync"
)

// connCountListener wraps a net.Listener and tracks distinct TCP connections.
type connCountListener struct {
	net.Listener
	mu    sync.Mutex
	count int
}

func (c *connCountListener) Accept() (net.Conn, error) {
	conn, err := c.Listener.Accept()
	if err == nil {
		c.mu.Lock()
		c.count++
		c.mu.Unlock()
	}
	return conn, err
}

// Count returns the total distinct connections accepted so far.
func (c *connCountListener) Count() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.count
}

// newServerWithConnCount creates an httptest.Server with a tracking listener.
func newServerWithConnCount(handler http.HandlerFunc) (*httptest.Server, *connCountListener) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		srv := httptest.NewServer(handler)
		return srv, nil
	}
	tracker := &connCountListener{Listener: ln}
	srv := httptest.NewUnstartedServer(handler)
	srv.Listener = tracker
	srv.Start()
	return srv, tracker
}

// newTestServer creates a plain httptest.Server.
func newTestServer() *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"D30-02":"leak_test"}`))
	}))
}
