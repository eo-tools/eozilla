(async () => {
  "use strict";

  /**
   * @typedef {Object} NotebookDisplayConfig
   * @property {string} baseSrc
   * @property {boolean} autoScheme
   * @property {string} width
   * @property {string} height
   * @property {number | null} proxyPort
   * @property {boolean} proxyApp
   * @property {boolean} autoProxy
   * @property {boolean} openInBrowser
   */

  function detectJupyterScheme() {
    const body = document.body;
    const root = document.documentElement;

    const themeLight =
      body.getAttribute("data-jp-theme-light") ??
      root.getAttribute("data-jp-theme-light");

    if (themeLight === "true") return "light";
    if (themeLight === "false") return "dark";

    const bg =
      getComputedStyle(root).getPropertyValue("--jp-layout-color0") ||
      getComputedStyle(body).backgroundColor;

    const match = bg.match(/\d+/g);
    if (match && match.length >= 3) {
      const [red, green, blue] = match.slice(0, 3).map(Number);
      const luminance =
        (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255;
      return luminance < 0.5 ? "dark" : "light";
    }

    return null;
  }

  function getJupyterBaseUrl() {
    const configElement = document.getElementById("jupyter-config-data");
    let configBaseUrl = null;

    if (configElement?.textContent) {
      try {
        configBaseUrl = JSON.parse(configElement.textContent).baseUrl;
      } catch {
        configBaseUrl = null;
      }
    }

    return (
      configBaseUrl ??
      document.body.dataset.baseUrl ??
      document.documentElement.dataset.baseUrl ??
      "/"
    );
  }

  function getJupyterProxyUrl(port, path) {
    const baseUrl = getJupyterBaseUrl();
    const basePath = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
    return new URL(
      `${basePath}proxy/${port}/${path}`,
      window.location.origin,
    );
  }

  async function isJupyterProxyAvailable(url) {
    try {
      const response = await fetch(url, { method: "GET" });
      console.debug("[cuiman] Jupyter proxy probe", {
        url: url.toString(),
        status: response.status,
        available: response.ok,
      });
      return response.ok;
    } catch (error) {
      console.debug("[cuiman] Jupyter proxy probe failed", {
        url: url.toString(),
        error: String(error),
      });
      return false;
    }
  }

  const scriptElement = document.currentScript;
  const configElement = scriptElement?.previousElementSibling;
  const root = configElement?.previousElementSibling;

  if (
    !(configElement instanceof HTMLScriptElement) ||
    !(root instanceof HTMLElement)
  ) {
    throw new Error("Invalid Cuiman notebook display markup");
  }

  /** @type {NotebookDisplayConfig} */
  const config = JSON.parse(configElement.textContent || "{}");
  const {
    baseSrc,
    autoScheme,
    width,
    height,
    proxyPort,
    proxyApp,
    autoProxy,
    openInBrowser,
  } = config;

  let src = new URL(baseSrc, window.location.href);
  let wsUrl = src.searchParams.get("ws");

  console.debug("[cuiman] display setup", {
    jupyterBaseUrl: proxyPort === null ? null : getJupyterBaseUrl(),
    proxyPort,
    proxyApp,
    autoProxy,
    openInBrowser,
  });

  if (proxyPort !== null) {
    const proxyUrl = getJupyterProxyUrl(proxyPort, "index.html");
    const proxyWsUrl = getJupyterProxyUrl(proxyPort, "ws");
    proxyWsUrl.protocol =
      window.location.protocol === "https:" ? "wss:" : "ws:";

    const useProxy =
      !autoProxy || (await isJupyterProxyAvailable(proxyUrl));

    if (useProxy && proxyApp) {
      const query = src.search;
      src = getJupyterProxyUrl(proxyPort, "index.html");
      src.search = query;
    }

    if (useProxy) {
      wsUrl = proxyWsUrl.toString();
    }
  }

  if (wsUrl !== null) {
    src.searchParams.set("ws", wsUrl);
  }

  console.debug("[cuiman] display target", {
    appUrl: `${src.origin}${src.pathname}`,
    wsUrl,
  });

  if (autoScheme) {
    const scheme = detectJupyterScheme();
    if (scheme) {
      src.searchParams.set("scheme", scheme);
    }
  }

  if (openInBrowser) {
    const opened = window.open(src.toString(), "_blank", "noopener");
    if (!opened) {
      const link = document.createElement("a");
      link.href = src.toString();
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Open Cuiman app";
      root.replaceChildren(link);
    }
    return;
  }

  const iframe = document.createElement("iframe");
  iframe.src = src.toString();
  iframe.width = width;
  iframe.height = height;
  iframe.style.border = "0";
  iframe.style.width = width;
  iframe.style.height = height;
  iframe.allow = "clipboard-read; clipboard-write";

  root.replaceChildren(iframe);
})();
