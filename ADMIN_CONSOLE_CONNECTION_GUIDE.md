# Admin Console Connection Guide

Complete guide to connect and use the admin console with portal-nav-api.

---

## 🎯 QUICK START (5 minutes)

### Step 1: Access Admin Console
```
Local: http://localhost:8000/admin-console.html
AWS:   https://your-api.execute-api.eu-west-1.amazonaws.com (point to API Gateway)
```

### Step 2: Enter API Details
```
API URL:      https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
Admin Token:  (from GitHub secrets NAV_ADMIN_TOKEN)
```

### Step 3: Click "Test Connection"
```
Expected: ✓ Connected (green checkmark)
```

### Step 4: Use Features
- **Configuration Tab**: Adjust search thresholds (L0/L1/L2)
- **Hot Paths Tab**: View top 70 popular pages
- **Index Pages Tab**: Add/manage indexed pages
- **Statistics Tab**: Monitor 24-hour analytics

---

## 📋 ADMIN CONSOLE FILE LOCATION

```
File: /admin-console.html
Location: C:\dev\work\portal-nav-api\admin-console.html
Access: http://localhost:8000/admin-console.html
```

---

## 🔑 API CREDENTIALS

### Local Testing
```
API Base URL:    http://localhost:3000
Admin Token:     (set in environment or GitHub secrets)
API Key:         (set in environment or GitHub secrets)
```

### AWS Lambda Deployment
```
API Gateway URL: https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
Region:          eu-west-1
Admin Token:     NAV_ADMIN_TOKEN (GitHub secret)
API Key:         NAV_API_KEY (GitHub secret)
```

---

## 📡 ADMIN CONSOLE INTERFACE

### Overview
The admin console is a **dark-themed web dashboard** that allows you to:
- ✅ Configure search thresholds in real-time
- ✅ View hot paths (top 70 pages by popularity)
- ✅ Manage indexed pages
- ✅ Monitor search statistics
- ✅ Test API connectivity

### Main UI Components

```
┌─────────────────────────────────────────────────────────┐
│ 🎛️ Portal Nav Admin Console                             │
│ Manage search configuration, index, and hot paths       │
├─────────────────────────────────────────────────────────┤
│ API URL: [https://3jz6sk8vt7.execute-api.eu-west-1.am] │
│ Token:   [*********************]     [Test Connection]  │
│ Status:  ✓ Connected (green)                            │
├─────────────────────────────────────────────────────────┤
│ [⚙️ Configuration] [📊 Statistics] [⚡ Hot Paths] [🔍 Index Pages] │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 CONFIGURATION TAB

### Purpose
Adjust the three-layer cascade thresholds for search optimization.

### Settings

#### HOT_PATH_THRESHOLD (L0 - Fuzzy Match)
```
Default:  0.75
Range:    0.0 - 1.0
Purpose:  Cache hit confidence for frequently accessed pages
Speed:    ~1ms
Example:  Query "file claim" → exact match in cache → instant result
```

#### L1_THRESHOLD (Embeddings)
```
Default:  0.65
Range:    0.0 - 1.0
Purpose:  Semantic search confidence using ONNX embeddings
Speed:    ~50ms
Example:  Query "submit claim" → embedding search → similar pages
```

#### L2_THRESHOLD (Re-ranker)
```
Default:  0.50
Range:    0.0 - 1.0
Purpose:  Cross-encoder re-ranking confidence
Speed:    ~180ms
Example:  Top 10 results → re-ranked by relevance → top 3 returned
```

#### MAX_HOT_PATHS
```
Default:  70
Range:    1 - 500
Purpose:  Number of top pages to keep in L0 cache
Memory:   ~10KB per page (700KB for 70 pages)
Example:  Set to 100 to cache more pages, reduce L1 queries
```

### How to Adjust

1. **Click "Load Current"**
   - Loads current values from API
   - Shows what's currently deployed

2. **Change Values**
   ```
   HOT_PATH_THRESHOLD: 0.75 → 0.80 (stricter matching)
   L1_THRESHOLD:       0.65 → 0.60 (more results)
   L2_THRESHOLD:       0.50 → 0.45 (lower confidence threshold)
   MAX_HOT_PATHS:      70 → 100 (cache more pages)
   ```

3. **Click "Save Changes"**
   - Sends PUT request to `/admin/config`
   - Updates Lambda environment immediately
   - ✓ Config saved! message confirms

### Testing After Changes

**Test Search**: Open demo site → Search for "file claim"
- Lower thresholds = more results
- Higher thresholds = fewer but more relevant results

---

## 📊 STATISTICS TAB

### Purpose
Monitor search performance and usage over the past 24 hours.

### Metrics Displayed

#### Total Queries
```
How many searches were performed in the last 24 hours
Example: 1,234 total queries
Useful for: Measuring search usage
```

#### MISS Rate
```
Percentage of searches that failed to find results
Example: 5.2% miss rate
Good:    < 10% (most searches find something)
Bad:     > 20% (too many no-results)
```

#### L0 Hits
```
Searches resolved from hot paths cache (~1ms)
Example: 450 L0 hits
Useful for: Measuring cache effectiveness
Goal:     60-70% of total queries
```

#### L1 Hits
```
Searches resolved from semantic embeddings (~50ms)
Example: 320 L1 hits
Useful for: Measuring semantic search usage
Goal:     20-30% of total queries
```

#### L2 Hits
```
Searches resolved from re-ranking (~180ms)
Example: 80 L2 hits
Useful for: Measuring rerank necessity
Goal:     5-10% of total queries
```

#### Indexed Pages
```
Total pages in the search index
Example: 6 indexed pages (demo site)
Need to add pages? Use Index Pages tab
```

### Interpretation

**Ideal Distribution:**
```
L0 (Cache):  60% = 745 queries
L1 (Search): 30% = 370 queries  
L2 (Rank):   10% = 123 queries
────────────────────────────────
Total:      100% = 1,238 queries
```

**What to Look For:**
- ✅ High L0 percentage = efficient caching
- ✅ Low miss rate = good index quality
- ✅ Balanced distribution = healthy cascade

---

## ⚡ HOT PATHS TAB

### Purpose
View and manage the top 70 most frequently accessed pages.

### How to Use

#### 1. Click "Load Hot Paths"
```
Shows table with:
- Path: Page URL
- Label: Display name
- Hits: Number of times accessed
- Pinned: Locked in cache (won't be evicted)
- Last Hit: When page was last accessed
```

#### 2. Example Output
```
┌───────────────────────────────────────────────────────────┐
│ Hot Path Registry (Top 70)                               │
├───────┬──────────────────────┬──────┬────────┬────────────┤
│ Path  │ Label                │ Hits │ Pinned │ Last Hit   │
├───────┼──────────────────────┼──────┼────────┼────────────┤
│ /c... │ File a Claim         │ 450  │ Yes    │ 2 sec ago  │
│ /p... │ Car Insurance Plans  │ 380  │ Yes    │ 5 sec ago  │
│ /p... │ Home Insurance Plans │ 320  │ Yes    │ 12 sec ago │
│ /s... │ Contact Support      │ 280  │ Yes    │ 1 min ago  │
│ /p... │ Life Insurance Plans │ 210  │ No     │ 10 min ago │
└───────┴──────────────────────┴──────┴────────┴────────────┘
```

#### 3. Add New Hot Path (Optional)
```
Click "➕ Add New" to manually pin a page:
- Path: /products/new-page.html
- Label: Display Name
- Aliases: comma-separated alternatives
- Pinned: Check to lock in cache
```

### Pin/Unpin Strategy

**Pin When:**
- Page is important (e.g., "File a Claim")
- High traffic expected
- Want guaranteed L0 cache hit

**Unpin When:**
- Page is rarely accessed
- Want to free cache space
- Seasonal traffic only

---

## 🔍 INDEX PAGES TAB

### Purpose
Manage which pages are indexed for search and add new pages.

### How to Use

#### 1. Click "Load Index Info"
```
Shows:
- Total indexed pages
- Pages list with descriptions
- Storage usage
```

#### 2. Add New Page
```
Click "➕ Index Page" and fill in:

Path:        /products/new-page.html (required)
Label:       Display Name (required)
Description: Search index text (required)
Tags:        comma-separated keywords (optional)
```

#### 3. Example
```
Path:        /products/dental-insurance.html
Label:       Dental Insurance Plans
Description: Comprehensive dental coverage for teeth, cleaning, and emergency procedures
Tags:        dental, teeth, checkup, cavity, root canal, orthodontics
```

#### 4. Click "Add to Index"
```
POST /admin/index/add
{
  "path": "/products/dental-insurance.html",
  "label": "Dental Insurance Plans",
  "description": "...",
  "tags": ["dental", "teeth", ...]
}

Response: ✓ Page indexed successfully
```

### Index Management

**View Current Index:**
```
Total Indexed Pages: 6
- /index.html (Home)
- /products/car-insurance.html
- /products/home-insurance.html
- /products/life-insurance.html
- /claims/file-claim.html
- /support/contact.html
```

**To Update Index:**
1. Use Index Pages tab
2. Add new pages
3. Or manually via API:
   ```bash
   curl -X POST https://api.example.com/admin/index/add \
     -H "Authorization: Bearer $NAV_ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "path": "/products/new-page.html",
       "label": "New Page",
       "description": "Description for search"
     }'
   ```

---

## 🔐 AUTHENTICATION

### Where Admin Token Comes From

#### Local Development
```
Environment Variable: NAV_ADMIN_TOKEN
Set in .env:
  NAV_ADMIN_TOKEN=demo-admin-token-12345
```

#### AWS Lambda
```
GitHub Secret: NAV_ADMIN_TOKEN
Set in: Settings → Secrets and variables → Actions

To add:
1. Go to repo → Settings
2. Click "Secrets and variables" → "Actions"
3. Click "New repository secret"
4. Name: NAV_ADMIN_TOKEN
5. Value: your-admin-token-here
```

### How Admin Console Uses It

```javascript
// Every API call includes token:
const headers = {
    'Authorization': `Bearer ${document.getElementById('adminToken').value}`,
    'Content-Type': 'application/json'
};

fetch(`${apiUrl}/admin/config`, {
    method: 'GET',
    headers: headers
});
```

### Token Format
```
Any string, recommend:
- 32+ characters
- Mix of uppercase/lowercase
- Numbers
- Special characters (if backend supports)

Example: "admin-token-3f8d9e2c-4b1a-9f5e-c7d2-8a3b9e1f5c2d"
```

---

## 🌐 API ENDPOINTS USED BY ADMIN CONSOLE

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/health` | GET | Test connection | `{status: "ok"}` |
| `/admin/config` | GET | Load current config | `{L0_THRESHOLD: 0.75, ...}` |
| `/admin/config` | PUT | Save config changes | `{status: "updated"}` |
| `/admin/hot-paths` | GET | Get top 70 pages | `[{path, label, hits, pinned, lastHit}]` |
| `/admin/stats` | GET | Get 24h statistics | `{total_queries, miss_rate, l0_hits, ...}` |
| `/admin/index/add` | POST | Add page to index | `{status: "indexed"}` |
| `/admin/index/info` | GET | Get index info | `{indexed_count, pages: []}` |
| `/admin/index/reindex-all` | POST | Re-embed all pages | `{status: "started"}` |

---

## 🧪 TESTING THE CONNECTION

### Step 1: Access Admin Console
```
Open: http://localhost:8000/admin-console.html
```

### Step 2: Enter API Details
```
API URL:   http://localhost:3000
          (or your AWS endpoint)

Admin Token: demo-token-123
            (or from GitHub secrets)
```

### Step 3: Test Connection
```
Click: "Test Connection" button

EXPECTED:
✓ Connected (green checkmark appears)

If error:
✗ Not Connected (red X appears)
→ Check API URL is correct
→ Check admin token matches
→ Check API server is running
```

### Step 4: Load Configuration
```
Click: "⚙️ Configuration" tab
Click: "Load Current"

EXPECTED:
- Shows current threshold values
- Status: "✓ Config loaded"

If error:
→ API endpoint /admin/config not available
→ Check API_KEY header is set
```

### Step 5: View Statistics
```
Click: "📊 Statistics" tab
Click: "Refresh"

EXPECTED:
- Shows query counts
- Shows miss rate
- Shows L0/L1/L2 hit distribution

If no data:
→ Normal (no searches yet)
→ Or stats endpoint not available
```

### Step 6: Load Hot Paths
```
Click: "⚡ Hot Paths" tab
Click: "Load Hot Paths"

EXPECTED:
- Shows table of top pages
- Sorted by hits count

If empty:
→ No pages indexed yet
→ Use Index Pages tab to add pages
```

### Step 7: Add Index Page
```
Click: "🔍 Index Pages" tab
Click: "➕ Index Page"

Fill in:
Path: /products/car-insurance.html
Label: Car Insurance Plans
Description: Comprehensive coverage...

Click: "Add to Index"

EXPECTED:
Status: "✓ Page indexed successfully"
```

---

## 🐛 TROUBLESHOOTING

### "Connection Failed" Error

**Problem:** Can't connect to API

**Solutions:**
1. ✅ Verify API URL format
   ```
   Correct:   https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
   Incorrect: https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com/
   ```

2. ✅ Check API is running
   ```bash
   # Local
   curl http://localhost:3000/health
   
   # AWS
   curl https://your-api.execute-api.eu-west-1.amazonaws.com/health \
     -H "x-api-key: YOUR_API_KEY"
   ```

3. ✅ Verify admin token
   ```bash
   echo $NAV_ADMIN_TOKEN  # Check it's set
   ```

4. ✅ Check CORS headers
   ```bash
   curl -i https://your-api.execute-api.eu-west-1.amazonaws.com/health
   # Look for: Access-Control-Allow-Origin: *
   ```

### "Config Load Failed" Error

**Problem:** Can't load configuration

**Solutions:**
1. ✅ Connection works but endpoint missing
   ```bash
   curl https://your-api.execute-api.eu-west-1.amazonaws.com/admin/config \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

2. ✅ Check admin token is correct
   ```bash
   # Token mismatch causes 401 Unauthorized
   ```

3. ✅ Check IAM permissions
   ```bash
   # Lambda needs permission to access SSM Parameter Store
   ```

### "Statistics Empty" Error

**Problem:** No statistics showing

**Solutions:**
1. ✅ No searches performed yet
   - Stats only show after searches
   - Try searching on demo site first

2. ✅ Stats endpoint not implemented
   ```bash
   curl https://your-api.execute-api.eu-west-1.amazonaws.com/admin/stats
   ```

3. ✅ CloudWatch logs disabled
   - Check Lambda is logging queries

### "Hot Paths Empty" Error

**Problem:** No hot paths showing

**Solutions:**
1. ✅ No pages indexed yet
   - Use Index Pages tab to add pages

2. ✅ Pages not accessed yet
   - Hot paths require access history

3. ✅ Cache not warmed up
   - Make searches to populate cache

---

## 💾 PERSISTENCE & STORAGE

### Where Config Is Stored

**Local (Development)**
```
Environment Variables:
- NAV_ADMIN_TOKEN
- L0_THRESHOLD
- L1_THRESHOLD
- L2_THRESHOLD
- MAX_HOT_PATHS
```

**AWS Lambda (Production)**
```
SSM Parameter Store:
/portal-nav-api/l0-threshold     = "0.75"
/portal-nav-api/l1-threshold     = "0.65"
/portal-nav-api/l2-threshold     = "0.50"
/portal-nav-api/max-hot-paths    = "70"

Accessed via:
import boto3
ssm = boto3.client('ssm')
value = ssm.get_parameter(Name='/portal-nav-api/l0-threshold')
```

### Hot Paths Storage

**Stored In:**
```
Database (PostgreSQL):
Table: hot_paths
- path (string)
- label (string)
- hits (integer)
- pinned (boolean)
- last_accessed (timestamp)
```

**Accessed Via:**
```
SELECT * FROM hot_paths 
ORDER BY hits DESC 
LIMIT 70;
```

### Index Storage

**Stored In:**
```
Database (PostgreSQL with pgvector):
Table: page_index
- path (string)
- label (string)
- description (text)
- embedding (vector) -- ONNX embedding
- tags (string[])
- indexed_at (timestamp)
```

---

## 🔄 WORKFLOW: OPTIMIZATION CYCLE

### Step 1: Baseline Measurement
```
Admin Console → Statistics Tab
Record:
- Current miss rate
- L0/L1/L2 distribution
```

### Step 2: Make Change
```
Admin Console → Configuration Tab
Change: L1_THRESHOLD from 0.65 → 0.60
Click: "Save Changes"
```

### Step 3: Test Impact
```
Demo Site → Search for "file claim"
Verify: Results still relevant
```

### Step 4: Monitor Metrics
```
Admin Console → Statistics Tab
Click: "Refresh" after 5 minutes
Compare:
- New miss rate vs baseline
- New L0/L1/L2 distribution
```

### Step 5: Decide
```
If better:  Keep changes
If worse:   Revert changes
If neutral: Try different setting
```

### Example Optimization
```
BASELINE:
- Miss rate: 15%
- L0: 45%, L1: 40%, L2: 15%

CHANGE:
- Lowered L1_THRESHOLD from 0.65 → 0.60

RESULT:
- Miss rate: 8% (improved!)
- L0: 45%, L1: 45%, L2: 10% (more L1 matches)

DECISION:
- Keep change (better coverage, acceptable latency)
```

---

## 📱 MOBILE SUPPORT

### Responsive Design
```
The admin console works on mobile devices

Desktop (1200px+):
- Full sidebar
- Wide tables
- All features visible

Tablet (768px - 1199px):
- Collapsed sidebar
- Resized tables
- All features accessible

Mobile (< 768px):
- Hamburger menu
- Stacked forms
- Vertical tables
- Touch-friendly buttons
```

### Mobile Usage
```
1. Open on phone: http://localhost:8000/admin-console.html
2. Tap menu icon (☰)
3. Select tab (Configuration, Statistics, etc.)
4. Input fields are touch-friendly (larger)
5. All buttons clickable on mobile
```

---

## 📖 SUMMARY

The admin console provides:
✅ Real-time configuration management
✅ Visual search performance monitoring
✅ Hot path management
✅ Page indexing tools
✅ Statistics & analytics
✅ Instant API connectivity testing

Ready to connect and optimize! 🚀
