// ####################
// System health checks
// --------------------
async function checkGateway() {
  const badge = document.getElementById('gw-badge');
  if (!badge) return;

  const label = badge.querySelector('.label');

  const results = await Promise.allSettled([
    fetch('/health-check', { cache: 'no-store' }),
    fetch('/api/openapi.json', { cache: 'no-store' })
  ]);

  const okHealth = results[0].status === 'fulfilled' && results[0].value.ok;
  const okApi    = results[1].status === 'fulfilled' && results[1].value.ok;

  badge.classList.remove('status-ok','status-warn','status-down');

  if (okHealth && okApi) {
    badge.classList.add('status-ok');
    label.textContent = 'Gateway reachable (API OK)';
  } else if (okHealth || okApi) {
    badge.classList.add('status-warn');
    label.textContent = okHealth ? 'Gateway OK, API unreachable' : 'API OK, gateway unhealthy';
  } else {
    badge.classList.add('status-down');
    label.textContent = 'Gateway unreachable';
  }
}

// #############################################################################
// Per-service availability: grey out rows whose service isn't running.
// Each row carries data-probe="/route". With the dev Nginx config, a route whose
// upstream is down returns 502/503/504 (or the fetch fails), so treat as offline.
// #############################################################################
// Fetch a probe URL: is the service up, and does it advertise a version?
async function probe(url) {
  try {
    const res = await fetch(url, { method: 'GET', redirect: 'manual', cache: 'no-store' });
    const up = !(res.status === 502 || res.status === 503 || res.status === 504);

    // A JSON payload may advertise the service version, e.g. {"version": "1.2.3"}
    const contentType = res.headers.get('content-type') || '';
    if (up && contentType.includes('application/json')) {
      try {
        const payload = await res.json();
        return { up, version: (payload && payload.version) || null };
      } catch (e) {
        // not valid JSON after all
      }
    }
    return { up, version: null };
  } catch (e) {
    return { up: false, version: null }; // connection failed
  }
}

// A row can also show a second service's version, e.g. Marva's row shows
// DCTap Dancer's: data-extra-version-probe="/route" data-extra-version-label="…".
// Only the main probe decides whether the row is available.
async function probeRow(row) {
  const extraUrl = row.getAttribute('data-extra-version-probe');
  const [main, extra] = await Promise.all([
    probe(row.getAttribute('data-probe')),
    extraUrl ? probe(extraUrl) : Promise.resolve(null)
  ]);
  row.classList.toggle('unavailable', !main.up);
  row.setAttribute('aria-disabled', String(!main.up));

  const parts = [];
  if (main.version) parts.push(`Version: ${main.version}`);
  if (main.up && extra && extra.version) {
    parts.push(`${row.getAttribute('data-extra-version-label') || 'Version'}: ${extra.version}`);
  }
  const versionEl = row.querySelector('.version');
  if (versionEl) versionEl.textContent = parts.join(', ');
}

function checkServices() {
  document.querySelectorAll('.row[data-probe]').forEach(probeRow);
}

document.addEventListener('DOMContentLoaded', () => {
  checkGateway();
  checkServices();
  setInterval(checkGateway, 60000);  // gateway badge: every minute
  setInterval(checkServices, 10000); // service rows: every 10s (light up as they boot)
});
