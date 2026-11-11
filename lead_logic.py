"""
Facebook Lead Report — ডাটা লজিক
--------------------------------
এই ফাইলে কোনো Streamlit কোড নেই, শুধু হিসাব-নিকাশ।
শীটের কলামের নাম বা শর্ট কোডের নিয়ম বদলাতে চাইলে নিচের SETTINGS অংশটুকু এডিট করুন।
"""
import re
import pandas as pd

# ======================= SETTINGS =======================

# লিড ডাটা শীট (published CSV link)। নাম বদলাতে চাইলে বামের লেখাটা বদলান।
LEAD_SHEETS = {
    "Sheet-1": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRhGpSv6YJ5uwMeTI3r06mc4ZmqcCZlrTCQGsjDlDq2o1Y7uYhT3snVgI1jZ_zMUzxN_RZfOKcC-Rfm/pub?gid=1218239306&single=true&output=csv",
    "Sheet-2": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfDJ5fR_NxnfT_1E5sfxh1BCuXIgHA_mwZ53P6Gw5oN6tHouRCx1GOxA7WDuWkmSrmz136pqXZmyv/pub?gid=1811215808&single=true&output=csv",
    "Sheet-3": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQI_3L0siijFsFxz2RR5IPVKDEORZEW7oWDGeGZuZCBDw-GUOtKHsiPIZzCrULyK28Sr1XCvLjHG0PK/pub?gid=1076964399&single=true&output=csv",
}

# অর্ডার শীট (সেলস অ্যামাউন্ট এখান থেকে আসে)
ORDER_SHEET = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTDhr-rwKe88LKKludd74G766j1l4vbvoaHi1YwwkefcfjCCgDGkZL6Ty9ngNv3gVvd5ezElgXghOs3/pub?gid=81417&single=true&output=csv"

# এই শর্ট কোড থাকলে লিড "কনভার্টেড" (অর্ডার হয়েছে)
ORDER_CODES = {"অর্ডার করেছেন"}

# এই শর্ট কোডগুলো মানে কাস্টমারের সাথে কথা হয়নি (নট-কন্টাক্টেড)।
# এর বাইরে যেকোনো শর্ট কোড = কন্টাক্টেড।
NOT_CONTACTED_CODES = {
    "কল ধরেনি",
    "কল কেটে দিয়েছে",
    "নাম্বার বন্ধ",
    "কল যাচ্ছে না",
    "নাম্বার বিজি",
    "কল ওয়েটিং",
    "রং নাম্বার",
}

# বানান ঠিক করা (একই কোড দুই রকম লেখা থাকলে একটা বানিয়ে দেয়)
CODE_FIX = {
    "কল যাাচ্ছে না": "কল যাচ্ছে না",
    "নিতে আগ্রহি না": "কিনতে আগ্রহী না",
    "নিতে আগ্রহী না": "কিনতে আগ্রহী না",
    "নিয়েছে অলরেডি": "নিয়েছে অলরেডী",
}

# অর্ডার শীটের "Campaign" কলামে এই মানগুলো থাকলে সেই অর্ডার ফেসবুক লিডের হিসেবে ধরা হবে।
# ফাঁকা ("") রাখা হয়েছে, কারণ অনেক ফেসবুক লিডের অর্ডারে Campaign ফাঁকা থাকে।
# Existing, Rokomari, Library ইত্যাদি বাদ যাবে।
FB_ORDER_CAMPAIGNS = {"facebook lead", ""}

NO_NAME = "(নাম নেই)"
NOT_CALLED = "কল হয়নি"
MAX_CALLS = 10

# ========================================================


def _clean_text(s):
    s = "" if pd.isna(s) else str(s)
    s = s.replace('"', " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def clean_campaign(s):
    s = _clean_text(s)
    if s == "" or s.lower().startswith("you don't have enough permission"):
        return NO_NAME
    return s


def clean_code(s):
    s = _clean_text(s)
    if s == "" or re.fullmatch(r"[\d/\-. ]+", s):  # ভুল করে তারিখ লেখা থাকলে বাদ
        return ""
    return CODE_FIX.get(s, s)


def phone_key(s):
    """ফোন নাম্বারের শেষ ১০ ডিজিট দিয়ে মিলানো হয় (+880, 0 ইত্যাদি বাদ)।"""
    d = re.sub(r"\D", "", "" if pd.isna(s) else str(s))
    return d[-10:] if len(d) >= 10 else ""


def to_number(series):
    cleaned = series.astype(str).str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def parse_date(series):
    """তারিখ পড়ে: 13-08-2026, 13-08-26, 13 -08-26, 13/8/2026, 13/08/26 — সব দিন-মাস-বছর ধরে।"""
    s = series.astype(str).str.replace(r"\s+", "", regex=True)
    d = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y"):
        rest = d.isna() & (s != "")
        if not rest.any():
            break
        d.loc[rest] = pd.to_datetime(s[rest], format=fmt, errors="coerce")
    # অসম্ভব তারিখ (ভুল টাইপ) বাদ
    d = d.where((d.dt.year >= 2020) & (d.dt.year <= 2035))
    return d.dt.normalize()


def _short_code_columns(columns):
    return [c for c in columns if str(c).strip().lower().startswith("short code")][:MAX_CALLS]


def prepare_leads(raw_by_sheet):
    """raw_by_sheet: {sheet_name: DataFrame (dtype=str)} -> প্রতি লিডের এক লাইন।"""
    frames = []
    for sheet_name, raw in raw_by_sheet.items():
        raw = raw.copy()
        raw.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in raw.columns]
        code_cols = _short_code_columns(raw.columns)

        df = pd.DataFrame(index=raw.index)
        df["Sheet"] = sheet_name
        lead_date = parse_date(raw.get("Date", pd.Series("", index=raw.index)))
        first_call = parse_date(raw.get("1st call date", pd.Series("", index=raw.index)))
        df["Date Missing"] = lead_date.isna()
        df["Lead Date"] = lead_date.fillna(first_call)  # Date ফাঁকা হলে 1st call date
        df["Phone"] = raw.get("Contact Number", pd.Series("", index=raw.index)).map(phone_key)
        df["Campaign"] = raw.get("Campaign Name", pd.Series("", index=raw.index)).map(clean_campaign)
        agent = raw.get("Agent Name", pd.Series("", index=raw.index)).map(_clean_text)
        df["Agent"] = agent.where(agent != "", "(অজানা)")

        codes = pd.DataFrame({i + 1: raw[c].map(clean_code) for i, c in enumerate(code_cols)}, index=raw.index)
        for n in range(len(code_cols) + 1, MAX_CALLS + 1):
            codes[n] = ""
        for n in range(1, MAX_CALLS + 1):
            df[f"Call {n}"] = codes[n]

        filled = codes != ""
        is_order = codes.isin(ORDER_CODES)
        is_contact = filled & ~codes.isin(NOT_CONTACTED_CODES)

        df["Calls"] = filled.sum(axis=1)
        df["Called"] = df["Calls"] > 0
        df["Contacted"] = is_contact.any(axis=1)
        df["Converted"] = is_order.any(axis=1)
        df["Order Call No"] = is_order.idxmax(axis=1).where(df["Converted"])
        df["First Contact Call"] = is_contact.idxmax(axis=1).where(df["Contacted"])

        last = codes.where(filled).ffill(axis=1).iloc[:, -1]
        df["Final Code"] = last.fillna(NOT_CALLED)
        df["Final Code"] = df["Final Code"].where(~df["Converted"], next(iter(ORDER_CODES)))

        # একদম খালি লাইন বাদ
        keep = (df["Phone"] != "") | df["Lead Date"].notna()
        frames.append(df[keep])

    leads = pd.concat(frames, ignore_index=True)
    leads["Lead ID"] = range(len(leads))
    return leads


def prepare_orders(raw):
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    get = lambda c: raw[c] if c in raw.columns else pd.Series("", index=raw.index)

    o = pd.DataFrame(index=raw.index)
    o["Order Date"] = parse_date(get("Order Date"))
    o["Phone"] = get("Contact Number").map(phone_key)
    o["Order Campaign"] = get("Campaign").map(_clean_text)
    o["Order Campaign Name"] = get("Campaign Name").map(clean_campaign)
    o["Order Collector"] = get("Order Collector").map(_clean_text)
    o["Qty"] = to_number(get("Total Qty"))

    total = to_number(get("Total Amount"))
    ship = to_number(get("Shipping Charge"))
    disc = to_number(get("Discount"))
    price = to_number(get("Product Price"))
    # আগের ড্যাশবোর্ডের নিয়মই: Revenue = Product Price, না থাকলে Total Amount - Shipping
    o["Revenue"] = price.where(price > 0, total - ship).clip(lower=0)
    o["Total Sales"] = (o["Revenue"] + disc).clip(lower=0)

    o = o[o["Order Date"].notna() & (o["Phone"] != "")]
    o["Is FB Lead Order"] = o["Order Campaign"].str.lower().isin(FB_ORDER_CAMPAIGNS)
    return o.reset_index(drop=True)


def attach_orders(leads, orders):
    """
    প্রতিটা ফেসবুক-লিড অর্ডারকে সেই লিডের সাথে জোড়া দেয় যেটা একই ফোন নাম্বারের
    এবং অর্ডারের তারিখের আগে (বা একই দিনে) সবচেয়ে শেষে দেওয়া হয়েছে।
    ফলে সেলস অ্যামাউন্ট লিডের তারিখে গোনা হয়, অর্ডারের তারিখে না।
    """
    fb = orders[orders["Is FB Lead Order"]].copy()
    lk = leads[(leads["Phone"] != "") & leads["Lead Date"].notna()][["Lead ID", "Phone", "Lead Date"]]

    fb = fb.sort_values("Order Date")
    lk = lk.sort_values("Lead Date")
    matched = pd.merge_asof(
        fb, lk, left_on="Order Date", right_on="Lead Date", by="Phone", direction="backward"
    )

    per_lead = matched.dropna(subset=["Lead ID"]).groupby("Lead ID").agg(
        **{"Matched Orders": ("Revenue", "size"),
           "Sales": ("Revenue", "sum"),
           "Gross Sales": ("Total Sales", "sum"),
           "Qty": ("Qty", "sum")}
    )
    out = leads.merge(per_lead, left_on="Lead ID", right_index=True, how="left")
    for c in ["Matched Orders", "Sales", "Gross Sales", "Qty"]:
        out[c] = out[c].fillna(0)

    matched["Matched To Lead"] = matched["Lead ID"].notna()
    return out, matched


def summarize(df, by=None):
    """লিড-লেভেলের ডাটা থেকে সামারি টেবিল।"""
    agg = dict(
        Leads=("Lead ID", "size"),
        Called=("Called", "sum"),
        Contacted=("Contacted", "sum"),
        Orders=("Converted", "sum"),
        **{"Matched Orders": ("Matched Orders", "sum")},
        Sales=("Sales", "sum"),
    )
    if by is None:
        g =df.assign(_all="Total").groupby("_all").agg(**agg).reset_index(drop=True)
    else:
        g = df.groupby(by, dropna=False).agg(**agg).reset_index()
    g["Contact %"] = g["Contacted"] / g["Called"].where(g["Called"] > 0) * 100
    g["Conversion %"] = g["Orders"] / g["Leads"].where(g["Leads"] > 0) * 100
    g["Conv % (Contacted)"] = g["Orders"] / g["Contacted"].where(g["Contacted"] > 0) * 100
    g["AOV"] = g["Sales"] / g["Matched Orders"].where(g["Matched Orders"] > 0)
    return g.fillna({"Contact %": 0, "Conversion %": 0, "Conv % (Contacted)": 0, "AOV": 0})
