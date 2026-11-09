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
        st.markdown('<div class="report-note">এখানে Date Range <b>Call Date</b>-এর ওপর কাজ করে। ১ম–১০ম সব কল গণনা হয়। একই Lead একাধিকবার “অর্ডার করেছেন” হলে প্রথম Confirmed কলেই Conversion গণনা করা হয়।</div>',unsafe_allow_html=True)
        c_total=len(day_calls)
        rc=int(day_calls.status.eq('Received').sum())
        nc=int(day_calls.status.eq('Not Received').sum())
        uc=int(day_calls.status.eq('Unknown').sum())
        buyers=day_calls.loc[day_calls.conversion_event,'phone'].where(day_calls.loc[day_calls.conversion_event,'phone'].ne(''),day_calls.loc[day_calls.conversion_event,'lead_key']).nunique()
        reached=day_calls.loc[day_calls.status.eq('Received'),'phone'].where(day_calls.loc[day_calls.status.eq('Received'),'phone'].ne(''),day_calls.loc[day_calls.status.eq('Received'),'lead_key']).nunique()
        metrics_grid(st,{'Calls':c_total,'Received':rc,'NotReceived':nc,'Unknown':uc,'Confirmed':buyers,'Answer':100*rc/max(c_total,1),'Conversion':100*buyers/max(reached,1)},[
            ('Call Attempts','Calls',lambda x:f'{x:,}','একটি Short Code/Call Date = একটি call'),
            ('Received Calls','Received',lambda x:f'{x:,}','Short Code classified Received'),
            ('Not Received Leads','NotReceived',lambda x:f'{x:,}','স্পষ্ট Not Received short codes'),
            ('Confirmed Buyers','Confirmed',lambda x:f'{x:,}','প্রথম অর্ডার করেছেন Call Date-এর দিন'),
            ('Conversion Rate','Conversion',percent,'Unique Confirmed Customers ÷ Unique Reached Customers'),
            ('Unknown Codes','Unknown',lambda x:f'{x:,}','Blank/unclear Short Code'),
            ('Answer Rate','Answer',percent,'Received Call Attempts ÷ All Call Attempts'),
        ])
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
                  'Facebook order rows (all dates)':len(orders)})
        st.markdown('**Reconciliation:** Confirmed Buyers are Short Code based. Lead-matched sales use the first qualifying Provided-Date lead for the same phone and no maximum days. Orders lacking a matching phone stay in the Order Date tab; blank Campaign Name is always retained. Contact Rate and Answer Rate are different metrics.')
        st.markdown('**Not Received classification** is based on explicit known labels. Review unknown or new Short Codes when they appear.')


if __name__ == '__main__':
    main()
