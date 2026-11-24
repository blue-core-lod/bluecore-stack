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

  // The same pieces' SVG code. It lives in this script so the whole logo draws at once.
  var LOGO_SVGS = {
    'icon-top': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 19.0385 19.032" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M9.39398 19.032C10.2075 19.0255 10.9461 18.9409 11.6261 18.7977C13.4255 18.391 15.033 17.4734 16.2857 16.2076L8.62932 11.7856C7.35054 11.047 6.84618 9.52739 7.50347 8.38853C8.16076 7.24967 9.72913 6.92428 11.0079 7.66291L18.6838 12.0947C18.9149 11.2747 19.0385 10.4124 19.0385 9.51763C19.0353 4.2626 14.7727 0 9.51763 0C4.2626 0 0 4.2626 0 9.51763C0 14.7727 4.19426 18.9669 9.39398 19.032Z" fill="#003CAF"/></svg>',
    'icon-middle': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 19.0353 19.0353" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M9.51763 0C4.2626 0 0 4.2626 0 9.51763C0 10.3799 0.11714 11.2162 0.331897 12.0134L7.95901 7.60759C9.23779 6.87221 10.8062 7.19435 11.4635 8.33321C12.1207 9.47207 11.6164 10.9916 10.3376 11.7303L2.69097 16.1458C4.42204 17.9257 6.83968 19.0353 9.51763 19.0353C14.7727 19.0353 19.0353 14.7727 19.0353 9.51763C19.0353 4.2626 14.7727 0 9.51763 0Z" fill="#003CAF"/></svg>',
    'icon-bottom': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 19.0353 18.7359" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M11.8962 0V8.92542C11.8962 10.3994 10.8322 11.5969 9.51763 11.5969C8.20306 11.5969 7.13903 10.4027 7.13903 8.92542V0C3.03263 1.05751 0 4.78322 0 9.21827C0 14.4733 4.2626 18.7359 9.51763 18.7359C14.7727 18.7359 19.0353 14.4733 19.0353 9.21827C19.0353 4.78322 16.0026 1.05751 11.8962 0Z" fill="#003CAF"/></svg>',
    'blue-B': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 15.2217 23.1319" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M10.7411 11.0795C11.8734 10.6988 12.7683 10.0643 13.419 9.17922C14.0698 8.29416 14.3952 7.25292 14.3952 6.05549C14.3952 4.06411 13.7542 2.5543 12.4722 1.53258C11.1901 0.510861 9.30938 0 6.83317 0H0V23.1319H7.73775C10.0903 23.1319 11.9255 22.5592 13.2433 21.4106C14.5612 20.262 15.2217 18.6676 15.2217 16.6241C15.2217 15.2803 14.8117 14.0926 13.9917 13.0676C13.1717 12.0394 12.0882 11.3789 10.7411 11.0827V11.0795ZM1.95559 1.64972H6.83317C8.70741 1.64972 10.1098 2.00114 11.0372 2.70724C11.9646 3.41333 12.4266 4.50989 12.4266 5.99367C12.4266 7.47744 11.9776 8.47964 11.0827 9.21827C10.1879 9.9569 8.92542 10.3409 7.29197 10.3734H1.95233V1.64972H1.95559ZM11.7986 20.2034C10.8192 21.0559 9.4916 21.4789 7.8191 21.4789H1.95559V12.0264H7.97854C9.63151 12.0264 10.9266 12.4429 11.8637 13.2726C12.8008 14.1024 13.2694 15.2315 13.2694 16.6599C13.2694 18.173 12.778 19.3541 11.7986 20.2034Z" fill="#003CAF"/></svg>',
    'blue-l': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 1.90678 24.4042" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M1.90678 0H0V24.4042H1.90678V0Z" fill="#003CAF"/></svg>',
    'blue-u': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 12.996 17.5124" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M11.0893 12.4396C10.3571 14.7173 8.6163 15.8562 5.86351 15.8562C3.11072 15.8562 1.89051 14.2195 1.89051 10.9461V0H0V11.1869C0.0195233 13.2726 0.507609 14.8475 1.461 15.9148C2.41439 16.9821 3.80705 17.5124 5.63899 17.5124C8.14774 17.5124 9.97643 16.6827 11.1218 15.0167L11.1543 17.1936H12.996V0.00325458H11.0893V12.4429V12.4396Z" fill="#003CAF"/></svg>',
    'blue-e': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 14.1577 17.8248" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M7.35705 0C6.02295 0 4.78323 0.377452 3.63786 1.13561C2.49249 1.89376 1.60092 2.93501 0.959901 4.25609C0.318885 5.58042 0 7.06745 0 8.72042V9.40374C0 11.0047 0.328642 12.4461 0.985928 13.7347C1.64321 15.0232 2.56081 16.0254 3.74197 16.7445C4.92313 17.4636 6.24422 17.8248 7.70522 17.8248C10.3636 17.8248 12.3908 16.8128 13.79 14.7889L12.5991 13.8843C11.9646 14.7011 11.2552 15.2933 10.4775 15.6642C9.69985 16.0352 8.80177 16.2206 7.78331 16.2206C6.08803 16.2206 4.68235 15.5731 3.56627 14.2748C2.44693 12.9765 1.89051 11.3528 1.89051 9.40374V9.03931H14.1577V7.97528C14.1577 5.50884 13.5459 3.55976 12.3225 2.13781C11.099 0.712602 9.44279 0 7.35705 0ZM12.2639 7.41887H1.95233C2.16384 5.64875 2.75931 4.23982 3.73873 3.19207C4.71815 2.14431 5.92208 1.62044 7.35379 1.62044C8.7855 1.62044 9.96015 2.14106 10.8485 3.17905C11.7368 4.21704 12.2086 5.5609 12.2639 7.21387V7.41887Z" fill="#003CAF"/></svg>',
    'core-C': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 18.3845 23.7697" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M5.47629 5.15741C6.41341 3.87864 7.75727 3.24087 9.50461 3.24087C11.0079 3.24087 12.15 3.60856 12.9277 4.34394C13.7054 5.07932 14.1902 6.28001 14.3822 7.94274H18.3845C18.1307 5.41122 17.2261 3.45563 15.6675 2.07273C14.1089 0.689824 12.0557 0 9.50135 0C7.60433 0 5.93509 0.449037 4.48711 1.35036C3.04238 2.25169 1.93281 3.53372 1.15838 5.19646C0.383958 6.8592 0 8.78225 0 10.9624V13.1229C0.0325389 15.251 0.429515 17.122 1.19092 18.7326C1.95233 20.3433 3.03588 21.583 4.44156 22.4583C5.84398 23.3336 7.46767 23.7697 9.31263 23.7697C11.9515 23.7697 14.0633 23.0798 15.6512 21.6969C17.2391 20.314 18.1502 18.391 18.3845 15.9213H14.3822C14.1707 17.5743 13.6663 18.7554 12.8724 19.4648C12.0784 20.1741 10.8908 20.5288 9.31263 20.5288C7.58481 20.5288 6.27675 19.8715 5.38193 18.5569C4.48711 17.2424 4.03808 15.3323 4.03808 12.8333V10.7834C4.06085 8.31369 4.53917 6.43945 5.47629 5.16067V5.15741Z" fill="#003CAF"/></svg>',
    'core-o': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 15.9831 17.8281" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M13.624 2.23868C12.1793 0.745141 10.2953 0 7.97529 0C6.40691 0 5.02075 0.364436 3.81356 1.0868C2.60637 1.81242 1.66925 2.85041 1.0022 4.20077C0.335156 5.55114 0 7.06745 0 8.75296V8.94494C0 11.6359 0.728878 13.7867 2.18337 15.4039C3.64111 17.0178 5.58043 17.8281 8.00783 17.8281C9.59573 17.8281 10.9981 17.4636 12.2118 16.7315C13.4255 15.9994 14.3562 14.9679 15.0069 13.6338C15.6577 12.2997 15.9831 10.7834 15.9831 9.09137L15.9668 8.18679C15.8497 5.72034 15.0688 3.73872 13.624 2.24518V2.23868ZM11.0502 13.2173C10.3246 14.2325 9.30938 14.7434 8.00783 14.7434C6.70627 14.7434 5.6878 14.2423 4.95568 13.2433C4.22355 12.2444 3.85912 10.8582 3.85912 9.08811C3.85912 7.09673 4.23006 5.59994 4.97194 4.601C5.71383 3.60206 6.71278 3.10096 7.97529 3.10096C9.23779 3.10096 10.2725 3.60856 11.0177 4.62703C11.7628 5.6455 12.137 7.02189 12.137 8.75947C12.137 10.7183 11.7726 12.2086 11.0502 13.2238V13.2173Z" fill="#003CAF"/></svg>',
    'core-r': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 9.02629 17.5059" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M3.78102 2.23868L3.68665 0.315626H0V17.5059H3.86237V5.74962C4.47735 4.39275 5.66827 3.71594 7.43839 3.71594C7.97853 3.71594 8.50241 3.75824 9.01002 3.84284L9.02629 0.221265C8.6651 0.0715857 8.20957 0 7.65966 0C6.00668 0 4.71489 0.745141 3.78428 2.23868H3.78102Z" fill="#003CAF"/></svg>',
    'core-e': '<svg style="position:absolute;inset:0;display:block;width:100%;height:100%" viewBox="0 0 15.1273 17.8248" preserveAspectRatio="none" overflow="visible" fill="none"><path d="M15.1208 8.57725C15.1208 5.84399 14.4831 3.73221 13.2075 2.23868C11.932 0.745141 10.1229 0 7.78332 0C6.30931 0 4.97521 0.37745 3.78103 1.1291C2.5836 1.88075 1.65298 2.93175 0.992442 4.28212C0.328649 5.63248 0 7.16506 0 8.88312V9.35819C0 11.9223 0.758159 13.9722 2.28098 15.5145C3.80055 17.0569 5.78541 17.8248 8.23234 17.8248C9.66079 17.8248 10.9526 17.5417 12.1012 16.9755C13.2498 16.4094 14.1707 15.6122 14.8573 14.5839L12.7748 12.5991C11.6619 14.0275 10.2205 14.7434 8.45362 14.7434C7.19436 14.7434 6.14661 14.3301 5.31686 13.5036C4.48387 12.6772 4.01205 11.5546 3.89491 10.1359H15.1273V8.57725H15.1208ZM11.3073 7.30498H3.95023C4.12919 5.98065 4.54569 4.94917 5.19647 4.20728C5.84725 3.46539 6.70301 3.09445 7.76378 3.09445C8.82454 3.09445 9.67056 3.42635 10.2725 4.08688C10.8778 4.75068 11.2194 5.72685 11.304 7.01864V7.30498H11.3073Z" fill="#003CAF"/></svg>',
  };

  // The footers' dotted dividers, kept here like the logo so they don't pop in.
  var FOOTER_DIVIDER_SVG = '<svg width="58" height="1" viewBox="0 0 58 1" fill="none" style="display:block"><path d="M0 0.5H0.966667M58 0.5H57.0333M2.9 0.5H4.83333M6.76667 0.5H8.7M10.6333 0.5H12.5667M14.5 0.5H16.4333M18.3667 0.5H20.3M22.2333 0.5H24.1667M26.1 0.5H28.0333M29.9667 0.5H31.9M33.8333 0.5H35.7667M37.7 0.5H39.6333M41.5667 0.5H43.5M45.4333 0.5H47.3667M49.3 0.5H51.2333M53.1667 0.5H55.1" stroke="#003CAF"/></svg>';
  var HOME_FOOTER_DIVIDER_SVG = '<svg width="120" height="1" viewBox="0 0 120 1" fill="none" style="display:block"><path d="M0 0.5H1M120 0.5H119M3 0.5H5M7 0.5H9M11 0.5H13M15 0.5H17M19 0.5H21M23 0.5H25M27 0.5H29M31 0.5H33M35 0.5H37M39 0.5H41M43 0.5H45M47 0.5H49M51 0.5H53M55 0.5H57M59 0.5H61M63 0.5H65M67 0.5H69M71 0.5H73M75 0.5H77M79 0.5H81M83 0.5H85M87 0.5H89M91 0.5H93M95 0.5H97M99 0.5H101M103 0.5H105M107 0.5H109M111 0.5H113M115 0.5H117" stroke="#003CAF"/></svg>';

  // Load the stylesheet once, however many elements the page has
  // The header and footer stay invisible (but keep their space) until it loads,
  // so they don't flash unstyled or change size as the page loads.
  if (!document.querySelector('link[data-bluecore-header-footer]')) {
    var hide = document.createElement('style');
    hide.textContent = 'bluecore-header,bluecore-footer{visibility:hidden}';
    var show = function () { hide.remove(); };
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = BASE + 'bluecore-header-footer.css';
    link.setAttribute('data-bluecore-header-footer', '');
    link.onload = show;
    link.onerror = show; // never hide them for good
    document.head.appendChild(hide);
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

  // The logo's layout styles are inline (not only in the stylesheet), because the
  // stylesheet loads a moment later and the logo would show huge until then.
  function logoHtml(width, extraClass) {
    var parts = LOGO_PARTS.map(function (p) {
      return '<span class="bluecore-logo-part" data-part="' + p[0] + '" style="position:absolute;top:' + p[1] + '%;right:' + p[2] +
        '%;bottom:' + p[3] + '%;left:' + p[4] + '%">' + LOGO_SVGS[p[0]] + '</span>';
    }).join('');
    return '<span class="bluecore-logo' + (extraClass ? ' ' + extraClass : '') +
      '" aria-hidden="true" style="display:block;position:relative;overflow:hidden;aspect-ratio:544.08/117;flex:none;width:' +
      width + 'px">' + parts + '</span>';
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
          ' aria-expanded="false" aria-controls="bluecore-app-menu">' +
          '<span class="bluecore-app-switcher-label">Switch applications</span>' +
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
          '<div class="bluecore-footer-divider" aria-hidden="true">' + FOOTER_DIVIDER_SVG + '</div>' +
          '<nav class="bluecore-footer-apps" aria-labelledby="bluecore-footer-apps-heading">' +
            '<h2 id="bluecore-footer-apps-heading" class="bluecore-footer-apps-heading">APPLICATIONS</h2>' +
            '<ul class="bluecore-footer-app-list">' + appLinks + '</ul>' +
          '</nav>' +
        '</footer>';
    }

    // homepage: logo, Contact us, then the link columns
    homeHtml(sizes) {
      var divider = '<div class="bluecore-footer-home-divider" aria-hidden="true">' +
        HOME_FOOTER_DIVIDER_SVG + '</div>';
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
