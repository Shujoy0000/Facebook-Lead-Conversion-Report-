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
    st.markdown('<div class="note">**Lead Campaign** comes from Facebook → Campaign Name; **order revenue** comes from Tele Sales Order CSV → Product Price. Only orders matched to an answered call are counted as conversions. Conversion Rate = unique buying phone numbers ÷ unique reached phone numbers × 100. Repeat calls and repeat orders do not inflate buyer counts.</div>',unsafe_allow_html=True)
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
        st.caption(f'Order CSV Campaign Name populated in {int(name_filled):,} of {len(orders):,} eligible orders (within order-source filter); the matching Facebook campaign name is used for lead conversion attribution instead.')
    else:
        st.warning('Order Published CSV থেকে ডেটা আসেনি। Sidebar-এর Refresh Google data ব্যবহার করুন।')

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
        st.info('Order Published CSV থেকে ডেটা পাওয়া যায়নি।')

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
