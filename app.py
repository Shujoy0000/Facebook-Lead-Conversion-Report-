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
.block-container { padding-top: 3.8rem !important; }
.main-title { text-align:center; color:#FF6600; font-size:44px; font-weight:800; margin:0 0 2px 0; line-height:1.1; }
.developer-text { text-align:center; font-style:italic; font-size:15px; color:#666; margin-bottom:2px; }
.slogan-text { text-align:center; font-size:24px; font-weight:800; color:#222; margin:2px 0 0 0; line-height:1.3; }
.vision-text { text-align:center; font-size:16px; color:#777; margin-bottom:2px; }
.sub-title { text-align:center; font-size:15px; color:#666; margin-bottom:8px; }
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


# ---------------- হেডার (কম জায়গা) ----------------
hc1, hc2, hc3 = st.columns([1, 6, 1])
with hc1:
    for logo in ("logo.png", "logo.jpg"):
        if os.path.exists(logo):
            st.image(logo, width=110)
            break
with hc2:
    st.markdown('<div class="main-title">Facebook Lead Report</div>', unsafe_allow_html=True)
    st.markdown('<div class="developer-text">Web App Developed By-Shujoy Shaha</div>', unsafe_allow_html=True)
    st.markdown('<div class="slogan-text">ম্যানুয়েল কাজের দিন শেষ, বিজ্ঞানবাক্সে বাংলাদেশ</div>', unsafe_allow_html=True)
    st.markdown('<div class="vision-text">অন্যরকম বাংলাদেশের স্বপ্ন নিয়ে</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">কন্টাক্ট রেট · কনভার্সন · সেলস</div>', unsafe_allow_html=True)

# ---------------- সাইডবার ফিল্টার ----------------
st.sidebar.header("📅 তারিখ")
today = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=6)).date()
start_date = st.sidebar.date_input("Start Date", today - datetime.timedelta(days=30))
end_date = st.sidebar.date_input("End Date", today)

st.sidebar.header("🔎 ফিল্টার")
all_sheets = sorted(leads["Sheet"].unique())
sheet_sel = st.sidebar.multiselect("ডাটা শীট", all_sheets, default=all_sheets)

# লিড: লিডের তারিখ ধরে
in_range = leads[(leads["Lead Date"].dt.date >= start_date) & (leads["Lead Date"].dt.date <= end_date)
                 & leads["Sheet"].isin(sheet_sel)].copy()
in_range["Date"] = in_range["Lead Date"]

# অর্ডার: Sales Data শীটের Campaign = Facebook Lead, অর্ডারের তারিখ ধরে (কোনো অর্ডার বাদ যায় না)
lead_campaign = leads.set_index("Lead ID")["Campaign"]
lead_sheet = leads.set_index("Lead ID")["Sheet"]
fbo = matched_orders[(matched_orders["Order Campaign"].str.lower() == "facebook lead")
                     & (matched_orders["Order Date"].dt.date >= start_date)
                     & (matched_orders["Order Date"].dt.date <= end_date)].copy()
# ক্যাম্পেইন = Sales Data শীটের Campaign Name, যেমন লেখা আছে তেমন। ফাঁকা থাকলে নাম ছাড়া (ফাঁকা) লাইনে যাবে।
fbo["Campaign"] = fbo["Order Campaign Name"]
fbo["Agent"] = fbo["Order Collector"].where(fbo["Order Collector"] != "", "(অজানা)")
fbo["Date"] = fbo["Order Date"]
if set(sheet_sel) != set(all_sheets):  # শীট বাছাই করলে শুধু সেই শীটের লিডের অর্ডার
    fbo = fbo[fbo["Lead ID"].map(lead_sheet).isin(sheet_sel)]

camp_opts = pd.concat([in_range["Campaign"], fbo["Campaign"]]).value_counts().index.tolist()
camp_sel = st.sidebar.multiselect("ক্যাম্পেইন (খালি রাখলে সব)", camp_opts,
                                  format_func=lambda s: short_label(s, 60) if s else "(নাম ছাড়া)")
agent_opts = sorted(set(in_range["Agent"]) | set(fbo["Agent"]))
agent_sel = st.sidebar.multiselect("এজেন্ট (খালি রাখলে সব)", agent_opts)

f = in_range
if camp_sel:
    f = f[f["Campaign"].isin(camp_sel)]
    fbo = fbo[fbo["Campaign"].isin(camp_sel)]
if agent_sel:
    f = f[f["Agent"].isin(agent_sel)]
    fbo = fbo[fbo["Agent"].isin(agent_sel)]

st.sidebar.markdown("---")
if st.sidebar.button("🔄 এখনই নতুন ডাটা আনো"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(f"শেষ আপডেট: {loaded_at:%d-%m-%Y %I:%M %p}\n\nশীট থেকে প্রতি ৫ মিনিটে নিজে থেকে নতুন ডাটা আসে।")

if f.empty and fbo.empty:
    st.warning("এই তারিখ/ফিল্টারে কোনো লিড বা অর্ডার নেই।")
    st.stop()


# ---------------- লিড + অর্ডার একসাথে ----------------
def add_rates(g):
    g = g.copy()
    nz = lambda s: s.where(s > 0)
    g["Contact %"] = (g["Contacted"] / nz(g["Called"]) * 100).fillna(0)
    g["Conversion %"] = (g["Orders"] / nz(g["Leads"]) * 100).fillna(0)
    g["Conv % (Contacted)"] = (g["Orders"] / nz(g["Contacted"]) * 100).fillna(0)
    g["AOV"] = (g["Sales"] / nz(g["Orders"])).fillna(0)
    return g


NUM = ["Leads", "Called", "Contacted", "Code Orders", "Orders", "Qty", "Sales"]


def combined(by):
    lp = pd.DataFrame({by: f[by],
                       "Leads": 1, "Called": f["Called"].astype(int), "Contacted": f["Contacted"].astype(int),
                       "Code Orders": f["Converted"].astype(int)}).groupby(by).sum().reset_index()
    op = fbo.groupby(by).agg(Orders=("Revenue", "size"), Qty=("Qty", "sum"), Sales=("Revenue", "sum")).reset_index()
    g = lp.merge(op, on=by, how="outer")
    for c in NUM:
        g[c] = g[c].fillna(0) if c in g else 0
    return add_rates(g)


def with_total(g, label_col):
    tot = {label_col: "Total", **{c: g[c].sum() for c in NUM}}
    return pd.concat([g, add_rates(pd.DataFrame([tot]))], ignore_index=True)


def format_table(g, label_col, label_fmt=str):
    return pd.DataFrame({
        label_col: g[label_col].map(label_fmt),
        "Leads": g["Leads"].map(fmt_int),
        "Called": g["Called"].map(fmt_int),
        "Contacted": g["Contacted"].map(fmt_int),
        "Contact %": g["Contact %"].map(fmt_pct),
        "Orders": g["Orders"].map(fmt_int),
        "Total Qty": g["Qty"].map(fmt_int),
        "Conversion %": g["Conversion %"].map(fmt_pct),
        "Conv % (Contacted)": g["Conv % (Contacted)"].map(fmt_pct),
        "Sales Amount": g["Sales"].map(fmt_tk),
        "AOV": g["AOV"].map(fmt_tk),
        "অর্ডার করেছেন (শর্ট কোড)": g["Code Orders"].map(fmt_int),
    })


def chart_label(s):
    return short_label(s) if s else " "


# ---------------- ১. সামারি কার্ড ----------------
T = with_total(combined("Campaign"), "Campaign").iloc[-1]
cols = st.columns(7)
card(cols[0], "Total Leads", fmt_int(T["Leads"]))
card(cols[1], "Called", fmt_int(T["Called"]), f"বাকি {fmt_int(T['Leads'] - T['Called'])}")
card(cols[2], "Contacted", fmt_int(T["Contacted"]))
card(cols[3], "Contact Rate", fmt_pct(T["Contact %"]), "কল করা লিডের মধ্যে")
card(cols[4], "Orders", fmt_int(T["Orders"]), f"Total Qty {fmt_int(T['Qty'])}")
card(cols[5], "Conversion", fmt_pct(T["Conversion %"]), f"কন্টাক্টেডের {fmt_pct(T['Conv % (Contacted)'])}")
card(cols[6], "Sales Amount", fmt_tk(T["Sales"]), f"AOV {fmt_tk(T['AOV'])}")

st.markdown(
    "<div class='note'><b>Leads, Called, Contacted</b> লিড শীট থেকে, লিড দেওয়ার তারিখ ধরে। "
    "<b>Orders, Total Qty, Sales Amount</b> Sales Data শীট থেকে: Campaign = Facebook Lead এমন <b>সব</b> অর্ডার, "
    "অর্ডারের তারিখ ধরে (Campaign Name ফাঁকা হলেও)। Sales Amount = Product Price।</div>",
    unsafe_allow_html=True)

# ---------------- ২. ক্যাম্পেইন অনুযায়ী ----------------
st.markdown('<div class="section-header">Campaign-wise Report</div>', unsafe_allow_html=True)
camp = combined("Campaign").sort_values(["Sales", "Leads"], ascending=False)
plot = camp.head(12).assign(Label=lambda d: d["Campaign"].map(chart_label))
c1, c2 = st.columns(2)
with c1:
    st.markdown("**কোন ক্যাম্পেইন থেকে কত সেল**")
    st.plotly_chart(hbar(plot, "Sales", "Label", "৳%{x:,.0f}"), use_container_width=True)
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
show_table(format_table(with_total(camp, "Campaign"), "Campaign"), "campaign_table")

# ---------------- ৩. তারিখ অনুযায়ী ----------------
st.markdown('<div class="section-header">Date-wise Report</div>', unsafe_allow_html=True)
daily = combined("Date").sort_values("Date")
dlabel = daily["Date"].dt.strftime("%d %b")
st.markdown("**প্রতিদিন: ধূসর বার = কত লিড এসেছে (ডান পাশের সংখ্যা), নীল লাইন = Contact %, কমলা লাইন = Conversion % (বাম পাশের %)**")
fig = go.Figure()
fig.add_bar(x=dlabel, y=daily["Leads"], name="Leads", marker_color="#D9D9D9", yaxis="y2",
            text=daily["Leads"].map(fmt_int), textposition="inside")
fig.add_scatter(x=dlabel, y=daily["Contact %"], name="Contact %", mode="lines+markers+text",
                line=dict(color="#4C9BE8", width=3), marker=dict(size=9),
                text=daily["Contact %"].map(lambda v: f"{v:.0f}%"), textposition="top center")
fig.add_scatter(x=dlabel, y=daily["Conversion %"], name="Conversion %", mode="lines+markers+text",
                line=dict(color=ORANGE, width=3), marker=dict(size=9),
                text=daily["Conversion %"].map(lambda v: f"{v:.1f}%"), textposition="bottom center")
fig.update_layout(height=360, margin=dict(t=30, b=10, l=10, r=10), hovermode="x unified",
                  xaxis=dict(type="category"),
                  yaxis=dict(title="%", ticksuffix="%", rangemode="tozero"),
                  yaxis2=dict(title="Leads", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
                  legend=dict(orientation="h", y=1.12, x=0))
fig.update_traces(hovertemplate="%{y:.1f}", selector=dict(type="scatter"))
st.plotly_chart(fig, use_container_width=True)
daily_t = with_total(daily.assign(Date=daily["Date"].dt.strftime("%d-%m-%Y")), "Date")
show_table(format_table(daily_t, "Date"), "daily_table")

# ---------------- ৪. শর্ট কোড অনুযায়ী ----------------
if not f.empty:
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

    sc = f.groupby("Final Code").agg(Leads=("Lead ID", "size")).reset_index()
    sc["Type"] = sc["Final Code"].map(code_group)
    sc = sc.sort_values("Leads", ascending=False)
    sc["%"] = sc["Leads"] / sc["Leads"].sum() * 100

    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(hbar(sc.head(20), "Leads", "Final Code", "%{x:,}", height_per=34), use_container_width=True)
    with c2:
        disp = pd.DataFrame({"Short Code": sc["Final Code"], "Type": sc["Type"],
                             "Leads": sc["Leads"].map(fmt_int), "%": sc["%"].map(fmt_pct)})
        disp.loc[len(disp)] = ["Total", "", fmt_int(sc["Leads"].sum()), "100.0%"]
        show_table(disp, "shortcode_table")

    st.markdown("#### ক্যাম্পেইন × শর্ট কোড (কোন ক্যাম্পেইনের লিড কোন অবস্থায় আছে)")
    pv = pd.crosstab(f["Campaign"], f["Final Code"])
    pv = pv[[c for c in sc["Final Code"].tolist() if c in pv.columns]]
    pv.insert(0, "Total Leads", pv.sum(axis=1))
    pv = pv.sort_values("Total Leads", ascending=False)
    pv.loc["Total"] = pv.sum()
    pv.columns.name = None
    show_table(pv.reset_index().astype(str), "campaign_code_pivot")

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
    st.markdown('<div class="section-header">কত নাম্বার কলে অর্ডার হয়েছে (শর্ট কোড অনুযায়ী)</div>',
                unsafe_allow_html=True)
    conv = f[f["Converted"]].copy()
    if conv.empty:
        st.info("এই সময়ের লিডে কোনো \"অর্ডার করেছেন\" শর্ট কোড নেই।")
    else:
        conv["Call No"] = conv["Order Call No"].astype(int)
        cn = conv.groupby("Call No").agg(Orders=("Lead ID", "size")).reset_index()
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
            fig.update_layout(height=360, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                              yaxis=dict(title="Orders"),
                              yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%", showgrid=False))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            disp = pd.DataFrame({"Call": cn["Call"], "Orders": cn["Orders"].map(fmt_int), "%": cn["%"].map(fmt_pct),
                                 "Cumulative %": cn["Cumulative %"].map(fmt_pct)})
            disp.loc[len(disp)] = ["Total", fmt_int(cn["Orders"].sum()), "100.0%", ""]
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
ag = combined("Agent").sort_values(["Sales", "Leads"], ascending=False)
show_table(format_table(with_total(ag, "Agent"), "Agent"), "agent_table")

# ---------------- ৭. Sales Data অর্ডারের তালিকা ----------------
with st.expander(f"Sales Data: Facebook Lead অর্ডারের তালিকা ({fmt_int(len(fbo))}টা)"):
    lst = fbo.sort_values("Order Date", ascending=False)
    show_table(pd.DataFrame({
        "Order Date": lst["Order Date"].dt.strftime("%d-%m-%Y"),
        "Order Collector": lst["Order Collector"],
        "Campaign": lst["Order Campaign"],
        "Campaign Name": lst["Campaign"],
        "Total Qty": lst["Qty"].map(fmt_int),
        "Product Price": lst["Revenue"].map(fmt_tk),
        "লিড শীটে পাওয়া গেছে": lst["Matched To Lead"].map({True: "হ্যাঁ", False: "না"}),
    }), "sales_data_list", bold_last=False)

# ---------------- হিসাবের নিয়ম ----------------
with st.expander("ℹ️ হিসাবের নিয়ম ও ডাটা চেক"):
    missing = int(in_range["Date Missing"].sum())
    no_date = int(leads["Lead Date"].isna().sum())
    st.markdown(f"""
- **Lead** = লিড শীটের প্রতিটা লাইন, লিডের তারিখ ধরে। তারিখ = `Date` কলাম; ফাঁকা থাকলে `1st call date` (এই রেঞ্জে {missing}টা)। দুটোই ফাঁকা এমন {no_date}টা লিড রিপোর্টে আসেনি।
- **Called** = অন্তত একটা শর্ট কোড আছে। **Contacted** = অন্তত একবার এগুলোর বাইরে কিছু: {", ".join(sorted(LL.NOT_CONTACTED_CODES))}। **Contact %** = Contacted ÷ Called।
- **Orders / Total Qty / Sales Amount** = Sales Data শীটের Campaign = Facebook Lead এমন সব অর্ডার, অর্ডারের তারিখ ধরে। Sales Amount = Product Price (ফাঁকা হলে Total Amount − Shipping)।
- **অর্ডারের Campaign** = Sales Data শীটের Campaign Name; ফাঁকা থাকলে নাম ছাড়া (ফাঁকা) লাইনে, অ্যামাউন্টসহ। একই ক্যাম্পেইনের ভিন্ন নাম মেলাতে `lead_logic.py`-এর `CAMPAIGN_ALIASES` এডিট করুন।
- **Conversion %** = Orders ÷ Leads। **অর্ডার করেছেন (শর্ট কোড)** = লিড শীটে শর্ট কোড "অর্ডার করেছেন" এমন লিড।
""")
