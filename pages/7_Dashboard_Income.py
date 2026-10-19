from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from utils.auth import get_account_id, has_role, render_sidebar, require_login
from utils.db import get_engine
from utils.formatting import BULAN_SINGKAT, rupiah
from utils.periode import render_filter_periode, terapkan_periode

st.set_page_config(page_title="Dashboard Income | FinTrack", page_icon="💵", layout="wide")

user = require_login()
render_sidebar(user)

KELOMPOK = ["Salary", "Freelance", "Other"]
WARNA = {"Salary": "#22c55e", "Freelance": "#3b82f6", "Other": "#f59e0b"}
PERIODE = {
    "All": None,
    "1 Bulan Terakhir": 1,
    "3 Bulan Terakhir": 3,
    "6 Bulan Terakhir": 6,
    "12 Bulan Terakhir": 12,
}

# ---------- Scope akun ----------
# Admin melihat semua akun, user lain hanya akunnya sendiri
is_admin = has_role(user, "admin")
account_id = None if is_admin else get_account_id(user)

if not is_admin and account_id is None:
    st.error("Akun ini belum terdaftar pada mapping account_id.")
    st.stop()


# ---------- Data ----------
@st.cache_data(ttl=60, show_spinner=False)
def load_income(account_id: int | None) -> pd.DataFrame:
    query = (
        "SELECT id, account_id, category, subcategory, income_amount, income_date "
        "FROM master_income"
    )
    params = {}
    if account_id is not None:
        query += " WHERE account_id = :account_id"
        params["account_id"] = account_id
    with get_engine().connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
    df["income_date"] = pd.to_datetime(df["income_date"])
    df["income_amount"] = pd.to_numeric(df["income_amount"]).fillna(0)
    return df


try:
    semua = load_income(account_id)
except Exception as e:
    st.error(f"Gagal membaca tabel `master_income`: {e}")
    st.stop()

# ---------- Header & filter ----------
st.title("💵 Dashboard Income")
st.caption(
    "Ringkasan seluruh akun." if is_admin else f"Ringkasan pemasukan milik {user['name']}."
)

n_bulan = render_filter_periode()
df = terapkan_periode(semua, "income_date", n_bulan)

if df.empty:
    st.info("Belum ada data income pada periode ini.")
    st.stop()

# Kelompok: Salary, Freelance, Other (kategori selain Salary dan Freelance)
df["kelompok"] = df["category"].where(df["category"].isin(["Salary", "Freelance"]), "Other")

# ---------- Card ----------
total_all = df["income_amount"].sum()
total_salary = df.loc[df["kelompok"] == "Salary", "income_amount"].sum()
total_freelance = df.loc[df["kelompok"] == "Freelance", "income_amount"].sum()
total_other = df.loc[df["kelompok"] == "Other", "income_amount"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total All Income", rupiah(total_all), help="SUM income_amount seluruh kategori.")
k2.metric("Total Salary Income", rupiah(total_salary), help="SUM income_amount dengan category = 'Salary'.")
k3.metric("Total Freelance Income", rupiah(total_freelance), help="SUM income_amount dengan category = 'Freelance'.")
k4.metric(
    "Total Other Income",
    rupiah(total_other),
    help="SUM income_amount dengan category selain 'Salary' dan 'Freelance'.",
)

st.divider()


# ---------- Helper ----------
def rapikan(fig, tinggi: int = 380):
    fig.update_layout(
        separators=",.",
        height=tinggi,
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="",
    )
    return fig


def bar_horizontal(data: pd.DataFrame, kolom: str, judul: str, warna: str):
    """Bar chart horizontal: SUM income_amount per kolom, urut terbesar di atas."""
    if data.empty:
        st.subheader(judul)
        st.caption("Belum ada data.")
        return
    agg = data.groupby(kolom, as_index=False)["income_amount"].sum()
    fig = px.bar(
        agg, x="income_amount", y=kolom, orientation="h", title=judul,
        labels={"income_amount": "", kolom: ""},
    )
    fig.update_traces(
        marker_color=warna,
        hovertemplate="<b>%{y}</b><br>Rp %{x:,.0f}<extra></extra>",
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_xaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)


# ---------- Agregasi bulanan ----------
df["bulan"] = df["income_date"].dt.to_period("M").dt.to_timestamp()
rentang = pd.date_range(df["bulan"].min(), df["bulan"].max(), freq="MS")
bulanan = (
    df.pivot_table(index="bulan", columns="kelompok", values="income_amount",
                   aggfunc="sum", fill_value=0)
    .reindex(rentang, fill_value=0)
    .reindex(columns=KELOMPOK, fill_value=0)
)
bulanan["Total"] = bulanan[KELOMPOK].sum(axis=1)
bulanan["Kumulatif"] = bulanan["Total"].cumsum()

urutan_bulan = [f"{BULAN_SINGKAT[b.month - 1]} {b.year}" for b in bulanan.index]
bulanan.index = urutan_bulan
bulanan.index.name = "bulan"

# ---------- Baris 1: bar per bulan & donut ----------
c1, c2 = st.columns([3, 2])

with c1:
    long = bulanan[KELOMPOK].reset_index().melt(
        id_vars="bulan", var_name="kelompok", value_name="nominal"
    )
    fig = px.bar(
        long, x="bulan", y="nominal", color="kelompok", barmode="group",
        color_discrete_map=WARNA,
        category_orders={"bulan": urutan_bulan, "kelompok": KELOMPOK},
        title="Salary, Freelance, dan Other Income per Bulan",
        labels={"bulan": "", "nominal": ""},
    )
    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Rp %{y:,.0f}<extra></extra>"
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c2:
    komposisi = (
        df.groupby("kelompok", as_index=False)["income_amount"].sum()
    )
    fig = px.pie(
        komposisi, names="kelompok", values="income_amount", hole=0.5,
        color="kelompok", color_discrete_map=WARNA,
        category_orders={"kelompok": KELOMPOK},
        title="Komposisi Income",
    )
    fig.update_traces(
        textinfo="percent",
        sort=False,
        hovertemplate="<b>%{label}</b><br>Rp %{value:,.0f}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(rapikan(fig), use_container_width=True)

# ---------- Baris 2: pertumbuhan & kumulatif ----------
c3, c4 = st.columns(2)

with c3:
    fig = px.line(
        bulanan.reset_index(), x="bulan", y="Total", markers=True,
        category_orders={"bulan": urutan_bulan},
        title="Pertumbuhan All Income per Bulan",
        labels={"bulan": "", "Total": ""},
    )
    fig.update_traces(
        line_color="#22c55e",
        hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c4:
    fig = px.area(
        bulanan.reset_index(), x="bulan", y="Kumulatif", markers=True,
        category_orders={"bulan": urutan_bulan},
        title="Pertumbuhan Kumulatif All Income",
        labels={"bulan": "", "Kumulatif": ""},
    )
    fig.update_traces(
        line_color="#a855f7",
        hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

# ---------- Baris 3: per category & per subcategory ----------
c5, c6 = st.columns(2)
with c5:
    bar_horizontal(df, "category", "Total All Income berdasarkan Category", "#22c55e")
with c6:
    bar_horizontal(df, "subcategory", "Total All Income berdasarkan Subcategory", "#14b8a6")

# ---------- Baris 4: Freelance & Other per subcategory ----------
c7, c8 = st.columns(2)
with c7:
    bar_horizontal(
        df[df["kelompok"] == "Freelance"], "subcategory",
        "Total Freelance Income berdasarkan Subcategory", WARNA["Freelance"],
    )
with c8:
    bar_horizontal(
        df[df["kelompok"] == "Other"], "subcategory",
        "Total Other Income berdasarkan Subcategory", WARNA["Other"],
    )

# ---------- Tabel 10 transaksi terakhir ----------
st.subheader("10 Transaksi Income Terakhir")
kolom_tabel = ["income_date", "category", "subcategory", "income_amount"]
if is_admin:
    kolom_tabel.insert(0, "account_id")

terakhir = (
    df.sort_values(["income_date", "id"], ascending=False).head(10)[kolom_tabel].copy()
)
terakhir["income_date"] = terakhir["income_date"].dt.strftime("%d-%m-%Y")
terakhir["income_amount"] = terakhir["income_amount"].apply(rupiah)
terakhir = terakhir.rename(
    columns={
        "account_id": "Account ID",
        "income_date": "Tanggal",
        "category": "Category",
        "subcategory": "Subcategory",
        "income_amount": "Nominal",
    }
)
st.dataframe(terakhir, hide_index=True, use_container_width=True)