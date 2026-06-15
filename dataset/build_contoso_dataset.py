# ContosoRetail Push Dataset — auto-generated 13-table sample data
#
# Usage:
#   python build_contoso_dataset.py <workspace_id> [tenant_id]
#
# Prerequisites:
#   pip install requests faker
#   az login (Azure CLI, for Power BI token)
#
# Outputs:
#   dataset_id.txt — the new dataset ID (read by deploy skills)
#
# The script creates a Power BI push dataset named "ContosoRetail" with 13 tables
# and 500 rows each. Data is seeded (random.seed(42)) for reproducibility.
import random, datetime, json, urllib.request, urllib.error, subprocess, sys, time

random.seed(42)

GROUP_ID   = sys.argv[1]  # Power BI workspace (group) ID
TENANT_ID  = sys.argv[2] if len(sys.argv) > 2 else None  # optional: tenant ID for az CLI
BASE       = "https://api.powerbi.com/v1.0/myorg"

# ── helpers ──────────────────────────────────────────────────────────────────

def get_token():
    print("Getting Bearer token …")
    r = subprocess.run(
        ["az","account","get-access-token",
         "--resource","https://analysis.windows.net/powerbi/api",
         "--tenant", TENANT_ID,
         "--query","accessToken","-o","tsv"],
        capture_output=True, text=True, shell=True)
    if r.returncode != 0:
        raise RuntimeError("az failed: " + r.stderr)
    return r.stdout.strip()

def api(method, url, body=None, token=None, expect=(200,201,204)):
    data = json.dumps(body).encode() if body is not None else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type",  "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode(errors="replace")
        if e.code not in expect:
            raise RuntimeError(f"HTTP {e.code} {method} {url}\n{body_txt}")
        return {}

def rand_date(start="2023-01-01", end="2025-12-31"):
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    delta = (e - s).days
    return (s + datetime.timedelta(days=random.randint(0, delta))).isoformat() + "T00:00:00Z"

def fmt_id(prefix, n, width):
    return f"{prefix}{str(n).zfill(width)}"

# ── region / city mapping ─────────────────────────────────────────────────────

REGIONS = ["Northeast","Southeast","Midwest","Southwest","West"]
CITIES = {
    "Northeast": ["New York","Boston","Philadelphia","Hartford","Providence"],
    "Southeast": ["Atlanta","Miami","Charlotte","Nashville","Orlando"],
    "Midwest":   ["Chicago","Detroit","Minneapolis","Columbus","Indianapolis"],
    "Southwest": ["Houston","Dallas","Phoenix","San Antonio","Austin"],
    "West":      ["Los Angeles","Seattle","San Francisco","Denver","Portland"],
}

# ── table generators ──────────────────────────────────────────────────────────

FIRST_NAMES = ["James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda",
               "William","Barbara","David","Susan","Richard","Jessica","Joseph","Sarah",
               "Thomas","Karen","Charles","Lisa","Christopher","Nancy","Daniel","Betty",
               "Matthew","Margaret","Anthony","Sandra","Mark","Ashley","Donald","Dorothy",
               "Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle"]
LAST_NAMES  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
               "Wilson","Anderson","Taylor","Thomas","Moore","Jackson","Martin","Lee",
               "Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson",
               "Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill",
               "Flores","Green","Adams","Nelson","Baker","Hall","Rivera"]

def rand_name():
    return random.choice(FIRST_NAMES) + " " + random.choice(LAST_NAMES)

AGE_GROUPS = ["18-24","25-34","35-44","45-54","55+"]
GENDERS    = ["Male","Female","Non-binary"]

PROD_NAMES = {
    "Electronics":       ["4K Smart TV","Wireless Earbuds","Laptop Pro","Gaming Mouse","USB-C Hub",
                          "Mechanical Keyboard","Webcam HD","Smart Speaker","Tablet 10in","Phone Stand"],
    "Apparel":           ["Slim-Fit Jeans","Floral Dress","Polo Shirt","Running Shorts","Wool Sweater",
                          "Leather Jacket","Yoga Pants","Baseball Cap","Chino Trousers","Hoodie"],
    "Home & Garden":     ["Garden Hose","Throw Pillow","Scented Candle","Cast Iron Pan","Planter Pot",
                          "Desk Lamp","Bath Towel Set","Storage Basket","Wall Clock","Electric Kettle"],
    "Sports & Outdoors": ["Yoga Mat","Hiking Boots","Water Bottle","Camping Tent","Cycling Helmet",
                          "Jump Rope","Resistance Bands","Running Shoes","Sleeping Bag","Dumbbell Set"],
    "Beauty":            ["Moisturizer SPF30","Lip Gloss Set","Shampoo Pro","Mascara Volume","Face Serum",
                          "Nail Polish Kit","Hair Dryer","Sunscreen SPF50","Perfume Bloom","Toner Refresh"],
}
SUBCATS = {
    "Electronics":       ["Audio","Computing","Gaming","Accessories","Wearables"],
    "Apparel":           ["Bottoms","Dresses","Tops","Outerwear","Activewear"],
    "Home & Garden":     ["Outdoor","Kitchen","Lighting","Decor","Storage"],
    "Sports & Outdoors": ["Fitness","Footwear","Camping","Cycling","Hydration"],
    "Beauty":            ["Skincare","Makeup","Haircare","Fragrance","Sun Care"],
}
BRANDS = {
    "Electronics":       ["TechNova","CircuitEdge","Luminos","QuantumX","ByteWave"],
    "Apparel":           ["UrbanThread","StyleForward","FitWear","ClassicLine","ActiveGear"],
    "Home & Garden":     ["HomeHaven","GardenPro","CozyCraft","NestWorks","GreenLeaf"],
    "Sports & Outdoors": ["TrailBlazer","PeakForm","ActiveZone","OutdoorPro","SwiftStep"],
    "Beauty":            ["GlowLab","PureSkin","RadiantCo","LuxeBeauty","NaturalGlow"],
}

DEPTS  = ["Sales","Marketing","Operations","Customer Service","Finance","IT","HR"]
TITLES = {
    "Sales":            ["Sales Rep","Account Executive","Sales Manager","Regional Director"],
    "Marketing":        ["Marketing Analyst","Campaign Manager","Brand Strategist","CMO"],
    "Operations":       ["Operations Analyst","Logistics Coord","Supply Chain Mgr","COO"],
    "Customer Service": ["Support Agent","CS Supervisor","CS Manager","VP Customer Success"],
    "Finance":          ["Financial Analyst","Controller","CFO","Accountant"],
    "IT":               ["Software Engineer","DevOps Engineer","IT Manager","CTO"],
    "HR":               ["HR Coordinator","Recruiter","HR Manager","Chief People Officer"],
}

SUPPORT_CATS = ["Returns","Billing","Shipping","Product Defect","Account","General"]
PRIORITIES   = ["Low","Medium","High","Critical"]
SUP_STATUS   = ["Open","In Progress","Resolved","Escalated"]
SUPPORT_CH   = ["Phone","Email","Chat","Social"]

SUPPLIERS = {f"SUP{str(i).zfill(2)}": f"Supplier {chr(64+i)}" for i in range(1,16)}
SUPP_CATS  = ["Electronics","Apparel","Home & Garden","Sports & Outdoors","Beauty"]

DAYS_OF_WEEK = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

CAMP_CHANNELS = ["Email","Social","Paid Search","Display","Influencer"]
CAMP_NAMES    = [
    "Spring Sale","Summer Blast","Back to School","Fall Frenzy","Holiday Rush",
    "New Year Deal","Valentine Special","Mother Day","Father Day","Labor Day Sale",
    "Black Friday","Cyber Monday","Flash Deal","Brand Awareness","Loyalty Boost",
    "Win-Back","Product Launch","Season Kickoff","Year-End Clearance","Referral Drive",
]

# ── dim_customers ─────────────────────────────────────────────────────────────

def gen_customers():
    rows = []
    scores = [random.random() for _ in range(500)]
    threshold = sorted(scores, reverse=True)[99]  # top 20%
    for i in range(500):
        cid   = fmt_id("C", i+1, 3)
        region= random.choice(REGIONS)
        seg   = "VIP" if scores[i] >= threshold else random.choice(["Regular","At-Risk","New"])
        ltv   = {"VIP": random.uniform(2000,8000),
                 "Regular": random.uniform(400,1500),
                 "At-Risk":  random.uniform(50,400),
                 "New":      random.uniform(10,200)}[seg]
        rows.append({
            "customer_id":    cid,
            "full_name":      rand_name(),
            "age_group":      random.choice(AGE_GROUPS),
            "gender":         random.choice(GENDERS),
            "region":         region,
            "city":           random.choice(CITIES[region]),
            "signup_date":    rand_date(),
            "segment":        seg,
            "lifetime_value": round(ltv, 2),
            "email_opt_in":   random.choice(["Yes","Yes","Yes","No"]),  # 75% Yes
        })
    return rows

# ── dim_products ──────────────────────────────────────────────────────────────

CATEGORIES = list(PROD_NAMES.keys())
MARGIN_RANGE = {
    "Electronics":       (15, 20),
    "Apparel":           (35, 45),
    "Home & Garden":     (40, 50),
    "Sports & Outdoors": (30, 40),
    "Beauty":            (55, 65),
}

def gen_products():
    rows = []
    for i in range(500):
        pid  = fmt_id("P", i+1, 3)
        cat  = CATEGORIES[i % len(CATEGORIES)]
        name = random.choice(PROD_NAMES[cat]) + f" v{random.randint(1,5)}"
        cost = round(random.uniform(5, 200), 2)
        lo, hi = MARGIN_RANGE[cat]
        margin  = round(random.uniform(lo, hi), 1)
        price   = round(cost / (1 - margin/100), 2)
        rows.append({
            "product_id":   pid,
            "product_name": name,
            "category":     cat,
            "subcategory":  random.choice(SUBCATS[cat]),
            "brand":        random.choice(BRANDS[cat]),
            "unit_cost":    cost,
            "list_price":   price,
            "margin_pct":   margin,
            "is_active":    "Yes" if random.random() < 0.9 else "No",
            "launch_year":  random.randint(2018, 2024),
        })
    return rows

# ── dim_stores ────────────────────────────────────────────────────────────────

STORE_TYPES = ["Flagship","Standard","Outlet"]
MONTHS_25 = []
d = datetime.date(2023, 1, 1)
for _ in range(25):
    MONTHS_25.append(f"{d.year}-{str(d.month).zfill(2)}")
    d = datetime.date(d.year + (d.month // 12), ((d.month % 12) + 1), 1)

STORE_META = []
for reg in REGIONS:
    for j in range(4):
        sid = fmt_id("ST", len(STORE_META)+1, 2)
        STORE_META.append({
            "store_id":   sid,
            "store_name": f"{random.choice(CITIES[reg])} {random.choice(STORE_TYPES)}",
            "region":     reg,
            "city":       random.choice(CITIES[reg]),
            "store_type": random.choice(STORE_TYPES),
        })

def gen_stores():
    rows = []
    idx  = 1
    for sm in STORE_META:
        for mo in MONTHS_25:
            yr   = int(mo[:4])
            west = sm["region"] == "West"
            rev  = round(random.uniform(80000,150000) * (0.78 if west else 1.0), 2)
            txn  = random.randint(500,3000)
            rows.append({
                "snapshot_id":          fmt_id("SS", idx, 3),
                "store_id":             sm["store_id"],
                "store_name":           sm["store_name"],
                "region":               sm["region"],
                "city":                 sm["city"],
                "store_type":           sm["store_type"],
                "month":                mo,
                "year":                 yr,
                "monthly_revenue":      rev,
                "monthly_transactions": txn,
                "avg_basket_size":      round(rev/txn, 2),
                "return_rate":          round(random.uniform(0.12,0.18) if west else random.uniform(0.06,0.10), 4),
                "headcount":            random.randint(10, 50),
            })
            idx += 1
    return rows[:500]

# ── dim_employees ─────────────────────────────────────────────────────────────

def gen_employees():
    rows = []
    eids = [fmt_id("E", i+1, 3) for i in range(500)]
    for i in range(500):
        dept = random.choice(DEPTS)
        reg  = random.choice(REGIONS)
        hire = rand_date("2015-01-01","2024-12-31")
        h_dt = datetime.date.fromisoformat(hire[:10])
        tenure = round((datetime.date(2025,1,1) - h_dt).days / 365.25, 1)
        salary = round(random.uniform(40000, 140000), 2)
        rows.append({
            "employee_id":        eids[i],
            "full_name":          rand_name(),
            "department":         dept,
            "title":              random.choice(TITLES[dept]),
            "region":             reg,
            "hire_date":          hire,
            "salary":             salary,
            "performance_rating": random.choice(["Exceeds","Meets","Meets","Below"]),
            "tenure_years":       tenure,
            "manager_id":         random.choice(eids[:50]),
        })
    return rows

# ── fact_orders ───────────────────────────────────────────────────────────────

CHANNELS   = ["In-Store","Online","Mobile App"]
ORD_STATUS = ["Completed","Returned","Cancelled","Pending"]
CUST_IDS   = [fmt_id("C", i+1, 3) for i in range(500)]
STORE_IDS  = [sm["store_id"] for sm in STORE_META]

def gen_orders():
    rows = []
    for i in range(500):
        dt = rand_date()
        d  = datetime.date.fromisoformat(dt[:10])
        mo = d.month
        sub = round(random.uniform(20,500), 2)
        disc = round(sub * random.uniform(0,0.15), 2)
        tax  = round((sub-disc)*0.08, 2)
        q = f"Q{(mo-1)//3+1}"
        rows.append({
            "order_id":       fmt_id("O", i+1, 4),
            "customer_id":    random.choice(CUST_IDS),
            "channel":        random.choice(CHANNELS),
            "store_id":       random.choice(STORE_IDS),
            "order_date":     dt,
            "year":           d.year,
            "month":          mo,
            "quarter":        q,
            "subtotal":       sub,
            "discount_amount":disc,
            "tax":            tax,
            "total_amount":   round(sub-disc+tax, 2),
            "status":         random.choices(ORD_STATUS,[0.75,0.12,0.08,0.05])[0],
        })
    return rows

# ── fact_order_items ──────────────────────────────────────────────────────────

PROD_IDS = [fmt_id("P", i+1, 3) for i in range(500)]
ORDER_IDS= [fmt_id("O", i+1, 4) for i in range(500)]

RET_RATES = {"Apparel":0.25,"Electronics":0.10,"Beauty":0.02,"Home & Garden":0.15,"Sports & Outdoors":0.15}

def gen_order_items():
    rows = []
    for i in range(500):
        cat = CATEGORIES[i % len(CATEGORIES)]
        qty = random.randint(1,5)
        up  = round(random.uniform(10,300), 2)
        dp  = round(random.uniform(0,0.20), 4)
        rows.append({
            "item_id":     fmt_id("I", i+1, 4),
            "order_id":    random.choice(ORDER_IDS),
            "product_id":  random.choice(PROD_IDS),
            "category":    cat,
            "quantity":    qty,
            "unit_price":  up,
            "discount_pct":dp,
            "line_total":  round(qty*up*(1-dp), 2),
            "returned":    "Yes" if random.random() < RET_RATES[cat] else "No",
        })
    return rows

# ── fact_returns ──────────────────────────────────────────────────────────────

RETURN_REASONS = {
    "Apparel":           ["Wrong Size","Wrong Size","Changed Mind","Not as Described"],
    "Electronics":       ["Defective","Defective","Not as Described","Damaged in Shipping"],
    "Beauty":            ["Changed Mind","Not as Described","Defective","Damaged in Shipping"],
    "Home & Garden":     ["Changed Mind","Damaged in Shipping","Not as Described","Defective"],
    "Sports & Outdoors": ["Changed Mind","Wrong Size","Not as Described","Defective"],
}

def gen_returns():
    rows = []
    # West region = 30% of returns
    regions_dist = ["West"]*3 + ["Northeast","Southeast","Midwest","Southwest"]
    # Apparel = 35% of returns
    cats_dist = ["Apparel"]*35 + CATEGORIES*13  # rough
    for i in range(500):
        cat = random.choice(cats_dist)
        reg = random.choice(regions_dist)
        dt  = rand_date()
        rows.append({
            "return_id":      fmt_id("R", i+1, 4),
            "order_id":       random.choice(ORDER_IDS),
            "product_id":     random.choice(PROD_IDS),
            "customer_id":    random.choice(CUST_IDS),
            "return_date":    dt,
            "days_to_return": random.randint(1,30),
            "category":       cat,
            "return_reason":  random.choice(RETURN_REASONS.get(cat,["Changed Mind","Defective","Not as Described"])),
            "refund_amount":  round(random.uniform(10,400), 2),
            "restocking_fee": round(random.uniform(0,20), 2),
            "region":         reg,
        })
    return rows

# ── fact_inventory ────────────────────────────────────────────────────────────

STOCKOUT_RATE = {"Sports & Outdoors":0.20,"Electronics":0.07,"Apparel":0.06,"Home & Garden":0.05,"Beauty":0.05}

def gen_inventory():
    rows = []
    for i in range(500):
        cat  = CATEGORIES[i % len(CATEGORIES)]
        qoh  = random.randint(0,500)
        rop  = random.randint(20,100)
        dos  = round(qoh / max(random.uniform(5,30),1), 1)
        so   = "Yes" if random.random() < STOCKOUT_RATE.get(cat,0.06) else "No"
        over = "Yes" if qoh > rop*3 else "No"
        rows.append({
            "snapshot_id":      fmt_id("INV", i+1, 3),
            "product_id":       random.choice(PROD_IDS),
            "category":         cat,
            "store_id":         random.choice(STORE_IDS),
            "snapshot_date":    rand_date(),
            "quantity_on_hand": qoh,
            "reorder_point":    rop,
            "days_of_supply":   dos,
            "stockout_flag":    so,
            "overstock_flag":   over,
        })
    return rows

# ── fact_marketing_campaigns ──────────────────────────────────────────────────

def ctr_roi(channel, year):
    if channel == "Email":
        ctr = {"2023": random.uniform(0.030,0.040), "2024": random.uniform(0.018,0.025), "2025": random.uniform(0.010,0.015)}[str(year)]
        roi = {"2023": random.uniform(2.5,3.5), "2024": random.uniform(1.5,2.0), "2025": random.uniform(0.8,1.2)}[str(year)]
    elif channel == "Social":
        ctr = random.uniform(0.020,0.030)
        roi = {"2023": random.uniform(1.5,2.0), "2024": random.uniform(2.5,3.5), "2025": random.uniform(3.5,4.5)}[str(year)]
    else:
        ctr = random.uniform(0.005,0.020)
        roi = random.uniform(1.0,3.0)
    return round(ctr,4), round(roi,2)

def gen_marketing():
    rows = []
    campaigns = [{"id":fmt_id("CAM",i+1,2),"name":CAMP_NAMES[i],"channel":random.choice(CAMP_CHANNELS)} for i in range(20)]
    idx = 1
    for cam in campaigns:
        for wk in range(1,26):  # 25 weeks per campaign → 500 total
            yr  = random.choice([2023,2024,2025])
            bgt = round(random.uniform(5000,50000),2)
            spd = round(bgt * random.uniform(0.8,1.0),2)
            imp = random.randint(10000,500000)
            ctr,roi_v = ctr_roi(cam["channel"],yr)
            clk = int(imp*ctr)
            conv= int(clk*random.uniform(0.02,0.10))
            rev = round(spd*roi_v,2)
            rows.append({
                "row_id":            fmt_id("MKT",idx,4),
                "campaign_id":       cam["id"],
                "campaign_name":     cam["name"],
                "channel":           cam["channel"],
                "start_date":        rand_date(),
                "week_number":       wk,
                "year":              yr,
                "budget_usd":        bgt,
                "spend_usd":         spd,
                "impressions":       imp,
                "clicks":            clk,
                "ctr":               ctr,
                "conversions":       conv,
                "revenue_attributed":rev,
                "roi":               roi_v,
            })
            idx += 1
    return rows[:500]

# ── fact_website_sessions ─────────────────────────────────────────────────────

SOURCES  = ["Organic","Email","Social","Paid","Direct","Referral"]
DEVICES  = ["Desktop","Mobile","Tablet"]

def gen_web_sessions():
    rows = []
    for i in range(500):
        dt = rand_date()
        d  = datetime.date.fromisoformat(dt[:10])
        src= random.choice(SOURCES)
        conv = random.random() < 0.08
        rows.append({
            "session_id":       fmt_id("WS", i+1, 4),
            "session_date":     dt,
            "year":             d.year,
            "month":            d.month,
            "source":           src,
            "device":           random.choice(DEVICES),
            "region":           random.choice(REGIONS),
            "page_views":       random.randint(1,20),
            "time_on_site_mins":round(random.uniform(0.5,30),1),
            "bounced":          "No" if conv else random.choice(["Yes","No"]),
            "converted":        "Yes" if conv else "No",
            "order_value":      round(random.uniform(20,500),2) if conv else 0.0,
        })
    return rows

# ── fact_support_tickets ──────────────────────────────────────────────────────

# Campaign spike months: March, June, September, November → lower satisfaction
SPIKE_MONTHS = {3,6,9,11}

def gen_support_tickets():
    rows = []
    for i in range(500):
        dt = rand_date()
        d  = datetime.date.fromisoformat(dt[:10])
        spike = d.month in SPIKE_MONTHS
        sat  = round(random.uniform(1.0,3.5) if spike else random.uniform(3.0,5.0), 1)
        rows.append({
            "ticket_id":        fmt_id("TKT", i+1, 4),
            "customer_id":      random.choice(CUST_IDS),
            "created_date":     dt,
            "year":             d.year,
            "month":            d.month,
            "category":         random.choice(SUPPORT_CATS),
            "priority":         random.choice(PRIORITIES),
            "status":           random.choice(SUP_STATUS),
            "resolution_days":  round(random.uniform(0.5,15),1),
            "satisfaction_score":sat,
            "channel":          random.choice(SUPPORT_CH),
            "region":           random.choice(REGIONS),
        })
    return rows

# ── fact_supplier_performance ─────────────────────────────────────────────────

BAD_SUPPLIERS = {"SUP03","SUP07"}

def gen_supplier_perf():
    rows = []
    sup_keys = list(SUPPLIERS.keys())
    for i in range(500):
        sid  = random.choice(sup_keys)
        dt   = rand_date()
        d    = datetime.date.fromisoformat(dt[:10])
        bad  = sid in BAD_SUPPLIERS
        on_t = "No" if random.random() < (0.37 if bad else 0.07) else "Yes"
        qsc  = round(random.uniform(3,7) if bad else random.uniform(7,10),1)
        dft  = round(random.uniform(0.05,0.15) if bad else random.uniform(0.01,0.05),3)
        fil  = round(random.uniform(0.70,0.85) if bad else random.uniform(0.90,0.99),3)
        q    = f"Q{(d.month-1)//3+1}"
        rows.append({
            "record_id":      fmt_id("SUP", i+1, 4),
            "supplier_id":    sid,
            "supplier_name":  SUPPLIERS[sid],
            "category":       random.choice(SUPP_CATS),
            "order_date":     dt,
            "year":           d.year,
            "quarter":        q,
            "po_value":       round(random.uniform(5000,100000),2),
            "lead_time_days": random.randint(2,30),
            "on_time_flag":   on_t,
            "quality_score":  qsc,
            "defect_rate":    dft,
            "fill_rate":      fil,
        })
    return rows

# ── fact_store_traffic ────────────────────────────────────────────────────────

def gen_store_traffic():
    rows = []
    for i in range(500):
        sm   = random.choice(STORE_META)
        dt   = rand_date()
        promo= random.random() < 0.25
        west = sm["region"] == "West"
        base_cr  = random.uniform(0.08,0.14) if west else random.uniform(0.18,0.28)
        cr   = round(base_cr * (random.uniform(1.20,1.40) if promo else 1.0), 4)
        ft   = int(random.randint(200,2000) * (random.uniform(1.20,1.40) if promo else 1.0))
        txn  = int(ft * cr)
        rows.append({
            "record_id":       fmt_id("TRF", i+1, 4),
            "store_id":        sm["store_id"],
            "store_name":      sm["store_name"],
            "region":          sm["region"],
            "traffic_date":    dt,
            "day_of_week":     DAYS_OF_WEEK[datetime.date.fromisoformat(dt[:10]).weekday()],
            "foot_traffic":    ft,
            "transactions":    txn,
            "conversion_rate": cr,
            "avg_basket_size": round(random.uniform(25,120),2),
            "promo_active":    "Yes" if promo else "No",
        })
    return rows

# ── Power BI schema definition ────────────────────────────────────────────────

def make_schema():
    def cols(*defs):
        return [{"name":n,"dataType":t} for n,t in defs]
    return {
        "name": "ContosoRetail",
        "defaultMode": "Push",
        "tables": [
            {"name":"dim_customers","columns":cols(
                ("customer_id","string"),("full_name","string"),("age_group","string"),
                ("gender","string"),("region","string"),("city","string"),
                ("signup_date","dateTime"),("segment","string"),
                ("lifetime_value","Double"),("email_opt_in","string"))},
            {"name":"dim_products","columns":cols(
                ("product_id","string"),("product_name","string"),("category","string"),
                ("subcategory","string"),("brand","string"),("unit_cost","Double"),
                ("list_price","Double"),("margin_pct","Double"),
                ("is_active","string"),("launch_year","Int64"))},
            {"name":"dim_stores","columns":cols(
                ("snapshot_id","string"),("store_id","string"),("store_name","string"),
                ("region","string"),("city","string"),("store_type","string"),
                ("month","string"),("year","Int64"),("monthly_revenue","Double"),
                ("monthly_transactions","Int64"),("avg_basket_size","Double"),
                ("return_rate","Double"),("headcount","Int64"))},
            {"name":"dim_employees","columns":cols(
                ("employee_id","string"),("full_name","string"),("department","string"),
                ("title","string"),("region","string"),("hire_date","dateTime"),
                ("salary","Double"),("performance_rating","string"),
                ("tenure_years","Double"),("manager_id","string"))},
            {"name":"fact_orders","columns":cols(
                ("order_id","string"),("customer_id","string"),("channel","string"),
                ("store_id","string"),("order_date","dateTime"),("year","Int64"),
                ("month","Int64"),("quarter","string"),("subtotal","Double"),
                ("discount_amount","Double"),("tax","Double"),("total_amount","Double"),
                ("status","string"))},
            {"name":"fact_order_items","columns":cols(
                ("item_id","string"),("order_id","string"),("product_id","string"),
                ("category","string"),("quantity","Int64"),("unit_price","Double"),
                ("discount_pct","Double"),("line_total","Double"),("returned","string"))},
            {"name":"fact_returns","columns":cols(
                ("return_id","string"),("order_id","string"),("product_id","string"),
                ("customer_id","string"),("return_date","dateTime"),
                ("days_to_return","Int64"),("category","string"),
                ("return_reason","string"),("refund_amount","Double"),
                ("restocking_fee","Double"),("region","string"))},
            {"name":"fact_inventory","columns":cols(
                ("snapshot_id","string"),("product_id","string"),("category","string"),
                ("store_id","string"),("snapshot_date","dateTime"),
                ("quantity_on_hand","Int64"),("reorder_point","Int64"),
                ("days_of_supply","Double"),("stockout_flag","string"),
                ("overstock_flag","string"))},
            {"name":"fact_marketing_campaigns","columns":cols(
                ("row_id","string"),("campaign_id","string"),("campaign_name","string"),
                ("channel","string"),("start_date","dateTime"),("week_number","Int64"),
                ("year","Int64"),("budget_usd","Double"),("spend_usd","Double"),
                ("impressions","Int64"),("clicks","Int64"),("ctr","Double"),
                ("conversions","Int64"),("revenue_attributed","Double"),("roi","Double"))},
            {"name":"fact_website_sessions","columns":cols(
                ("session_id","string"),("session_date","dateTime"),("year","Int64"),
                ("month","Int64"),("source","string"),("device","string"),
                ("region","string"),("page_views","Int64"),
                ("time_on_site_mins","Double"),("bounced","string"),
                ("converted","string"),("order_value","Double"))},
            {"name":"fact_support_tickets","columns":cols(
                ("ticket_id","string"),("customer_id","string"),
                ("created_date","dateTime"),("year","Int64"),("month","Int64"),
                ("category","string"),("priority","string"),("status","string"),
                ("resolution_days","Double"),("satisfaction_score","Double"),
                ("channel","string"),("region","string"))},
            {"name":"fact_supplier_performance","columns":cols(
                ("record_id","string"),("supplier_id","string"),
                ("supplier_name","string"),("category","string"),
                ("order_date","dateTime"),("year","Int64"),("quarter","string"),
                ("po_value","Double"),("lead_time_days","Int64"),
                ("on_time_flag","string"),("quality_score","Double"),
                ("defect_rate","Double"),("fill_rate","Double"))},
            {"name":"fact_store_traffic","columns":cols(
                ("record_id","string"),("store_id","string"),("store_name","string"),
                ("region","string"),("traffic_date","dateTime"),
                ("day_of_week","string"),("foot_traffic","Int64"),
                ("transactions","Int64"),("conversion_rate","Double"),
                ("avg_basket_size","Double"),("promo_active","string"))},
        ]
    }

# ── main ──────────────────────────────────────────────────────────────────────

def push_rows(token, ds_id, table, rows):
    url  = f"{BASE}/groups/{GROUP_ID}/datasets/{ds_id}/tables/{table}/rows"
    # Push in batches of 100 (API limit)
    for start in range(0, len(rows), 100):
        batch = rows[start:start+100]
        api("POST", url, {"rows": batch}, token)
    print(f"  ✓ {table}: {len(rows)} rows")

def main():
    token = get_token()

    # Step 1 – (skipped: no old dataset to delete in fresh installs)
    except Exception as ex:
        print(f"  ⚠ Delete failed: {ex}")

    # Step 2 – create new dataset
    print("\nStep 2: Creating ContosoRetail dataset …")
    schema  = make_schema()
    result  = api("POST", f"{BASE}/groups/{GROUP_ID}/datasets", schema, token, expect=(200,201,202))
    ds_id   = result.get("id")
    if not ds_id:
        raise RuntimeError("No dataset ID in response: " + json.dumps(result))
    print(f"  ✓ Dataset ID: {ds_id}")
    with open("dataset_id.txt","w") as f:
        f.write(ds_id)

    # Step 3 – push rows
    print("\nStep 3: Pushing 500 rows to each table …")
    generators = [
        ("dim_customers",             gen_customers),
        ("dim_products",              gen_products),
        ("dim_stores",                gen_stores),
        ("dim_employees",             gen_employees),
        ("fact_orders",               gen_orders),
        ("fact_order_items",          gen_order_items),
        ("fact_returns",              gen_returns),
        ("fact_inventory",            gen_inventory),
        ("fact_marketing_campaigns",  gen_marketing),
        ("fact_website_sessions",     gen_web_sessions),
        ("fact_support_tickets",      gen_support_tickets),
        ("fact_supplier_performance", gen_supplier_perf),
        ("fact_store_traffic",        gen_store_traffic),
    ]
    for tname, gfunc in generators:
        rows = gfunc()
        push_rows(token, ds_id, tname, rows)

    print(f"\n✅ Done! New dataset ID: {ds_id}")

if __name__ == "__main__":
    main()

