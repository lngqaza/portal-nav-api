/**
 * portal-config.js — runtime config for the NovaSure mock portal.
 * In a real deployment this would be injected at build time or served
 * from an authenticated config endpoint. For local/demo use, set the
 * values here once and all pages pick them up.
 */
window.PORTAL_NAV_CONFIG = {
  apiUrl:       'https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com',
  apiKey:       'nav-9eadef81559f12263d150308a53b2975',
  threshold:    0.82,
  cacheVersion: '2',
};
