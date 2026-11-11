import os
import sys
import json
import re
import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# repo-এর মূল ফোল্ডার থেকে lead_logic.py ইমপোর্ট
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.dirname(_here))
import lead_logic as LL  # noqa: E402

st.set_page_config(page_title="Facebook Lead Report", layout="wide", page_icon="📞")

ORANGE = "#FF6600"

# ---------------- স্টাইল (আগের ড্যাশবোর্ডের মতো) ----------------
st.markdown("""
<style>
html, body, [class*="css"] { color:#333 !important; font-family:'Segoe UI', sans-serif; }
.main-title { text-align:center; color:#FF6600; font-size:55px; font-weight:800; margin-top:-100px; margin-bottom:5px; }
.developer-text { text-align:center; font-style:italic; font-size:18px; color:#666; margin-bottom:10px; }
.slogan-text { text-align:center; font-size:30px; font-weight:800; color:#222; margin-top:10px; }
.vision-text { text-align:center; font-size:20px; color:#777; margin-bottom:10px; }
.sub-title { text-align:center; font-size:18px; color:#666; margin-bottom:30px; }
.metric-card { background:#fff; padding:14px 6px; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,.1);
  text-align:center; border-top:8px solid #FF6600; margin-bottom:10px; min-height:118px;
  display:flex; flex-direction:column; justify-content:center; }
.metric-label { font-size:15px; color:#444; margin:0 0 8px 0; font-weight:900; text-transform:uppercase; white-space:nowrap; }
.metric-value { font-size:30px; color:#2b2b2b; font-weight:900; margin:0; line-height:1.1; white-space:nowrap; }
.metric-sub { font-size:13px; color:#777; margin-top:4px; }
.section-header { font-size:26px; color:#333; background:#F0F2F6; padding:12px 20px; border-radius:8px;
  border-left:10px solid #FF6600; margin-top:40px; margin-bottom:18px; font-weight:700; }
.note { font-size:14px; color:#555; background:#FFF7F0; border-left:4px solid #FF6600; padding:8px 12px; border-radius:6px; margin-bottom:12px; }
</style>
""", unsafe_allow_html=True)


# ---------------- কপি-যোগ্য টেবিল (আগের ড্যাশবোর্ড থেকে) ----------------
def clean_key(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def show_table(df_display, key_name, bold_last=True):
    if df_display.empty:
        st.info("কোনো ডাটা নেই।")
        return
    h = min(620, max(160, 38 * (len(df_display) + 1)))
    k = clean_key(key_name)
    text_json = json.dumps(df_display.to_csv(sep="\t", index=False), ensure_ascii=False)
    last_css = f".w-{k} tbody tr:last-child td {{ font-weight:900; background:#FCFCFC; }}" if bold_last else ""
    components.html(f"""
    <style>
      .w-{k} {{ max-height:{h}px; overflow:auto; border:1px solid #E0E0E0; border-radius:8px; background:#fff; margin-bottom:8px; }}
      .w-{k} table {{ width:100%; border-collapse:collapse; font-family:'Segoe UI',sans-serif; font-size:14px; color:#111827; }}
      .w-{k} thead th {{ font-weight:900; color:#000; background:#F8F9FB; border:1px solid #E0E0E0; padding:9px 10px;
                        text-align:left; position:sticky; top:0; z-index:2; white-space:nowrap; }}
      .w-{k} tbody td {{ border:1px solid #E8E8E8; padding:7px 10px; text-align:left; white-space:nowrap; }}
      {last_css}
      .b-{k} {{ background:#FF6600; color:#fff; border:none; border-radius:7px; padding:8px 14px; font-weight:700; cursor:pointer; font-size:14px; }}
    </style>
    <div class="w-{k}">{df_display.to_html(index=False, escape=True)}</div>
    <button class="b-{k}" id="b_{k}">📋 Copy full table</button>
    <script>
      const b = document.getElementById("b_{k}"); const t = {text_json};
      b.onclick = async () => {{ try {{ await navigator.clipboard.writeText(t); b.innerText="✅ Copied!"; }}
        catch(e) {{ b.innerText="Copy failed"; }} setTimeout(()=>b.innerText="📋 Copy full table",1300); }};
    </script>""", height=h + 60)


def fmt_int(x):
    return f"{int(round(float(x))):,}"


def fmt_tk(x):
    return f"৳{int(round(float(x))):,}"


def fmt_pct(x):
    return f"{float(x):.1f}%"


def format_summary(g, label_col, add_total_from=None):
    """summarize() টেবিলকে সুন্দর করে দেখানোর জন্য ফরম্যাট + Total লাইন।"""
    g = g.copy()
    if add_total_from is not None:
        tot = LL.summarize(add_total_from)
        tot.insert(0, label_col, "Total")
        g = pd.concat([g, tot], ignore_index=True)
    out = pd.DataFrame({label_col: g[label_col].astype(str)})
    out["Leads"] = g["Leads"].map(fmt_int)
    out["Called"] = g["Called"].map(fmt_int)
    out["Contacted"] = g["Contacted"].map(fmt_int)
    out["Contact %"] = g["Contact %"].map(fmt_pct)
    out["Orders"] = g["Orders"].map(fmt_int)
    out["Conversion %"] = g["Conversion %"].map(fmt_pct)
    out["Conv % (Contacted)"] = g["Conv % (Contacted)"].map(fmt_pct)
    out["Sales Amount"] = g["Sales"].map(fmt_tk)
    out["AOV"] = g["AOV"].map(fmt_tk)
    return out


def card(col, label, value, sub=""):
    sub_html = f"<div class='metric-sub'>{sub}</div>" if sub else ""
    col.markdown(f"<div class='metric-card'><p class='metric-label'>{label}</p>"
                 f"<p class='metric-value'>{value}</p>{sub_html}</div>", unsafe_allow_html=True)


def hbar(df, x, y, text_fmt, hover_extra="", height_per=42):
    fig = px.bar(df, x=x, y=y, orientation="h", color=y,
                 color_discrete_sequence=px.colors.qualitative.Vivid, text_auto=True)
    fig.update_traces(textangle=0, textposition="outside", texttemplate=text_fmt,
                      hovertemplate=f"<b>%{{y}}</b><br>{x}=%{{x:,}}{hover_extra}<extra></extra>",
                      cliponaxis=False)
    fig.update_layout(height=len(df) * height_per + 60, margin=dict(t=10, b=10, l=10, r=90),
                      yaxis=dict(categoryorder="array", categoryarray=df[y].tolist()[::-1], title=""),
                      xaxis=dict(showticklabels=False, title=""), showlegend=False)
    return fig


def short_label(s, n=45):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------- ডাটা লোড (৫ মিনিট পর পর শীট থেকে নতুন ডাটা) ----------------
@st.cache_data(ttl=300, show_spinner="শীট থেকে ডাটা আনা হচ্ছে…")
def load_all():
    raw_leads = {name: pd.read_csv(url, dtype=str, keep_default_na=False)
                 for name, url in LL.LEAD_SHEETS.items()}
    raw_orders = pd.read_csv(LL.ORDER_SHEET, dtype=str, keep_default_na=False)
    leads = LL.prepare_leads(raw_leads)
    orders = LL.prepare_orders(raw_orders)
    leads, matched_orders = LL.attach_orders(leads, orders)
    loaded_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=6)  # বাংলাদেশ সময়
    return leads, orders, matched_orders, loaded_at


try:
    leads, orders, matched_orders, loaded_at = load_all()
except Exception as e:
    st.error(f"শীট থেকে ডাটা আনতে সমস্যা হয়েছে: {e}")
    st.stop()

# ---------------- হেডার ----------------
for logo in ("logo.png", "logo.jpg"):
    if os.path.exists(logo):
        st.image(logo, width=120)
        break
st.markdown('<div class="main-title">Facebook Lead Report</div>', unsafe_allow_html=True)
st.markdown('<div class="developer-text">Web App Developed By-Shujoy Shaha</div>', unsafe_allow_html=True)
st.markdown('<div class="slogan-text">ম্যানুয়েল কাজের দিন শেষ, বিজ্ঞানবাক্সে বাংলাদেশ</div>', unsafe_allow_html=True)
st.markdown('<div class="vision-text">অন্যরকম বাংলাদেশের স্বপ্ন নিয়ে</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">কন্টাক্ট রেট · কনভার্সন · সেলস — <b>লিড দেওয়ার তারিখ</b> ধরে</div>',
            unsafe_allow_html=True)

# ---------------- সাইডবার ফিল্টার ----------------
st.sidebar.header("📅 লিডের তারিখ")
today = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=6)).date()
start_date = st.sidebar.date_input("Start Date", today - datetime.timedelta(days=30))
end_date = st.sidebar.date_input("End Date", today)

st.sidebar.header("🔎 ফিল্টার")
sheet_sel = st.sidebar.multiselect("ডাটা শীট", sorted(leads["Sheet"].unique()), default=sorted(leads["Sheet"].unique()))

in_range = leads[(leads["Lead Date"].dt.date >= start_date) & (leads["Lead Date"].dt.date <= end_date)
                 & leads["Sheet"].isin(sheet_sel)]

camp_opts = in_range["Campaign"].value_counts().index.tolist()
camp_sel = st.sidebar.multiselect("ক্যাম্পেইন (খালি রাখলে সব)", camp_opts, format_func=lambda s: short_label(s, 60))
agent_opts = sorted(in_range["Agent"].unique())
agent_sel = st.sidebar.multiselect("এজেন্ট (খালি রাখলে সব)", agent_opts)

f = in_range
if camp_sel:
    f = f[f["Campaign"].isin(camp_sel)]
if agent_sel:
    f = f[f["Agent"].isin(agent_sel)]

st.sidebar.markdown("---")
if st.sidebar.button("🔄 এখনই নতুন ডাটা আনো"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(f"শেষ আপডেট: {loaded_at:%d-%m-%Y %I:%M %p}\n\nশীট থেকে প্রতি ৫ মিনিটে নিজে থেকে নতুন ডাটা আসে।")

# ---------------- Sales Data: Facebook Lead অর্ডার (অর্ডারের তারিখ ধরে) ----------------
st.markdown('<div class="section-header">Sales Data: Facebook Lead অর্ডার</div>', unsafe_allow_html=True)
st.markdown("<div class='note'>Sales Data শীটের যেসব অর্ডারে <b>Campaign = Facebook Lead</b>, <b>অর্ডারের তারিখ</b> ধরে "
            "(সাইডবারের তারিখ অনুযায়ী)। Campaign Name ফাঁকা থাকলে <b>(ফাঁকা)</b> লাইনে দেখাবে, অ্যামাউন্ট ঠিকই গোনা হবে। "
            "Sales = Product Price কলামের যোগফল।</div>", unsafe_allow_html=True)
mo = matched_orders[(matched_orders["Order Campaign"].str.lower() == "facebook lead")
                    & (matched_orders["Order Date"].dt.date >= start_date)
                    & (matched_orders["Order Date"].dt.date <= end_date)].copy()
if agent_sel:
    mo = mo[mo["Order Collector"].isin(agent_sel)]
if mo.empty:
    st.info("এই তারিখে Sales Data শীটে কোনো Facebook Lead অর্ডার নেই।")
else:
    mo["Campaign Name"] = mo["Order Campaign Name"].replace({LL.NO_NAME: "(ফাঁকা)"})
    s_orders, s_qty, s_sales = len(mo), mo["Qty"].sum(), mo["Revenue"].sum()
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    card(sc1, "FB Lead Orders", fmt_int(s_orders))
    card(sc2, "Total Qty", fmt_int(s_qty))
    card(sc3, "Sales (Product Price)", fmt_tk(s_sales))
    card(sc4, "AOV", fmt_tk(s_sales / s_orders))
    card(sc5, "Campaign Name ফাঁকা", fmt_int((mo["Campaign Name"] == "(ফাঁকা)").sum()),
         fmt_tk(mo.loc[mo["Campaign Name"] == "(ফাঁকা)", "Revenue"].sum()))

    oc = mo.groupby("Campaign Name").agg(
        Orders=("Revenue", "size"), Qty=("Qty", "sum"), Sales=("Revenue", "sum"),
        Matched=("Matched To Lead", "sum")).reset_index().sort_values("Sales", ascending=False)
    oc["%"] = oc["Sales"] / oc["Sales"].sum() * 100
    c1, c2 = st.columns([2, 3])
    with c1:
        pl = oc.assign(Label=oc["Campaign Name"].map(short_label))
        st.plotly_chart(hbar(pl, "Sales", "Label", "৳%{x:,.0f}"), use_container_width=True)
    with c2:
        tbl = pd.DataFrame({
            "Campaign Name": oc["Campaign Name"],
            "Orders": oc["Orders"].map(fmt_int),
            "Total Qty": oc["Qty"].map(fmt_int),
            "Product Price (Sales)": oc["Sales"].map(fmt_tk),
            "%": oc["%"].map(fmt_pct),
            "লিড শীটে পাওয়া গেছে": oc["Matched"].map(fmt_int),
        })
        tbl.loc[len(tbl)] = ["Total", fmt_int(s_orders), fmt_int(s_qty), fmt_tk(s_sales), "100.0%",
                             fmt_int(mo["Matched To Lead"].sum())]
        show_table(tbl, "sales_data_fb")

    with st.expander("অর্ডারগুলোর তালিকা দেখুন"):
        lst = mo.sort_values("Order Date", ascending=False)
        show_table(pd.DataFrame({
            "Order Date": lst["Order Date"].dt.strftime("%d-%m-%Y"),
            "Order Collector": lst["Order Collector"],
            "Campaign": lst["Order Campaign"],
            "Campaign Name": lst["Campaign Name"],
            "Total Qty": lst["Qty"].map(fmt_int),
            "Product Price": lst["Revenue"].map(fmt_tk),
            "লিড শীটে পাওয়া গেছে": lst["Matched To Lead"].map({True: "হ্যাঁ", False: "না"}),
        }), "sales_data_list", bold_last=False)

st.markdown('<div class="section-header">Lead Report (লিড শীট থেকে, লিডের তারিখ ধরে)</div>', unsafe_allow_html=True)
if f.empty:
    st.warning("এই তারিখ/ফিল্টারে কোনো লিড নেই।")
    st.stop()

# ---------------- ১. সামারি কার্ড ----------------
tot = LL.summarize(f).iloc[0]
cols = st.columns(7)
card(cols[0], "Total Leads", fmt_int(tot["Leads"]))
card(cols[1], "Called", fmt_int(tot["Called"]), f"বাকি {fmt_int(tot['Leads'] - tot['Called'])}")
card(cols[2], "Contacted", fmt_int(tot["Contacted"]))
card(cols[3], "Contact Rate", fmt_pct(tot["Contact %"]), "কল করা লিডের মধ্যে")
card(cols[4], "Orders", fmt_int(tot["Orders"]), "শর্ট কোড: অর্ডার করেছেন")
card(cols[5], "Conversion", fmt_pct(tot["Conversion %"]), f"কন্টাক্টেডের {fmt_pct(tot['Conv % (Contacted)'])}")
card(cols[6], "Sales Amount", fmt_tk(tot["Sales"]), "এই লিডগুলোর অর্ডার থেকে")

st.markdown(
    "<div class='note'>এখানে সবকিছু <b>লিড দেওয়ার তারিখ</b> ধরে গোনা হয়েছে। ১০ তারিখের লিড ১৫ তারিখে ৩য় কলে অর্ডার করলেও "
    "সেটা ১০ তারিখের হিসাবে যাবে। এখানে সেলস অ্যামাউন্ট = এই লিডগুলোর ফোন নাম্বার Sales Data শীটে মিলিয়ে, Campaign = Facebook Lead অর্ডারের Product Price।</div>",
    unsafe_allow_html=True)

# ---------------- ২. ক্যাম্পেইন অনুযায়ী ----------------
st.markdown('<div class="section-header">Campaign-wise Report</div>', unsafe_allow_html=True)
camp = LL.summarize(f, "Campaign").sort_values("Leads", ascending=False)
plot = camp.head(12).assign(Label=lambda d: d["Campaign"].map(short_label))
c1, c2 = st.columns(2)
with c1:
    st.markdown("**কোন ক্যাম্পেইন থেকে কত লিড**")
    st.plotly_chart(hbar(plot, "Leads", "Label", "%{x:,}"), use_container_width=True)
with c2:
    st.markdown("**কন্টাক্ট রেট বনাম কনভার্সন (%)**")
    fig = go.Figure()
    fig.add_bar(y=plot["Label"], x=plot["Contact %"], name="Contact %", orientation="h",
                marker_color="#4C9BE8", texttemplate="%{x:.1f}%", textposition="outside")
    fig.add_bar(y=plot["Label"], x=plot["Conversion %"], name="Conversion %", orientation="h",
                marker_color=ORANGE, texttemplate="%{x:.1f}%", textposition="outside")
    fig.update_layout(barmode="group", height=len(plot) * 52 + 80, margin=dict(t=10, b=10, l=10, r=60),
                      yaxis=dict(categoryorder="array", categoryarray=plot["Label"].tolist()[::-1]),
                      xaxis=dict(showticklabels=False), legend=dict(orientation="h", y=1.04, x=0))
    st.plotly_chart(fig, use_container_width=True)
show_table(format_summary(camp, "Campaign", add_total_from=f), "campaign_table")

# ---------------- ৩. তারিখ অনুযায়ী ----------------
st.markdown('<div class="section-header">Date-wise Report (লিডের তারিখ)</div>', unsafe_allow_html=True)
daily = LL.summarize(f, "Lead Date").sort_values("Lead Date")
fig = go.Figure()
fig.add_bar(x=daily["Lead Date"], y=daily["Leads"], name="Leads", marker_color="#D9D9D9", yaxis="y2", opacity=0.7)
fig.add_scatter(x=daily["Lead Date"], y=daily["Contact %"], name="Contact %", mode="lines+markers",
                line=dict(color="#4C9BE8", width=3))
fig.add_scatter(x=daily["Lead Date"], y=daily["Conversion %"], name="Conversion %", mode="lines+markers",
                line=dict(color=ORANGE, width=3))
fig.update_layout(height=380, margin=dict(t=30, b=10, l=10, r=10), hovermode="x unified",
                  yaxis=dict(title="%", ticksuffix="%", rangemode="tozero"),
                  yaxis2=dict(title="Leads", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
                  legend=dict(orientation="h", y=1.1, x=0))
st.plotly_chart(fig, use_container_width=True)
daily_disp = daily.copy()
daily_disp["Date"] = daily_disp["Lead Date"].dt.strftime("%d-%m-%Y")
show_table(format_summary(daily_disp, "Date", add_total_from=f), "daily_table")

# ---------------- ৪. শর্ট কোড অনুযায়ী ----------------
st.markdown('<div class="section-header">Short Code-wise Report</div>', unsafe_allow_html=True)
st.markdown("<div class='note'>প্রতিটা লিডের <b>সর্বশেষ</b> শর্ট কোড ধরা হয়েছে (অর্ডার হয়ে থাকলে \"অর্ডার করেছেন\")। "
            "একটা লিড একবারই গোনা হয়েছে।</div>", unsafe_allow_html=True)


def code_group(code):
    if code in LL.ORDER_CODES:
        return "✅ অর্ডার"
    if code == LL.NOT_CALLED:
        return "⏳ কল হয়নি"
    if code in LL.NOT_CONTACTED_CODES:
        return "📵 কথা হয়নি"
    return "💬 কথা হয়েছে"


sc = f.groupby("Final Code").agg(Leads=("Lead ID", "size"), Sales=("Sales", "sum")).reset_index()
sc["Type"] = sc["Final Code"].map(code_group)
sc = sc.sort_values("Leads", ascending=False)
sc["%"] = sc["Leads"] / sc["Leads"].sum() * 100

c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(hbar(sc.head(20), "Leads", "Final Code", "%{x:,}", height_per=34), use_container_width=True)
with c2:
    disp = pd.DataFrame({"Short Code": sc["Final Code"], "Type": sc["Type"],
                         "Leads": sc["Leads"].map(fmt_int), "%": sc["%"].map(fmt_pct)})
    disp = pd.concat([disp, pd.DataFrame([{"Short Code": "Total", "Type": "", "Leads": fmt_int(sc["Leads"].sum()),
                                           "%": "100.0%"}])], ignore_index=True)
    show_table(disp, "shortcode_table")

st.markdown("#### ক্যাম্পেইন × শর্ট কোড (কোন ক্যাম্পেইনের লিড কোন অবস্থায় আছে)")
pv = pd.crosstab(f["Campaign"], f["Final Code"])
order_cols = sc["Final Code"].tolist()
pv = pv[[c for c in order_cols if c in pv.columns]]
pv.insert(0, "Total Leads", pv.sum(axis=1))
pv = pv.sort_values("Total Leads", ascending=False)
pv.loc["Total"] = pv.sum()
pv.columns.name = None
pv = pv.reset_index()
show_table(pv.astype(str), "campaign_code_pivot")

with st.expander("সব কলের শর্ট কোড (প্রতিটা কল আলাদা করে গোনা)"):
    call_cols = [f"Call {n}" for n in range(1, LL.MAX_CALLS + 1)]
    long = f[call_cols].melt(var_name="Call", value_name="Short Code")
    long = long[long["Short Code"] != ""]
    allc = long.pivot_table(index="Short Code", columns="Call", aggfunc="size", fill_value=0)
    allc = allc[[c for c in call_cols if c in allc.columns]]
    allc.insert(0, "Total", allc.sum(axis=1))
    allc = allc.sort_values("Total", ascending=False)
    allc.loc["Total"] = allc.sum()
    allc.columns.name = None
    show_table(allc.reset_index().astype(str), "all_calls_codes")

# ---------------- ৫. কত নাম্বার কলে অর্ডার ----------------
st.markdown('<div class="section-header">কত নাম্বার কলে অর্ডার হয়েছে</div>', unsafe_allow_html=True)
conv = f[f["Converted"]].copy()
if conv.empty:
    st.info("এই সময়ে কোনো অর্ডার নেই।")
else:
    conv["Call No"] = conv["Order Call No"].astype(int)
    cn = conv.groupby("Call No").agg(Orders=("Lead ID", "size"), Sales=("Sales", "sum")).reset_index()
    cn = cn.set_index("Call No").reindex(range(1, int(cn["Call No"].max()) + 1), fill_value=0).reset_index()
    cn["%"] = cn["Orders"] / cn["Orders"].sum() * 100
    cn["Cumulative %"] = cn["%"].cumsum()
    ords = {1: "1st", 2: "2nd", 3: "3rd"}
    cn["Call"] = cn["Call No"].map(lambda n: f"{ords.get(n, f'{n}th')} Call")

    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.bar(cn, x="Call", y="Orders", text="Orders", color_discrete_sequence=[ORANGE])
        fig.add_scatter(x=cn["Call"], y=cn["Cumulative %"], yaxis="y2", mode="lines+markers",
                        name="Cumulative %", line=dict(color="#333", width=2))
        fig.update_traces(selector=dict(type="bar"), textposition="outside")
        fig.update_layout(height=380, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                          yaxis=dict(title="Orders"),
                          yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%", showgrid=False))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        disp = pd.DataFrame({"Call": cn["Call"], "Orders": cn["Orders"].map(fmt_int), "%": cn["%"].map(fmt_pct),
                             "Cumulative %": cn["Cumulative %"].map(fmt_pct), "Sales Amount": cn["Sales"].map(fmt_tk)})
        disp = pd.concat([disp, pd.DataFrame([{"Call": "Total", "Orders": fmt_int(cn["Orders"].sum()), "%": "100.0%",
                                               "Cumulative %": "", "Sales Amount": fmt_tk(cn["Sales"].sum())}])],
                         ignore_index=True)
        show_table(disp, "call_no_table")

    st.markdown("#### ক্যাম্পেইন অনুযায়ী: কত নাম্বার কলে অর্ডার")
    cp = pd.crosstab(conv["Campaign"], conv["Call No"])
    cp.columns = [f"{ords.get(int(c), f'{int(c)}th')} Call" for c in cp.columns]
    cp.insert(0, "Total Orders", cp.sum(axis=1))
    cp = cp.sort_values("Total Orders", ascending=False)
    cp.loc["Total"] = cp.sum()
    cp.columns.name = None
    cp.index.name = "Campaign"
    show_table(cp.reset_index().astype(str), "campaign_call_pivot")

# ---------------- ৬. এজেন্ট অনুযায়ী ----------------
st.markdown('<div class="section-header">Agent-wise Report</div>', unsafe_allow_html=True)
ag = LL.summarize(f, "Agent").sort_values("Orders", ascending=False)
show_table(format_summary(ag, "Agent", add_total_from=f), "agent_table")

# ---------------- ডাটা কোয়ালিটি ----------------
with st.expander("ℹ️ হিসাবের নিয়ম ও ডাটা চেক"):
    missing = int(in_range["Date Missing"].sum())
    no_date = int(leads["Lead Date"].isna().sum())
    st.markdown(f"""
- **Lead** = লিড শীটের প্রতিটা লাইন। তারিখ = `Date` কলাম; ফাঁকা থাকলে `1st call date` ধরা হয়েছে (এই রেঞ্জে {missing}টা)। দুটোই ফাঁকা এমন {no_date}টা লিড কোনো রিপোর্টে আসেনি।
- **Called** = অন্তত একটা শর্ট কোড আছে।
- **Contacted** = অন্তত একবার এই কোডগুলোর বাইরে কিছু: {", ".join(sorted(LL.NOT_CONTACTED_CODES))}।
- **Contact %** = Contacted ÷ Called।
- **Orders** = যেকোনো কলে শর্ট কোড "অর্ডার করেছেন"। **Conversion %** = Orders ÷ Leads।
- **Sales Amount** = অর্ডার শীট থেকে, একই ফোন নাম্বার, অর্ডারের তারিখ লিডের তারিখের দিনে বা পরে, Campaign = Facebook Lead (Existing, Cart Abandon, Rokomari ইত্যাদি ও ফাঁকা Campaign বাদ)। Revenue = Product Price (না থাকলে Total Amount − Shipping)।
- শর্ট কোড বা নিয়ম বদলাতে `lead_logic.py`-এর উপরের SETTINGS অংশ এডিট করুন।
""")
