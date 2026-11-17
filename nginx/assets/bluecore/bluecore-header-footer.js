// Blue Core header and footer, as custom elements, for every Blue Core app served from this
// host: the static pages (e.g. /marva-login/) and apps such as the DCTap Dancer.
//
//   <script src="/assets/bluecore/bluecore-header-footer.js"></script>   (in <head>, no defer)
//   <bluecore-header app-name="MARVA" current-app="marva"></bluecore-header>
//   <bluecore-footer></bluecore-footer>
//
// <bluecore-header> attributes:
//   app-name     the name after the logo
//   current-app  an id from APPS below, left out of the "Switch applications" menu
//   username     shows "Signed in as <username>"
//   logout       shows a Logout button, which fires a `bluecore-logout` event (bubbles) for
//                the app to handle, e.g. header.addEventListener('bluecore-logout', ...)
//   slim         compact one-row version that keeps more vertical space for editing
// <bluecore-footer> attributes:
//   slim         compact one-row version
//
// Changing an attribute re-renders the element. While shown, each element sets its height on
// :root as --bluecore-header-height / --bluecore-footer-height (borders included), so an app
// can size its full-height views to fit between them.
//
// The script also loads bluecore-header-footer.css (next to it). Loading it in <head> without
// defer lets the elements render as the page is parsed rather than popping in afterwards; an
// app can also add the script itself and create the elements once it has loaded.
(function () {
  if (customElements.get('bluecore-header')) return;

  var BASE = new URL('.', document.currentScript.src).href;

  var CONTACT_URL = 'mailto:contact@bluecore.info';

  var APPS = [
    { id: 'search', label: 'Search', href: '/api/search' },
    { id: 'marva', label: 'Marva', href: '/marva/' },
    { id: 'sinopia', label: 'Sinopia', href: '/sinopia/' },
    { id: 'toolbox', label: 'Graph Toolbox', href: '/toolbox/' },
    { id: 'api', label: 'API', href: '/api/docs' },
    { id: 'keycloak', label: 'Keycloak', href: '/keycloak/' },
    { id: 'workflows', label: 'Workflows', href: '/workflows/' },
  ];

  // Pixel heights (borders included) and logo widths, full and slim
  var SIZES = {
    full: { header: 57, footer: 157, headerLogo: 177, footerLogo: 163 },
    slim: { header: 23, footer: 23, headerLogo: 93, footerLogo: 70 },
  };

  // The logo's vector pieces: [file, top, right, bottom, left] insets in percent, from Figma
  var LOGO_PARTS = [
    ['icon-top', 0, 89.25, 50.01, 0],
    ['icon-middle', 25, 79.84, 25, 9.41],
    ['icon-bottom', 50.79, 89.25, 0, 0],
    ['blue-B', 18.73, 66.13, 20.51, 25.27],
    ['blue-l', 15.38, 62.52, 20.51, 36.41],
    ['blue-u', 34.33, 52.29, 19.67, 40.37],
    ['blue-e', 33.5, 42.1, 19.68, 49.9],
    ['core-C', 17.89, 26.74, 19.68, 62.87],
    ['core-o', 33.5, 16.31, 19.67, 74.67],
    ['core-r', 33.5, 9.37, 20.51, 85.54],
    ['core-e', 33.5, 0, 19.68, 91.46],
  ];

  // Load the stylesheet once, however many elements the page has
  if (!document.querySelector('link[data-bluecore-header-footer]')) {
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = BASE + 'bluecore-header-footer.css';
    link.setAttribute('data-bluecore-header-footer', '');
    document.head.appendChild(link);
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function logoHtml(width, extraClass) {
    var parts = LOGO_PARTS.map(function (p) {
      return '<span class="bluecore-logo-part" data-part="' + p[0] + '" style="top:' + p[1] + '%;right:' + p[2] +
        '%;bottom:' + p[3] + '%;left:' + p[4] + '%"><img src="' + BASE + 'logo/' + p[0] + '.svg" alt=""/></span>';
    }).join('');
    return '<span class="bluecore-logo' + (extraClass ? ' ' + extraClass : '') +
      '" role="img" aria-label="Blue Core" style="width:' + width + 'px">' + parts + '</span>';
  }

  function setRootHeight(name, px) {
    if (px === null) {
      document.documentElement.style.removeProperty(name);
    } else {
      document.documentElement.style.setProperty(name, px + 'px');
    }
  }

  // Shared by both elements: render on connect and on attribute changes, and keep the
  // :root height variable in step while the element is in the page.
  class BluecoreElement extends HTMLElement {
    connectedCallback() {
      this.render();
    }

    disconnectedCallback() {
      setRootHeight(this.heightVar, null);
    }

    attributeChangedCallback() {
      if (this.isConnected) this.render();
    }

    sizes() {
      return this.hasAttribute('slim') ? SIZES.slim : SIZES.full;
    }
  }

  class BluecoreHeader extends BluecoreElement {
    static get observedAttributes() {
      return ['app-name', 'current-app', 'username', 'logout', 'slim'];
    }

    constructor() {
      super();
      this.heightVar = '--bluecore-header-height';
      this.onDocumentClick = this.onDocumentClick.bind(this);
      this.onKeydown = this.onKeydown.bind(this);
    }

    connectedCallback() {
      super.connectedCallback();
      document.addEventListener('click', this.onDocumentClick);
      document.addEventListener('keydown', this.onKeydown);
    }

    disconnectedCallback() {
      super.disconnectedCallback();
      document.removeEventListener('click', this.onDocumentClick);
      document.removeEventListener('keydown', this.onKeydown);
    }

    render() {
      var sizes = this.sizes();
      var slim = this.hasAttribute('slim');
      var currentApp = this.getAttribute('current-app');
      var username = this.getAttribute('username');
      var menuItems = APPS.filter(function (app) { return app.id !== currentApp; }).map(function (app) {
        return '<li><a href="' + app.href + '">' + escapeHtml(app.label) + '</a></li>';
      }).join('');

      this.innerHTML =
        '<header class="bluecore-header' + (slim ? ' bluecore-header-slim' : '') + '" style="height:' + sizes.header + 'px">' +
          '<div class="bluecore-header-brand">' +
            logoHtml(sizes.headerLogo) +
            '<span class="bluecore-header-app-name"><span class="bluecore-header-divider" aria-hidden="true">|</span>' +
              escapeHtml(this.getAttribute('app-name') || '') + '</span>' +
          '</div>' +
          '<nav class="bluecore-header-links" aria-label="Blue Core">' +
            (username ? '<span class="bluecore-header-user">Signed in as <strong>' + escapeHtml(username) + '</strong></span>' : '') +
            '<a class="bluecore-link" href="' + CONTACT_URL + '">Contact</a>' +
            '<div class="bluecore-app-switcher">' +
              '<button type="button" class="bluecore-link bluecore-app-switcher-button" aria-haspopup="true"' +
                ' aria-expanded="false" aria-controls="bluecore-app-menu">Switch applications' +
                '<img class="bluecore-app-switcher-caret" src="' + BASE + 'caret-down.svg" alt=""/></button>' +
              '<ul id="bluecore-app-menu" class="bluecore-app-menu" hidden>' + menuItems + '</ul>' +
            '</div>' +
            (this.hasAttribute('logout') ? '<button type="button" class="bluecore-link bluecore-logout-button">Logout</button>' : '') +
          '</nav>' +
        '</header>';
      setRootHeight(this.heightVar, sizes.header);

      var self = this;
      this.querySelector('.bluecore-app-switcher-button').addEventListener('click', function () {
        self.setMenuOpen(self.querySelector('.bluecore-app-menu').hidden);
      });
      this.querySelector('.bluecore-app-menu').addEventListener('click', function (event) {
        if (event.target.closest('a')) self.setMenuOpen(false);
      });
      var logout = this.querySelector('.bluecore-logout-button');
      if (logout) {
        logout.addEventListener('click', function () {
          self.dispatchEvent(new CustomEvent('bluecore-logout', { bubbles: true }));
        });
      }
    }

    setMenuOpen(open) {
      var menu = this.querySelector('.bluecore-app-menu');
      if (!menu) return;
      menu.hidden = !open;
      this.querySelector('.bluecore-app-switcher-button').setAttribute('aria-expanded', open ? 'true' : 'false');
      this.querySelector('.bluecore-app-switcher-caret').classList.toggle('open', open);
    }

    menuOpen() {
      var menu = this.querySelector('.bluecore-app-menu');
      return Boolean(menu && !menu.hidden);
    }

    onDocumentClick(event) {
      var switcher = this.querySelector('.bluecore-app-switcher');
      if (this.menuOpen() && switcher && !switcher.contains(event.target)) this.setMenuOpen(false);
    }

    onKeydown(event) {
      if (event.key === 'Escape' && this.menuOpen()) {
        this.setMenuOpen(false);
        this.querySelector('.bluecore-app-switcher-button').focus();
      }
    }
  }

  class BluecoreFooter extends BluecoreElement {
    static get observedAttributes() {
      return ['slim'];
    }

    constructor() {
      super();
      this.heightVar = '--bluecore-footer-height';
    }

    render() {
      var sizes = this.sizes();
      var slim = this.hasAttribute('slim');
      var appLinks = APPS.map(function (app) {
        return '<li><a class="bluecore-link" href="' + app.href + '">' + escapeHtml(app.label) + '</a></li>';
      }).join('');

      this.innerHTML =
        '<footer class="bluecore-footer' + (slim ? ' bluecore-footer-slim' : '') + '" style="height:' + sizes.footer + 'px">' +
          logoHtml(sizes.footerLogo, 'bluecore-footer-logo') +
          '<a class="bluecore-footer-contact" href="' + CONTACT_URL + '">Contact us</a>' +
          '<div class="bluecore-footer-divider" aria-hidden="true"><img src="' + BASE + 'footer-divider.svg" alt=""/></div>' +
          '<nav class="bluecore-footer-apps" aria-labelledby="bluecore-footer-apps-heading">' +
            '<h2 id="bluecore-footer-apps-heading" class="bluecore-footer-apps-heading">APPLICATIONS</h2>' +
            '<ul class="bluecore-footer-app-list">' + appLinks + '</ul>' +
          '</nav>' +
        '</footer>';
      setRootHeight(this.heightVar, sizes.footer);
    }
  }

  customElements.define('bluecore-header', BluecoreHeader);
  customElements.define('bluecore-footer', BluecoreFooter);
})();
