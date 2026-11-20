// Homepage login panel: log in, reset a password, or show "Welcome back" if already logged in.
//
// The apps each do their own Keycloak login. Logging in here starts a Keycloak session, so the
// apps then let the user straight in without asking again.
//
// - On load: ask Keycloak (silently) if the user is logged in; show "Welcome back" or the form.
// - Login: send the username and password to Keycloak's login form, then open the chosen app.
// - Forgot password: send the username to Keycloak's own reset form; Keycloak sends the email.
// - Logout: end the Keycloak session (logs out of every app).
//
// Settings on <div id="home-login">:
//   data-keycloak-realm   Keycloak realm path, e.g. /keycloak/realms/bluecore
//   data-client-id        Keycloak client, e.g. bluecore_api
//   data-redirect-path    allowed redirect (and logout redirect) path for that client
(function () {
  var panel = document.getElementById('home-login');
  if (!panel) return;

  var REALM = panel.dataset.keycloakRealm;
  var CLIENT_ID = panel.dataset.clientId;
  var REDIRECT_URI = new URL(panel.dataset.redirectPath, window.location.origin).href;
  var SESSION_CHECK_TIMEOUT_MS = 4000;

  var header = document.querySelector('bluecore-header');

  var loginForm = document.getElementById('home-login-form');
  var username = loginForm.elements.username;
  var password = loginForm.elements.password;
  var loginApp = loginForm.elements.app;
  var loginSubmit = loginForm.querySelector('.home-login-submit');
  var loginError = loginForm.querySelector('.home-login-error');
  var reveal = loginForm.querySelector('.home-login-reveal');

  var resetForm = document.getElementById('home-reset-form');
  var resetUsername = resetForm.elements.username;
  var resetSubmit = resetForm.querySelector('.home-reset-submit');
  var resetMessage = resetForm.querySelector('.home-reset-message');

  var signedIn = document.getElementById('home-signed-in');

  var GENERIC_ERROR = 'Sign-in failed. Please try again.';
  var RESET_UNAVAILABLE = 'Password reset isn’t available right now. Please contact us at contact@bluecore.info.';

  // needed to log out
  var idToken = null;

  // ---------------------------------------------------------------------------------------
  // Keycloak
  // ---------------------------------------------------------------------------------------

  function randomString() {
    var bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    return Array.prototype.map.call(bytes, function (b) {
      return b.toString(16).padStart(2, '0');
    }).join('');
  }

  function base64Url(bytes) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(bytes)))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  // PKCE codes (secures the silent login check)
  function makePkce() {
    var verifier = randomString();
    if (!window.crypto.subtle) return Promise.resolve({ verifier: verifier, challenge: verifier, method: 'plain' });
    return window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)).then(function (digest) {
      return { verifier: verifier, challenge: base64Url(digest), method: 'S256' };
    });
  }

  function authorizationUrl(extra) {
    var params = new URLSearchParams(Object.assign({
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      response_type: 'code',
      scope: 'openid',
      state: randomString(),
      nonce: randomString(),
    }, extra || {}));
    return REALM + '/protocol/openid-connect/auth?' + params.toString();
  }

  // Keycloak's reply params, if it redirected back to us
  function redirectParams(response) {
    var url = new URL(response.url);
    var redirect = new URL(REDIRECT_URI);
    if (url.origin !== redirect.origin || url.pathname.indexOf(redirect.pathname) !== 0) return null;
    if (!url.searchParams.has('code') && !url.searchParams.has('error')) return null;
    return url.searchParams;
  }

  function reachedRedirectWithCode(response) {
    var params = redirectParams(response);
    return Boolean(params && params.has('code'));
  }

  function parseHtml(text) {
    return new DOMParser().parseFromString(text, 'text/html');
  }

  // only trust URLs on this site
  function sameOriginUrl(href) {
    if (!href) return null;
    var url = new URL(href, window.location.origin);
    return url.origin === window.location.origin ? url.href : null;
  }

  // where Keycloak's login form posts to, and its "Forgot password" link
  function loginFormOf(doc) {
    var kcForm = doc.querySelector('#kc-form-login');
    var action = kcForm && sameOriginUrl(kcForm.getAttribute('action'));
    if (!action) return null;
    var reset = doc.querySelector('#kc-forgot-password a, a[href*="reset-credentials"]');
    return { action: action, resetUrl: reset ? sameOriginUrl(reset.getAttribute('href')) : null };
  }

  // the message on a Keycloak page, and whether it's an error
  function messageOf(doc) {
    var el = doc.querySelector('#input-error, #input-error-username, .kc-feedback-text, .alert-error, .pf-m-danger');
    if (!el) return null;
    var alert = el.closest('[class*="alert"]') || el;
    var kind = /success|info/.test(alert.className) ? 'ok' : 'error';
    if (/^input-error/.test(el.id)) kind = 'error';
    return { text: el.textContent.trim(), kind: kind };
  }

  function post(url, fields) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(fields),
    });
  }

  // open Keycloak's login page; { signedIn: true } if already logged in
  function openLoginPage() {
    return fetch(authorizationUrl(), { credentials: 'same-origin', cache: 'no-store' }).then(function (response) {
      if (reachedRedirectWithCode(response)) return { signedIn: true };
      if (!response.ok) throw new Error('Keycloak answered ' + response.status);
      return response.text().then(function (html) {
        var form = loginFormOf(parseHtml(html));
        if (!form) throw new Error('No Keycloak login form');
        return { form: form };
      });
    });
  }

  function decodeJwt(token) {
    try {
      var json = atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'));
      return JSON.parse(decodeURIComponent(Array.prototype.map.call(json, function (c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join('')));
    } catch (e) {
      return null;
    }
  }

  // the logged-in user, or null
  function checkSession() {
    var state = randomString();
    return makePkce().then(function (pkce) {
      var url = authorizationUrl({
        prompt: 'none',
        state: state,
        code_challenge: pkce.challenge,
        code_challenge_method: pkce.method,
      });
      return fetch(url, { credentials: 'same-origin', cache: 'no-store' }).then(function (response) {
        var params = redirectParams(response);
        if (!params || !params.has('code') || params.get('state') !== state) return null;
        return post(REALM + '/protocol/openid-connect/token', {
          grant_type: 'authorization_code',
          client_id: CLIENT_ID,
          code: params.get('code'),
          redirect_uri: REDIRECT_URI,
          code_verifier: pkce.verifier,
        }).then(function (tokenResponse) {
          if (!tokenResponse.ok) return null;
          return tokenResponse.json().then(function (tokens) {
            var claims = tokens.id_token && decodeJwt(tokens.id_token);
            if (!claims) return null;
            return {
              username: claims.preferred_username || claims.email || claims.sub,
              firstName: claims.given_name || '',
              idToken: tokens.id_token,
            };
          });
        });
      });
    });
  }

  function withTimeout(promise, ms) {
    return Promise.race([
      promise,
      new Promise(function (resolve) { window.setTimeout(function () { resolve(null); }, ms); }),
    ]);
  }

  // ---------------------------------------------------------------------------------------
  // Panel views
  // ---------------------------------------------------------------------------------------

  function showView(view) {
    [loginForm, resetForm, signedIn].forEach(function (el) {
      el.hidden = el !== view;
    });
  }

  function showSignedIn(user) {
    idToken = user.idToken;
    signedIn.querySelector('.home-signed-in-name').textContent = ', ' + (user.firstName || user.username);
    if (header) {
      header.setAttribute('logout', '');
    }
    showView(signedIn);
  }

  function showSignedOut() {
    idToken = null;
    if (header) {
      header.removeAttribute('logout');
    }
    showView(loginForm);
  }

  function goTo(url) {
    window.location.assign(url);
  }

  // ---------------------------------------------------------------------------------------
  // Login form
  // ---------------------------------------------------------------------------------------

  reveal.addEventListener('click', function () {
    var show = password.type === 'password';
    password.type = show ? 'text' : 'password';
    reveal.setAttribute('aria-pressed', String(show));
    reveal.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });

  function showLoginError(message) {
    loginError.textContent = message;
    loginError.hidden = false;
  }

  function clearLoginError() {
    loginError.textContent = '';
    loginError.hidden = true;
    username.removeAttribute('aria-invalid');
    password.removeAttribute('aria-invalid');
  }

  function setBusy(button, busy, busyText, text) {
    button.disabled = busy;
    button.setAttribute('aria-busy', String(busy));
    button.textContent = busy ? busyText : text;
  }

  function login(event) {
    event.preventDefault();
    clearLoginError();

    if (!username.value.trim() || !password.value) {
      if (!username.value.trim()) username.setAttribute('aria-invalid', 'true');
      if (!password.value) password.setAttribute('aria-invalid', 'true');
      showLoginError('Enter your username and password.');
      (username.value.trim() ? password : username).focus();
      return;
    }

    var appUrl = loginApp.value;
    setBusy(loginSubmit, true, 'Logging in…', 'Login');

    openLoginPage()
      .then(function (page) {
        if (page.signedIn) return 'signed-in'; // already logged in
        return post(page.form.action, {
          username: username.value.trim(),
          password: password.value,
          credentialId: '',
        });
      })
      .then(function (result) {
        if (result === 'signed-in' || reachedRedirectWithCode(result)) return goTo(appUrl);
        return result.text().then(function (html) {
          var doc = parseHtml(html);
          if (loginFormOf(doc)) {
            // wrong username or password
            var message = messageOf(doc);
            setBusy(loginSubmit, false, '', 'Login');
            password.value = '';
            password.setAttribute('aria-invalid', 'true');
            showLoginError((message && message.text) || 'Invalid username or password.');
            password.focus();
            return;
          }
          // Keycloak needs more (e.g. a new password): finish on Keycloak's page
          goTo(result.url);
        });
      })
      .catch(function (error) {
        console.warn('Blue Core homepage login: going through the app instead', error);
        setBusy(loginSubmit, false, '', 'Login');
        if (error instanceof TypeError) {
          showLoginError(GENERIC_ERROR);
        } else {
          goTo(appUrl);
        }
      });
  }

  loginForm.addEventListener('submit', login);

  // ---------------------------------------------------------------------------------------
  // Forgot password
  // ---------------------------------------------------------------------------------------

  function showResetMessage(text, isError) {
    resetMessage.textContent = text;
    resetMessage.classList.toggle('is-error', Boolean(isError));
    resetMessage.hidden = false;
  }

  loginForm.querySelector('.home-login-forgot').addEventListener('click', function () {
    resetUsername.value = username.value.trim();
    resetMessage.hidden = true;
    resetUsername.removeAttribute('aria-invalid');
    showView(resetForm);
    resetUsername.focus();
  });

  resetForm.querySelector('.home-login-back').addEventListener('click', function () {
    showView(loginForm);
    username.focus();
  });

  function requestReset(event) {
    event.preventDefault();
    resetMessage.hidden = true;
    resetUsername.removeAttribute('aria-invalid');
    var who = resetUsername.value.trim();
    if (!who) {
      resetUsername.setAttribute('aria-invalid', 'true');
      showResetMessage('Enter your username or e-mail address.', true);
      resetUsername.focus();
      return;
    }

    setBusy(resetSubmit, true, 'Sending…', 'Send reset link');
    openLoginPage()
      .then(function (page) {
        if (page.signedIn) return { signedIn: true };
        if (!page.form.resetUrl) throw new Error('Keycloak has no "Forgot password" link');
        return fetch(page.form.resetUrl, { credentials: 'same-origin', cache: 'no-store' })
          .then(function (response) { return response.text(); })
          .then(function (html) {
            var resetDoc = parseHtml(html);
            var kcForm = resetDoc.querySelector('#kc-reset-password-form');
            var action = kcForm && sameOriginUrl(kcForm.getAttribute('action'));
            if (!action) throw new Error('No Keycloak reset password form');
            return post(action, { username: who });
          })
          .then(function (response) { return response.text(); })
          .then(function (html) { return { message: messageOf(parseHtml(html)) }; });
      })
      .then(function (result) {
        setBusy(resetSubmit, false, '', 'Send reset link');
        if (result.signedIn) {
          // logged in from another tab meanwhile
          return start();
        }
        var message = result.message;
        if (!message) {
          showResetMessage(RESET_UNAVAILABLE, true);
        } else if (message.kind === 'ok') {
          showResetMessage(message.text, false);
        } else {
          resetUsername.setAttribute('aria-invalid', 'true');
          showResetMessage(message.text, true);
        }
      })
      .catch(function (error) {
        console.warn('Blue Core homepage password reset failed', error);
        setBusy(resetSubmit, false, '', 'Send reset link');
        showResetMessage(RESET_UNAVAILABLE, true);
      });
  }

  resetForm.addEventListener('submit', requestReset);

  // ---------------------------------------------------------------------------------------
  // Welcome back
  // ---------------------------------------------------------------------------------------

  function logout() {
    var params = new URLSearchParams({ client_id: CLIENT_ID, post_logout_redirect_uri: REDIRECT_URI });
    if (idToken) params.set('id_token_hint', idToken);
    var logoutUrl = REALM + '/protocol/openid-connect/logout?' + params.toString();
    fetch(logoutUrl, { credentials: 'same-origin', cache: 'no-store' })
      .then(checkSession)
      .then(function (user) {
        if (user) {
          // Keycloak wants to confirm the logout
          goTo(logoutUrl);
          return;
        }
        showSignedOut();
        username.focus();
      })
      .catch(function () {
        goTo(logoutUrl);
      });
  }

  signedIn.querySelector('.home-signed-in-logout').addEventListener('click', logout);
  if (header) header.addEventListener('bluecore-logout', logout);

  // ---------------------------------------------------------------------------------------
  // Start
  // ---------------------------------------------------------------------------------------

  function start() {
    panel.setAttribute('aria-busy', 'true');
    return withTimeout(checkSession().catch(function () { return null; }), SESSION_CHECK_TIMEOUT_MS)
      .then(function (user) {
        if (user) {
          showSignedIn(user);
        } else {
          showSignedOut();
        }
        panel.removeAttribute('aria-busy');
      });
  }

  start();
})();
