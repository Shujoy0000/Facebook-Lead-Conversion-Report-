"""Facebook tele-sales analytics — pure pandas functions, independent of Streamlit."""
from __future__ import annotations
import bisect
import re
import datetime as dt
import pandas as pd
import numpy as np

NO_ANSWER_CODES = {
    'কল ধরেনি', 'ফোন বন্ধ', 'কল যাচ্ছে না', 'নাম্বার বিজি', 'কল ওয়েটিং',
    'রিং বাযার পর কল কেটে দিয়েছে', 'রিং বাজার পর কল কেটে দিয়েছে',
    'ডিজিট কম', 'ডিজিট বেশি', 'নাম্বার নেই', 'নাম্বার ভুল',
    'রং নাম্বার', 'বিদেশি নাম্বার', 'নম্বর ভুল', 'নম্বর বন্ধ',
}
# "ব্যস্ত আছেন" is treated as answered by default; the UI lets the user override.
UNKNOWN_CODES = {'আদার্স', 'অন্যান্য', 'other', 'others', 'unknown', 'n/a', '-'}
BN_TO_EN = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def number_key(value):
    if value is None or pd.isna(value):
        return ''
    text = str(value).translate(BN_TO_EN).strip()
    # Some Excel cells store telephone numbers as a float: 1719255457.0
    if re.fullmatch(r'\d+\.0+', text):
        text = text.split('.')[0]
    digits = re.sub(r'\D', '', text)
    return digits[-10:] if len(digits) >= 10 else ''


def dates(values, preference='dayfirst'):
    s = pd.Series(values, copy=False)
    # Preserve true pandas timestamps; parse text per locale; support Google serial dates.
    first_day = preference != 'monthfirst'
    try:
        result = pd.to_datetime(s, errors='coerce', dayfirst=first_day, format='mixed')
    except (TypeError, ValueError):
        result = pd.to_datetime(s, errors='coerce', dayfirst=first_day)
    n = pd.to_numeric(s, errors='coerce')
    serial_mask = result.isna() & n.between(40000, 65000)
    if serial_mask.any():
        result.loc[serial_mask] = pd.to_datetime(n[serial_mask], unit='D', origin='1899-12-30', errors='coerce')
    return result.where(result.dt.year.between(2020, 2036))


def _series(df, col, default=''):
    return df[col] if col in df else pd.Series(default, index=df.index)


def blank_to(value, default):
    s = pd.Series(value, copy=False).fillna('').astype(str).str.strip()
    return s.mask(s.isin(['', 'nan', 'None', 'NaN', '<NA>']), default)


def normalize_leads(raw, preference='dayfirst'):
    df = raw.copy()
    df.columns = df.columns.astype(str).str.strip()
    needed = ['Date', 'Contact Number', 'Campaign Name']
    missing = [x for x in needed if x not in df]
    if missing:
        raise ValueError('Facebook tab missing required columns: ' + ', '.join(missing))
    df = df.reset_index(drop=True)
    df['lead_id'] = np.arange(len(df), dtype=int)
    df['phone'] = df['Contact Number'].map(number_key)
    df['provided_date'] = dates(df['Date'], preference).dt.normalize()
    df['campaign'] = blank_to(df['Campaign Name'], 'Unknown Campaign')
    df['agent'] = blank_to(_series(df, 'Agent Name'), 'Unknown Agent')
    # Exclude entirely empty preformatted rows; keep leads with a contact or other identifying information.
    df = df.loc[df['phone'].ne('') | df['provided_date'].notna()].copy()
    return df


def build_call_events(leads, preference='dayfirst'):
    columns = list(leads.columns)
    code_cols = [x for x in columns if str(x).lower().startswith('short code')]
    # Main sheet: Short Code-, 1st call date, 2nd call remarks, Short Code-2nd, 2nd call date, ...
    date_cols = [x for x in columns if 'call date' in str(x).lower()]
    if not code_cols:
        raise ValueError('No Short Code fields found in Facebook tab.')
    all_calls = []
    for i, code_col in enumerate(code_cols):
        date_col = date_cols[i] if i < len(date_cols) else None
        code = blank_to(_series(leads, code_col), '')
        call_date = dates(_series(leads, date_col), preference).dt.normalize() if date_col else pd.Series(pd.NaT, index=leads.index)
        keep = code.ne('') | call_date.notna()
        if not keep.any():
            continue
        temp = leads.loc[keep, ['lead_id', 'phone', 'provided_date', 'campaign', 'agent']].copy()
        temp['call_number'] = i + 1
        temp['short_code'] = code.loc[keep].values
        temp['call_date'] = call_date.loc[keep].values
        all_calls.append(temp)
    if not all_calls:
        return pd.DataFrame(columns=['call_id','lead_id','phone','provided_date','campaign','agent','call_number','short_code','call_date','status'])
    calls = pd.concat(all_calls, ignore_index=True)
    calls['call_id'] = np.arange(len(calls), dtype=int)
    return calls


def classify_short_code(code, no_answer=None, unknown=None):
    text = str(code).strip()
    if not text or text.lower() in ('nan', 'none'):
        return 'Unclassified'
    no_answer = NO_ANSWER_CODES if no_answer is None else no_answer
    unknown = UNKNOWN_CODES if unknown is None else unknown
    if text in no_answer:
        return 'Not Received'
    if text in unknown or text.lower() in unknown:
        return 'Unclassified'
    return 'Received'


def is_confirmed_order_short_code(code):
    """Only the explicit 1st–10th call Short Code 'অর্ডার করেছেন' means conversion.

    Similar but different statuses (e.g. pre-order, will order later) are NOT
    converted. Whitespace around the dropdown value is harmless.
    """
    text = re.sub(r'\s+', ' ', str(code).strip()).casefold()
    return text in {'অর্ডার করেছেন', 'order confirmed', 'ordered', 'order placed'}


def set_call_status(calls, not_received, unclassified):
    out = calls.copy()
    out['confirmed_order'] = out['short_code'].map(is_confirmed_order_short_code).fillna(False).astype(bool)
    out['status'] = out['short_code'].map(lambda x: classify_short_code(x, set(not_received), set(unclassified)))
    # A confirmed order necessarily implies a reached customer.
    out.loc[out['confirmed_order'], 'status'] = 'Received'

    # A lead may show 'অর্ডার করেছেন' more than once across 1st–10th calls.
    # Attribute its conversion to the FIRST dated confirmed call only.
    # Use original lead_id to avoid double-counting a follow-up; summary buyers
    # are additionally de-duplicated by phone number across lead rows.
    out['conversion_event'] = False
    verified = out.loc[out['confirmed_order'] & out['call_date'].notna()].copy()
    if not verified.empty:
        first = (verified.sort_values(['lead_id', 'call_date', 'call_number', 'call_id'])
                .drop_duplicates(subset=['lead_id'], keep='first'))
        out.loc[first.index, 'conversion_event'] = True
    return out


def numeric(column):
    return pd.to_numeric(pd.Series(column, copy=False).astype(str).str.replace('৳','',regex=False).str.replace(',','',regex=False).str.strip(), errors='coerce').fillna(0)


def normalize_orders(raw, preference='dayfirst'):
    df = raw.copy()
    df.columns = df.columns.astype(str).str.strip()
    missing = [c for c in ['Order Date','Contact Number'] if c not in df]
    if missing:
        raise ValueError('Tele Sales order file missing: ' + ', '.join(missing))
    df = df.reset_index(drop=True)
    df['order_id'] = np.arange(len(df), dtype=int)
    df['phone'] = df['Contact Number'].map(number_key)
    df['order_date'] = dates(df['Order Date'], preference).dt.normalize()
    df['campaign'] = blank_to(_series(df, 'Campaign'), 'Unknown Campaign')
    df['campaign_name'] = blank_to(_series(df, 'Campaign Name'), '')
    # Campaign Name may legitimately be blank. Preserve it; never replace with
    # Facebook lead campaign or the broader Campaign category.
    df['order_campaign_label'] = df['campaign_name']
    price = numeric(_series(df,'Product Price',0))
    gross_total = numeric(_series(df,'Total Amount',0))
    shipping = numeric(_series(df,'Shipping Charge',0))
    df['order_value'] = price.where(price > 0, (gross_total-shipping).clip(lower=0))
    df['qty'] = numeric(_series(df,'Total Qty',0))
    df['order_collector'] = blank_to(_series(df,'Order Collector'), 'Unknown Agent')
    # All dated orders must count in Order Date reports even if the phone is
    # missing / differently formatted. Phone is needed ONLY for optional lead attribution.
    df = df.loc[df['order_date'].notna()].copy()
    return df


def attribute_to_lead(leads, orders, days=30):
    """Each order maps to at most one (most recent eligible) lead."""
    l = leads.loc[leads['phone'].ne('') & leads['provided_date'].notna(), ['phone','lead_id','provided_date']].sort_values(['phone','provided_date','lead_id'])
    bucket = {}
    for phone, frame in l.groupby('phone', sort=False):
        bucket[phone] = (list(frame['provided_date'].astype('int64')), list(frame['lead_id']))
    limit_ns = int(days) * 86400 * 10**9
    matched = []
    for r in orders.itertuples(index=False):
        b = bucket.get(r.phone)
        if not b:
            continue
        d = int(r.order_date.value)
        i = bisect.bisect_right(b[0], d)-1
        if i < 0 or d - b[0][i] > limit_ns:
            continue
        matched.append((int(r.order_id), int(b[1][i])))
    return pd.DataFrame(matched,columns=['order_id','lead_id'])


def attribute_to_received_call(calls, orders, days=30):
    """Each order maps to the most recent preceding answered call, once only."""
    c = calls.loc[calls['status'].eq('Received') & calls['call_date'].notna() & calls['phone'].ne(''),['phone','call_id','call_date','call_number']].sort_values(['phone','call_date','call_number','call_id'])
    bucket = {}
    for phone, frame in c.groupby('phone', sort=False):
        bucket[phone] = (list(frame['call_date'].astype('int64')),list(frame['call_id']))
    limit_ns = int(days) * 86400 * 10**9
    matched = []
    for r in orders.itertuples(index=False):
        b = bucket.get(r.phone)
        if not b:
            continue
        d = int(r.order_date.value)
        i = bisect.bisect_right(b[0],d)-1
        if i < 0 or d - b[0][i] > limit_ns:
            continue
        matched.append((int(r.order_id),int(b[1][i])))
    return pd.DataFrame(matched,columns=['order_id','call_id'])


def linked_order_summary(data, id_col, links, orders):
    result = data.copy()
    if links.empty or orders.empty:
        result['orders'] = 0
        result['order_value'] = 0.0
        return result
    d = links.merge(orders[['order_id','order_value']],on='order_id',how='left')
    g = d.groupby(id_col).agg(orders=('order_id','count'),order_value=('order_value','sum'))
    result = result.join(g,on=id_col)
    result['orders'] = result['orders'].fillna(0).astype(int)
    result['order_value'] = result['order_value'].fillna(0).astype(float)
    return result


def build_provided_view(leads, calls, lead_order_links, orders):
    base = leads[['lead_id','phone','provided_date','campaign','agent']].copy()
    if not calls.empty:
        group = calls.groupby('lead_id').agg(
            attempts=('call_id','size'),
            received_calls=('status',lambda x: (x=='Received').sum()),
            missed_calls=('status',lambda x: (x=='Not Received').sum()),
            unknown_calls=('status',lambda x: (x=='Unclassified').sum()),
            confirmed_calls=('conversion_event', 'sum'),
        )
        base = base.join(group,on='lead_id')
    for c in ['attempts','received_calls','missed_calls','unknown_calls','confirmed_calls']:
        if c not in base:
            base[c]=0
        base[c] = base[c].fillna(0).astype(int)
    base['called'] = base['attempts'] > 0
    base['received'] = base['received_calls'] > 0
    base['not_received'] = base['called'] & ~base['received'] & base['missed_calls'].gt(0)
    base = linked_order_summary(base,'lead_id',lead_order_links,orders)
    # Facebook team records confirmed conversions in 1st–10th Short Code,
    # not in Outcome and not necessarily in the order file under the same phone.
    base['confirmed'] = base['confirmed_calls'].gt(0)
    base['converted'] = base['received'] & base['confirmed']
    return base


def build_call_view(calls, call_order_links, orders):
    base = linked_order_summary(calls,'call_id',call_order_links,orders)
    base['received'] = base['status'].eq('Received')
    base['not_received'] = base['status'].eq('Not Received')
    base['unclassified'] = base['status'].eq('Unclassified')
    base['confirmed'] = base['confirmed_order'].fillna(False).astype(bool)
    # Only the first dated 'অর্ডার করেছেন' event for each lead is a conversion.
    base['converted'] = base['conversion_event'].fillna(False).astype(bool)
    return base


def _ratio(n,d):
    return 100*float(n)/float(d) if d else 0.0


def lead_metrics(df):
    if df.empty:
        return dict(Data=0,Called=0,Not_Called=0,Received=0,Not_Received=0,Unknown=0,Calls=0,Received_Calls=0,Not_Received_Calls=0,Orders=0,Buyers=0,Order_Value=0.,Contact_Rate=0.,Answer_Rate=0.,Missed_Rate=0.,Conversion_Rate=0.)
    data=len(df);called=int(df['called'].sum());received=int(df['received'].sum()); missed=int(df['not_received'].sum())
    received_phones=df.loc[df['received'] & df['phone'].ne(''),'phone'].nunique()
    buyer=df.loc[df['converted'] & df['phone'].ne(''),'phone'].nunique()
    order_count=int(df['orders'].sum())
    return dict(Data=data,Called=called,Not_Called=data-called,Received=received,Not_Received=missed,
                Unknown=called-received-missed,Calls=int(df['attempts'].sum()),Received_Calls=int(df['received_calls'].sum()),
                Not_Received_Calls=int(df['missed_calls'].sum()),Orders=order_count,Buyers=buyer,
                Order_Value=float(df['order_value'].sum()),Contact_Rate=_ratio(received,data),
                Answer_Rate=_ratio(received,called),Missed_Rate=_ratio(missed,called),Conversion_Rate=_ratio(buyer,received_phones))


def call_metrics(df):
    if df.empty:
        return dict(Calls=0,Received=0,Not_Received=0,Unclassified=0,Unique_Called=0,Unique_Received=0,Orders=0,Buyers=0,Order_Value=0.,Answer_Rate=0.,Missed_Rate=0.,Conversion_Rate=0.)
    reached = df.loc[df['received']]
    n_unique = df.loc[df['phone'].ne(''),'phone'].nunique(); yes_unique = reached.loc[reached['phone'].ne(''),'phone'].nunique()
    buyers = df.loc[df['converted'] & df['phone'].ne(''),'phone'].nunique()
    return dict(Calls=len(df), Received=int(df['received'].sum()),Not_Received=int(df['not_received'].sum()),
                Unclassified=int(df['unclassified'].sum()),Unique_Called=int(n_unique),Unique_Received=int(yes_unique),
                Orders=int(df['orders'].sum()),Buyers=int(buyers),Order_Value=float(df['order_value'].sum()),
                Answer_Rate=_ratio(df['received'].sum(),len(df)),Missed_Rate=_ratio(df['not_received'].sum(),len(df)),Conversion_Rate=_ratio(buyers,yes_unique))


def group_metrics(df, group_by, kind='provided'):
    keys = [group_by] if isinstance(group_by,str) else list(group_by)
    frames=[]
    for values, group in df.groupby(keys,dropna=False,sort=True):
        if not isinstance(values,tuple):values=(values,)
        item = dict(zip(keys,values))
        item.update(lead_metrics(group) if kind=='provided' else call_metrics(group))
        frames.append(item)
    return pd.DataFrame(frames)


def selected_between(df, col, begin, end):
    begin=pd.Timestamp(begin);end=pd.Timestamp(end)
    return df.loc[df[col].notna() & df[col].between(begin,end)].copy()


def campaign_order_report(df, dimension='order_campaign_label'):
    if df.empty:
        return pd.DataFrame(columns=['Campaign','Orders','Qty','Order Value','AOV','%'])
    grouped=df.groupby(dimension,dropna=False).agg(Orders=('order_id','count'),Qty=('qty','sum'), **{'Order Value':('order_value','sum')}).reset_index()
    grouped=grouped.rename(columns={dimension:'Campaign'})
    grouped['AOV']=grouped['Order Value']/grouped['Orders'].replace(0,np.nan)
    grouped['AOV']=grouped['AOV'].fillna(0)
    grouped['%']=100*grouped['Order Value']/max(grouped['Order Value'].sum(),1)
    return grouped.sort_values('Order Value',ascending=False).reset_index(drop=True)


def product_order_report(orders):
    if orders.empty:
        return pd.DataFrame(columns=['Product','Qty','Gross Product Value'])
    rows=[]
    for i in range(1,16):
        n=f'Product Name-{i}';q=f'Product QTY-{i}';p=f'Product Price-{i}'
        if n not in orders or q not in orders: continue
        sub=pd.DataFrame({'Product':blank_to(orders[n],'').values,'Qty':numeric(orders[q]).values,
                          'UnitPrice':numeric(_series(orders,p,0)).values})
        sub=sub.loc[sub['Product'].ne('') & sub['Qty'].gt(0)]
        if sub.empty:continue
        sub['Gross Product Value']=sub['Qty']*sub['UnitPrice']
        rows.append(sub[['Product','Qty','Gross Product Value']])
    if not rows:return pd.DataFrame(columns=['Product','Qty','Gross Product Value'])
    return pd.concat(rows).groupby('Product',as_index=False).agg({'Qty':'sum','Gross Product Value':'sum'}).sort_values('Gross Product Value',ascending=False)


# Campaign conversion uses received (answered) customers as the denominator.
# An order contributes only once to the relevant time-based attribution model.
def campaign_conversion_report(view, kind='provided'):
    columns = ['Campaign', 'Provided Leads' if kind == 'provided' else 'Call Attempts',
               'Received Calls', 'Unique Reached', 'Buying Customers', 'Orders',
               'Order Value', 'Conversion Rate', 'AOV', 'Revenue Share %']
    if view.empty:
        return pd.DataFrame(columns=columns)
    results = []
    for campaign, grp in view.groupby('campaign', dropna=False, sort=False):
        if kind == 'provided':
            received = grp[grp['received'].eq(True)]
            lead_count = len(grp)
            attempts = int(grp['received_calls'].sum())
        else:
            received = grp[grp['status'].eq('Received')]
            lead_count = len(grp)
            attempts = len(received)
        unique_reached = received.loc[received['phone'].ne(''), 'phone'].nunique()
        # Confirmed conversions come from the Facebook Short Code.
        # Attributed order rows/revenue are a separate optional reconciliation.
        buying = received.loc[received['converted']]
        buyers = buying.loc[buying['phone'].ne(''), 'phone'].nunique()
        order_count = int(grp['orders'].sum())
        value = float(grp['order_value'].sum())
        results.append({
            'Campaign': campaign,
            'Provided Leads' if kind == 'provided' else 'Call Attempts': lead_count,
            'Received Calls': attempts,
            'Unique Reached': int(unique_reached),
            'Buying Customers': int(buyers),
            'Orders': order_count,
            'Order Value': value,
            'Conversion Rate': _ratio(buyers, unique_reached),
            'AOV': value / order_count if order_count else 0.0,
        })
    report = pd.DataFrame(results)
    total_value = report['Order Value'].sum()
    report['Revenue Share %'] = (100 * report['Order Value'] / total_value) if total_value else 0.0
    return report.sort_values(['Order Value','Orders'],ascending=False).reset_index(drop=True)[columns]


def campaign_conversion_total(view, kind='provided'):
    # Overall conversion uses global unique phones, not summed per-campaign denominators.
    metric = 'Provided Leads' if kind == 'provided' else 'Call Attempts'
    if view.empty:
        return {'Campaign': 'TOTAL', metric: 0, 'Received Calls': 0,
                'Unique Reached': 0, 'Buying Customers': 0, 'Orders': 0,
                'Order Value': 0., 'Conversion Rate': 0., 'AOV': 0., 'Revenue Share %': 0.}
    received = view[view['received'].eq(True)] if kind == 'provided' else view[view['status'].eq('Received')]
    unique = received.loc[received['phone'].ne(''), 'phone'].nunique()
    buyers_df = received.loc[received['converted']]
    buyers = buyers_df.loc[buyers_df['phone'].ne(''), 'phone'].nunique()
    orders = int(view['orders'].sum())
    amount = float(view['order_value'].sum())
    calls = int(view['received_calls'].sum()) if kind == 'provided' else len(received)
    return {'Campaign': 'TOTAL', metric: len(view), 'Received Calls': calls,
            'Unique Reached': int(unique), 'Buying Customers': int(buyers),
            'Orders': orders, 'Order Value': amount,
            'Conversion Rate': _ratio(buyers, unique),
            'AOV': amount/orders if orders else 0., 'Revenue Share %': 100.0 if amount else 0.0}


def campaign_order_attribution_detail(links, key, event_view, orders):
    columns=['Facebook Campaign','Order Campaign','Order Campaign Name','Orders','Buying Customers','Order Value','AOV']
    if links.empty or orders.empty or event_view.empty:
        return pd.DataFrame(columns=columns)
    valid = event_view.loc[event_view['received'].eq(True)] if 'received' in event_view.columns else event_view.loc[event_view['status'].eq('Received')]
    allowed = valid[[key,'campaign']].drop_duplicates(subset=[key])
    link = links.merge(allowed, on=key, how='inner')
    order_cols = ['order_id','phone','campaign','campaign_name','order_value']
    joined = link.merge(orders[order_cols],on='order_id',how='inner',suffixes=('_fb','_order'))
    if joined.empty:
        return pd.DataFrame(columns=columns)
    joined = joined.rename(columns={'campaign_fb':'Facebook Campaign','campaign_order':'Order Campaign','campaign_name':'Order Campaign Name'})
    joined['Order Campaign Name']=blank_to(joined['Order Campaign Name'],'(not supplied)')
    group=['Facebook Campaign','Order Campaign','Order Campaign Name']
    agg=joined.groupby(group,dropna=False).agg(Orders=('order_id','nunique'),**{'Buying Customers':('phone','nunique'),'Order Value':('order_value','sum')}).reset_index()
    agg['AOV']=agg['Order Value']/agg['Orders'].replace(0,np.nan)
    return agg.fillna({'AOV':0.}).sort_values('Order Value',ascending=False).reset_index(drop=True)[columns]
