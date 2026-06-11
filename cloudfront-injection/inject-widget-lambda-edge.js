/**
 * Lambda@Edge — zero-touch widget body injection (origin-response trigger).
 *
 * This is the FULL injection approach: modifies the HTML response body to
 * insert the nav-widget <script> tag before </body>.  Must be deployed as a
 * Lambda@Edge function in us-east-1 and associated with the CloudFront
 * distribution's origin-response event.
 *
 * Deploy: see cloudfront-injection/deploy.sh
 *
 * IAM: the function's execution role needs lambda.amazonaws.com and
 * edgelambda.amazonaws.com as trusted principals, and logs:CreateLogGroup +
 * logs:CreateLogStream + logs:PutLogEvents on *.
 */
'use strict';

const zlib = require('zlib');

// ── Configuration ─────────────────────────────────────────────────────────────
// Injected by deploy.sh via sed; do not hardcode production values here.
const API_KEY    = '__API_KEY__';
const API_URL    = '__API_URL__';
const WIDGET_URL = '__WIDGET_URL__';

const SCRIPT_TAG = `<script
  src="${WIDGET_URL}"
  data-api-url="${API_URL}"
  data-api-key="${API_KEY}"
  data-discover="on"
  defer
></script>`;

exports.handler = async (event) => {
    const response = event.Records[0].cf.response;
    const headers  = response.headers;

    const ct = (headers['content-type'] || [{ value: '' }])[0].value;
    if (!ct.includes('text/html')) {
        return response;
    }

    // Body may be base64-encoded and/or gzip-compressed by the origin.
    let body = response.body || '';
    let isGzip = false;

    if (response.bodyEncoding === 'base64') {
        const buf = Buffer.from(body, 'base64');
        // Check for gzip magic bytes
        if (buf[0] === 0x1f && buf[1] === 0x8b) {
            isGzip = true;
            body = zlib.gunzipSync(buf).toString('utf-8');
        } else {
            body = buf.toString('utf-8');
        }
    }

    // Inject before </body> (case-insensitive)
    if (body.toLowerCase().includes('</body>')) {
        body = body.replace(/<\/body>/i, SCRIPT_TAG + '\n</body>');
    } else {
        // Append if no </body> found (single-page shells, etc.)
        body += '\n' + SCRIPT_TAG;
    }

    // Re-compress if origin used gzip
    if (isGzip) {
        const compressed = zlib.gzipSync(Buffer.from(body, 'utf-8'));
        response.body = compressed.toString('base64');
        response.bodyEncoding = 'base64';
        headers['content-encoding'] = [{ key: 'Content-Encoding', value: 'gzip' }];
    } else {
        response.body = body;
        response.bodyEncoding = 'text';
        // Remove stale content-encoding if origin didn't compress
        delete headers['content-encoding'];
    }

    // Update content-length after body modification
    delete headers['content-length'];

    return response;
};
