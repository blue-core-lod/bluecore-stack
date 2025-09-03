// ####################
// System health checks
// --------------------
async function checkOnce() {
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

document.addEventListener('DOMContentLoaded', () => {
  checkOnce();
  setInterval(checkOnce, 60000); // refresh every minute
});
