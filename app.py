import io
import base64
import os
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from analytics import (
    NO_ANSWER_CODES, UNKNOWN_CODES, normalize_leads, build_call_events,
    normalize_orders, set_call_status, attribute_to_lead,
    attribute_to_received_call, build_provided_view, build_call_view,
    lead_metrics, call_metrics, group_metrics, selected_between,
    campaign_order_report, product_order_report,
    campaign_conversion_report, campaign_conversion_total, campaign_order_attribution_detail,
)

st.set_page_config(page_title='Facebook Lead Conversion Report',page_icon='📊',layout='wide')
st.markdown('''<style>
.block-container{padding-top:1.4rem;max-width:1480px}
/* Preserved legacy header: responsive and centered, separate from analytics content. */
.bb-legacy-header{position:relative;text-align:center;padding:7px 92px 25px;margin:3px 0 20px;min-height:166px;background:#ffffff}
.bb-legacy-logo{position:absolute;left:0;top:16px;width:80px;height:auto;border-radius:6px}
.bb-legacy-main-title{color:#ff6600;font-weight:800;font-size:clamp(28px,3vw,48px);line-height:1.22;margin:0 0 20px;letter-spacing:-.3px}
.bb-legacy-developer-text{font-size:12px;color:#777;font-style:italic;margin:0 0 14px}
.bb-legacy-slogan-text{font-size:25px;font-weight:800;color:#202020;line-height:1.45;margin:0}
.bb-legacy-vision-text{font-size:16px;color:#777;line-height:1.4;margin:0}
@media(max-width:760px){.bb-legacy-header{padding:58px 6px 22px;min-height:unset}.bb-legacy-logo{top:5px;left:6px;width:80px}.bb-legacy-main-title{font-size:28px;margin-bottom:11px}.bb-legacy-developer-text{margin-bottom:10px}.bb-legacy-slogan-text{font-size:18px}.bb-legacy-vision-text{font-size:13px}}
.section{font-size:21px;font-weight:800;border-left:5px solid #ff6600;padding-left:10px;margin:24px 0 11px}
.note{background:#f8fafc;border-radius:8px;padding:11px 14px;color:#555;font-size:13px}
div[data-testid="stMetric"]{border:1px solid #ebedf0;border-top:4px solid #ff6600;padding:12px 14px;border-radius:10px;background:#fff}
</style>''',unsafe_allow_html=True)

SHEET_ID = '1M7WjEuO82suxvkOTTEwGuOWcPFzYej2c_iRvAA9RipM'
SHEET_GID = '1218239306'
FACEBOOK_SHEET = 'Facebook'

@st.cache_data(ttl=300, show_spinner='Reading Facebook Google Sheet…')
def fetch_google_sheet():
    """Try private service-account access first, then publicly accessible CSV export."""
    try:
        if 'gcp_service_account' in st.secrets:
            import gspread
            creds = dict(st.secrets['gcp_service_account'])
            client = gspread.service_account_from_dict(creds)
            values = client.open_by_key(SHEET_ID).worksheet(FACEBOOK_SHEET).get_all_values()
            if not values:
                return pd.DataFrame(), 'Google API: tab is empty'
            header=[str(x).strip() for x in values[0]]
            width=len(header)
            rows=[(row[:width] + ['']*max(0,width-len(row))) for row in values[1:]]
            return pd.DataFrame(rows,columns=header),'Google Sheets API (live)'
    except Exception as exc:
        service_error=f'Service account could not read sheet: {str(exc)[:200]}'
    else:
        service_error='No service account configured.'
    export_url=f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}'
    try:
        d=pd.read_csv(export_url,dtype=str,low_memory=False)
        if 'Contact Number' not in d.columns:
            raise ValueError('CSV did not contain the Facebook header (the file may be private).')
        return d,'Google Sheets public CSV (live)'
    except Exception as exc:
        raise RuntimeError(service_error+' Public CSV unavailable: '+str(exc)[:180])

@st.cache_data(ttl=900,show_spinner='Reading uploaded Facebook data…')
def read_facebook_bytes(data,filename):
    src=io.BytesIO(data)
    if filename.lower().endswith('.csv'):
        try: return pd.read_csv(src,dtype=str,low_memory=False)
        except UnicodeDecodeError:
            src.seek(0);return pd.read_csv(src,dtype=str,encoding='utf-8-sig',low_memory=False)
    return pd.read_excel(src,sheet_name='Facebook',dtype=str,engine='openpyxl')

@st.cache_data(ttl=900,show_spinner='Reading Tele Sales orders…')
def read_orders_bytes(data):
    # The workbook contains very wide report/formatting columns; read only data fields.
    required={'Order Date','Contact Number','Campaign','Campaign Name','Product Price',
              'Total Amount','Shipping Charge','Total Qty','Order Collector','Invoice ID'}
    for i in range(1,16):
        required.update({f'Product Name-{i}',f'Product QTY-{i}',f'Product Price-{i}'})
    return pd.read_excel(io.BytesIO(data),sheet_name='Tele Sales',
                         dtype={'Contact Number':str},engine='openpyxl',
                         usecols=lambda name: str(name).strip() in required)

@st.cache_data(ttl=300,show_spinner='Reading private Tele Sales Order from Google Drive…')
def fetch_private_order_file(file_id):
    # The same service account requires Viewer permission on this specific XLSX file.
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    creds=service_account.Credentials.from_service_account_info(
        dict(st.secrets['gcp_service_account']),scopes=['https://www.googleapis.com/auth/drive.readonly'])
    drive=build('drive','v3',credentials=creds,cache_discovery=False)
    request=drive.files().get_media(fileId=file_id)
    buffer=io.BytesIO()
    downloader=MediaIoBaseDownload(buffer,request)
    done=False
    while not done:
        _,done=downloader.next_chunk()
    return buffer.getvalue()


def money(x):return f'৳{float(x):,.0f}'
def pct(x):return f'{float(x):.1f}%'

def report_table(df, filename):
    if df.empty:
        st.info('No records found in the selected period / filters.')
        return
    shown=df.copy()
    for col in shown.columns:
        if pd.api.types.is_datetime64_any_dtype(shown[col]): shown[col]=shown[col].dt.strftime('%Y-%m-%d')
        elif col in ('Order Value','Gross Product Value','AOV'): shown[col]=shown[col].map(money)
        elif col in ('Contact_Rate','Answer_Rate','Missed_Rate','Conversion_Rate','%','Conversion Rate','Revenue Share %'): shown[col]=shown[col].map(pct)
    st.dataframe(shown,use_container_width=True,hide_index=True,height=min(500,90+len(shown)*34))
    st.download_button('⬇ Download CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name=filename,mime='text/csv',key='export_'+filename)


def horizontal_bar(df,label,val,title,top=15):
    if df.empty:return
    chart=df.head(top).copy()
    fig=px.bar(chart,y=label,x=val,color=label,orientation='h',text=val,
               color_discrete_sequence=px.colors.qualitative.Vivid,title=title)
    fig.update_layout(showlegend=False,height=max(320,48*len(chart)+95),margin=dict(l=5,r=35,t=55,b=15))
    fig.update_yaxes(categoryorder='total ascending')
    fig.update_traces(textposition='outside',hovertemplate='<b>%{y}</b><br>'+val+': %{x:,.0f}<extra></extra>')
    st.plotly_chart(fig,use_container_width=True)


def daily_chart(day,kind):
    if day.empty:return
    d=day.copy().sort_values('Day')
    cols=['Data','Received','Not_Received','Orders'] if kind=='provided' else ['Calls','Received','Not_Received','Orders']
    m=d.melt(id_vars=['Day'],value_vars=[c for c in cols if c in d.columns],var_name='Metric',value_name='Count')
    fig=px.line(m,x='Day',y='Count',color='Metric',markers=True,title='Daily trends',
                color_discrete_sequence=['#ff6600','#13a97e','#e45757','#5773c9'])
    fig.update_layout(height=360,legend_orientation='h',margin=dict(l=10,r=10,t=52,b=25),hovermode='x unified')
    st.plotly_chart(fig,use_container_width=True)


def metric_card_columns(items):
    for chunk_start in range(0,len(items),6):
        chunk=items[chunk_start:chunk_start+6]
        cols=st.columns(len(chunk))
        for c,(label,value,helptext) in zip(cols,chunk):c.metric(label,value,help=helptext)

# The exact legacy dashboard title, credit, slogan and vision are restored.
# The supplied screenshot's Bigganbaksho logo is included as logo.png in this GitHub-ready ZIP.
logo_file = Path(__file__).resolve().parent / 'logo.png'
if not logo_file.exists():
    logo_file = Path(__file__).resolve().parent / 'logo.jpg'
if logo_file.exists():
    logo_type = 'image/png' if logo_file.suffix.lower() == '.png' else 'image/jpeg'
    logo_src = f'data:{logo_type};base64,' + base64.b64encode(logo_file.read_bytes()).decode('ascii')
    logo_html = f'<img src="{logo_src}" class="bb-legacy-logo" alt="Bigganbaksho logo">'
else:
    logo_html = ''
st.markdown(f'''<div class="bb-legacy-header">
    {logo_html}
    <div class="bb-legacy-main-title">Facebook Lead Conversion Report</div>
    <div class="bb-legacy-developer-text">Web App Developed By-Shujoy Shaha</div>
    <div class="bb-legacy-slogan-text">ম্যানুয়েল কাজের দিন শেষ, বিজ্ঞানবাক্সে বাংলাদেশ</div>
    <div class="bb-legacy-vision-text">অন্যরকম বাংলাদেশের স্বপ্ন নিয়ে</div>
</div>''', unsafe_allow_html=True)

with st.sidebar:
    st.header('📊 Data connections')
    fb_file=st.file_uploader('Facebook data upload (optional CSV / Excel)',type=['csv','xlsx'],key='fb_upload',help='Uploading overrides live Google Sheet. XLSX must have the Facebook tab.')
    order_file=st.file_uploader('Tele Sales Order.xlsx',type=['xlsx'],key='order_upload',help='Load locally or upload your order workbook. Do not publish customer data in a public GitHub repo.')
    if st.button('🔄 Refresh data',use_container_width=True):
        st.cache_data.clear();st.rerun()

try:
    if fb_file is not None:
        raw_fb=read_facebook_bytes(fb_file.getvalue(),fb_file.name)
        source_name='Uploaded Facebook file'
    else:
        try:
            raw_fb,source_name=fetch_google_sheet()
        except Exception as exc:
            st.error('Could not load Facebook Google Sheet: '+str(exc))
            st.info('To continue: upload the Facebook tab as CSV/XLSX in the sidebar, or configure `gcp_service_account` in Streamlit Secrets and share the Google Sheet with the service-account email.')
            st.stop()
    st.sidebar.success(f'Facebook: {source_name}')
except Exception as exc:
    st.error('Facebook load failed: '+str(exc));st.stop()

try:
    if order_file is not None:
        raw_orders=read_orders_bytes(order_file.getvalue());order_source='Uploaded Tele Sales Order.xlsx'
    elif 'order_drive_file_id' in st.secrets and 'gcp_service_account' in st.secrets:
        try:
            remote_data=fetch_private_order_file(str(st.secrets['order_drive_file_id']))
            raw_orders=read_orders_bytes(remote_data);order_source='Google Drive private XLSX (live)'
        except Exception as err:
            st.warning('Private Drive order auto-read unavailable: '+str(err)[:220])
            raw_orders=pd.DataFrame();order_source='Upload the order workbook in the sidebar.'
    elif Path('Tele Sales Order.xlsx').is_file():
        raw_orders=read_orders_bytes(Path('Tele Sales Order.xlsx').read_bytes());order_source='Local order workbook'
    else:
        raw_orders=pd.DataFrame();order_source='Missing: upload workbook to enable order reports'
    if raw_orders.empty:
        st.sidebar.warning(order_source)
        st.warning('Order workbook is not loaded. Call and lead reports work, but revenue/conversion will show zero until you upload **Tele Sales Order.xlsx**.')
    else:st.sidebar.success(f'Orders: {order_source}')
except Exception as exc:
    st.error('Order workbook could not load: '+str(exc));st.stop()

with st.sidebar:
    st.header('⚙ Analysis settings')
    date_preference=st.radio('Facebook Date format',['DD-MM-YYYY / DD/MM/YYYY','MM/DD/YYYY'],horizontal=False,index=0)
    date_mode='dayfirst' if date_preference.startswith('DD-') else 'monthfirst'
    order_date_preference='dayfirst' # Excel genuine date objects are preserved.
    window=st.slider('Order attribution window (days)',0,90,30,help='An order must occur on/after the lead/call date and within this many days to be matched.')
    facebook_orders_only=st.checkbox('Match only Facebook Lead orders',value=True,help='Prevents other campaigns such as Existing and Cart Abandon from inflating Facebook conversion.')

try:
    leads=normalize_leads(raw_fb,date_mode)
    calls=build_call_events(leads,date_mode)
    orders=normalize_orders(raw_orders,order_date_preference) if not raw_orders.empty else pd.DataFrame(columns=['order_id','phone','order_date','campaign','campaign_name','order_campaign_label','order_value','qty'])
except Exception as exc:
    st.error('Column mapping / date parsing error: '+str(exc));st.stop()

if facebook_orders_only and not orders.empty:
    orders=orders.loc[orders['campaign'].astype(str).str.contains(r'facebook|face\s*book|fb\s*lead',case=False,regex=True,na=False)].copy()

with st.sidebar:
    all_codes=sorted([str(c) for c in calls['short_code'].unique() if str(c).strip()]) if not calls.empty else []
    with st.expander('Short Code classification (edit anytime)',expanded=False):
        st.caption('Only these labels count as Not Received; everything else except Unclassified is Received. Check against your team’s Short Code definitions.')
        default_missed=[x for x in all_codes if x in NO_ANSWER_CODES]
        missed_set=st.multiselect('Not Received codes',all_codes,default=default_missed)
        options_unknown=[x for x in all_codes if x not in missed_set]
        default_unknown=[x for x in options_unknown if x.lower() in UNKNOWN_CODES]
        unknown_set=st.multiselect('Unclassified codes',options_unknown,default=default_unknown)

calls=set_call_status(calls,missed_set,unknown_set)
valid_date_series=pd.concat([leads['provided_date'],calls['call_date']],ignore_index=True).dropna()
if valid_date_series.empty:
    st.error('No valid Facebook dates found. Check the Date format selector and Facebook file.');st.stop()
max_date=valid_date_series.max().date();min_date=valid_date_series.min().date()
default_start=max(min_date,max_date-pd.Timedelta(days=30))
with st.sidebar:
    st.header('📅 Report filters')
    choice=st.date_input('Start and end date',value=(default_start,max_date),help='No fixed min/max; any date can be selected.')
    if not isinstance(choice,(tuple,list)) or len(choice)!=2:st.info('Select both start and end dates.');st.stop()
    start,end=sorted(choice)
    campaign_options=sorted(leads['campaign'].dropna().unique().tolist())
    campaign_select=st.multiselect('Facebook Campaign / Lead Source',campaign_options,default=[])
    agent_options=sorted(leads['agent'].dropna().unique().tolist())
    agent_select=st.multiselect('Agent',agent_options,default=[])

if campaign_select:leads=leads.loc[leads['campaign'].isin(campaign_select)].copy()
if agent_select:leads=leads.loc[leads['agent'].isin(agent_select)].copy()
calls=calls.loc[calls['lead_id'].isin(leads['lead_id'])].copy()

# Order attribution: once per order; no duplicate order value across lead/call rows.
link_lead=attribute_to_lead(leads,orders,window)
link_call=attribute_to_received_call(calls,orders,window)
# If an order Campaign Name is empty, use its matched Facebook lead Campaign Name.
# Never overwrite a campaign name already present in Tele Sales Order.
if not orders.empty and not link_lead.empty:
    match_names = (link_lead.merge(leads[['lead_id','campaign']], on='lead_id', how='left')
                    .set_index('order_id')['campaign'])
    orders = orders.copy()
    match_names = orders['order_id'].map(match_names).fillna('')
    fallback = orders['campaign_name'].astype(str).str.strip().eq('')
    known = match_names.ne('') & match_names.ne('Unknown Campaign')
    orders.loc[fallback & known,'order_campaign_label'] = match_names.loc[fallback & known].values
provided_all=build_provided_view(leads,calls,link_lead,orders)
call_all=build_call_view(calls,link_call,orders)
provided=selected_between(provided_all,'provided_date',start,end)
call_dates=selected_between(call_all,'call_date',start,end)

unmatched_lead_dates=int(leads['provided_date'].isna().sum())
undated_call=int(calls['call_date'].isna().sum())

st.caption(f'Facebook records loaded: {len(leads):,} | Calls extracted: {len(calls):,} | Eligible order records: {len(orders):,} | Period: {start:%d %b %Y} – {end:%d %b %Y}')

t1,t2,t3,t4,t5=st.tabs(['📆 1 · Data Provided Date','📞 2 · Call Date','🎯 3 · Campaign Conversion + ৳','💰 4 · Order Sheet Campaigns','🔎 5 · Data Quality'])

with t1:
    st.markdown('<div class="section">Data Provided Date — lead cohort report</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">Date = Facebook column A (data provided). Received lead = at least one answered call across all follow-ups. Orders are matched by phone and attributed to the latest eligible lead within the chosen days. Contact Rate = received leads ÷ provided leads; Conversion = unique buying phone numbers ÷ unique received phone numbers.</div>',unsafe_allow_html=True)
    a=lead_metrics(provided)
    metric_card_columns([
        ('Data Provided',f"{a['Data']:,}",'Lead rows received in period'),
        ('Called Leads',f"{a['Called']:,}",'Unique lead records with any call attempt'),
        ('Received Leads',f"{a['Received']:,}",'Lead rows with at least one answered call'),
        ('Not Received',f"{a['Not_Received']:,}",'Attempted lead rows without a received call, but with a not-received result'),
        ('Contact Rate',pct(a['Contact_Rate']),'Received leads / all provided leads'),
        ('Conversion Rate',pct(a['Conversion_Rate']),'Unique buying phone numbers / unique reached phone numbers'),
        ('Not Called',f"{a['Not_Called']:,}",'No recorded attempts'),
        ('Call Attempts',f"{a['Calls']:,}",'Includes follow-up calls'),
        ('Received Calls',f"{a['Received_Calls']:,}",'Number of received attempts'),
        ('Orders',f"{a['Orders']:,}",'Matched order records, counted only once'),
        ('Buying Customers',f"{a['Buyers']:,}",'Unique phone numbers with a received call and an order'),
        ('Order Value',money(a['Order_Value']),'Sum of matched final Product Price (net price fallback)')
    ])
    day=group_metrics(provided,'provided_date')
    if not day.empty:day=day.rename(columns={'provided_date':'Day'})
    daily_chart(day,'provided')
    st.subheader('Day-wise Data Provided Report')
    report_table(day,'data_provided_daily.csv')
    st.subheader('Campaign / Lead Source-wise Report')
    camp=group_metrics(provided,'campaign').sort_values('Data',ascending=False) if not provided.empty else pd.DataFrame()
    if not camp.empty:
        left,right=st.columns([1.4,1])
        with left: horizontal_bar(camp,'campaign','Data','Lead volume by source')
        with right: horizontal_bar(camp.sort_values('Order_Value',ascending=False),'campaign','Order_Value','Matched order value by source')
    report_table(camp,'data_provided_campaign.csv')
    with st.expander('Day × Campaign table',expanded=False):
        report_table(group_metrics(provided,['provided_date','campaign']),'data_provided_day_campaign.csv')
    with st.expander('Agent-wise Provided Data & Conversion',expanded=False):
        report_table(group_metrics(provided,'agent'),'data_provided_agents.csv')
    st.subheader('Short Code Breakdown (for leads provided in the selected period)')
    codes=calls.loc[calls['lead_id'].isin(provided['lead_id'])].copy()
    if not codes.empty:
        sc=codes.groupby(['short_code','status']).size().reset_index(name='Calls').sort_values('Calls',ascending=False)
        sc['%']=100*sc['Calls']/max(len(codes),1)
        report_table(sc,'provided_short_codes.csv')
        with st.expander('Short Code × Campaign (share of source calls)',expanded=False):
            code_by_campaign=codes.groupby(['campaign','short_code','status']).size().reset_index(name='Calls')
            code_by_campaign['%']=100*code_by_campaign['Calls']/code_by_campaign.groupby('campaign')['Calls'].transform('sum')
            report_table(code_by_campaign.sort_values(['campaign','Calls'],ascending=[True,False]),'provided_shortcode_campaign.csv')
    else:st.info('No recorded call codes for this lead cohort.')

with t2:
    st.markdown('<div class="section">Call Date — call activity report</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">Call Date = 1st through 10th call dates. Each attempt is one call; unique reached leads and attributed orders are separately deduplicated. Orders are attributed to the most recent earlier **Received** call within the chosen days. Answer Rate = received attempts ÷ all attempts; Conversion = unique buying phone numbers ÷ unique received phone numbers.</div>',unsafe_allow_html=True)
    b=call_metrics(call_dates)
    metric_card_columns([
        ('Total Calls',f"{b['Calls']:,}",'All recorded call attempts dated in the period'),
        ('Received Calls',f"{b['Received']:,}",'Answered call attempts'),
        ('Not Received',f"{b['Not_Received']:,}",'Unanswered call attempts'),
        ('Unclassified',f"{b['Unclassified']:,}",'Missing/ambiguous codes'),
        ('Answer Rate',pct(b['Answer_Rate']),'Received call attempts / total call attempts'),
        ('Not Received %',pct(b['Missed_Rate']),'Not received call attempts / total call attempts'),
        ('Conversion Rate',pct(b['Conversion_Rate']),'Unique buying phone numbers / unique reached phone numbers'),
        ('Unique Leads Called',f"{b['Unique_Called']:,}",'Unique phone numbers receiving one or more calls'),
        ('Unique Leads Reached',f"{b['Unique_Received']:,}",'Unique phone numbers reached'),
        ('Buying Customers',f"{b['Buyers']:,}",'Unique phone numbers with a received call and an attributed order'),
        ('Orders',f"{b['Orders']:,}",'Unique order rows attributed to a received call'),
        ('Order Value',money(b['Order_Value']),'Order value attributed to received calls')
    ])
    d2=group_metrics(call_dates,'call_date',kind='call')
    if not d2.empty:d2=d2.rename(columns={'call_date':'Day'})
    daily_chart(d2,'call')
    st.subheader('Day-wise Call Report')
    report_table(d2,'call_date_daily.csv')
    st.subheader('Campaign / Lead Source-wise Call Performance')
    s2=group_metrics(call_dates,'campaign',kind='call').sort_values('Calls',ascending=False) if not call_dates.empty else pd.DataFrame()
    if not s2.empty:horizontal_bar(s2,'campaign','Calls','Calls by Facebook source')
    report_table(s2,'call_date_campaign.csv')
    with st.expander('Day × Campaign report',expanded=False):
        report_table(group_metrics(call_dates,['call_date','campaign'],kind='call'),'call_date_day_campaign.csv')
    with st.expander('Agent-wise Call Report',expanded=False):
        report_table(group_metrics(call_dates,'agent',kind='call'),'call_date_agents.csv')
    st.subheader('Call Number / Follow-up Efficiency')
    report_table(group_metrics(call_dates,'call_number',kind='call'),'call_number_efficiency.csv')
    st.subheader('Short Code-wise Report & Percentages')
    if not call_dates.empty:
        code_stats=call_dates.groupby(['short_code','status']).agg(Calls=('call_id','count'),Orders=('orders','sum'), **{'Order Value':('order_value','sum')}).reset_index().sort_values('Calls',ascending=False)
        code_stats['%']=100*code_stats['Calls']/max(len(call_dates),1)
        report_table(code_stats,'call_date_short_codes.csv')
        with st.expander('Short Code × Campaign (share of source calls)',expanded=False):
            by_source=call_dates.groupby(['campaign','short_code','status']).agg(Calls=('call_id','count'),Orders=('orders','sum'),**{'Order Value':('order_value','sum')}).reset_index()
            by_source['%']=100*by_source['Calls']/by_source.groupby('campaign')['Calls'].transform('sum')
            report_table(by_source.sort_values(['campaign','Calls'],ascending=[True,False]),'call_short_codes_by_campaign.csv')
    else:st.info('No call-date rows in this period.')

with t3:
    st.markdown('<div class="section">Facebook Campaign → Converted Customers → Orders → Amount</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">**Lead Campaign** comes from Facebook → Campaign Name; **order revenue** comes from Tele Sales Order.xlsx → Product Price. Only orders matched to an answered call are counted as conversions. Conversion Rate = unique buying phone numbers ÷ unique reached phone numbers × 100. Repeat calls and repeat orders do not inflate buyer counts.</div>',unsafe_allow_html=True)
    mode=st.radio('Campaign conversion by', ['Data Provided Date','Call Date'],horizontal=True,key='conv_campaign_mode')
    kind='provided' if mode.startswith('Data') else 'call'
    cohort=provided if kind=='provided' else call_dates
    conv=campaign_conversion_report(cohort,kind)
    total=campaign_conversion_total(cohort,kind)
    metric_card_columns([
        ('Facebook Campaigns',f'{len(conv):,}','Distinct Facebook Campaign Name labels in the selected date mode'),
        ('Unique Reached',f"{total['Unique Reached']:,}",'Unique phone numbers whose calls were received'),
        ('Buying Customers',f"{total['Buying Customers']:,}",'Unique received phone numbers with a matched order'),
        ('Converted Orders',f"{total['Orders']:,}",'Unique matched order rows for reached leads'),
        ('Conversion Rate',pct(total['Conversion Rate']),'Buying Customers / Unique Reached'),
        ('Converted Revenue',money(total['Order Value']),'Matched order net Product Price total'),
    ])
    st.subheader('Campaign-wise Conversion & Order Amount')
    if not conv.empty:
        left,right=st.columns(2)
        with left:horizontal_bar(conv.sort_values('Order Value',ascending=False),'Campaign','Order Value','Order amount by Facebook campaign',top=15)
        with right:horizontal_bar(conv.sort_values('Conversion Rate',ascending=False),'Campaign','Conversion Rate','Customer conversion % by Facebook campaign',top=15)
        full=pd.concat([conv,pd.DataFrame([total])],ignore_index=True)
    else:
        full=conv
    report_table(full,'facebook_campaign_conversion_amount.csv')
    with st.expander('Campaign × Day (with converted orders & revenue)',expanded=False):
        day_col='provided_date' if kind=='provided' else 'call_date'
        if not cohort.empty:
            blocks=[]
            for (day,cam),grp in cohort.groupby([day_col,'campaign'],dropna=False):
                piece=campaign_conversion_report(grp,kind)
                if not piece.empty:
                    item=piece.iloc[0].to_dict();item['Day']=day;blocks.append(item)
            by_day=pd.DataFrame(blocks)
            if not by_day.empty:
                first=['Day','Campaign']
                report_table(by_day[first+[x for x in by_day.columns if x not in first]].sort_values(['Day','Order Value'],ascending=[True,False]),'campaign_conversion_daily.csv')
    st.subheader('Cross-check: Facebook Campaign × Tele Sales Order Campaign')
    st.caption('Facebook campaign shows the lead source; Order Campaign and Order Campaign Name come from the actual order workbook. Blank order Campaign Name is explicitly shown as “(not supplied)”, never guessed.')
    matching_links=link_lead if kind=='provided' else link_call
    key='lead_id' if kind=='provided' else 'call_id'
    source_detail=campaign_order_attribution_detail(matching_links,key,cohort,orders)
    report_table(source_detail,'facebook_to_order_campaign_attribution.csv')
    if not orders.empty:
        name_filled=orders['campaign_name'].astype(str).str.strip().ne('').sum()
        st.caption(f'Order workbook Campaign Name populated in {int(name_filled):,} of {len(orders):,} eligible orders (within order-source filter); the matching Facebook campaign name is used for lead conversion attribution instead.')
    else:
        st.warning('Upload Tele Sales Order.xlsx in the sidebar. Without that file, revenue and conversion cannot be calculated.')

with t4:
    st.markdown('<div class="section">Order & Campaign Performance</div>',unsafe_allow_html=True)
    st.caption('Final order value = Tele Sales order sheet "Product Price"; fallback when blank/zero: Total Amount − Shipping Charge. It does not add discount twice.')
    report_type=st.radio('Which orders?', ['All eligible Tele Sales Orders (Order Date)','Matched Facebook data leads (Data Provided Date)','Matched Received calls (Call Date)'],horizontal=False)
    if report_type.startswith('All'):
        o=selected_between(orders,'order_date',start,end)
    elif report_type.startswith('Matched Facebook'):
        ids=link_lead.loc[link_lead['lead_id'].isin(provided['lead_id']),'order_id'].unique()
        o=orders.loc[orders['order_id'].isin(ids)].copy()
    else:
        ids=link_call.loc[link_call['call_id'].isin(call_dates['call_id']),'order_id'].unique()
        o=orders.loc[orders['order_id'].isin(ids)].copy()
    metric_card_columns([
        ('Orders',f'{len(o):,}','Count of order rows'),
        ('Buying Phone Numbers',f'{o["phone"].nunique():,}' if not o.empty else '0','Unique phone numbers'),
        ('Revenue',money(o['order_value'].sum()) if not o.empty else money(0),'Product Price summed across orders'),
        ('AOV',money(o['order_value'].sum()/len(o)) if len(o) else money(0),'Order Value / Orders')
    ])
    dim=st.selectbox('Campaign breakdown',('Campaign Name (fallback Campaign)','Campaign (category)'),index=0)
    dimension='order_campaign_label' if dim.startswith('Campaign Name') else 'campaign'
    cmp=campaign_order_report(o,dimension)
    if not cmp.empty:horizontal_bar(cmp,'Campaign','Order Value','Campaign-wise order revenue',top=20)
    report_table(cmp,'campaign_orders.csv')
    st.subheader('Product-wise Order Report')
    products=product_order_report(o)
    if not products.empty:horizontal_bar(products,'Product','Qty','Products ordered (QTY)',top=15)
    report_table(products,'campaign_products.csv')
    with st.expander('Day × Campaign order value',expanded=False):
        if not o.empty:
            od=o.copy();od['Order Day']=od['order_date']
            x=od.groupby(['Order Day',dimension],as_index=False).agg(Orders=('order_id','count'),**{'Order Value':('order_value','sum')})
            x=x.rename(columns={dimension:'Campaign'})
            report_table(x,'daily_campaign_order_value.csv')
    if raw_orders.empty:
        st.info('Upload the order workbook in the sidebar to populate these reports.')

with t5:
    st.markdown('<div class="section">Data Quality & Attribution Rules</div>',unsafe_allow_html=True)
    received_count=int((calls['status']=='Received').sum())
    st.write({'Facebook loaded lead rows':len(leads), 'Leads without parseable provided date':unmatched_lead_dates,
              'Calls without parseable call date':undated_call,'Calls classified Received':received_count,
              'Calls classified Not Received':int((calls['status']=='Not Received').sum()),
              'Unclassified calls':int((calls['status']=='Unclassified').sum()),
              'Order rows after campaign scope':len(orders),
              'Orders linked to leads':len(link_lead),'Orders linked to received calls':len(link_call)})
    st.markdown('''**Important definitions**
- One Facebook row = one provided lead record. Repeated telephone numbers in separate lead rows remain separate lead records.
- One Short Code + corresponding call date = one attempted call; calls without valid dates are available for the provided-date report, not the call-date report.
- Contact/Answer Rates are distinct from Conversion Rates. Only a **Received** lead/call may contribute to the conversion numerator.
- Every eligible order is attributed **at most once** for each attribution model, to the latest prior lead or latest prior answered call within the attribution window.
- Orders placed after the selected date period can appear in a cohort's revenue if they fall within the attribution window. This is intentional, not same-day order revenue.
- The Facebook tab has **Campaign Name**, not a separate Source column. The dashboard labels Campaign Name as the lead source; Tele Sales Order provides its own Campaign and Campaign Name fields.
- Dropdown Short Code classification is editable in the sidebar. Codes without a confirmed meaning should be assigned to Unclassified.
- Both date-report modes use the selected period, but their denominators differ: **lead rows** in Provided Date versus **call attempts** in Call Date. Conversion uses unique reached phone numbers.
''')
    st.caption('Missing Order ID linkage is handled by normalized last 10 phone digits plus date-window attribution; this is a proxy, not a proven direct causal attribution. Check campaign values against your order system.')
    if not calls.empty:
        unclassified_codes=calls.loc[calls['status'].eq('Unclassified'),'short_code'].value_counts().rename_axis('Short Code').reset_index(name='Calls')
        if not unclassified_codes.empty:
            st.subheader('Review unclassified Short Codes')
            st.dataframe(unclassified_codes,hide_index=True,use_container_width=True)
    st.subheader('Source data checklist')
    with st.expander('Show column labels (no customer rows)',expanded=False):
        st.write({'Facebook fields':list(raw_fb.columns), 'Order fields':list(raw_orders.columns) if not raw_orders.empty else []})

