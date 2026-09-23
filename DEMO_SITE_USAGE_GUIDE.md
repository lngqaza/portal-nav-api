# Demo Site Usage Guide

Complete guide to using the SafeGuard Insurance demo site with search and voice features.

---

## 🚀 QUICK START (2 minutes)

### Step 1: Start the Demo Site
```bash
# HTTP server already running on port 8000
# If not, run:
python -m http.server 8000 --bind 127.0.0.1
```

### Step 2: Open in Browser
```
http://localhost:8000/demo-site/
```

### Step 3: Explore
```
- Read content on home page
- Try text search: "file claim"
- Try voice search: Click 🎤 and speak
- Click results to navigate
```

---

## 📍 ACCESSING THE DEMO SITE

### URLs by Page

| Page | URL | Purpose |
|------|-----|---------|
| **Home** | `http://localhost:8000/demo-site/index.html` | Welcome page, features overview |
| **Car Insurance** | `http://localhost:8000/demo-site/products/car-insurance.html` | 3 car plans, coverage details |
| **Home Insurance** | `http://localhost:8000/demo-site/products/home-insurance.html` | 3 home plans, coverage details |
| **Life Insurance** | `http://localhost:8000/demo-site/products/life-insurance.html` | 3 life plans, medical options |
| **File a Claim** | `http://localhost:8000/demo-site/claims/file-claim.html` | 6-step claim process, online form |
| **Contact Support** | `http://localhost:8000/demo-site/support/contact.html` | 6 contact methods, FAQ |
| **Search Results** | `http://localhost:8000/demo-site/search-results.html` | Results page (auto-loads with ?q=query) |

### Direct Navigation

**Option A: Use Navigation Menu**
```
Every page has top menu:
🛡️ SafeGuard Insurance [Home] [Car Insurance] [Home Insurance] [Life Insurance] [File a Claim] [Support]

Click any link to navigate
```

**Option B: Use Search**
```
Every page has search box (text or voice)
Type or speak → Click Search → See results
Click "View Page →" to navigate
```

**Option C: Direct URL**
```
Copy/paste URL into browser address bar
Press Enter to navigate
```

---

## 🏠 HOME PAGE (`index.html`)

### What You'll See
```
┌────────────────────────────────────────────┐
│        🛡️ SafeGuard Insurance              │
│  Trusted Insurance Protection              │
│  [Explore Plans] button                    │
├────────────────────────────────────────────┤
│ Why Choose SafeGuard?                      │
│ ⚡ Fast Claims Processing                  │
│ 💰 Competitive Rates                       │
│ 🤝 24/7 Support                            │
│ 🔒 Secure & Reliable                       │
│ 📱 Mobile First                            │
│ 🎯 Customizable Plans                      │
├────────────────────────────────────────────┤
│ Quick Search                               │
│ [Search box] [🎤 Voice] [Search]          │
│ Try: "file claim" • "car insurance" ...    │
└────────────────────────────────────────────┘
```

### Interactive Elements
1. **"Explore Plans" Button** → Goes to car insurance page
2. **Search Box** → Text search functionality
3. **Voice Button** → Speak to search
4. **Navigation Menu** → Links to all pages
5. **Feature Cards** → Information only (no action)

### Actions You Can Do
```
✅ Scroll to read content
✅ Click navigation menu links
✅ Type in search box (text)
✅ Click 🎤 Voice button (speak)
✅ Click "Search" or press Enter
✅ Click "Explore Plans" button
```

---

## 🚗 CAR INSURANCE PAGE

### What You'll See
```
┌────────────────────────────────────────────┐
│ [Header with search] [Search box] [🎤]   │
│ Home / Car Insurance                       │
│                                            │
│ 🚗 Car Insurance Plans                    │
│ Protect your vehicle...                    │
│                                            │
│ Our Car Insurance Plans                    │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────┐
│ │ Basic       │ │ Standard    │ │ Premium │
│ │ $49/mo      │ │ $79/mo      │ │ $129/mo │
│ │ • Liability │ │ • Liability │ │ • All   │
│ │ • Damage    │ │ • Collision │ │ options │
│ │ • Support   │ │ • Medical   │ │ + more  │
│ │ • Roadside  │ │ • Priority  │ │ covered │
│ │ [Get Quote] │ │ [Get Quote] │ │ [Quote] │
│ └─────────────┘ └─────────────┘ └─────────┘
│                                            │
│ What's Covered?                            │
│ • Liability Protection                     │
│ • Collision Protection                     │
│ • Comprehensive Coverage                   │
│ • Medical Payments                         │
│ • Uninsured Motorist                       │
│ • Roadside Assistance                      │
│                                            │
│ Discounts Available                        │
│ ✓ Safe Driver Discount - Up to 15% off   │
│ ✓ Multi-Policy Bundling - Save up to 25% │
│ ✓ Good Student Discount                   │
│ ✓ Safety Feature Discount                 │
│ ✓ Low Mileage Discount                    │
│ ✓ Paperless Discount                      │
│                                            │
│ How to Get a Quote                         │
│ 1. Provide vehicle information             │
│ 2. Share your driving history              │
│ 3. Select coverage levels                  │
│ 4. Review and compare quotes               │
│ 5. Enroll online or call                   │
└────────────────────────────────────────────┘
```

### Interactive Elements
1. **Search Bar** (top right) → Search from this page
2. **Navigation Menu** → Go to other pages
3. **"Get Quote" Buttons** → Submit interest (form)
4. **Internal Links** → None (static demo)

### Actions You Can Do
```
✅ Scroll to read all sections
✅ Read plan comparison (Basic/Standard/Premium)
✅ View coverage details
✅ See discount options
✅ Use search box (top right)
✅ Search for related topics
```

### Useful Searches from This Page
```
Type: "home insurance"      → Get home insurance page
Type: "life insurance"      → Get life insurance page
Type: "file claim"          → Get claims page
Type: "contact support"     → Get support page
Type: "discounts"           → Find discount info
Type: "collision"           → Find collision coverage info
```

---

## 🏠 HOME INSURANCE PAGE

### What You'll See
```
Similar layout to car insurance page with:
- 3 Home Insurance Plans (Basic/Standard/Premium)
- $89/mo - $179/mo pricing
- Dwelling, Personal Property, Liability coverage
- Special coverages (Water, Hurricane, Earthquake, Flood)
- Safety Feature Discounts
```

### Sections
1. **Plans** - 3 tier options with pricing
2. **What's Covered** - Coverage types grid
3. **Special Coverages** - Optional protections
4. **Safety Discounts** - Discount options
5. **Setup Guide** - How to buy coverage

### Searches from This Page
```
Type: "homeowner coverage"  → Finds this page
Type: "house protection"    → Finds this page
Type: "water damage"        → Finds this page
Type: "flood insurance"     → Finds this page
Type: "earthquake"          → Finds this page
```

---

## ❤️ LIFE INSURANCE PAGE

### What You'll See
```
Similar layout with:
- 3 Life Insurance Plans (Term 10/20, Whole Life)
- $19/mo - $89/mo pricing
- Coverage amounts $100K to $5M+
- Term vs Whole Life comparison
- Medical underwriting options
```

### Sections
1. **Plans** - Term and Whole Life options
2. **Understanding Life Insurance** - Types explained
3. **Why Life Insurance Matters** - Benefits listed
4. **Medical Underwriting** - Options for underwriting
5. **Coverage Calculator** - Guidance for amounts

### Searches from This Page
```
Type: "term life"           → Finds this page
Type: "whole life"          → Finds this page
Type: "death benefit"       → Finds this page
Type: "beneficiary"         → Finds this page
Type: "coverage amount"     → Finds this page
```

---

## 📋 FILE A CLAIM PAGE

### What You'll See
```
┌────────────────────────────────────────────┐
│ [Header with search] [Search box] [🎤]   │
│ Home / File a Claim                        │
│                                            │
│ 📋 File a Claim                           │
│ We're here to help! Follow these steps...  │
│                                            │
│ Claim Filing Process (6 Steps)             │
│ 1️⃣  Report the Incident (24/7)            │
│ 2️⃣  Provide Details (fill form)            │
│ 3️⃣  Submit Documentation (photos/receipts) │
│ 4️⃣  Claims Review (our team checks)        │
│ 5️⃣  Settlement (payment within 48h)        │
│ 6️⃣  Follow-Up (customer satisfaction)      │
│                                            │
│ Quick Claim Filing Form                    │
│ [Policy Number]        [SG-1234567890]   │
│ [Claim Type]           [Auto / Home / ...]│
│ [Date of Incident]     [MM/DD/YYYY]      │
│ [Describe What Happened] [Text box...]   │
│ [Estimated Amount]     [0.00]            │
│ [Submit Claim]                            │
│                                            │
│ Contact Our Claims Team                    │
│ ☎️  Phone: 1-800-CLAIMS-1 (24/7)          │
│ 💬 Chat: M-F 8am-8pm EST                  │
│ 📧 Email: claims@safeguard.insurance      │
│                                            │
│ What You'll Need                           │
│ ✓ Policy number                            │
│ ✓ Date and time of incident                │
│ ✓ Description of what happened             │
│ ✓ Photos or videos of damage               │
│ ✓ Police report (if applicable)            │
│ ✓ Receipts or proof of loss                │
│                                            │
│ Claims FAQ                                 │
│ [Expandable items]                         │
│ Q: How long does processing take?          │
│ A: Most claims within 48 hours...          │
└────────────────────────────────────────────┘
```

### Interactive Elements
1. **Claim Form** → Fill and submit (demo only)
2. **Contact Info** → Phone/email/chat options
3. **FAQ Expandable Items** → Click to expand/collapse
4. **Search Box** (top) → Search from this page

### Actions You Can Do
```
✅ Scroll to read 6-step process
✅ Read "What You'll Need" checklist
✅ Fill out claim form (demo - doesn't actually submit)
✅ View contact methods
✅ Expand/collapse FAQ items
✅ Use search box
```

### Useful Searches from This Page
```
Type: "file claim"          → Finds this page (best match)
Type: "submit claim"        → Finds this page
Type: "accident"            → Finds this page
Type: "claims"              → Finds this page
Type: "phone support"       → Finds support page
Type: "contact"             → Finds support page
```

---

## 💬 CONTACT SUPPORT PAGE

### What You'll See
```
6 Contact Methods Displayed:
☎️  Phone: 1-800-234-5678 (24/7)
💬 Chat: M-F 8am-8pm EST (avg wait: 2 min)
📧 Email: support@safeguard.insurance (24h response)
🏢 Mail: SafeGuard Insurance, 123 Plaza, NY 10001
📱 Mobile App: In-app support available
🌐 Online Portal: 24/7 self-service

Contact Form:
[Full Name]
[Email Address]
[Phone Number]
[Subject dropdown]
[Message text area]
[Send Message]

FAQ Section:
- How do I reset my password?
- When will my payment be processed?
- How do I update my information?
- Can I cancel my policy?
- Do you offer discounts?
- What if I have a complaint?

Each FAQ item is clickable to expand/collapse
```

### Interactive Elements
1. **Contact Methods Grid** → Shows 6 options
2. **Message Form** → Fill and submit (demo)
3. **FAQ Items** → Click to expand/collapse
4. **Search Box** (top) → Search from this page

### Actions You Can Do
```
✅ Read all contact methods
✅ View response times
✅ Fill contact form (demo)
✅ Click FAQ items to expand
✅ Read FAQ answers
✅ Use search box
```

### Useful Searches from This Page
```
Type: "contact us"          → Finds this page
Type: "phone support"       → Finds this page
Type: "customer support"    → Finds this page
Type: "email"               → Finds this page
Type: "live chat"           → Finds this page
Type: "faq"                 → Finds this page
```

---

## 🔍 SEARCH RESULTS PAGE

### What You'll See (After Search)
```
┌────────────────────────────────────────────┐
│ [Header with search] [Search box] [🎤]   │
│ Found 3 results for "file claim"           │
│                                            │
│ 1. SafeGuard Insurance - Home              │
│    /demo-site/index.html                   │
│    Welcome to SafeGuard Insurance...       │
│    Relevance: [████████░] 85% | L0        │
│    [View Page →]                           │
│                                            │
│ 2. Car Insurance Plans                     │
│    /demo-site/products/car-insurance.html │
│    Protect your vehicle with...            │
│    Relevance: [█████████░] 92% | L0       │
│    [View Page →]                           │
│                                            │
│ 3. Home Insurance Plans                    │
│    /demo-site/products/home-insurance.html│
│    Protect your most valuable...           │
│    Relevance: [████████░] 88% | L1        │
│    [View Page →]                           │
└────────────────────────────────────────────┘
```

### Information Displayed
1. **Result Count** - How many results found
2. **Result Title** - Page name
3. **Result Path** - URL location
4. **Description** - Search index text
5. **Relevance Score** - Percentage + visual bar
6. **Layer Badge** - L0/L1/L2 (cache/search/rank)
7. **View Page Button** - Navigate to result

### Understanding Relevance & Layers

**Relevance Score (%):**
```
95-100% = Exact match
80-94%  = Very relevant
70-79%  = Relevant
60-69%  = Somewhat relevant
< 60%   = Low relevance (not shown by default)
```

**Layer Badges:**
```
L0 (Green badge)  = Hot path cache (~1ms)
                    Page frequently accessed
                    Instant result

L1 (Blue badge)   = Semantic embedding search (~50ms)
                    Semantic similarity match
                    Good relevance

L2 (Yellow badge) = Re-ranked by cross-encoder (~180ms)
                    Most relevant of all
                    Highest quality ranking
```

### Actions You Can Do
```
✅ Read all 3 results
✅ Compare relevance scores
✅ Check which layer returned result
✅ Click "View Page →" to navigate
✅ Use search box to refine search
✅ Try different search queries
```

---

## 🎤 VOICE SEARCH (DETAILED)

### Getting Started

**Step 1: Check Browser Support**
```
Supported:
✅ Chrome 25+
✅ Edge 79+
✅ Safari 14.1+
⚠️  Firefox 25+ (limited support)
✅ Opera 27+

Not supported:
❌ Internet Explorer
❌ Old Safari versions
```

**Step 2: Allow Microphone Permission**
```
First time you click 🎤:
1. Browser asks: "Allow access to microphone?"
2. Click: "Allow"
3. Permission saved for next time
```

### How to Use Voice Search

**Text Search (Traditional):**
```
1. See search box on any page
2. Type: "file claim"
3. Press: Enter OR Click "Search"
4. Results appear
```

**Voice Search (New):**
```
1. See search box with 🎤 Voice button
2. Click: 🎤 Voice button (GREEN)
3. Button turns: Orange → "⏹️ Listening..."
4. Status shows: "🎤 Listening... speak now"
5. Speak clearly: "file claim"
6. Transcription appears: "📝 Transcribed: 'file claim'"
7. Search box filled: "file claim"
8. Click: "Search" button
9. Results appear
```

### Voice Search Examples

**Example 1: Simple Search**
```
Speak:  "Car insurance"
Result: Car Insurance Plans page (92% L0)
Action: Click "View Page →"
```

**Example 2: Phrase Search**
```
Speak:  "How do I file a claim?"
Result: File a Claim page (95% L0)
Action: Click "View Page →"
```

**Example 3: Specific Topic**
```
Speak:  "Phone support"
Result: Contact Support page (81% L1)
Action: Click "View Page →"
```

**Example 4: Product Search**
```
Speak:  "Life insurance options"
Result: Life Insurance Plans page (79% L1)
Action: Click "View Page →"
```

### Troubleshooting Voice Search

**"Microphone access denied"**
```
Solution 1: Allow permission when browser asks
Solution 2: Check browser settings:
  - Chrome/Edge: Settings → Privacy → Site Settings → Microphone → Allow
  - Safari: Settings → Privacy → Microphone
  - Firefox: Settings → Privacy & Security → Permissions
Solution 3: Refresh page and try again
```

**"Voice not recognized"**
```
Solution 1: Speak louder and clearer
Solution 2: Check microphone works (use OS sound settings)
Solution 3: Try different words
Solution 4: Use text search instead
```

**"Microphone not working"**
```
Solution 1: Check microphone is plugged in
Solution 2: Check system microphone settings
Solution 3: Try different browser
Solution 4: Restart browser
```

**"No results found"**
```
Solution 1: Refine search terms
Solution 2: Try different words
Solution 3: Use text search for comparison
```

---

## 📊 SEARCH EXAMPLES WITH EXPECTED RESULTS

### Example 1: "file claim"
```
Query:  "file claim"
Results (3):
  1. Home page (85% L0)
  2. Car Insurance (92% L0)  
  3. Home Insurance (88% L1)

Best Result: File a Claim page
Why: Contains "file" and "claim" directly

Navigation: Click "View Page →" on result 1 or search again
```

### Example 2: "car insurance"
```
Query:  "car insurance"
Results (3):
  1. Car Insurance Plans (92% L0)
  2. Home Insurance Plans (88% L1)
  3. Life Insurance Plans (79% L1)

Best Result: Car Insurance Plans
Why: Direct match with high relevance

Navigation: Click result 1 to view car plans
```

### Example 3: "phone support"
```
Query:  "phone support"
Results (3):
  1. Contact Support (81% L1)
  2. File a Claim (75% L1)
  3. Home page (68% L1)

Best Result: Contact Support page
Why: Shows phone contact info (1-800-234-5678)

Navigation: Click result 1 to get phone number
```

### Example 4: "homeowner coverage"
```
Query:  "homeowner coverage"
Results (3):
  1. Home Insurance Plans (88% L1)
  2. Home page (65% L1)
  3. Car Insurance Plans (45% L2)

Best Result: Home Insurance Plans
Why: Perfect match for homeowner/home/coverage

Navigation: Click result 1 to see home plans
```

### Example 5: "submit claim"
```
Query:  "submit claim"
Results (3):
  1. File a Claim (95% L0)
  2. Contact Support (60% L1)
  3. Home page (50% L1)

Best Result: File a Claim page
Why: Exact page for filing/submitting claims

Navigation: Click result 1 to file claim form
```

### Example 6: "discounts"
```
Query:  "discounts"
Results (3):
  1. Car Insurance Plans (80% L1)
  2. Home Insurance Plans (75% L1)
  3. Life Insurance Plans (50% L1)

All Results: Show discount information
Why: All product pages list available discounts

Navigation: Click any to see discount details
```

---

## 🧪 TESTING CHECKLIST

### Navigation Test
```
✅ Home page loads
✅ All navigation links work
✅ Breadcrumb trail shows on product pages
✅ Can navigate between all 6 pages
✅ Back button works
```

### Text Search Test
```
✅ Search box visible on all pages
✅ Can type in search box
✅ Search button clickable
✅ Results page loads after search
✅ Results show 3 items
✅ Relevance scores displayed
✅ Layer badges shown (L0/L1/L2)
✅ "View Page →" buttons work
✅ Click result navigates to page
```

### Voice Search Test
```
✅ 🎤 Voice button visible on all pages
✅ Button is green color
✅ Clicking button asks for microphone permission
✅ Permission dialog appears once
✅ After permission, button turns orange
✅ Microphone icon shows "Listening..."
✅ Can speak search query
✅ Transcribed text appears in box
✅ Text is accurate to spoken words
✅ Click Search button works
✅ Results page shows after voice search
✅ Button returns to green after search
```

### Content Test
```
✅ All text readable and formatted
✅ All images/icons display
✅ Feature cards visible
✅ Plan comparison tables show
✅ Forms display fields (claim, contact)
✅ FAQ items expand/collapse
✅ All links internal (no external links)
✅ Mobile responsive (try on phone)
```

### Search Accuracy Test
```
✅ "file claim" → Shows File a Claim (top result)
✅ "car insurance" → Shows Car Insurance (top result)
✅ "home insurance" → Shows Home Insurance (top result)
✅ "life insurance" → Shows Life Insurance (top result)
✅ "contact support" → Shows Contact Support (top result)
✅ "phone support" → Shows Contact Support (top result)
✅ "submit claim" → Shows File a Claim (top result)
✅ "discounts" → Shows product pages (top results)
```

### Performance Test
```
✅ Pages load quickly (< 2 seconds)
✅ Search results appear (< 1 second)
✅ Voice transcription real-time
✅ No console errors
✅ No broken links
✅ Navigation smooth
✅ No lag when typing search
```

---

## 💡 TIPS & TRICKS

### Tip 1: Try Different Search Terms
```
Instead of:      Try:
"insurance"      "car insurance" (more specific)
"help"           "contact support" or "file claim"
"plans"          "life insurance plans"
```

### Tip 2: Use Breadcrumb Navigation
```
On any product page:
Home / Car Insurance
       ↑ Click "Home" to go back
Click "Car Insurance" to stay
```

### Tip 3: Voice Search Tips
```
✅ Speak clearly and naturally
✅ Avoid background noise
✅ Pause between words if unsure
✅ Check transcription before searching
✅ Use text search if voice fails
```

### Tip 4: Compare Prices
```
On product pages:
- See 3 plan tiers side by side
- Compare pricing
- Compare features
- Check discounts available
```

### Tip 5: Find Contact Info Fast
```
Search for:
- "phone" → Shows phone number
- "email" → Shows email address
- "chat" → Shows chat info
- "contact" → Shows all methods
```

### Tip 6: Claim Info Quick Access
```
Navigate directly:
1. Click "File a Claim" in menu
2. Or search "file claim"
3. See 6-step process
4. Fill form to submit claim
5. Get phone number if needed
```

---

## 🎯 COMMON USER JOURNEYS

### Journey 1: Get Car Insurance Quote
```
1. Open: http://localhost:8000/demo-site/
2. Click: "Explore Plans" button
3. See: Car Insurance Plans (3 options)
4. Read: Plan details and pricing
5. Action: Click "Get Quote" button
6. Result: Form pre-filled, ready to submit
```

### Journey 2: File an Insurance Claim
```
1. Search: "file claim"
2. Results: File a Claim (top result)
3. Click: "View Page →"
4. See: 6-step process explained
5. Read: "What You'll Need" checklist
6. Action: Fill claim form
7. Contact: Use phone/chat/email options
```

### Journey 3: Compare All Insurance Types
```
1. Home: http://localhost:8000/demo-site/
2. Search: "car insurance"
3. Read: Car plans ($49-$129/mo)
4. Search: "home insurance"  
5. Read: Home plans ($89-$179/mo)
6. Search: "life insurance"
7. Read: Life plans ($19-$89/mo)
8. Compare: Pricing and features
```

### Journey 4: Get Support Contact Info
```
1. Search: "phone support"
2. See: Contact Support page (top)
3. Click: "View Page →"
4. See: 6 contact methods
5. Find: Phone number, email, chat
6. Choose: Preferred contact method
7. Action: Call/email/chat to support
```

### Journey 5: Find Discounts
```
1. Search: "discounts"
2. See: Product pages (all have discounts)
3. Click: Car Insurance result
4. Scroll: To "Discounts Available"
5. Read: 6 discount options
6. Calculate: Potential savings
```

---

## 🎓 LEARNING PROGRESSION

### Level 1: Beginner (5 min)
```
✅ Access home page
✅ Read main content
✅ Try one text search
✅ Click one result
✅ Navigate back
```

### Level 2: Intermediate (15 min)
```
✅ Use menu navigation
✅ Try multiple searches
✅ Explore different pages
✅ Compare products/plans
✅ Read FAQ sections
```

### Level 3: Advanced (30 min)
```
✅ Use voice search
✅ Refine search terms
✅ Fill out demo forms
✅ Expand FAQ items
✅ View all pages
✅ Test all features
```

### Level 4: Expert (Testing)
```
✅ Complete full testing checklist
✅ Test on mobile device
✅ Test different browsers
✅ Verify all search results
✅ Check page performance
✅ Document any issues
```

---

## 📱 MOBILE EXPERIENCE

### Responsive Design
```
Desktop (1200px+):
- Full navigation menu
- All content visible
- Optimal reading

Tablet (768px - 1199px):
- Adjusted layout
- Touch-friendly buttons
- Content reflows

Mobile (< 768px):
- Hamburger menu (☰)
- Stacked content
- Large touch targets
- Vertical layout
```

### Testing on Mobile
```
1. Open in phone browser:
   http://localhost:8000/demo-site/

2. Try:
   - Tap menu hamburger (☰)
   - Tap navigation links
   - Tap search box
   - Tap 🎤 Voice button
   - Speak search query
   - Tap search results

3. Check:
   - All content readable
   - Buttons easy to tap
   - No horizontal scroll
   - Layout looks good
```

---

## ✨ SUMMARY

The demo site includes:
✅ **6 interconnected pages** with professional insurance content
✅ **Text search** with keyword matching
✅ **Voice search** with real-time transcription
✅ **Search results page** with relevance scoring
✅ **Layer indicators** (L0/L1/L2 cascade)
✅ **Responsive design** (desktop/tablet/mobile)
✅ **Interactive forms** (demo - no actual submission)
✅ **Complete navigation** (menu + breadcrumbs + search)
✅ **FAQ sections** with expandable items
✅ **Professional branding** (SafeGuard Insurance)

**Start exploring now at:** `http://localhost:8000/demo-site/` 🚀
