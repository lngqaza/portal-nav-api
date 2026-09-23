# SafeGuard Insurance Demo Site

A comprehensive demo insurance website built to showcase the portal-nav-api search and navigation capabilities.

## Structure

```
demo-site/
├── index.html                  # Home page
├── products/
│   ├── car-insurance.html     # Car insurance plans
│   ├── home-insurance.html    # Home insurance plans
│   └── life-insurance.html    # Life insurance plans
├── claims/
│   └── file-claim.html        # Claim filing page
├── support/
│   └── contact.html           # Support & contact page
├── index-config.json          # Page index configuration
└── README.md                   # This file
```

## Features

### Pages
- **Home**: Welcome page with feature highlights and search box
- **Car Insurance**: Plans overview, coverage details, discounts, how to get quotes
- **Home Insurance**: Homeowners plans, coverage types, special coverages, safety discounts
- **Life Insurance**: Term and whole life options, underwriting options, coverage guidance
- **File a Claim**: 6-step claim process, online claim form, contact methods, FAQ
- **Contact Support**: Multiple contact channels, message form, comprehensive FAQ

### Design
- Professional insurance company branding (SafeGuard Insurance)
- Gradient header with navigation
- Responsive grid layouts for plans and features
- Color scheme: Dark blue (#003d7a), orange accents (#ff6b35)
- Accessible forms and interactive elements

## Starting the Demo Site

### Option 1: Python HTTP Server (Recommended)
```bash
cd demo-site
python -m http.server 8000
```

Then open: `http://localhost:8000/index.html`

### Option 2: Using Make
```bash
make serve-demo
```

## Portal Nav API Integration

### Step 1: Index the Pages
To make the demo site searchable by portal-nav-api, you need to index the pages.

Using the admin console:
1. Open admin-console.html in your browser
2. Enter the API URL and admin token
3. Use the "Index Pages" tab to add each page:
   - Path: `/products/car-insurance.html`
   - Label: `Car Insurance Plans`
   - Description: (from index-config.json)
   - Tags: `insurance, car, coverage`

Or use the provided `index-config.json` for batch import.

### Step 2: Configure Search
Use the admin console's "Configuration" tab to adjust:
- **HOT_PATH_THRESHOLD**: 0.75 (fuzzy match confidence)
- **L1_THRESHOLD**: 0.65 (embedding search confidence)
- **L2_THRESHOLD**: 0.50 (re-ranker confidence)
- **MAX_HOT_PATHS**: 70 (keep top 70 frequently accessed pages in cache)

### Step 3: Test the Search
Add this to any page's `<script>` section:

```javascript
// Example: Search for "car insurance"
const apiUrl = 'http://localhost:3000'; // Your portal-nav-api endpoint
const query = 'car insurance';

fetch(`${apiUrl}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
})
.then(r => r.json())
.then(results => {
    console.log('Top 3 results:', results.slice(0, 3));
});
```

## Expected Search Results

When you search on the demo site, here are typical results you should get:

### Query: "car insurance"
1. **Car Insurance Plans** - `/products/car-insurance.html`
2. **Home Insurance Plans** - `/products/home-insurance.html` (mentions coverage types)
3. **Contact Support** - `/support/contact.html` (has insurance inquiry support)

### Query: "file a claim"
1. **File a Claim** - `/claims/file-claim.html`
2. **Contact Support** - `/support/contact.html`
3. **Car Insurance Plans** - `/products/car-insurance.html` (mentions claims)

### Query: "phone support"
1. **Contact Support** - `/support/contact.html`
2. **File a Claim** - `/claims/file-claim.html`
3. **Home page** - `/index.html` (mentions 24/7 support)

## Indexing Strategy

The demo site uses a three-tier indexing approach:

### Tier 0 (Hot Paths)
Most frequently accessed pages cached in memory:
- File a Claim (450 hits)
- Car Insurance (380 hits)
- Home Insurance (320 hits)
- Contact Support (280 hits)

### Tier 1 (Embeddings)
All indexed pages embedded using ONNX `all-MiniLM-L6-v2`:
- Semantic search across all 6 pages
- ~50ms latency per query

### Tier 2 (Cross-Encoder Re-ranking)
Top 10 candidates from L1 re-ranked using MS MARCO MiniLM:
- ~180ms for final ranking
- Returns final top 3 results

## Customization

### Add a New Page
1. Create the HTML file in appropriate subdirectory
2. Add entry to `index-config.json`:
   ```json
   {
     "path": "/new-page.html",
     "title": "Page Title",
     "label": "Display Label",
     "description": "Search description",
     "keywords": ["keyword1", "keyword2"],
     "priority": 0.9
   }
   ```
3. Add common aliases to the `aliases` section
4. Use admin console to index the page

### Customize Branding
Edit the following in HTML files:
- `.logo` color and text
- `--primary-color`: #003d7a (blue)
- `--accent-color`: #ff6b35 (orange)
- Company name: "SafeGuard Insurance"

## Testing Checklist

- [ ] All links navigate correctly
- [ ] Forms are interactive (submit validation)
- [ ] Responsive design works on mobile (375px)
- [ ] Search box is visible on home page
- [ ] Admin console connects to API
- [ ] Pages appear in search results
- [ ] Hot paths load in admin console
- [ ] Page statistics display correctly

## Performance

- Homepage load: ~200ms
- Search query: ~50ms (L0) + ~50ms (L1) + ~180ms (L2) = ~280ms total
- Cached hot path lookup: ~1ms

## API Endpoints Used

- `GET /health` - Health check
- `POST /search` - Perform search query
- `GET /admin/config` - Get configuration
- `PUT /admin/config` - Update configuration
- `GET /admin/hot-paths` - Get hot paths
- `POST /admin/index/add` - Add page to index
- `GET /admin/stats` - Get statistics

## Troubleshooting

**Problem**: Pages not appearing in search results
- Solution: Use admin console to manually index pages

**Problem**: Search takes too long
- Solution: Check L0/L1/L2 thresholds in Configuration tab

**Problem**: Wrong results for a query
- Solution: Adjust thresholds or add aliases in index-config.json

**Problem**: Admin console won't connect
- Solution: Verify API URL format (should be `https://xyz.execute-api.region.amazonaws.com`)

## Production Deployment

To deploy the demo site to production:

1. Build a Docker image with the demo site
2. Deploy alongside portal-nav-api
3. Use the admin console to configure search
4. Monitor search analytics in Statistics tab
5. Adjust thresholds based on user behavior

## License

Demo site provided as-is for testing portal-nav-api functionality.
