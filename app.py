
এই চ্যাটে আমি টেলি সেলস ড্যাশবোর্ড বানিয়েছি না? তো সেখানেকি এতো কিছু করেছিলাম?
হ্যাঁ ভাই, এই চ্যাটেই আমরা Tele Sales Analytics Dashboard বানিয়েছি। আর সেখানে এত কিছু করতে হয়নি। আপনি ঠিকই বলেছেন।

আগের Tele Sales Dashboard-এ আমরা যা করেছিলাম:

Google Sheet-এর Published CSV URL সরাসরি app.py-তে দিয়েছিলাম।

pd.read_csv(url) দিয়ে ডেটা আনতাম।

Sidebar থেকে Date Select করতাম।

Google Sheet-এ ডেটা আপডেট হলে Dashboard Refresh করলেই নতুন রিপোর্ট আসত।

সেখানে Service Account, Google API, Streamlit Secrets কিংবা প্রতিবার Excel Upload—কোনোটাই লাগেনি।

তাহলে নতুন Facebook Lead Conversion Report-এ এত কিছু কেন?
আমি আগের সহজ পদ্ধতি অনুসরণ না করে অপ্রয়োজনীয়ভাবে জটিল করেছি।

নতুন Dashboard-ও আগের মতো করতে চাই:

Facebook Sheet → Published CSV → Streamlit

Tele Sales Order Sheet → Published CSV → Streamlit

দুই Sheet-এর ডেটা মিলিয়ে Campaign Conversion %, Received/Not Received, Short Code ও Order Amount হিসাব

আগের Header ও Design অপরিবর্তিত

শুধু একটা বিষয়: Facebook Sheet-এ গ্রাহকদের ফোন নম্বর ও ব্যক্তিগত তথ্য আছে। Published CSV করলে সেই ট্যাবের ডেটা লিংকধারীদের কাছে উন্মুক্ত হতে পারে। তাই এটি প্রকাশ করার আগে গোপনীয়তার বিষয়টি বিবেচনা করতে হবে।

আপনার Tele Sales Dashboard-এর মতো একই সহজ কাঠামোতেই Facebook Lead Conversion Report বানানো উচিত ছিল। অপ্রয়োজনীয় পরিবর্তন না করে এখন থেকে সেটাই অনুসরণ করব।

https://docs.google.com/spreadsheets/d/e/2PACX-1vRhGpSv6YJ5uwMeTI3r06mc4ZmqcCZlrTCQGsjDlDq2o1Y7uYhT3snVgI1jZ_zMUzxN_RZfOKcC-Rfm/pub?output=csv


https://docs.google.com/spreadsheets/d/e/2PACX-1vTDhr-rwKe88LKKludd74G766j1l4vbvoaHi1YwwkefcfjCCgDGkZL6Ty9ngNv3gVvd5ezElgXghOs3/pub?gid=81417&single=true&output=csv

ঠিক আছে। আপনার দেওয়া দুটি Published Google Sheets CSV লিংক ব্যবহার করে Facebook Lead Conversion Report-এর Streamlit কোড আপডেট করেছি।

এখন আগের Tele Sales Dashboard-এর মতোই pd.read_csv() দিয়ে Google Sheet থেকে সরাসরি ডেটা নেওয়ার ব্যবস্থা আছে। Service Account, Streamlit Secrets কিংবা প্রতিবার Excel আপলোড করার প্রয়োজন নেই।

Facebook Lead Conversion Report — Updated

GitHub-ready ZIP · 6 files

 সম্পূর্ণ Dashboard ডাউনলোড করুন

Dashboard-এ যা থাকবে
Data Provided Date Report: Daily leads, Contact Rate এবং Conversion Rate।

Call Date Report: Received, Not Received এবং Short Code অনুযায়ী রিপোর্ট।

Campaign Conversion Report: Campaign-wise Leads, Orders, Conversion % এবং Amount (৳)।

Order Report: Product Price, Order Value এবং Campaign-wise Revenue।

আগের হেডার: Bigganbaksho লোগো, কমলা টাইটেল ও বাংলা লেখা।

GitHub-এ যা করবেন
ZIP Extract করুন।

আপনার GitHub Repository খুলুন।

Add file → Upload files থেকে ছয়টি ফাইল আপলোড/replace করুন।

Commit changes দিন।

Streamlit App Refresh করুন।

ডাউনলোডে সমস্যা হলে আলাদাভাবে app.py, analytics.py এবং requirements.txt নিতে পারবেন।

যাচাই: কোডের syntax এবং sample Conversion Calculation পরীক্ষা করেছি। তবে এই পরিবেশ থেকে আপনার Published CSV দুটির live content ডাউনলোড করা যায়নি, তাই বাস্তব ডেটার সংখ্যা এখনো নিশ্চিত করা হয়নি। App চালু হলে CSV-এর সঠিক column পাওয়া যাচ্ছে কি না তা যাচাই করবে।

একটি সতর্কতা: Published CSV-তে গ্রাহকের ফোন নম্বর থাকলে লিংকটি অন্য কেউ পেলেও সেই তথ্য পড়তে পারতে পারেন।


app.py
Code

analytics.py
Code

requirements.txt
Document
User attachment
User attachment
এটা দেখো আর পরেরটা দেখো
দুইটা Screenshot মিলিয়ে দেখলাম। প্রথমটা আগের Tele Sales Dashboard, দ্বিতীয়টা নতুন Facebook Lead Conversion Report। নতুনটার ডিজাইন ও Date Selection আগেরটার মতো হয়নি।

বিশেষ করে তিনটি সমস্যা দেখা যাচ্ছে:

Header নষ্ট হয়েছে: আগের Dashboard-এ লোগো, কমলা টাইটেল ও বাংলা লেখাগুলো সুন্দরভাবে দেখা যায়। নতুনটায় HTML code সরাসরি দেখা যাচ্ছে।

Date Selection-এ সমস্যা: নতুনটায় 29 June 2027 – 29 July 2027 দেখাচ্ছে, অথচ এখন নভেম্বর ২০২৬।

রিপোর্টে অস্বাভাবিক সংখ্যা: 9,533 Facebook records লোড হলেও নির্বাচিত সময়ে মাত্র ১টি lead দেখাচ্ছে। Date parsing ও filtering যাচাই করা প্রয়োজন।

আমি আগের Dashboard-এর ডিজাইন ও Date Picker অনুসরণ করে নতুনটার সমস্যা সংশোধন করব। Campaign Conversion, Call Date, Short Code, Order Amount—এসব রিপোর্ট বাদ দেওয়া হবে না।

আর Date-এর সমস্যার নির্দিষ্ট কারণও পেয়েছি।

Google Sheet-এর Facebook ট্যাবের 8422 নম্বর সারিতে Date = 29-07-2027 আছে। এই একটি ভবিষ্যতের তারিখকেই নতুন Dashboard সর্বশেষ তারিখ ধরে নিয়েছে। তাই Default Date Range ২০২৭-এ চলে গেছে এবং মাত্র ১টি lead দেখাচ্ছে।

এর সমাধানে আসল ডেটা পরিবর্তন না করে Dashboard-এর Default End Date আজকের তারিখ বা তার আগের সর্বশেষ ডেটার মধ্যে রাখব। ভবিষ্যতের তারিখগুলো আলাদাভাবে চিহ্নিত হবে।

সংশোধিত Dashboard তৈরি করেছি
Facebook Lead Conversion Report — Header & Date Fixed

ZIP · GitHub-ready · সব রিপোর্ট ও হিসাব অক্ষত

 সংশোধিত Dashboard ডাউনলোড করুন

শুধু প্রয়োজনীয় ফাইলটি চাইলে:

 Updated app.py

GitHub-এ যা করবেন: আপনার Repository-তে গিয়ে শুধু app.py replace করে Commit changes দিন। তারপর Streamlit Dashboard Refresh করুন।

এখন Header সঠিকভাবে render হওয়ার কথা এবং Date Picker আগের Tele Sales Dashboard-এর মতো আলাদা Start Date / End Date দেখাবে। Default Date আর ভবিষ্যতের ভুল এন্ট্রি ধরে নির্ধারিত হবে না।

কোডের syntax এবং আগের রিপোর্টের calculation অংশ অপরিবর্তিত আছে কি না যাচাই করেছি। তবে নতুন Streamlit UI লাইভ চালিয়ে এখনো পরীক্ষা করা হয়নি।

আর Google Sheet-এর 8422 নম্বর সারির 29-07-2027 তারিখটি ভুল এন্ট্রি হলে শিটে সংশোধন করাও ভালো।


app.py
Code
User attachment
সমস্যাটা নিশ্চিতভাবে পেয়েছি। আপনার GitHub Repository-র বর্তমান app.py-এর প্রথম লাইনই হলো:

    with st.expander('Day × Campaign report',expanded=False):

অর্থাৎ পুরো Python ফাইলের বদলে মাঝখানের একটি অংশ GitHub-এ আপলোড হয়েছে। তাই IndentationError আসছে।

সমাধান: সম্পূর্ণ app.py দিয়ে বর্তমান ফাইলটি replace করতে হবে। শুধু প্রথম লাইনের স্পেস মুছে দিলে হবে না।

আগের Header, Date Filter, Campaign Conversion, Call Report এবং Order Amount-এর কোডসহ সম্পূর্ণ ফাইলটি দিচ্ছি।

সম্পূর্ণ সংশোধিত app.py

514 lines · Python syntax verified

 Fixed app.py ডাউনলোড করুন

GitHub-এ যেভাবে ঠিক করবেন
আপনার GitHub Repository খুলুন।

Add file → Upload files নির্বাচন করুন।

ডাউনলোড করা সম্পূর্ণ app.py আপলোড করুন, যাতে পুরোনো app.py replace হয়।

Commit changes দিন।

Streamlit Dashboard খুলে Refresh করুন।

ফাইলটি ঠিকভাবে আপলোড হয়েছে কি না যাচাই করতে GitHub-এর app.py খুলুন। প্রথম লাইন হবে:

import io

পুরো ছয়টি ফাইল একসঙ্গে প্রয়োজন হলে Complete Fixed ZIP নিতে পারবেন।

যাচাই করেছি: সম্পূর্ণ app.py এবং analytics.py Python syntax check পাস করেছে। তবে Streamlit Cloud-এ নতুন deployment চলা এখনো যাচাই করা হয়নি।


app.py
Code
User attachment
সমস্যাটা পেয়েছি। আপনার GitHub-এ এখনো পুরোনো, অসম্পূর্ণ app.py আছে। তাই একই IndentationError বারবার দেখাচ্ছে।

আমি সম্পূর্ণ ফাইলটি আবার পরীক্ষা করেছি—৫১৪ লাইন, Python syntax check পাস করেছে।

সম্পূর্ণ সংশোধিত app.py

Python · 514 lines · 34 KB

 সঠিক app.py ডাউনলোড করুন

এবার GitHub-এ ঠিক এইভাবে করবেন
GitHub-এর বর্তমান app.py খুলুন।

উপরের তিন ডট (...) → Delete file দিয়ে পুরোনো app.py মুছে Commit changes দিন।

Repository-তে ফিরে Add file → Upload files চাপুন।

উপরের লিংক থেকে ডাউনলোড করা নতুন app.py আপলোড করুন।

আবার Commit changes দিন।

কীভাবে বুঝবেন এবার ঠিক হয়েছে?
GitHub-এ নতুন app.py খুলে দেখবেন প্রথম তিন লাইন:

import io
import base64
import os

প্রথম লাইনে আর with st.expander(...) থাকবে না।

তারপর Facebook Lead Conversion Report খুলে Refresh করুন।

শুধু app.py পরিবর্তন করবেন। analytics.py, requirements.txt, logo.png অপরিবর্তিত থাকবে। এতে আগের রিপোর্ট ও ডিজাইন নষ্ট হবে না।

আমি GitHub-এর বর্তমান ভুল ফাইলটি শনাক্ত করেছি, তবে Repository-তে সরাসরি পরিবর্তন করার অনুমতি না থাকায় Commit আপনাকেই করতে হবে।


app.py
Code
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




