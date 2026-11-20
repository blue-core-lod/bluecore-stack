// Shared Blue Core header and footer for every app.
//
//   <script src="/assets/bluecore/bluecore-header-footer.js"></script>   (in <head>, no defer)
//   <bluecore-header app-name="MARVA" current-app="marva"></bluecore-header>
//   <bluecore-footer></bluecore-footer>
//
// Two looks:
//   default          the apps (Marva, Dancer, Airflow): app name, Contact, app menu
//   variant="home"   the homepage: Applications / Community / About, Partners in the footer
// The logo always links to the homepage.
//
// <bluecore-header> attributes:
//   app-name      name shown after the logo
//   current-app   app to leave out of the "Switch applications" menu
//   username      shows "Signed in as <username>"
//   logout        shows Logout; clicking it fires a `bluecore-logout` event
//   slim          smaller one-row header
//   links         JSON [{label, href}]: extra links (app) or replaces the section links (home)
//   home-href     homepage URL (default "/")
//   variant       "home" for the homepage look
//   contact       home only: add the Contact link
//   app-switcher  home only: add the "Switch applications" menu
// <bluecore-footer> attributes:
//   slim          smaller one-row footer
//   home-href     homepage URL (default "/")
//   variant       "home" for the homepage look
//   sections      home only: JSON [{heading, links: [{label, href}]}] (default Partners, Community)
//
// The header (and the apps' footer) stick to the window. Each element keeps its height in
// --bluecore-header-height / --bluecore-footer-height so apps can fit between them.
// The matching CSS file is loaded automatically.
(function () {
  if (customElements.get('bluecore-header')) return;

  var BASE = new URL('.', document.currentScript.src).href;

  var CONTACT_URL = 'mailto:contact@bluecore.info';
  var HOME_URL = '/';

  var APPS = [
    { id: 'search', label: 'Search', href: '/api/search' },
    { id: 'marva', label: 'Marva', href: '/marva/' },
    { id: 'sinopia', label: 'Sinopia', href: '/sinopia/' },
    { id: 'toolbox', label: 'Graph Toolbox', href: '/toolbox/' },
    { id: 'api', label: 'API', href: '/api/docs' },
    { id: 'keycloak', label: 'Keycloak', href: '/keycloak/' },
    { id: 'workflows', label: 'Workflows', href: '/workflows/' },
  ];

  // homepage header links
  var NAV_SECTIONS = [
    { label: 'Applications', hash: '#applications' },
    { label: 'Community', hash: '#community' },
    { label: 'About', hash: '#about' },
  ];

  // homepage footer link columns
  var SECTIONS = [
    {
      heading: 'Partners',
      links: [
        { label: 'Cornell University Library', href: 'https://www.library.cornell.edu/' },
        { label: 'Stanford University Libraries', href: 'https://library.stanford.edu/' },
        { label: 'Library of Congress', href: 'https://www.loc.gov/' },
        { label: 'University of California Davis Library', href: 'https://library.ucdavis.edu/' },
        { label: 'University of Pennsylvania Library', href: 'https://www.library.upenn.edu/' },
      ],
    },
    {
      heading: 'Community',
      links: [
        { label: 'Publications', href: 'https://bluecore.info/publications' },
        { label: 'Presentations', href: 'https://bluecore.info/presentations' },
        { label: 'Events', href: 'https://bluecore.info/' },
      ],
    },
  ];

  // heights and logo widths (homepage heights are minimums)
  var SIZES = {
    full: { header: 57, footer: 157, headerLogo: 177, footerLogo: 163 },
    slim: { header: 23, footer: 23, headerLogo: 93, footerLogo: 70 },
    home: { header: 57, footer: 221, headerLogo: 177, footerLogo: 163 },
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

  // read a JSON list attribute (null if it isn't valid)
  function jsonArrayAttribute(element, name) {
    var raw = element.getAttribute(name);
    if (!raw) return null;
    try {
      var value = JSON.parse(raw);
      if (Array.isArray(value)) return value;
    } catch (e) {
      // reported below
    }
    console.warn('<' + element.localName + '>: ' + name + ' is not a JSON array');
    return null;
  }

  function isLink(link) {
    return Boolean(link) && typeof link.label === 'string' && typeof link.href === 'string';
  }

  // Links off this site open in a new tab
  function linkHtml(link, className) {
    var external = /^https?:\/\//.test(link.href) && new URL(link.href).origin !== window.location.origin;
    return '<a class="' + className + '" href="' + escapeHtml(link.href) + '"' +
      (external ? ' target="_blank" rel="noopener"' : '') + '>' + escapeHtml(link.label) + '</a>';
  }

  // logo, linking to the homepage
  function homeLogoHtml(element, width, extraClass) {
    var href = element.getAttribute('home-href') || HOME_URL;
    return '<a class="bluecore-home-link' + (extraClass ? ' ' + extraClass : '') + '" href="' + escapeHtml(href) +
      '" aria-label="Blue Core home">' + logoHtml(width) + '</a>';
  }

  function logoHtml(width, extraClass) {
    var parts = LOGO_PARTS.map(function (p) {
      return '<span class="bluecore-logo-part" data-part="' + p[0] + '" style="top:' + p[1] + '%;right:' + p[2] +
        '%;bottom:' + p[3] + '%;left:' + p[4] + '%"><img src="' + BASE + 'logo/' + p[0] + '.svg" alt=""/></span>';
    }).join('');
    return '<span class="bluecore-logo' + (extraClass ? ' ' + extraClass : '') +
      '" aria-hidden="true" style="width:' + width + 'px">' + parts + '</span>';
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
      // homepage header/footer get taller when they wrap; keep the height variable right
      if (window.ResizeObserver && !this.resizeObserver) {
        var self = this;
        this.resizeObserver = new ResizeObserver(function () { self.updateHeight(); });
        this.resizeObserver.observe(this);
      }
    }

    disconnectedCallback() {
      if (this.resizeObserver) {
        this.resizeObserver.disconnect();
        this.resizeObserver = null;
      }
      setRootHeight(this.heightVar, null);
    }

    updateHeight() {
      var bar = this.firstElementChild;
      if (bar && this.isConnected) setRootHeight(this.heightVar, Math.round(bar.getBoundingClientRect().height));
    }

    attributeChangedCallback() {
      if (this.isConnected) this.render();
    }

    isHome() {
      return this.getAttribute('variant') === 'home';
    }

    sizes() {
      if (this.hasAttribute('slim')) return SIZES.slim;
      return this.isHome() ? SIZES.home : SIZES.full;
    }

    // apps: fixed height; homepage: at least this tall
    heightStyle(px) {
      return (this.isHome() && !this.hasAttribute('slim') ? 'min-height:' : 'height:') + px + 'px';
    }
  }

  class BluecoreHeader extends BluecoreElement {
    static get observedAttributes() {
      return ['app-name', 'current-app', 'username', 'logout', 'slim', 'links', 'home-href', 'variant', 'contact',
        'app-switcher'];
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

    // the `links` attribute, or the homepage section links
    navLinks() {
      var links = jsonArrayAttribute(this, 'links');
      if (links) return links.filter(isLink);
      if (!this.isHome()) return [];
      var home = this.getAttribute('home-href') || HOME_URL;
      return NAV_SECTIONS.map(function (section) {
        return { label: section.label, href: home + section.hash };
      });
    }

    appSwitcherHtml() {
      var currentApp = this.getAttribute('current-app');
      var menuItems = APPS.filter(function (app) { return app.id !== currentApp; }).map(function (app) {
        return '<li><a href="' + app.href + '">' + escapeHtml(app.label) + '</a></li>';
      }).join('');
      return '<div class="bluecore-app-switcher">' +
        '<button type="button" class="bluecore-link bluecore-app-switcher-button" aria-haspopup="true"' +
          ' aria-expanded="false" aria-controls="bluecore-app-menu">Switch applications' +
          '<img class="bluecore-app-switcher-caret" src="' + BASE + 'caret-down.svg" alt=""/></button>' +
        '<ul id="bluecore-app-menu" class="bluecore-app-menu" hidden>' + menuItems + '</ul>' +
      '</div>';
    }

    render() {
      var sizes = this.sizes();
      var slim = this.hasAttribute('slim');
      var home = this.isHome();
      var appName = this.getAttribute('app-name');
      var username = this.getAttribute('username');
      var navLinks = this.navLinks().map(function (link) {
        return linkHtml(link, 'bluecore-link bluecore-header-nav-link');
      }).join('');
      // apps always get Contact and the app menu; the homepage only if asked
      var contact = !home || this.hasAttribute('contact');
      var appSwitcher = !home || this.hasAttribute('app-switcher');

      this.innerHTML =
        '<header class="bluecore-header' + (slim ? ' bluecore-header-slim' : '') + (home ? ' bluecore-header-home' : '') +
          '" style="' + this.heightStyle(sizes.header) + '">' +
          '<div class="bluecore-header-brand">' +
            homeLogoHtml(this, sizes.headerLogo) +
            (appName ? '<span class="bluecore-header-app-name"><span class="bluecore-header-divider" aria-hidden="true">|</span>' +
              escapeHtml(appName) + '</span>' : '') +
          '</div>' +
          '<nav class="bluecore-header-links" aria-label="Blue Core">' +
            (username ? '<span class="bluecore-header-user">Signed in as <strong>' + escapeHtml(username) + '</strong></span>' : '') +
            navLinks +
            (contact ? '<a class="bluecore-link" href="' + CONTACT_URL + '">Contact</a>' : '') +
            (appSwitcher ? this.appSwitcherHtml() : '') +
            (this.hasAttribute('logout') ? '<button type="button" class="bluecore-link bluecore-logout-button">Logout</button>' : '') +
          '</nav>' +
        '</header>';
      setRootHeight(this.heightVar, sizes.header);

      var self = this;
      var switcherButton = this.querySelector('.bluecore-app-switcher-button');
      if (switcherButton) {
        switcherButton.addEventListener('click', function () {
          self.setMenuOpen(self.querySelector('.bluecore-app-menu').hidden);
        });
        this.querySelector('.bluecore-app-menu').addEventListener('click', function (event) {
          if (event.target.closest('a')) self.setMenuOpen(false);
        });
      }
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
      return ['slim', 'home-href', 'variant', 'sections'];
    }

    constructor() {
      super();
      this.heightVar = '--bluecore-footer-height';
    }

    // the `sections` attribute, or the default columns
    sections() {
      var sections = jsonArrayAttribute(this, 'sections') || SECTIONS;
      return sections.filter(function (section) {
        return section && typeof section.heading === 'string' && Array.isArray(section.links);
      });
    }

    render() {
      var sizes = this.sizes();
      this.innerHTML = this.isHome() && !this.hasAttribute('slim') ? this.homeHtml(sizes) : this.appHtml(sizes);
      setRootHeight(this.heightVar, sizes.footer);
    }

    // logo, Contact us, then every Blue Core app
    appHtml(sizes) {
      var slim = this.hasAttribute('slim');
      var appLinks = APPS.map(function (app) {
        return '<li><a class="bluecore-link" href="' + app.href + '">' + escapeHtml(app.label) + '</a></li>';
      }).join('');
      return '<footer class="bluecore-footer' + (slim ? ' bluecore-footer-slim' : '') + '" style="' +
          this.heightStyle(sizes.footer) + '">' +
          homeLogoHtml(this, sizes.footerLogo, 'bluecore-footer-logo') +
          '<a class="bluecore-footer-contact" href="' + CONTACT_URL + '">Contact us</a>' +
          '<div class="bluecore-footer-divider" aria-hidden="true"><img src="' + BASE + 'footer-divider.svg" alt=""/></div>' +
          '<nav class="bluecore-footer-apps" aria-labelledby="bluecore-footer-apps-heading">' +
            '<h2 id="bluecore-footer-apps-heading" class="bluecore-footer-apps-heading">APPLICATIONS</h2>' +
            '<ul class="bluecore-footer-app-list">' + appLinks + '</ul>' +
          '</nav>' +
        '</footer>';
    }

    // homepage: logo, Contact us, then the link columns
    homeHtml(sizes) {
      var divider = '<div class="bluecore-footer-home-divider" aria-hidden="true"><img src="' + BASE +
        'home/footer-divider.svg" alt=""/></div>';
      var sectionsHtml = this.sections().map(function (section, index) {
        var id = 'bluecore-footer-section-' + index;
        var links = section.links.filter(isLink).map(function (link) {
          return '<li>' + linkHtml(link, 'bluecore-link') + '</li>';
        }).join('');
        return divider +
          '<nav class="bluecore-footer-section" aria-labelledby="' + id + '">' +
            '<h2 id="' + id + '" class="bluecore-footer-heading">' + escapeHtml(section.heading) + '</h2>' +
            '<ul class="bluecore-footer-links">' + links + '</ul>' +
          '</nav>';
      }).join('');
      return '<footer class="bluecore-footer bluecore-footer-home" style="' + this.heightStyle(sizes.footer) + '">' +
          '<div class="bluecore-footer-brand">' +
            homeLogoHtml(this, sizes.footerLogo, 'bluecore-footer-home-logo') +
            '<a class="bluecore-footer-home-contact" href="' + CONTACT_URL + '">Contact us</a>' +
          '</div>' +
          sectionsHtml +
        '</footer>';
    }
  }

  customElements.define('bluecore-header', BluecoreHeader);
  customElements.define('bluecore-footer', BluecoreFooter);
})();
