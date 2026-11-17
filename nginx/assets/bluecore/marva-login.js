// Skip the Marva login page when the user is already signed in to Marva.
//
// Marva keeps its access token in localStorage (marva_jwt), on this same origin. When there is
// one, ask Keycloak whether its session is still alive (the same login-status iframe check
// Marva runs, see marva_editor src/bluecore/sso.js):
//   - session alive: go straight to Marva. If the token itself has expired, Marva sends the
//     browser through Keycloak, which signs the user back in without asking for a password.
//   - session ended (e.g. logged out of Sinopia): show this page.
//   - Keycloak can't be asked: trust the token's expiry time.
// The inline script in the page's <head> hides the page while this runs, so it doesn't flash.
(function () {
  var MARVA_URL = '/marva/';
  var TOKEN_KEY = 'marva_jwt';
  var SESSION_CHECK_TIMEOUT_MS = 3000;

  function decodeJwt(token) {
    try {
      return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch (e) {
      return null;
    }
  }

  function isUnexpired(claims) {
    return !claims.exp || claims.exp * 1000 > Date.now();
  }

  function showPage() {
    document.documentElement.classList.remove('bluecore-checking-session');
  }

  function goToMarva() {
    window.location.replace(MARVA_URL);
  }

  // Calls done('unchanged') when the Keycloak session is alive, 'changed' when it ended,
  // or 'unknown' when Keycloak can't say.
  function checkKeycloakSession(claims, done) {
    var kcOrigin;
    try {
      kcOrigin = new URL(claims.iss).origin;
    } catch (e) {
      done('unknown');
      return;
    }
    var iframe = document.createElement('iframe');
    var finished = false;
    var timer = null;

    function finish(state) {
      if (finished) return;
      finished = true;
      window.clearTimeout(timer);
      window.removeEventListener('message', onMessage);
      iframe.remove();
      done(state);
    }

    function onMessage(event) {
      if (event.origin !== kcOrigin || event.source !== iframe.contentWindow) return;
      if (event.data === 'unchanged' || event.data === 'changed') {
        finish(event.data);
      } else {
        finish('unknown');
      }
    }

    window.addEventListener('message', onMessage);
    iframe.title = 'keycloak-session-iframe';
    iframe.style.display = 'none';
    iframe.src = claims.iss + '/protocol/openid-connect/login-status-iframe.html';
    iframe.addEventListener('load', function () {
      iframe.contentWindow.postMessage(claims.azp + ' ' + claims.sid, kcOrigin);
    });
    timer = window.setTimeout(function () {
      finish('unknown');
    }, SESSION_CHECK_TIMEOUT_MS);
    document.body.appendChild(iframe);
  }

  var token = null;
  try {
    token = window.localStorage.getItem(TOKEN_KEY);
  } catch (e) {
    // storage blocked: treat as signed out
  }
  var claims = token ? decodeJwt(token) : null;

  if (!claims) {
    showPage();
  } else if (claims.iss && claims.azp && claims.sid) {
    checkKeycloakSession(claims, function (state) {
      if (state === 'unchanged' || (state === 'unknown' && isUnexpired(claims))) {
        goToMarva();
      } else {
        showPage();
      }
    });
  } else if (isUnexpired(claims)) {
    goToMarva();
  } else {
    showPage();
  }
})();
