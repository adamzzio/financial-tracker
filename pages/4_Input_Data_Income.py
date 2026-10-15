from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import insert, select, text
from sqlalchemy.exc import SQLAlchemyError

from utils.auth import can_input_data, get_account_id, render_sidebar, require_login
from utils.db import get_engine, get_table
from utils.formatting import rupiah

st.set_page_config(page_title="Input Data Income | FinTrack", page_icon="📝", layout="wide")

user = require_login()
render_sidebar(user)

if not can_input_data(user):
    st.error("Akun ini tidak memiliki akses ke halaman input data.")
    st.stop()

account_id = get_account_id(user)
if account_id is None:
    st.error("Akun ini belum terdaftar pada mapping account_id.")
    st.stop()

TABLE_NAME = "master_income"
FLOW = "Inflow"


# ---------- Data kategori ----------
@st.cache_data(ttl=60, show_spinner=False)
def load_kategori(flow: str) -> pd.DataFrame:
    query = text(
        "SELECT DISTINCT category, subcategory FROM master_category "
        "WHERE flow = :flow ORDER BY category, subcategory"
    )
    with get_engine().connect() as conn:
        return pd.read_sql(query, conn, params={"flow": flow})


try:
    kategori_df = load_kategori(FLOW)
except Exception as e:
    st.error(f"Gagal membaca master_category: {e}")
    st.stop()

if kategori_df.empty:
    st.warning(f"Belum ada kategori dengan flow '{FLOW}' di master_category.")
    st.stop()

# ---------- Header ----------
st.title("📝 Input Data Income")
st.caption("Catat pemasukan baru. Data akan tersimpan ke tabel `master_income`.")

if "income_ver" not in st.session_state:
    st.session_state["income_ver"] = 0
v = st.session_state["income_ver"]

# ---------- Form input ----------
# Widget sengaja tidak memakai st.form agar subcategory bisa menyesuaikan category secara langsung
with st.container(border=True):
    c1, c2 = st.columns(2)

    daftar_kategori = sorted(kategori_df["category"].unique())
    category = c1.selectbox(
        "Category", daftar_kategori, index=None,
        placeholder="Pilih category", key=f"inc_cat_{v}",
    )

    daftar_sub = (
        sorted(kategori_df.loc[kategori_df["category"] == category, "subcategory"].dropna().unique())
        if category else []
    )
    subcategory = c2.selectbox(
        "Subcategory", daftar_sub, index=None,
        placeholder="Pilih subcategory" if category else "Pilih category terlebih dahulu",
        disabled=not category, key=f"inc_sub_{v}",
    )

    c3, c4 = st.columns(2)
    amount = c3.number_input(
        "Income Amount (Rp)", min_value=0, step=1000, value=None,
        format="%d", placeholder="Contoh: 5000000", key=f"inc_amt_{v}",
    )
    tanggal = c4.date_input(
        "Income Date", value=None, format="DD/MM/YYYY",
        help="Kosongkan untuk memakai tanggal hari ini.", key=f"inc_date_{v}",
    )

    if amount:
        c3.caption(rupiah(amount))

    simpan = st.button("Simpan", type="primary", use_container_width=True)

# ---------- Simpan ----------
if simpan:
    if not category or not subcategory:
        st.warning("Category dan Subcategory wajib dipilih.")
    elif not amount or amount <= 0:
        st.warning("Income Amount wajib diisi dan lebih dari 0.")
    else:
        income_date = tanggal or datetime.now(ZoneInfo("Asia/Jakarta")).date()
        try:
            tabel = get_table(TABLE_NAME)
            with get_engine().begin() as conn:
                conn.execute(
                    insert(tabel).values(
                        account_id=account_id,
                        category=category,
                        subcategory=subcategory,
                        income_amount=int(amount),
                        income_date=income_date,
                    )
                )
            st.session_state["income_ver"] += 1  # reset form
            st.toast("Data income berhasil disimpan.", icon="✅")
            st.rerun()
        except SQLAlchemyError as e:
            st.error(f"Gagal menyimpan: {e}")

# ---------- Riwayat input ----------
st.subheader("10 Input Terakhir")
try:
    tabel = get_table(TABLE_NAME)
    with get_engine().connect() as conn:
        terakhir = pd.read_sql(
            select(tabel)
            .where(tabel.c.account_id == account_id)
            .order_by(tabel.c.income_date.desc(), tabel.c.id.desc())
            .limit(10),
            conn,
        )
    if terakhir.empty:
        st.caption("Belum ada data.")
    else:
        terakhir["income_amount"] = terakhir["income_amount"].apply(rupiah)
        st.dataframe(terakhir, hide_index=True, use_container_width=True)
except Exception as e:
    st.error(f"Gagal membaca tabel `{TABLE_NAME}`: {e}")