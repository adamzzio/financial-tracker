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

st.set_page_config(page_title="Dashboard Investment | FinTrack", page_icon="🏦", layout="wide")

user = require_login()
render_sidebar(user)

INV_DARURAT = "Dana Darurat"
INV_WEDDING = "Wedding"
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
def load_investment(account_id: int | None) -> pd.DataFrame:
    query = (
        "SELECT id, account_id, platform, investment, investment_amount, investment_date "
        "FROM master_investment"
    )
    params = {}
    if account_id is not None:
        query += " WHERE account_id = :account_id"
        params["account_id"] = account_id
    with get_engine().connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
    df["investment_date"] = pd.to_datetime(df["investment_date"])
    df["investment_amount"] = pd.to_numeric(df["investment_amount"]).fillna(0)
    return df


try:
    semua = load_investment(account_id)
except Exception as e:
    st.error(f"Gagal membaca tabel `master_investment`: {e}")
    st.stop()

# ---------- Header & filter ----------
st.title("🏦 Dashboard Investment")
st.caption(
    "Ringkasan seluruh akun." if is_admin else f"Ringkasan investasi milik {user['name']}."
)

n_bulan = render_filter_periode()
df = terapkan_periode(semua, "investment_date", n_bulan)

if df.empty:
    st.info("Belum ada data investment pada periode ini.")
    st.stop()

# ---------- Card ----------
total_all = df["investment_amount"].sum()
total_darurat = df.loc[df["investment"] == INV_DARURAT, "investment_amount"].sum()
total_wedding = df.loc[df["investment"] == INV_WEDDING, "investment_amount"].sum()
total_other = df.loc[
    ~df["investment"].isin([INV_DARURAT, INV_WEDDING]), "investment_amount"
].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total All Investment", rupiah(total_all), help="SUM investment_amount seluruh investment.")
k2.metric(
    "Total Emergency Fund",
    rupiah(total_darurat),
    help="SUM investment_amount dengan investment = 'Dana Darurat'.",
)
k3.metric(
    "Total Wedding",
    rupiah(total_wedding),
    help="SUM investment_amount dengan investment = 'Wedding'.",
)
k4.metric(
    "Total Other Investment",
    rupiah(total_other),
    help="SUM investment_amount dengan investment selain 'Dana Darurat' dan 'Wedding'.",
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


# ---------- Agregasi bulanan ----------
df["bulan"] = df["investment_date"].dt.to_period("M").dt.to_timestamp()
rentang = pd.date_range(df["bulan"].min(), df["bulan"].max(), freq="MS")
bulanan = (
    df.groupby("bulan")["investment_amount"].sum()
    .reindex(rentang, fill_value=0)
    .rename("Total")
    .to_frame()
)
bulanan["Kumulatif"] = bulanan["Total"].cumsum()

urutan_bulan = [f"{BULAN_SINGKAT[b.month - 1]} {b.year}" for b in bulanan.index]
bulanan.index = urutan_bulan
bulanan.index.name = "bulan"

# ---------- Baris 1: pertumbuhan & kumulatif ----------
c1, c2 = st.columns(2)

with c1:
    fig = px.line(
        bulanan.reset_index(), x="bulan", y="Total", markers=True,
        category_orders={"bulan": urutan_bulan},
        title="Pertumbuhan All Investment per Bulan",
        labels={"bulan": "", "Total": ""},
    )
    fig.update_traces(
        line_color="#3b82f6",
        hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c2:
    fig = px.area(
        bulanan.reset_index(), x="bulan", y="Kumulatif", markers=True,
        category_orders={"bulan": urutan_bulan},
        title="Pertumbuhan Kumulatif All Investment",
        labels={"bulan": "", "Kumulatif": ""},
    )
    fig.update_traces(
        line_color="#a855f7",
        hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

# ---------- Baris 2: donut per platform & bar per investment ----------
c3, c4 = st.columns([2, 3])

with c3:
    per_platform = df.groupby("platform", as_index=False)["investment_amount"].sum()
    fig = px.pie(
        per_platform, names="platform", values="investment_amount", hole=0.5,
        title="Total All Investment berdasarkan Platform",
    )
    fig.update_traces(
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>Rp %{value:,.0f}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c4:
    per_investment = df.groupby("investment", as_index=False)["investment_amount"].sum()
    fig = px.bar(
        per_investment, x="investment_amount", y="investment", orientation="h",
        title="Total All Investment berdasarkan Investment",
        labels={"investment_amount": "", "investment": ""},
    )
    fig.update_traces(
        marker_color="#14b8a6",
        hovertemplate="<b>%{y}</b><br>Rp %{x:,.0f}<extra></extra>",
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_xaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

# ---------- Tabel 10 transaksi terakhir ----------
st.subheader("10 Transaksi Investment Terakhir")
kolom_tabel = ["investment_date", "platform", "investment", "investment_amount"]
if is_admin:
    kolom_tabel.insert(0, "account_id")

terakhir = (
    df.sort_values(["investment_date", "id"], ascending=False).head(10)[kolom_tabel].copy()
)
terakhir["investment_date"] = terakhir["investment_date"].dt.strftime("%d-%m-%Y")
terakhir["investment_amount"] = terakhir["investment_amount"].apply(rupiah)
terakhir = terakhir.rename(
    columns={
        "account_id": "Account ID",
        "investment_date": "Tanggal",
        "platform": "Platform",
        "investment": "Investment",
        "investment_amount": "Nominal",
    }
)
st.dataframe(terakhir, hide_index=True, use_container_width=True)