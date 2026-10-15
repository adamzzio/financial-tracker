import numpy as np
import pandas as pd
import streamlit as st

TIPE = ["Income", "Expense", "Investment"]

# kategori: (jumlah transaksi min, max, nominal min, max) per bulan
EXPENSE_SPEC = {
    "Makan & Minum": (14, 20, 25_000, 120_000),
    "Transport": (8, 12, 15_000, 80_000),
    "Tagihan": (3, 4, 150_000, 900_000),
    "Belanja": (2, 4, 100_000, 700_000),
    "Hiburan": (2, 4, 50_000, 400_000),
    "Kesehatan": (0, 2, 80_000, 500_000),
    "Lainnya": (1, 3, 20_000, 200_000),
}

INVEST_SPEC = {
    "Saham": (0, 2, 500_000, 2_000_000),
    "Emas": (0, 1, 300_000, 1_000_000),
    "Kripto": (0, 1, 200_000, 800_000),
}


def _bulatkan(nilai: float, step: int = 5_000) -> int:
    return int(round(nilai / step) * step)


@st.cache_data(show_spinner=False)
def generate_transactions(
    hari_ini: str, jumlah_bulan: int = 12, seed: int = 42
) -> pd.DataFrame:
    """Data transaksi dummy. Kolom: tanggal, tipe, kategori, nominal."""
    rng = np.random.default_rng(seed)
    today = pd.Timestamp(hari_ini)
    awal = today.replace(day=1) - pd.DateOffset(months=jumlah_bulan - 1)

    rows: list[dict] = []

    for periode in pd.period_range(awal, periods=jumlah_bulan, freq="M"):
        mulai = periode.start_time
        hari = periode.days_in_month

        def tambah(tipe: str, kategori: str, nominal: int, hari_ke: int | None = None):
            h = int(rng.integers(0, hari)) if hari_ke is None else min(hari_ke, hari - 1)
            rows.append(
                {
                    "tanggal": mulai + pd.Timedelta(days=h),
                    "tipe": tipe,
                    "kategori": kategori,
                    "nominal": int(nominal),
                }
            )

        # Income
        tambah("Income", "Gaji", 12_000_000, 24)
        for _ in range(int(rng.integers(0, 3))):
            tambah("Income", "Freelance", _bulatkan(rng.integers(500_000, 3_000_001), 50_000))
        if periode.month in (6, 12):
            tambah("Income", "Bonus", 4_000_000, 10)

        # Expense
        for kategori, (jmin, jmax, nmin, nmax) in EXPENSE_SPEC.items():
            for _ in range(int(rng.integers(jmin, jmax + 1))):
                tambah("Expense", kategori, _bulatkan(rng.integers(nmin, nmax + 1)))

        # Investment
        tambah("Investment", "Reksa Dana", 1_500_000, 25)
        for kategori, (jmin, jmax, nmin, nmax) in INVEST_SPEC.items():
            for _ in range(int(rng.integers(jmin, jmax + 1))):
                tambah("Investment", kategori, _bulatkan(rng.integers(nmin, nmax + 1), 50_000))

    df = pd.DataFrame(rows)
    df = df[df["tanggal"] <= today].sort_values("tanggal").reset_index(drop=True)
    return df