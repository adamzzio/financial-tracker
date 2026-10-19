from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import insert, select, text
from sqlalchemy.exc import SQLAlchemyError

from utils.auth import can_input_data, get_account_id, render_sidebar, require_login
from utils.db import get_engine, get_table
from utils.formatting import rupiah

st.set_page_config(page_title="Input Data Investment | FinTrack", page_icon="📈", layout="wide")

user = require_login()
render_sidebar(user)

if not can_input_data(user):
    st.error("Akun ini tidak memiliki akses ke halaman input data.")
    st.stop()

account_id = get_account_id(user)
if account_id is None:
    st.error("Akun ini belum terdaftar pada mapping account_id.")
    st.stop()

FLOW = "Investment"

# Pemetaan jenis transaksi ke tabel dan nama kolomnya
JENIS = {
    "Investment": {
        "tabel": "master_investment",
        "item": "investment",
        "amount": "investment_amount",
        "date": "investment_date",
    },
    "Outvestment": {
        "tabel": "master_outvestment",
        "item": "outvestment",
        "amount": "outvestment_amount",
        "date": "outvestment_date",
    },
}


# ---------- Data platform & investasi ----------
@st.cache_data(ttl=60, show_spinner=False)
def load_kategori(flow: str) -> pd.DataFrame:
    query = text(
        "SELECT DISTINCT category AS platform, subcategory AS investment "
        "FROM master_category WHERE flow = :flow ORDER BY 1, 2"
    )
    with get_engine().connect() as conn:
        return pd.read_sql(query, conn, params={"flow": flow})


try:
    kategori_df = load_kategori(FLOW)
except Exception as e:
    st.error(f"Gagal membaca master_category: {e}")
    st.stop()

if kategori_df.empty:
    st.warning(f"Belum ada data dengan flow '{FLOW}' di master_category.")
    st.stop()

# ---------- Header ----------
st.title("📈 Input Data Investment")

if "investment_ver" not in st.session_state:
    st.session_state["investment_ver"] = 0
v = st.session_state["investment_ver"]

# ---------- Form input ----------
# Widget sengaja tidak memakai st.form agar pilihan dependen bisa menyesuaikan secara langsung
with st.container(border=True):
    jenis = st.selectbox(
        "Jenis Transaksi",
        list(JENIS),
        index=0,
        key="inv_jenis",  # tanpa versi, agar pilihan tetap setelah simpan
        help="Investment: dana masuk ke investasi. Outvestment: dana ditarik dari investasi.",
    )
    cfg = JENIS[jenis]
    st.caption(f"Data akan tersimpan ke tabel `{cfg['tabel']}`.")

    c1, c2 = st.columns(2)

    daftar_platform = sorted(kategori_df["platform"].unique())
    platform = c1.selectbox(
        "Platform", daftar_platform, index=None,
        placeholder="Pilih platform", key=f"inv_plat_{v}",
    )

    daftar_investment = (
        sorted(kategori_df.loc[kategori_df["platform"] == platform, "investment"].dropna().unique())
        if platform else []
    )
    investment = c2.selectbox(
        "Investment", daftar_investment, index=None,
        placeholder="Pilih investment" if platform else "Pilih platform terlebih dahulu",
        disabled=not platform, key=f"inv_name_{v}",
    )

    c3, c4 = st.columns(2)
    amount = c3.number_input(
        f"{jenis} Amount (Rp)", min_value=0, step=1000, value=None,
        format="%d", placeholder="Contoh: 1000000", key=f"inv_amt_{v}",
    )
    tanggal = c4.date_input(
        f"{jenis} Date", value=None, format="DD/MM/YYYY",
        help="Kosongkan untuk memakai tanggal hari ini.", key=f"inv_date_{v}",
    )

    if amount:
        c3.caption(rupiah(amount))

    simpan = st.button("Simpan", type="primary", use_container_width=True)

# ---------- Simpan ----------
if simpan:
    if not platform or not investment:
        st.warning("Platform dan Investment wajib dipilih.")
    elif not amount or amount <= 0:
        st.warning(f"{jenis} Amount wajib diisi dan lebih dari 0.")
    else:
        tanggal_simpan = tanggal or datetime.now(ZoneInfo("Asia/Jakarta")).date()
        try:
            tabel = get_table(cfg["tabel"])
            with get_engine().begin() as conn:
                conn.execute(
                    insert(tabel).values(
                        **{
                            "account_id": account_id,
                            "platform": platform,
                            cfg["item"]: investment,
                            cfg["amount"]: int(amount),
                            cfg["date"]: tanggal_simpan,
                        }
                    )
                )
            st.session_state["investment_ver"] += 1  # reset form
            st.toast(f"Data {jenis.lower()} berhasil disimpan.", icon="✅")
            st.rerun()
        except SQLAlchemyError as e:
            st.error(f"Gagal menyimpan: {e}")

# ---------- Riwayat input ----------
st.subheader("10 Transaksi Terakhir")

QUERY_RIWAYAT = text(
    """
    SELECT * FROM (
        SELECT id, account_id, 'Investment' AS "Flow", platform,
               investment AS "Category",
               investment_amount AS "Amount",
               investment_date AS "Date"
        FROM master_investment
        UNION ALL
        SELECT id, account_id, 'Outvestment', platform,
               outvestment,
               outvestment_amount,
               outvestment_date
        FROM master_outvestment
    ) t
    WHERE account_id = :account_id
    ORDER BY "Date" DESC, id DESC
    LIMIT 10
    """
)

try:
    with get_engine().connect() as conn:
        terakhir = pd.read_sql(QUERY_RIWAYAT, conn, params={"account_id": account_id})
    if terakhir.empty:
        st.caption("Belum ada data.")
    else:
        terakhir["Amount"] = terakhir["Amount"].apply(rupiah)
        st.dataframe(terakhir, hide_index=True, use_container_width=True)
except Exception as e:
    st.error(f"Gagal membaca tabel `master_investment` dan `master_outvestment`: {e}")