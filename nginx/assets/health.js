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
async function probeRow(row) {
  const url = row.getAttribute('data-probe');
  let up = false;
  let version = null;
  try {
    const res = await fetch(url, { method: 'GET', redirect: 'manual', cache: 'no-store' });
    up = !(res.status === 502 || res.status === 503 || res.status === 504);

    // A JSON payload may advertise the service version, e.g. {"version": "1.2.3"}
    const contentType = res.headers.get('content-type') || '';
    if (up && contentType.includes('application/json')) {
      try {
        const payload = await res.json();
        if (payload && payload.version) version = payload.version;
        console.log(`Version: ${version}`)
      } catch (e) {
        version = null; // not valid JSON after all
      }
    }
  } catch (e) {
    up = false; // connection failed
  }
  row.classList.toggle('unavailable', !up);
  row.setAttribute('aria-disabled', String(!up));

  const versionEl = row.querySelector('.version');
  if (versionEl) versionEl.innerHTML = version ? `Version: ${version}` : '';
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
