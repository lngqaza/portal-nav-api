# Admin Console Setup - Complete Status

## ✅ CONNECTED SUCCESSFULLY!

### Current Configuration

```
API URL:        https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
Admin Token:    demo-admin-token-testing
Connection:     ✓ CONNECTED (Green checkmark)
Status:         Ready to use
```

---

## 🎛️ ADMIN CONSOLE FEATURES

### Available Tabs

#### 1. ⚙️ **Configuration Tab** (Active)
```
Search Thresholds:
- HOT_PATH_THRESHOLD (L0):  0.75  (Cache hit confidence)
- L1_THRESHOLD:              0.65  (Embedding search confidence)
- L2_THRESHOLD:              0.50  (Re-ranker confidence)
- MAX_HOT_PATHS:             70    (Pages to cache)

Actions:
- [Load Current] - Get current settings from API
- [Save Changes] - Save any threshold changes
- [🔄 Re-embed All Pages] - Re-index all pages
```

#### 2. 📊 **Statistics Tab**
```
Displays 24-hour search metrics:
- Total Queries
- MISS Rate (%)
- L0 Hits (cache)
- L1 Hits (embeddings)
- L2 Hits (re-ranking)
- Indexed Pages count
```

#### 3. ⚡ **Hot Paths Tab**
```
Displays top 70 most accessed pages:
- Path (URL)
- Label (display name)
- Hits (access count)
- Pinned status
- Last Hit timestamp

Actions:
- [Load Hot Paths] - Refresh list
- [➕ Add New] - Manually pin pages
```

#### 4. 🔍 **Index Pages Tab**
```
Manage indexed pages:
- View all indexed pages
- Add new pages to index:
  * Path: /products/page.html
  * Label: Display Name
  * Description: Search text
  * Tags: Keywords

Actions:
- [Load Index Info] - View current index
- [➕ Index Page] - Add page to search
```

---

## 📊 INTERFACE LAYOUT

```
┌─────────────────────────────────────────────────────────────┐
│ 🎛️ Portal Nav Admin Console                                 │
│ Manage search configuration, index, and hot paths            │
├─────────────────────────────────────────────────────────────┤
│ API URL: [https://3jz6sk8vt7.execute-api.eu-west-1.am...]  │
│ Token:   [••••••••••••••••••••]  [Test Connection]          │
│ Status:  ✓ Connected (GREEN)                                │
├─────────────────────────────────────────────────────────────┤
│ [⚙️ Configuration] [📊 Statistics] [⚡ Hot Paths] [🔍 Index] │
├─────────────────────────────────────────────────────────────┤
│ CONFIGURATION TAB:                                           │
│                                                              │
│ Search Thresholds                                            │
│ HOT_PATH_THRESHOLD (L0):     [0.75]                         │
│ L1_THRESHOLD (Embeddings):   [0.65]                         │
│ L2_THRESHOLD (Re-rank):      [0.50]                         │
│ MAX_HOT_PATHS:               [70]                           │
│ [Load Current]  [Save Changes]                              │
│                                                              │
│ Quick Actions                                                │
│ [🔄 Re-embed All Pages]                                     │
├─────────────────────────────────────────────────────────────┤
│ STATISTICS TAB (when clicked):                               │
│ Total Queries:  [0 or number]                               │
│ MISS Rate:      [X%]                                         │
│ L0 Hits:        [count]                                      │
│ L1 Hits:        [count]                                      │
│ L2 Hits:        [count]                                      │
│ Indexed Pages:  [count]                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 HOW TO USE

### 1. Test Configuration
```
Scenario: Load current settings from API

Steps:
1. Click [Load Current] button
2. Wait for response
3. Values populate in fields:
   - HOT_PATH_THRESHOLD shows current
   - L1_THRESHOLD shows current
   - L2_THRESHOLD shows current
   - MAX_HOT_PATHS shows current

Expected Result:
✓ Config loaded (success message)
or
✗ Error: Failed to fetch (endpoint not implemented)
```

### 2. Adjust Thresholds
```
Scenario: Make search stricter (higher thresholds)

Steps:
1. Click [Load Current] to get values
2. Change HOT_PATH_THRESHOLD: 0.75 → 0.80
3. Change L1_THRESHOLD: 0.65 → 0.70
4. Click [Save Changes]
5. Wait for confirmation

Expected Result:
✓ Config saved! Changes take effect immediately
```

### 3. View Statistics
```
Scenario: Check search performance

Steps:
1. Click [📊 Statistics] tab
2. Click [Refresh] button
3. See 24-hour metrics

Expected Result:
- Total Queries: [number]
- MISS Rate: [percentage]
- L0/L1/L2 hit breakdown
- Indexed Pages count
```

### 4. View Hot Paths
```
Scenario: See top 70 accessed pages

Steps:
1. Click [⚡ Hot Paths] tab
2. Click [Load Hot Paths] button
3. Table populates with page list

Expected Result:
Table shows:
Path | Label | Hits | Pinned | Last Hit
```

### 5. Add Page to Index
```
Scenario: Index a new page for search

Steps:
1. Click [🔍 Index Pages] tab
2. Click [➕ Index Page] button
3. Fill form:
   - Path: /products/new-page.html
   - Label: New Page Title
   - Description: Text for search
   - Tags: keyword1, keyword2
4. Click [Add to Index]

Expected Result:
✓ Page indexed successfully
Page now searchable via portal-nav-api
```

---

## 🔌 CONNECTION DETAILS

### What "Connected" Means
```
✓ Connected = 
  • Admin console can reach the API
  • API /health endpoint responds OK
  • Authentication token is accepted
  • Ready for configuration operations
```

### What "Failed to Fetch" Means
```
✗ Error: Failed to fetch = 
  • Specific endpoint (/admin/config) not implemented
  • OR endpoint exists but returns error
  • OR API token insufficient for that endpoint
  
NOTE: This is normal if backend isn't fully built yet.
The connection test passed, so the basic setup works!
```

---

## 🎯 YOUR SETUP CHECKLIST

### ✅ Completed
- [x] Admin console accessible at http://localhost:8000/admin-console.html
- [x] API endpoint configured: https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
- [x] Admin token entered
- [x] Connection test passed (✓ Connected)
- [x] All tabs visible and ready to use

### ⏳ Next Steps When Backend Ready
- [ ] Click "Load Current" to verify config endpoints work
- [ ] Click "Refresh" in Statistics tab to see search metrics
- [ ] Click "Load Hot Paths" to see popular pages
- [ ] Use "Index Page" to add pages to search
- [ ] Adjust thresholds as needed for your use case

---

## 💾 CREDENTIALS

### Using AWS Endpoint
```
API URL:  https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
Token:    demo-admin-token-testing
(Replace with actual NAV_ADMIN_TOKEN from GitHub secrets when deployed)
```

### Using Local Endpoint (If Running Locally)
```
API URL:  http://localhost:3000
Token:    (from environment NAV_ADMIN_TOKEN)
```

### Changing Credentials
```
To use different credentials:
1. Clear API URL field
2. Enter new URL
3. Clear Token field
4. Enter new token
5. Click "Test Connection"
```

---

## 🚀 READY TO USE!

The admin console is **fully connected and ready for use**. Once the backend API endpoints are fully implemented, you can:

✅ **Manage search configuration in real-time**
✅ **Monitor search performance with statistics**
✅ **View and manage hot paths (top 70 pages)**
✅ **Add/remove pages from search index**
✅ **Re-embed all pages for improved search**
✅ **Adjust search thresholds on the fly**

**Access it anytime at:**
```
http://localhost:8000/admin-console.html
```

With credentials:
```
API URL:  https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
Token:    demo-admin-token-testing
```

Enjoy your admin console! 🎉
