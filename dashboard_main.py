"""Facebook Lead Conversion Report | Bigganbaksho

Three Google Sheets published CSV sources. No uploaded customer files and no Google API credentials.
Data Provided is a lead COHORT report; date selection never cuts off later calls/orders.
Call Date and Order Date are independent activity-date reports.
"""
from __future__ import annotations

import base64
import datetime as dt
import re
from pathlib import Path

import pandas as pd


FACEBOOK_LEADS_1 = (
    'https://docs.google.com/spreadsheets/d/e/'
    '2PACX-1vRhGpSv6YJ5uwMeTI3r06mc4ZmqcCZlrTCQGsjDlDq2o1Y7uYhT3snVgI1jZ_zMUzxN_RZfOKcC-Rfm/'
    'pub?gid=1218239306&single=true&output=csv'
)
FACEBOOK_LEADS_2 = (
    'https://docs.google.com/spreadsheets/d/e/'
    '2PACX-1vSWfDJ5fR_NxnfT_1E5sfxh1BCuXIgHA_mwZ53P6Gw5oN6tHouRCx1GOxA7WDuWkmSrmz136pqXZmyv/'
    'pub?gid=1811215808&single=true&output=csv'
)
TELE_SALES_ORDERS = (
    'https://docs.google.com/spreadsheets/d/e/'
    '2PACX-1vTDhr-rwKe88LKKludd74G766j1l4vbvoaHi1YwwkefcfjCCgDGkZL6Ty9ngNv3gVvd5ezElgXghOs3/'
    'pub?gid=81417&single=true&output=csv'
)
BN_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
NOT_RECEIVED_CODES = {
    'কল ধরেনি', 'কল ধরেন নাই', 'কল রিসিভ করেনি', 'ফোন ধরেনি', 'ফোন রিসিভ করেনি',
    'ফোন বন্ধ', 'মোবাইল বন্ধ', 'নম্বর বন্ধ', 'নাম্বার বন্ধ', 'কল যাচ্ছে না',
    'ফোন যাচ্ছে না', 'নাম্বার বিজি', 'নম্বর বিজি', 'ফোন বিজি', 'কল ওয়েটিং',
    'রিং বাজার পর কল কেটে দিয়েছে', 'রিং বাযার পর কল কেটে দিয়েছে',
    'ডিজিট কম', 'ডিজিট বেশি', 'নাম্বার নেই', 'নাম্বার ভুল', 'নম্বর ভুল',
    'রং নাম্বার', 'বিদেশি নাম্বার', 'wrong number', 'not received', 'no answer',
    'not answered', 'busy', 'switched off', 'unreachable', 'not reachable',
}
UNKNOWN_CODES = {'', '-', 'n/a', 'nan', 'none', 'unknown', 'other', 'others', 'আদার্স', 'অন্যান্য'}
CONFIRMED_CODES = {'অর্ডার করেছেন', 'order confirmed', 'order placed', 'ordered'}


def norm_header(x):
    return re.sub(r'[^a-z0-9]+', '', str(x).strip().lower())


def find_col(frame, alternatives, required=False):
    lookup = {norm_header(c): c for c in frame.columns}
    for candidate in alternatives:
        col = lookup.get(norm_header(candidate))
        if col is not None:
            return col
    if required:
        raise ValueError(f"Expected one of {alternatives}; actual CSV columns begin: {list(frame.columns[:16])}")
    return None


def string_series(frame, col):
    if col is None:
        return pd.Series('', index=frame.index, dtype='object')
    return frame[col].fillna('').astype(str).str.strip()


def parse_date(values):
    """Day-first Google CSV dates; keeps invalid rows as NaT (never silently swaps month/day)."""
    s = pd.Series(values, copy=False).fillna('').astype(str).str.translate(BN_DIGITS).str.strip()
    try:
        dates = pd.to_datetime(s, dayfirst=True, errors='coerce', format='mixed')
    except (ValueError, TypeError):
        dates = pd.to_datetime(s, dayfirst=True, errors='coerce')
    serial = pd.to_numeric(s, errors='coerce')
    serial_mask = dates.isna() & serial.between(40000, 65000)
    if serial_mask.any():
        dates.loc[serial_mask] = pd.to_datetime(serial.loc[serial_mask], unit='D', origin='1899-12-30', errors='coerce')
    return dates.dt.normalize().where(dates.dt.year.between(2020, 2036))


def phone_key(value):
    s = str(value or '').translate(BN_DIGITS).strip()
    if re.fullmatch(r'\d+\.0+', s):
        s = s.split('.')[0]
    s = re.sub(r'\D', '', s)
    return s[-10:] if len(s) >= 10 else ''


def as_amount(series):
    cleaned = (pd.Series(series, copy=False).fillna('').astype(str).str.translate(BN_DIGITS)
               .str.replace(r'[^0-9.\-]', '', regex=True))
    return pd.to_numeric(cleaned, errors='coerce').fillna(0).clip(lower=0)


def is_converted(code):
    x = re.sub(r'\s+', ' ', str(code or '').strip()).casefold()
    return ('অর্ডার করেছেন' in x) or (x in CONFIRMED_CODES)


def classify_code(code):
    x = re.sub(r'\s+', ' ', str(code or '').strip()).casefold()
    if is_converted(x):
        return 'Received'
    if x in UNKNOWN_CODES:
        return 'Unknown'
    if x in NOT_RECEIVED_CODES:
        return 'Not Received'
    # Only explicitly labelled no-answer codes are marked Not Received;
    # unverified labels can be inspected in the Short Code report.
    return 'Received'


def call_columns(frame):
    """Map 1st..10th Short Code fields to their own Call Date, irrespective of column positions."""
    codes, dated = {}, {}
    for col in frame.columns:
        name = norm_header(col)
        if 'shortcode' in name:
            match = re.search(r'(\d+)(?:st|nd|rd|th)?', name)
            if match:
                number = int(match.group(1))
            else:
                word = next((i for w, i in [('first', 1), ('second', 2), ('third', 3),
                           ('fourth', 4), ('fifth', 5), ('sixth', 6), ('seventh', 7),
                           ('eighth', 8), ('ninth', 9), ('tenth', 10)] if w in name), None)
                number = word if word else (1 if name in {'shortcode', 'shortcode1st'} else None)
            if number is not None and 1 <= number <= 10:
                codes[number] = col
        if 'calldate' in name:
            match = re.search(r'(\d+)', name)
            if match:
                num = int(match.group(1))
                if 1 <= num <= 10:
                    dated[num] = col
    if not codes:
        # Useful for a differently named second sheet; do not infer conversions from Remarks.
        return []
    return [(num, code, dated.get(num)) for num, code in sorted(codes.items())]


def prepare_lead_sheet(raw, source_label, source_no):
    """Read one source. Return normalized leads, call events and source notes."""
    frame = raw.copy()
    frame.columns = [str(x).strip().replace('\ufeff', '') for x in frame.columns]
    date_col = find_col(frame, ['Date', 'Data Provided', 'Date Provided', 'Provided Date', 'Lead Date', 'Date of Lead', 'Lead Created Date', 'Created Date', 'Created At', 'Entry Date', 'Submission Date', 'Timestamp'], True)
    phone_col = find_col(frame, ['Contact Number', 'Contact No', 'Phone Number', 'Phone No.', 'Phone', 'Mobile Number', 'Mobile No', 'Mobile No.', 'Mobile', 'Contact', 'Phone No', 'WhatsApp Number'], True)
    campaign_col = find_col(frame, ['Campaign Name', 'Lead Campaign', 'Campaign', 'Lead Source', 'Source Name', 'Source', 'Ad Name', 'Ad Campaign'])
    agent_col = find_col(frame, ['Agent Name', 'Agent', 'Assigned To', 'Call Agent', 'Order Collector', 'Caller'])
    d = pd.DataFrame(index=frame.index)
    d['provided_date'] = parse_date(string_series(frame, date_col))
    d['phone'] = string_series(frame, phone_col).map(phone_key)
    d['campaign'] = string_series(frame, campaign_col).replace('', '(Campaign Blank)')
    d['agent'] = string_series(frame, agent_col).replace('', '(No Agent)')
    d['source'] = source_label
    d['row_uid'] = [f'{source_no}:{i + 2}' for i in range(len(d))]
    # Empty template/formatted rows are excluded; a no-phone lead with a valid Date still counts.
    meaningful = d['phone'].ne('') | d['provided_date'].notna()
    d = d.loc[meaningful].copy()
    d['lead_key'] = [
        f"{ph}|{day:%Y-%m-%d}|{camp.strip().casefold()}" if ph and pd.notna(day)
        else uid for ph, day, camp, uid in zip(d['phone'], d['provided_date'], d['campaign'], d['row_uid'])
    ]
    pairs = call_columns(frame)
    events = []
    missing_result_events = []
    event_columns = ['row_uid','lead_key','phone','campaign','agent','source','provided_date']
    for number, code_col, when_col in pairs:
        codes = string_series(frame, code_col).loc[d.index]
        when = parse_date(string_series(frame, when_col)).loc[d.index]

        # A date with a blank Short Code is NOT evidence that a call was made.
        # Keep it for transparent data-quality auditing instead of calling it an attempt.
        missing = codes.eq('') & when.notna()
        if missing.any():
            pending = d.loc[missing, event_columns].copy()
            pending['call_no'] = int(number)
            pending['call_date'] = when.loc[missing]
            missing_result_events.append(pending)

        # The official call metrics are based on recorded Short Code outcomes.
        mask = codes.ne('')
        if not mask.any():
            continue
        x = d.loc[mask, event_columns].copy()
        x['call_no'] = int(number)
        x['short_code'] = codes.loc[mask]
        x['call_date'] = when.loc[mask]
        events.append(x)
    calls = pd.concat(events, ignore_index=True) if events else pd.DataFrame(columns=[
        'row_uid','lead_key','phone','campaign','agent','source','provided_date',
        'call_no','short_code','call_date'])
    missing_results = pd.concat(missing_result_events, ignore_index=True) if missing_result_events else pd.DataFrame(columns=[
        'row_uid','lead_key','phone','campaign','agent','source','provided_date','call_no','call_date'])
    notes = {'source': source_label, 'rows': len(d), 'missing_dates': int(d.provided_date.isna().sum()),
             'short_code_fields': len(pairs)}
    return d.reset_index(drop=True), calls, notes, missing_results


def build_leads(raw1, raw2):
    d1, c1, n1, p1 = prepare_lead_sheet(raw1, 'Facebook Sheet 1', 1)
    d2, c2, n2, p2 = prepare_lead_sheet(raw2, 'Facebook Sheet 2', 2)
    all_rows = pd.concat([d1, d2], ignore_index=True)
    # Same phone + provided date + campaign in both sources is one lead, not two;
    # merge later followups instead of dropping a source's Short Codes.
    source_map = all_rows.groupby('lead_key')['source'].agg(lambda s: ' + '.join(sorted(s.unique())))
    leads = all_rows.drop_duplicates('lead_key', keep='first').copy()
    leads['source'] = leads['lead_key'].map(source_map)
    calls = pd.concat([c1, c2], ignore_index=True)
    missing_results = pd.concat([p1, p2], ignore_index=True)
    if not missing_results.empty:
        # Same lead/call/date across sources should not create duplicate warnings.
        missing_results = missing_results.drop_duplicates(['lead_key','call_no','call_date'],keep='first').copy()
        missing_results['source'] = missing_results['lead_key'].map(source_map)
    if not calls.empty:
        calls = calls.drop_duplicates(['lead_key','call_no','short_code','call_date'], keep='first').copy()
        calls['source'] = calls['lead_key'].map(source_map)
        calls['status'] = calls.short_code.map(classify_code)
        calls['confirmed'] = calls.short_code.map(is_converted)
        calls.sort_values(['lead_key','call_no','call_date'], kind='stable', inplace=True)
        calls['conversion_event'] = calls.confirmed & ~calls.loc[calls.confirmed, 'lead_key'].duplicated().reindex(calls.index, fill_value=False)
        calls.reset_index(drop=True, inplace=True)
        if not missing_results.empty:
            # If a duplicate sheet has the corresponding actual Short Code, it is recorded.
            actual = calls[['lead_key','call_no','call_date']].drop_duplicates().assign(_recorded=True)
            missing_results = missing_results.merge(
                actual, on=['lead_key','call_no','call_date'],how='left')
            missing_results = missing_results.loc[missing_results['_recorded'].isna()].drop(columns=['_recorded'])
    else:
        calls['status'] = pd.Series(dtype='object')
        calls['confirmed'] = pd.Series(dtype='bool')
        calls['conversion_event'] = pd.Series(dtype='bool')
    leads['person_key'] = leads['phone'].where(leads.phone.ne(''), leads['lead_key'])
    notes = [n1, n2]
    notes.append({'deduped_leads': int(len(all_rows)-len(leads)), 'total_leads':len(leads),
                  'total_calls':len(calls), 'date_only_no_code':len(missing_results)})
    return leads, calls, notes, missing_results.reset_index(drop=True)


def prepare_orders(raw):
    d = raw.copy()
    d.columns = [str(x).strip().replace('\ufeff','') for x in d.columns]
    date_col = find_col(d, ['Order Date', 'Date', 'Invoice Date'], True)
    price_col = find_col(d, ['Product Price'], True)  # Exact final column; never sum item unit prices.
    category_col = find_col(d, ['Campaign', 'Source', 'Order Source'], True)
    name_col = find_col(d, ['Campaign Name', 'Ad Campaign Name', 'Ad Name'])
    phone_col = find_col(d, ['Contact Number','Phone Number','Mobile Number','Phone','Mobile'])
    invoice_col = find_col(d, ['Invoice ID','Order ID','Invoice Number'])
    qty_col = find_col(d, ['Total Qty','Total QTY','Quantity'])
    orders = pd.DataFrame(index=d.index)
    orders['order_date'] = parse_date(string_series(d,date_col))
    orders['phone'] = string_series(d,phone_col).map(phone_key)
    orders['campaign_type'] = string_series(d,category_col)
    orders['order_campaign_name'] = string_series(d,name_col)  # Blank MUST stay blank.
    orders['invoice'] = string_series(d,invoice_col)
    orders['amount'] = as_amount(string_series(d,price_col))
    orders['qty'] = as_amount(string_series(d,qty_col))
    orders['order_id'] = [f'O{i + 2}' for i in range(len(orders))]
    # Explicit Facebook category, not Existing / Cart Abandon.
    is_fb = orders.campaign_type.str.contains('facebook',case=False,regex=False) | (
        orders.campaign_type.str.contains(r'\bfb\b',case=False,regex=True))
    fb = orders.loc[is_fb].copy()
    invalid = int(fb.order_date.isna().sum())
    fb = fb.loc[fb.order_date.notna()].copy()
    # Repeat exports of an *identical* invoice/order record should not inflate money;
    # preserve distinct rows when an invoice ID is blank or amounts differ.
    has_invoice = fb.invoice.ne('')
    duplicates = fb.loc[has_invoice].duplicated(['invoice','order_date','amount','phone'],keep='first')
    duplicate_ids = fb.loc[has_invoice].loc[duplicates].index
    fb = fb.drop(index=duplicate_ids)
    return fb.reset_index(drop=True), {'raw_rows':len(d), 'facebook_order_rows':len(fb),
                                      'invalid_fb_dates':invalid, 'duplicate_orders_removed':len(duplicate_ids)}


def attach_orders_to_leads(leads, orders):
    """First qualifying Provided-Date lead owns future orders for the same phone, with NO 30-day cap.

    Every order maps to zero or one lead; unmatched orders stay visible in Order Date report.
    """
    out = orders.copy()
    out['lead_key'] = pd.Series(pd.NA, index=out.index, dtype='object')
    eligible = (leads.loc[leads.phone.ne('') & leads.provided_date.notna(),
                           ['phone','provided_date','lead_key']]
                .sort_values(['phone','provided_date','lead_key'])
                .drop_duplicates(['phone','provided_date','lead_key']))
    groups = {phone: part for phone, part in eligible.groupby('phone', sort=False)}
    for i, row in out.iterrows():
        if not row.phone or pd.isna(row.order_date):
            continue
        matches = groups.get(row.phone)
        if matches is None:
            continue
        preceding = matches.loc[matches.provided_date <= row.order_date]
        if not preceding.empty:
            out.at[i, 'lead_key'] = preceding.iloc[0]['lead_key']
    return out


def make_cohort(leads, calls, orders):
    d = leads[['lead_key','person_key','provided_date','phone','source','campaign','agent']].copy()
    if not calls.empty:
        counts = calls.groupby('lead_key').agg(
            calls=('short_code','size'),
            received_calls=('status', lambda s: int((s=='Received').sum())),
            not_received_calls=('status', lambda s: int((s=='Not Received').sum())),
            unknown_calls=('status', lambda s: int((s=='Unknown').sum())),
            converted=('confirmed','any'))
        d = d.join(counts,on='lead_key')
    for col in ['calls','received_calls','not_received_calls','unknown_calls']:
        d[col] = pd.to_numeric(d.get(col, pd.Series(0,index=d.index)),errors='coerce').fillna(0).astype(int)
    d['converted'] = d.get('converted',pd.Series(False,index=d.index)).fillna(False).astype(bool)
    d['called'] = d.calls.gt(0)
    d['received'] = d.received_calls.gt(0)
    d['not_received'] = d.called & ~d.received & d.not_received_calls.gt(0)
    if not orders.empty:
        stats = (orders.dropna(subset=['lead_key']).groupby('lead_key')
                 .agg(orders=('order_id','count'), amount=('amount','sum')))
        d = d.join(stats,on='lead_key')
    d['orders'] = pd.to_numeric(d.get('orders',pd.Series(0,index=d.index)),errors='coerce').fillna(0).astype(int)
    d['amount'] = pd.to_numeric(d.get('amount',pd.Series(0.,index=d.index)),errors='coerce').fillna(0.)
    return d


def cohort_metrics(view):
    """Unique phone-based buyer and reached counts; other counts are lead records."""
    if view.empty:
        return dict(Leads=0,Called=0,Received=0,NotReceived=0,Unknown=0,NotCalled=0,
                    Calls=0,ReceivedCalls=0,Conversions=0,ReceivedCustomers=0,Rate=0.,
                    ContactRate=0.,Orders=0,Amount=0.)
    rec = view.loc[view.received,'person_key'].nunique()
    buyers = view.loc[view.converted,'person_key'].nunique()
    return dict(Leads=len(view),Called=int(view.called.sum()),Received=int(view.received.sum()),
                NotReceived=int(view.not_received.sum()),
                Unknown=int((view.called & ~view.received & ~view.not_received).sum()),
                NotCalled=int((~view.called).sum()), Calls=int(view.calls.sum()),
                ReceivedCalls=int(view.received_calls.sum()),Conversions=buyers,ReceivedCustomers=rec,
                Rate=round(buyers/max(rec,1)*100,1),ContactRate=round(rec/max(view.person_key.nunique(),1)*100,1),
                Orders=int(view.orders.sum()),Amount=float(view.amount.sum()))


def cohort_group(view, by):
    fields = [by] if isinstance(by,str) else list(by)
    names = fields + ['Leads','Called','Received','Not Received','Not Called','Confirmed Buyers',
                      'Contact %','Conversion %','Order Count','Order Value']
    if view.empty:
        return pd.DataFrame(columns=names)
    rows=[]
    grouped = view.groupby(fields[0] if len(fields)==1 else fields,dropna=False,sort=True)
    for key, group in grouped:
        keyvals = (key,) if len(fields)==1 else key
        m = cohort_metrics(group)
        rows.append([*keyvals,m['Leads'],m['Called'],m['Received'],m['NotReceived'],m['NotCalled'],
                     m['Conversions'],m['ContactRate'],m['Rate'],m['Orders'],m['Amount']])
    return pd.DataFrame(rows,columns=names)


def call_group(calls, by):
    fields = [by] if isinstance(by,str) else list(by)
    names=fields+['Call Attempts','Received','Not Received','Unknown','Confirmed Buyers','Answer %',
                  'Conversion %']
    if calls.empty:
        return pd.DataFrame(columns=names)
    rows=[]
    for key,g in calls.groupby(fields[0] if len(fields)==1 else fields,dropna=False,sort=True):
        values=(key,) if len(fields)==1 else key
        received=int(g.status.eq('Received').sum())
        buyer=g.loc[g.conversion_event,'phone'].where(g.loc[g.conversion_event,'phone'].ne(''),
                                                     g.loc[g.conversion_event,'lead_key']).nunique()
        reached=g.loc[g.status.eq('Received'),'phone'].where(g.loc[g.status.eq('Received'),'phone'].ne(''),
                                                             g.loc[g.status.eq('Received'),'lead_key']).nunique()
        rows.append([*values,len(g),received,int(g.status.eq('Not Received').sum()),
                     int(g.status.eq('Unknown').sum()),buyer,round(100*received/max(len(g),1),1),
                     round(100*buyer/max(reached,1),1)])
    return pd.DataFrame(rows,columns=names)


def order_group(orders, by):
    fields=[by] if isinstance(by,str) else list(by)
    columns=fields+['Orders','Order Value','Avg Order Value','Qty']
    if orders.empty:
        return pd.DataFrame(columns=columns)
    data = (orders.groupby(fields,dropna=False).agg(Orders=('order_id','count'),
            **{'Order Value':('amount','sum'), 'Qty':('qty','sum')}).reset_index())
    data['Avg Order Value'] = data['Order Value'] / data['Orders'].clip(lower=1)
    return data[columns]


def date_filter(frame, field, start, end):
    if frame.empty:
        return frame.copy()
    return frame.loc[frame[field].dt.date.between(start,end, inclusive='both')].copy()


def money(n):
    return f'৳{float(n):,.0f}'


def percent(n):
    return f'{float(n):.1f}%'


def display_table(st, table, name, date_columns=()):
    if table.empty:
        st.info('এই Date Range/Filter-এ কোনো ডেটা নেই।')
        return
    printable = table.copy()
    for col in printable.columns:
        if col in date_columns or pd.api.types.is_datetime64_any_dtype(printable[col]):
            printable[col] = pd.to_datetime(printable[col],errors='coerce').dt.strftime('%d-%m-%Y')
        elif col in {'Order Value','Avg Order Value'}:
            printable[col] = printable[col].map(money)
        elif col.endswith('%'):
            printable[col] = printable[col].map(percent)
    st.dataframe(printable,hide_index=True,use_container_width=True,height=min(480,65+len(printable)*35))
    st.download_button('⬇ CSV',table.to_csv(index=False).encode('utf-8-sig'),
                       file_name=name,mime='text/csv',key='download_'+name)


def theme(st):
    st.markdown('''<style>
    .block-container{max-width:1480px;padding-top:1.5rem;padding-bottom:3rem}
    section[data-testid="stSidebar"]{background:#f5f7fa}
    div[data-testid="stMetric"]{background:#fff;border:1px solid #e9edf3;border-top:4px solid #ff6600;
        border-radius:11px;padding:12px 14px;box-shadow:0 2px 8px rgba(0,0,0,.035)}
    div[data-testid="stMetricLabel"]{font-size:13px;font-weight:700;color:#42526c}
    div[data-testid="stMetricValue"]{font-size:29px;font-weight:800}
    .report-head{border-left:5px solid #ff6600;padding-left:12px;font-size:22px;font-weight:800;margin:20px 0 14px}
    .report-note{color:#5f6d83;font-size:14px;margin:5px 0 17px}
    .bb-header{position:relative;text-align:center;padding:6px 90px 22px;margin:0 0 18px;min-height:142px}
    .bb-logo{position:absolute;top:12px;left:6px;width:84px;height:auto;border-radius:5px}
    .bb-title{color:#ff6600;font-weight:850;font-size:clamp(25px,3vw,42px);line-height:1.3}
    .bb-credit{font-size:12px;color:#718096;font-style:italic;margin:12px 0 8px}
    .bb-slogan{font-size:22px;font-weight:800;color:#1b2430}
    .bb-vision{font-size:15px;color:#6b7280}
    @media(max-width:700px){.bb-header{padding:60px 2px 15px}.bb-logo{top:5px;left:5px;width:66px}
     .bb-slogan{font-size:17px}}
    </style>''',unsafe_allow_html=True)


def header(st):
    pic = Path(__file__).resolve().parent / 'logo.png'
    logo=''
    if pic.exists():
        logo = '<img class="bb-logo" src="data:image/png;base64,'+base64.b64encode(pic.read_bytes()).decode('ascii')+'" alt="Bigganbaksho">'
    st.markdown(f'''<div class="bb-header">{logo}<div class="bb-title">Facebook Lead Conversion Report</div>
    <div class="bb-credit">Web App Developed By-Shujoy Shaha</div>
    <div class="bb-slogan">ম্যানুয়েল কাজের দিন শেষ, বিজ্ঞানবাক্সে বাংলাদেশ</div>
    <div class="bb-vision">অন্যরকম বাংলাদেশের স্বপ্ন নিয়ে</div></div>''',unsafe_allow_html=True)


def metrics_grid(st, stats, schema):
    for i in range(0,len(schema),5):
        row=schema[i:i+5]
        cols=st.columns(len(row))
        for col,(label,key,formatter,tip) in zip(cols,row):
            value=stats.get(key,0)
            col.metric(label,formatter(value),help=tip)


def bar_chart(st, frame, label, value, caption, top=10):
    if frame.empty:
        return
    import plotly.express as px
    x=frame.sort_values(value,ascending=False).head(top).sort_values(value)
    fig=px.bar(x,x=value,y=label,orientation='h',color=label,text=value,
               color_discrete_sequence=px.colors.qualitative.Vivid)
    fig.update_layout(height=max(300,len(x)*42+70),margin=dict(l=10,r=65,t=14,b=25),showlegend=False,
                      xaxis_title='',yaxis_title='')
    fig.update_traces(textposition='outside',hovertemplate='%{y}<br>%{x:,.0f}<extra></extra>')
    st.caption(caption)
    st.plotly_chart(fig,use_container_width=True)


def main():
    import streamlit as st
    import plotly.express as px
    st.set_page_config(page_title='Facebook Lead Conversion Report',page_icon='📊',layout='wide')
    theme(st)
    header(st)

    @st.cache_data(ttl=300,show_spinner='Google Sheets থেকে তথ্য আনা হচ্ছে…')
    def get_csv(url, kind='leads'):
        # The published Tele Sales sheet can be very wide; read only report columns.
        selected = {'orderdate','date','invoicedate','contactnumber','phonenumber','mobilenumber',
                    'phone','mobile','campaign','source','ordersource','campaignname','adcampaignname',
                    'adname','productprice','invoiceid','orderid','invoicenumber','totalqty','quantity'}
        col_filter = (lambda name: norm_header(name) in selected) if kind=='orders' else None
        data=pd.read_csv(url,dtype=str,low_memory=False,encoding='utf-8-sig',
                         keep_default_na=False,usecols=col_filter)
        data.columns=data.columns.astype(str).str.strip()
        if len(data.columns)<2 or data.empty:
            raise ValueError('Published CSV-তে প্রয়োজনীয় data/columns পাওয়া যায়নি।')
        return data

    with st.sidebar:
        st.markdown('### <span style="color:#ff6600">Filters</span>',unsafe_allow_html=True)
        if st.button('↻ Refresh Google Sheets',use_container_width=True):
            get_csv.clear()
            st.rerun()

    try:
        raw1=get_csv(FACEBOOK_LEADS_1)
        raw2=get_csv(FACEBOOK_LEADS_2)
        raw_orders=get_csv(TELE_SALES_ORDERS,'orders')
        leads,calls,notes,missing_results=build_leads(raw1,raw2)
        orders,order_notes=prepare_orders(raw_orders)
        orders=attach_orders_to_leads(leads,orders)
        cohort=make_cohort(leads,calls,orders)
    except Exception as exc:
        st.error('Google Sheet data load / column mapping সমস্যা হয়েছে: '+str(exc))
        st.caption('সঠিক তিনটি Published CSV link, Date/Phone/Short Code/Order Date/Product Price কলাম যাচাই করুন। কোনো CSV বা Excel upload করার প্রয়োজন নেই।')
        st.stop()

    if notes[0]['short_code_fields']==0 or notes[1]['short_code_fields']==0:
        st.warning('একটি Facebook Lead Sheet-এ Short Code কলাম চেনা যায়নি। Data Quality অংশে source ও column naming যাচাই করুন।')

    if cohort.empty:
        st.warning('Google Sheet-এ কোনো বৈধ Lead পাওয়া যায়নি।')
        st.stop()
    # Default latest REAL provided date, never a future typo. Calendar remains freely selectable.
    today=dt.date.today()
    valid=cohort.loc[cohort.provided_date.notna() & (cohort.provided_date.dt.date<=today),'provided_date']
    latest=valid.max().date() if not valid.empty else today
    first=cohort.provided_date.dropna().min()
    earliest=first.date() if pd.notna(first) else today-dt.timedelta(days=30)
    default_start=max(earliest,latest-dt.timedelta(days=30))

    with st.sidebar:
        start=st.date_input('Start Date',value=default_start,format='YYYY/MM/DD',key='fb_cohort_start_v4')
        end=st.date_input('End Date',value=latest,format='YYYY/MM/DD',key='fb_cohort_end_v4')
        selected_campaign=st.selectbox('Campaign',['All Campaigns']+sorted(cohort.campaign.dropna().unique().tolist()))
        selected_agent=st.selectbox('Agent',['All Agents']+sorted(cohort.agent.dropna().unique().tolist()))
        st.caption('ডেটা: Google Sheet থেকে সরাসরি · Auto-refresh প্রতি ৫ মিনিটে')
    if start>end:
        st.warning('Start Date অবশ্যই End Date-এর আগে বা সমান হতে হবে।')
        st.stop()

    filtered_cohort=cohort.copy()
    if selected_campaign!='All Campaigns':
        filtered_cohort=filtered_cohort.loc[filtered_cohort.campaign.eq(selected_campaign)]
    if selected_agent!='All Agents':
        filtered_cohort=filtered_cohort.loc[filtered_cohort.agent.eq(selected_agent)]
    visible_lead_ids=set(filtered_cohort.lead_key)
    filtered_calls=calls.loc[calls.lead_key.isin(visible_lead_ids)].copy()
    chosen=date_filter(filtered_cohort,'provided_date',start,end)
    chosen_ids=set(chosen.lead_key)
    cohort_calls=calls.loc[calls.lead_key.isin(chosen_ids)]
    day_calls=date_filter(filtered_calls,'call_date',start,end)
    filtered_missing=missing_results.loc[missing_results.lead_key.isin(visible_lead_ids)]
    day_missing=date_filter(filtered_missing,'call_date',start,end)
    order_dates=date_filter(orders,'order_date',start,end)

    st.caption(f'Lead Sheet 1: {notes[0]["rows"]:,} rows · Lead Sheet 2: {notes[1]["rows"]:,} rows · '
               f'Combined leads: {len(leads):,} · Recorded calls: {len(calls):,} · '
               f'Facebook orders: {len(orders):,} · Selected dates: {start:%d %b %Y} – {end:%d %b %Y}')
    t1,t2,t3,t4=st.tabs(['📅 Data Provided','📞 Call Date','🎯 Campaign & Revenue','💰 Order Date'])

    with t1:
        st.markdown('<div class="report-head">Data Provided — Lead Cohort Report</div>',unsafe_allow_html=True)
        st.markdown('<div class="report-note"><b>শুধু Lead দেওয়ার তারিখ ফিল্টার হয়।</b> ৫ নভেম্বরের Lead ২০ নভেম্বর বা পরের মাসে Call/Convert/Order হলেও ফলাফল <b>৫ নভেম্বরের সারিতেই</b> দেখাবে। পরের Call/Order Date-এর কোনো ৩০ দিনের সীমা নেই।</div>',unsafe_allow_html=True)
        m=cohort_metrics(chosen)
        metrics_grid(st,m,[
            ('Leads','Leads',lambda x:f'{x:,}','একই ফোন + দিন + Campaign duplicate হলে এক Lead'),
            ('Called Leads','Called',lambda x:f'{x:,}','At least one nonempty recorded Short Code'),
            ('Received Leads','Received',lambda x:f'{x:,}','কমপক্ষে একবার Received'),
            ('Confirmed Buyers','Conversions',lambda x:f'{x:,}','১ম–১০ম যেকোনো Short Code = অর্ডার করেছেন'),
            ('Conversion Rate','Rate',percent,'Unique Buyers ÷ Unique Received Customers'),
            ('Not Received Leads','NotReceived',lambda x:f'{x:,}','একবারও Received নয় কিন্তু Not Received আছে'),
            ('Not Called','NotCalled',lambda x:f'{x:,}','কোনো কল এন্ট্রি নেই'),
            ('Contact Rate','ContactRate',percent,'Unique Received ÷ Unique Leads'),
            ('Matched Orders','Orders',lambda x:f'{x:,}','ফোন নম্বর + পরে Order Date মিলেছে; অতিরিক্ত ৩০ দিনের সীমা নেই'),
            ('Matched Order Value','Amount',money,'বাছাই করা Leads-এর সঙ্গে মেলা ভবিষ্যতের Orders-এর Product Price')
        ])
        st.markdown('#### Day-wise Data Provided')
        day=cohort_group(chosen,'provided_date').sort_values('provided_date')
        if not day.empty:
            fig=px.line(day,x='provided_date',y=['Leads','Received','Confirmed Buyers','Order Count'],markers=True,
                        color_discrete_sequence=['#ff6600','#2e9c75','#5d65be','#f1ab29'])
            fig.update_layout(height=330,legend_orientation='h',margin=dict(l=10,r=10,t=15,b=15),
                              xaxis_title='',yaxis_title='')
            st.plotly_chart(fig,use_container_width=True)
        display_table(st,day,'data_provided_day.csv')
        st.markdown('#### Source-wise (Two Facebook Lead Sheets)')
        display_table(st,cohort_group(chosen,'source').sort_values('Leads',ascending=False),'data_provided_sources.csv')
        st.markdown('#### Campaign / Lead Source-wise')
        ca=cohort_group(chosen,'campaign').sort_values('Leads',ascending=False)
        columns=st.columns([1.15,1])
        with columns[0]:bar_chart(st,ca,'campaign','Leads','Campaign অনুযায়ী Lead সংখ্যা')
        with columns[1]:bar_chart(st,ca,'campaign','Confirmed Buyers','Campaign অনুযায়ী Confirmed Buyers')
        display_table(st,ca,'data_provided_campaigns.csv')
        with st.expander('Day × Campaign — Detailed',expanded=False):
            display_table(st,cohort_group(chosen,['provided_date','campaign']),'data_provided_day_campaign.csv')
        with st.expander('Agent Performance',expanded=False):
            display_table(st,cohort_group(chosen,'agent'),'data_provided_agents.csv')
        with st.expander('Short Code Breakdown (including later calls)',expanded=False):
            codes=cohort_calls.groupby(['short_code','status'],dropna=False).agg(
                Calls=('lead_key','size'), **{'Confirmed Events':('confirmed','sum')}).reset_index()
            if not codes.empty:
                codes['%'] = codes.Calls/max(len(cohort_calls),1)*100
            display_table(st,codes.sort_values('Calls',ascending=False),'data_provided_short_codes.csv')

    with t2:
        st.markdown('<div class="report-head">Call Date — Calling Performance</div>',unsafe_allow_html=True)
        st.markdown('<div class="report-note">Call Date selects recorded Short Code outcomes from 1st to 10th follow-ups. Date-only entries with no Short Code are shown separately as <b>Result Not Entered</b>, not treated as completed calls. A confirmed conversion is counted only once per lead.</div>',unsafe_allow_html=True)
        c_total=len(day_calls)
        rc=int(day_calls.status.eq('Received').sum())
        nc=int(day_calls.status.eq('Not Received').sum())
        uc=int(day_calls.status.eq('Unknown').sum())
        buyers=day_calls.loc[day_calls.conversion_event,'phone'].where(day_calls.loc[day_calls.conversion_event,'phone'].ne(''),day_calls.loc[day_calls.conversion_event,'lead_key']).nunique()
        reached=day_calls.loc[day_calls.status.eq('Received'),'phone'].where(day_calls.loc[day_calls.status.eq('Received'),'phone'].ne(''),day_calls.loc[day_calls.status.eq('Received'),'lead_key']).nunique()
        metrics_grid(st,{'Calls':c_total,'Received':rc,'NotReceived':nc,'Unknown':uc,
                         'Unrecorded':len(day_missing),'Confirmed':buyers,
                         'Answer':100*rc/max(c_total,1),'Conversion':100*buyers/max(reached,1)},[
            ('Call Attempts','Calls',lambda x:f'{x:,}','একটি Short Code/Call Date = একটি call'),
            ('Received Calls','Received',lambda x:f'{x:,}','Short Code classified Received'),
            ('Not Received Calls','NotReceived',lambda x:f'{x:,}','Only recorded Not Received short codes'),
            ('Confirmed Buyers','Confirmed',lambda x:f'{x:,}','প্রথম অর্ডার করেছেন Call Date-এর দিন'),
            ('Conversion Rate','Conversion',percent,'Unique Confirmed Customers ÷ Unique Reached Customers'),
            ('Result Not Entered','Unrecorded',lambda x:f'{x:,}','Call Date is present, but its Short Code is empty; excluded from attempts'),
            ('Unknown Codes','Unknown',lambda x:f'{x:,}','A nonempty but unclassified Short Code'),
            ('Answer Rate','Answer',percent,'Received recorded calls / recorded call attempts'),
        ])
        if len(day_missing):
            st.caption(f'{len(day_missing):,} date-only entries have no Short Code in this date range. '
                       'They are NOT counted as received, missed, or attempted calls.')
        with st.expander('Audit: Call Date filled, Short Code blank',expanded=False):
            audit=day_missing.groupby(['call_date','source','call_no'],dropna=False).size().reset_index(name='No Result Entries')
            display_table(st,audit,'date_only_no_result_audit.csv')
        st.markdown('#### Day-wise Call Report')
        daycall=call_group(day_calls,'call_date').sort_values('call_date')
        display_table(st,daycall,'call_date_daily.csv')
        st.markdown('#### 1st–10th Call Performance')
        callno=call_group(day_calls,'call_no').sort_values('call_no')
        display_table(st,callno,'call_number_report.csv')
        st.markdown('#### Short Code Report & Percentage')
        bycode=call_group(day_calls,['short_code','status']).sort_values('Call Attempts',ascending=False)
        if not bycode.empty:
            bycode['Call Share %']=100*bycode['Call Attempts']/max(c_total,1)
        display_table(st,bycode,'short_code_report.csv')
        with st.expander('Source / Campaign / Agent breakdown',expanded=False):
            st.markdown('**Lead Sheet-wise Calls**')
            display_table(st,call_group(day_calls,'source'),'call_source.csv')
            st.markdown('**Campaign-wise Calls**')
            display_table(st,call_group(day_calls,'campaign'),'call_campaign.csv')
            st.markdown('**Agent-wise Calls**')
            display_table(st,call_group(day_calls,'agent'),'call_agent.csv')
        with st.expander('Call Date × Campaign',expanded=False):
            display_table(st,call_group(day_calls,['call_date','campaign']),'call_date_campaign.csv')

    with t3:
        st.markdown('<div class="report-head">Campaign Conversion & Revenue</div>',unsafe_allow_html=True)
        st.caption('Lead Campaign-এর Conversion = Facebook Short Code; Order Value = ফোন নম্বর দিয়ে attribution করা Facebook Lead Orders। Order Sheet-এর Campaign Name ফাঁকা থাকলে আলাদা Blank group-এ টাকা দেখানো হয়।')
        cmp=cohort_group(chosen,'campaign').sort_values('Order Value',ascending=False)
        display_table(st,cmp,'lead_campaign_conversion_and_amount.csv')
        bar_chart(st,cmp,'campaign','Order Value','Phone-matched Order Value by Lead Campaign')
        st.markdown('#### Order Sheet Campaign Name — All Facebook Orders')
        st.caption('এটি Order Sheet-এর Campaign Name field, Lead Campaign attribution নয়। খালি Campaign Name-ও Order Value-সহ গণনা হয়। এখানে Date Filter Order Date-এর ওপর কাজ করে।')
        s=order_dates.copy()
        s['order_campaign_display']=s.order_campaign_name.replace('', '(Blank Campaign Name)')
        byorder=order_group(s,'order_campaign_display').sort_values('Order Value',ascending=False)
        display_table(st,byorder.rename(columns={'order_campaign_display':'Campaign Name'}),'order_campaign_names.csv')
        unmatch=orders.loc[orders.lead_key.isna()]
        st.caption(f'Full Facebook Order file: {len(orders):,} orders · {money(orders.amount.sum())} | '
                   f'Lead-unmatched: {len(unmatch):,} orders · {money(unmatch.amount.sum())}. '
                   'Unmatched orders remain in the Order Date/Campaign Name reports, not silently discarded.')

    with t4:
        st.markdown('<div class="report-head">Order Date — Facebook Sales</div>',unsafe_allow_html=True)
        st.caption('এখানে Date Range কেবল Tele Sales Order-এর Order Date বেছে নেয়। Campaign category Facebook হলে Order Value গণনা হবে, Campaign Name ফাঁকা হলেও।')
        metrics_grid(st,{'orders':len(order_dates),'amount':float(order_dates.amount.sum()),
                        'qty':float(order_dates.qty.sum()),'aov':float(order_dates.amount.mean()) if len(order_dates) else 0},[
            ('Facebook Orders','orders',lambda x:f'{x:,}','Order Date অনুযায়ী'),
            ('Order Value','amount',money,'শেষের Product Price'),
            ('Product Qty','qty',lambda x:f'{x:,.0f}','Total Qty'),
            ('AOV','aov',money,'Amount ÷ Orders'),
        ])
        st.markdown('#### Day-wise Orders')
        display_table(st,order_group(order_dates,'order_date').sort_values('order_date'),'order_date_daily.csv')
        st.markdown('#### Campaign Name-wise Order Amount')
        oc=order_dates.copy()
        oc['order_campaign_display']=oc.order_campaign_name.replace('', '(Blank Campaign Name)')
        oc_stats=order_group(oc,'order_campaign_display').sort_values('Order Value',ascending=False)
        display_table(st,oc_stats.rename(columns={'order_campaign_display':'Campaign Name'}),'order_date_campaign.csv')
        bar_chart(st,oc_stats,'order_campaign_display','Order Value','Order Sheet Campaign Name')

    with st.expander('Data Quality / Calculation Notes',expanded=False):
        badlead=sum(x['missing_dates'] for x in notes[:2])
        badcall=int(calls.call_date.isna().sum())
        duplicates=notes[2]['deduped_leads']
        st.write({'Facebook Sheet 1 rows':notes[0]['rows'],'Facebook Sheet 2 rows':notes[1]['rows'],
                  'Duplicate leads merged':duplicates,'Lead rows without Provided Date':badlead,
                  'Calls without Call Date (cohort can still count their Short Codes)':badcall,
                  'Facebook orders with invalid Order Date':order_notes['invalid_fb_dates'],
                  'Exact duplicate invoice/amount rows removed':order_notes['duplicate_orders_removed'],
                  'Facebook order rows (all dates)':len(orders),
                  'Date filled but Short Code blank (all dates)':len(missing_results)})
        st.markdown('**Reconciliation:** Confirmed Buyers are Short Code based. Lead-matched sales use the first qualifying Provided-Date lead for the same phone and no maximum days. Orders lacking a matching phone stay in the Order Date tab; blank Campaign Name is always retained. Contact Rate and Answer Rate are different metrics.')
        st.markdown('**Not Received classification** is based on explicit known labels. Review unknown or new Short Codes when they appear.')


if __name__ == '__main__':
    main()
