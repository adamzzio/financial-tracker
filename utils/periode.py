from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

PERIODE = {
    "All": None,
    "1 Bulan Terakhir": 1,
    "2 Bulan Terakhir": 2,
    "3 Bulan Terakhir": 3,
    "6 Bulan Terakhir": 6,
    "12 Bulan Terakhir": 12,
}


def hari_ini() -> pd.Timestamp:
    """Tanggal hari ini (WIB) tanpa jam."""
    return pd.Timestamp(datetime.now(ZoneInfo("Asia/Jakarta")).date())


def awal_periode(n_bulan: int | None) -> pd.Timestamp | None:
    """Tanggal 1 pada awal rentang. 1 bulan = tanggal 1 bulan ini,
    N bulan = tanggal 1 pada (N - 1) bulan sebelum bulan ini."""
    if n_bulan is None:
        return None
    return hari_ini().replace(day=1) - pd.DateOffset(months=n_bulan - 1)


def render_filter_periode() -> int | None:
    """Tampilkan filter periode (default All) dan kembalikan jumlah bulan (None = All)."""
    kol_filter, _ = st.columns([1, 3])
    pilihan = kol_filter.selectbox(
        "Periode",
        list(PERIODE),
        index=0,
        help="Rentang dimulai dari tanggal 1 pada awal periode sampai hari ini. "
        "Contoh: 1 Bulan Terakhir = tanggal 1 bulan ini sampai hari ini.",
    )
    n_bulan = PERIODE[pilihan]

    awal = awal_periode(n_bulan)
    if awal is None:
        kol_filter.caption("Semua data")
    else:
        kol_filter.caption(f"{awal:%d-%m-%Y} sampai {hari_ini():%d-%m-%Y}")
    return n_bulan


def terapkan_periode(df: pd.DataFrame, kolom_tanggal: str, n_bulan: int | None) -> pd.DataFrame:
    """Filter DataFrame sesuai periode. All mengembalikan semua data."""
    if n_bulan is None:
        return df.copy()
    awal = awal_periode(n_bulan)
    mask = (df[kolom_tanggal] >= awal) & (df[kolom_tanggal] <= hari_ini())
    return df.loc[mask].copy()