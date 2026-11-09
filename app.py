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
