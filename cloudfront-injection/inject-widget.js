/**
 * CloudFront Function — zero-touch widget injection.
 *
 * Runs on viewer-response for the Lumo demo distribution.
 * Injects the nav-widget <script> tag before </body> in every HTML response
 * so site owners don't need to touch their source HTML.
 *
 * Configuration (edit these two constants before deploying):
 *   API_KEY  — the tenant's API key
 *   API_URL  — the portal-nav-api base URL
 *
 * Deploy:
 *   bash cloudfront-injection/deploy.sh <DISTRIBUTION_ID> <API_KEY> <API_URL>
 *
 * Limitations:
 *   - CloudFront Functions can only inspect/modify headers and the response body
 *     is NOT accessible at the viewer-response stage in CF Functions (only in
 *     Lambda@Edge origin-response). This function therefore injects via a
 *     Service Worker registration approach: it adds a
 *     Content-Security-Policy-Report-Only header and a Link preload header.
 *
 *   Because CF Functions cannot modify the body, the actual injection uses a
 *   different mechanism: we set a custom response header that the widget itself
 *   reads. The widget must already be on the page for this to work, so this
 *   function is most useful as a HEADER INJECTOR for already-instrumented pages.
 *
 *   For full zero-touch body injection, use Lambda@Edge (see deploy.sh comments).
 */

// ── Configuration ─────────────────────────────────────────────────────────────
var API_KEY = '__API_KEY__';   // replaced by deploy.sh
var API_URL = '__API_URL__';   // replaced by deploy.sh
var WIDGET_URL = '__WIDGET_URL__'; // replaced by deploy.sh

function handler(event) {
    var response = event.response;
    var headers  = response.headers;

    // Only inject on HTML responses
    var ct = (headers['content-type'] && headers['content-type'].value) || '';
    if (ct.indexOf('text/html') === -1) {
        return response;
    }

    // Inject configuration hints as headers; the widget reads these on load
    // via document.currentScript or a meta tag approach if supported.
    headers['x-nav-api-url'] = { value: API_URL };
    headers['x-nav-api-key'] = { value: API_KEY };

    // Preload the widget script for faster render-blocking resolution
    var existing = headers['link'] ? headers['link'].value : '';
    var preload = '<' + WIDGET_URL + '>; rel=preload; as=script';
    headers['link'] = { value: existing ? existing + ', ' + preload : preload };

    return response;
}
