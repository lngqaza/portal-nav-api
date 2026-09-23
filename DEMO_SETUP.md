# Demo Setup Guide - SafeGuard Insurance

Complete guide to set up and test the portal-nav-api with a fully-featured insurance website demo.

## 🎯 What You'll Have

A complete insurance website with:
- ✅ 6 interconnected pages (Home, Products, Claims, Support)
- ✅ Professional graphics and branding
- ✅ 100+ searchable content items
- ✅ Admin console for real-time configuration
- ✅ Three-tier semantic search (L0/L1/L2)
- ✅ Real-time analytics and statistics

## 📁 File Structure

```
portal-nav-api/
├── demo-site/                          # NEW: Demo website
│   ├── index.html                      # Home page
│   ├── products/
│   │   ├── car-insurance.html
│   │   ├── home-insurance.html
│   │   └── life-insurance.html
│   ├── claims/
│   │   └── file-claim.html
│   ├── support/
│   │   └── contact.html
│   ├── index-config.json               # Page index configuration
│   └── README.md                       # Demo site documentation
├── admin-console.html                  # Admin panel (existing)
├── start-demo.sh                       # Demo startup script
├── DEMO_SETUP.md                       # This file
└── LOCAL_DEPLOYMENT.md                 # Local deployment guide
```

## 🚀 Quick Start (5 minutes)

### 1. Start the Demo Website

```bash
# Option A: Using Make
make serve-demo

# Option B: Using Python directly
cd demo-site
python -m http.server 8000
```

Access the site: **http://localhost:8000**

You should see:
- SafeGuard Insurance branding (dark blue header)
- Feature cards (Fast Claims, Competitive Rates, etc.)
- Search box at bottom of hero section
- Navigation menu linking to products and support

### 2. View the Admin Console

Open admin-console.html:
```bash
# Option A: Use Python HTTP server
python -m http.server 8000

# Option B: Open directly
# Open: http://localhost:8000/../admin-console.html
# (Adjust path based on where you run the server)
```

## 📊 Understanding the Architecture

### Three-Layer Search Cascade

When you search "file a claim":

```
1️⃣  L0 (Hot Paths) - 1ms
   ├─ Check cache for top 70 pages
   ├─ Fuzzy match: /claims/file-claim.html
   └─ Return immediately if confidence > 0.75

2️⃣  L1 (Embeddings) - 50ms
   ├─ If L0 miss, generate embedding
   ├─ Search PostgreSQL pgvector
   ├─ Find 10 similar pages
   └─ Return if best match > 0.65 confidence

3️⃣  L2 (Re-ranker) - 180ms
   ├─ Take top 10 from L1
   ├─ Use cross-encoder model
   ├─ Re-rank for semantic relevance
   └─ Return top 3 with scores
```

### Expected Behavior by Search Query

| Query | L0 Result | L1/L2 Results |
|-------|-----------|---------------|
| "file claim" | ✓ Hot Path hit | `/claims/file-claim.html` (1st) |
| "car insurance" | ✓ Hot Path hit | `/products/car-insurance.html` (1st) |
| "phone number" | ✗ Miss | `/support/contact.html` (1st) |
| "submit accident" | ✗ Miss | `/claims/file-claim.html` (1st) |
| "homeowner coverage" | ✗ Miss | `/products/home-insurance.html` (1st) |

## 🔧 Configuration

### Adjusting Search Thresholds

Use the admin console "Configuration" tab:

```
HOT_PATH_THRESHOLD: 0.75
├─ Higher = stricter matching
├─ Lower = more results (but less relevant)
└─ Default: 0.75 (recommended)

L1_THRESHOLD: 0.65
├─ Embedding search confidence
├─ Controls sensitivity of semantic matching
└─ Default: 0.65

L2_THRESHOLD: 0.50
├─ Re-ranker confidence
├─ Lower threshold = more results
└─ Default: 0.50

MAX_HOT_PATHS: 70
├─ Pages to keep in L0 cache
├─ More = better cache hit rate, more memory
└─ Default: 70
```

### Adding New Pages to Index

Via admin console:
1. Go to **Index Pages** tab
2. Click **"➕ Add New"**
3. Fill in:
   - **Path**: `/products/new-page.html`
   - **Label**: Display name
   - **Description**: Search index text
   - **Tags**: Comma-separated search terms
4. Click **"Add to Index"**

## 🧪 Testing Scenarios

### Scenario 1: Hot Path Performance

**Goal**: Verify L0 cache works

1. Open admin console → **Hot Paths** tab
2. Click **"Load Hot Paths"**
3. Should see top 70 pages ranked by hits:
   - File a Claim (450 hits)
   - Car Insurance (380 hits)
   - Home Insurance (320 hits)
   - Contact Support (280 hits)
4. Verify these load in ~1ms (no network latency visible)

### Scenario 2: Semantic Search (L1)

**Goal**: Test embedding-based search

1. Open admin console
2. Go to **Configuration** tab
3. Set `L0_THRESHOLD: 1.0` (disable L0 to force L1)
4. Search for: "homeowner protection"
5. Should return:
   - 1st: `/products/home-insurance.html` (~50ms)
   - 2nd: `/products/life-insurance.html` (related topic)
   - 3rd: `/index.html` (mentions protection)

### Scenario 3: Re-Ranking (L2)

**Goal**: Verify cross-encoder improves results

1. Compare two queries:
   - "insurance plans" (ambiguous, needs L2)
   - "file accident claim" (specific, L0 hits)
2. Ambiguous query results should be re-ranked
3. Final top 3 should be most semantically relevant

### Scenario 4: Admin Analytics

**Goal**: Check statistics collection

1. Open admin console → **Statistics** tab
2. Click **"Refresh"**
3. Should display:
   - Total Queries (test: 0+ or cached)
   - MISS Rate (0-100%)
   - L0 Hits (cache hits)
   - L1 Hits (embedding matches)
   - L2 Hits (re-ranked results)
   - Indexed Pages (6 from demo site)

## 🔍 Debugging

### Issue: Admin console can't connect

**Check**:
```bash
# 1. Verify API is running
curl -X GET http://localhost:3000/health

# 2. Verify correct API URL in console
# Should be: https://xyz.execute-api.eu-west-1.amazonaws.com
# NOT: http://localhost:3000 (unless running locally)

# 3. Check CORS headers
curl -X OPTIONS http://localhost:3000/health -v
```

### Issue: Pages not in search results

**Check**:
1. Use admin console → **Index Pages** tab
2. Click **"Load Index Info"**
3. Verify 6 pages are indexed:
   - `/index.html`
   - `/products/car-insurance.html`
   - `/products/home-insurance.html`
   - `/products/life-insurance.html`
   - `/claims/file-claim.html`
   - `/support/contact.html`

### Issue: Search results are poor quality

**Fix**:
1. Lower thresholds in Configuration tab
2. Add more aliases in `index-config.json`
3. Re-index pages with better descriptions
4. Run "Re-embed All Pages" in Configuration tab (slow but effective)

## 📈 Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| L0 Search | <5ms | In-memory cache |
| L1 Search | 50-100ms | Embedding generation + vector search |
| L2 Search | 150-200ms | Re-ranking with cross-encoder |
| **Total** | **~280ms** | Typical full cascade |
| Admin load | <500ms | Multiple API calls |
| Page load | <1s | 6 demo pages, ~50KB each |

## 🎓 Learning Path

1. **Start**: Read `demo-site/README.md`
2. **Understand**: Review this file's architecture section
3. **Test**: Run Quick Start scenarios
4. **Experiment**: Adjust thresholds in admin console
5. **Deploy**: Follow `LOCAL_DEPLOYMENT.md` to push to AWS

## 📝 Demo Site Pages

### Home Page (`/index.html`)
- Hero section: Trusted Insurance Protection
- Features: Fast Claims, Competitive Rates, 24/7 Support
- Search box for testing
- Links to all other sections

### Car Insurance (`/products/car-insurance.html`)
- 3 plan tiers: Basic, Standard, Premium
- Coverage types: Liability, Collision, Comprehensive
- 6 available discounts
- Quote request form

### Home Insurance (`/products/home-insurance.html`)
- 3 plan tiers for homeowners
- Dwelling, personal property, liability coverage
- Special coverages: Water, Hurricane, Earthquake
- Safety feature discounts

### Life Insurance (`/products/life-insurance.html`)
- Term Life (10/20 year) and Whole Life options
- Coverage amounts: $100K-$5M+
- Medical underwriting options
- Coverage calculator guidance

### File a Claim (`/claims/file-claim.html`)
- 6-step claim process
- Online claim form
- 3 contact methods (phone, chat, email)
- Claims FAQ with 4 Q&A pairs

### Contact Support (`/support/contact.html`)
- 6 contact channels (phone, chat, email, mail, app, portal)
- Message form
- 6 expandable FAQ items

## ✅ Verification Checklist

Before considering the demo complete:

- [ ] Demo site loads at http://localhost:8000
- [ ] All 6 pages are accessible and styled correctly
- [ ] Admin console connects successfully
- [ ] Configuration tab shows threshold values
- [ ] Hot Paths tab loads with 5+ entries
- [ ] Index Pages tab shows 6 indexed pages
- [ ] Statistics tab displays analytics
- [ ] Search for "file claim" returns correct results
- [ ] Thresholds can be adjusted and saved
- [ ] Page can be re-embedded

## 🚀 Next Steps

Once verified:

1. **Test locally** with your own queries
2. **Adjust configuration** based on results
3. **Add more pages** to the demo site
4. **Prepare for AWS** deployment via `LOCAL_DEPLOYMENT.md`
5. **Push to master** and let GitHub Actions deploy

See `LOCAL_DEPLOYMENT.md` for the pre-push validation workflow.
