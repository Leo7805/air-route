# Authentication regression tests

Run `npm run test:auth` from `frontend`. Google Chrome must be installed; set
`CHROME_PATH` to its executable if it is not at the default macOS location or
available as `google-chrome` on other platforms. No test dependencies are needed.

The runner starts Vite on a temporary port and launches headless Chrome with an
isolated temporary profile. A nonzero exit status means the tests failed.
Alternatively, run `npm run dev` and open `/tests/auth.html` to inspect results.

Tests mount the real React provider, login page, layout, and route guards in
StrictMode. Fetch responses are mocked at the HTTP boundary, including delayed
responses that ignore cancellation. They check matching account, role, token,
Authorization headers, navigation, restoration by remount, and stale requests.
Invalid/expired JWT tests simulate the backend's rejection statuses; these tests
do not validate JWT signatures or replace live backend permission tests.
They do not constitute manual browser testing or a live full-stack login test.
