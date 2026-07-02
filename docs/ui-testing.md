# 🖥️ UI Testing

Browser-driven tests that exercise a real Chromium browser (via `pytest-playwright`) 
through Nginx. They live in `tests/ui/` and run in the same suite as the 
[integration tests](integration-testing.md), under the same commands.

## ✅ What Is Covered

`tests/ui/sinopia/` drives Chromium through Nginx:

- Editor load, home page content, and no uncaught JS errors or same-origin `5xx`.
- Login panel, the Keycloak SSO redirect and its OAuth parameters, and rejection
  of invalid credentials.
- Authenticated flows (full login/logout round trip, nav, Dashboard, Resource
  Templates page) run only in dev-mode; on the published image they skip (its
  bundle bakes a non-local URL).

Requires the full stack (Nginx + Sinopia), which the runner enables by default;
UI tests skip automatically in a lightweight run. Chromium installs
automatically (`playwright install chromium`).

```bash
./scripts/test/integration-tests.sh tests/ui/sinopia
```

## 🐛 Debugging

The UI tests use the `pytest-playwright` plugin, so its flags pass straight
through the runner. These only apply to `tests/ui/*` and are for local debugging
(do not use them in CI):

| Flag | What it does |
|---|---|
| `--headed` | Show the Chromium window instead of running headless. |
| `--slowmo <ms>` | Pause `<ms>` milliseconds before each browser action so you can watch the flow. Use with `--headed`. |
| `--tracing on` | Record a Playwright trace; view it later with `playwright show-trace`. |
| `--video on` | Save a video of each test. |
| `--screenshot on` | Save a screenshot at the end of each test. |

Standard pytest flags work too, e.g. `-k <expr>` to run a single test.

```bash
# Watch the whole UI suite step through slowly
./scripts/test/integration-tests.sh tests/ui/sinopia --headed --slowmo 400

# Debug just the SSO login/logout flow, headed
./scripts/test/integration-tests.sh tests/ui/sinopia -k test_full_sso_login_and_logout --headed --slowmo 500
```

## ⚡ Dev Mode

Dev mode keeps the stack up between runs for fast iteration, and serves Sinopia
from local source so the authenticated flows run instead of skipping (see
[Dev Mode](integration-testing.md#-dev-mode-for-fast-reruns)):

```bash
./scripts/test/integration-tests.sh --dev-mode tests/ui/sinopia --headed
```
