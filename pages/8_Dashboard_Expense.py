from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from utils.auth import get_account_id, has_role, render_sidebar, require_login
from utils.db import get_engine
from utils.formatting import BULAN_SINGKAT, rupiah

st.set_page_config(page_title="Dashboard Expense | FinTrack", page_icon="💸", layout="wide")

user = require_login()
render_sidebar(user)

KELOMPOK = ["Foods", "Living", "Other"]
WARNA = {"Foods": "#f97316", "Living": "#8b5cf6", "Other": "#64748b"}
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
def load_expense(account_id: int | None) -> pd.DataFrame:
    query = (
        "SELECT id, account_id, category, subcategory, expense_amount, expense_date "
        "FROM master_expense"
    )
    params = {}
    if account_id is not None:
        query += " WHERE account_id = :account_id"
        params["account_id"] = account_id
    with get_engine().connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
    df["expense_date"] = pd.to_datetime(df["expense_date"])
    df["expense_amount"] = pd.to_numeric(df["expense_amount"]).fillna(0)
    return df


try:
    semua = load_expense(account_id)
except Exception as e:
    st.error(f"Gagal membaca tabel `master_expense`: {e}")
    st.stop()

# ---------- Header & filter ----------
st.title("💸 Dashboard Expense")
st.caption(
    "Ringkasan seluruh akun." if is_admin else f"Ringkasan pengeluaran milik {user['name']}."
)

kol_filter, _ = st.columns([1, 3])
pilihan = kol_filter.selectbox(
    "Periode",
    list(PERIODE),
    index=0,
    help="Periode dihitung mundur dari hari ini, contoh: 3 Bulan Terakhir = 3 bulan ke belakang.",
)
n_bulan = PERIODE[pilihan]

hari_ini = pd.Timestamp(datetime.now(ZoneInfo("Asia/Jakarta")).date())
df = semua.copy()
if n_bulan:
    df = df[df["expense_date"] >= hari_ini - pd.DateOffset(months=n_bulan)]

if df.empty:
    st.info("Belum ada data expense pada periode ini.")
    st.stop()

# Kelompok: Foods, Living, Other (kategori selain Foods dan Living)
df["kelompok"] = df["category"].where(df["category"].isin(["Foods", "Living"]), "Other")

# ---------- Card ----------
total_all = df["expense_amount"].sum()
total_foods = df.loc[df["kelompok"] == "Foods", "expense_amount"].sum()
total_living = df.loc[df["kelompok"] == "Living", "expense_amount"].sum()
total_other = df.loc[df["kelompok"] == "Other", "expense_amount"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total All Expense", rupiah(total_all), help="SUM expense_amount seluruh kategori.")
k2.metric("Total Foods Expense", rupiah(total_foods), help="SUM expense_amount dengan category = 'Foods'.")
k3.metric("Total Living Expense", rupiah(total_living), help="SUM expense_amount dengan category = 'Living'.")
k4.metric(
    "Total Other Expense",
    rupiah(total_other),
    help="SUM expense_amount dengan category selain 'Foods' dan 'Living'.",
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
    """Bar chart horizontal: SUM expense_amount per kolom, urut terbesar di atas."""
    if data.empty:
        st.subheader(judul)
        st.caption("Belum ada data.")
        return
    agg = data.groupby(kolom, as_index=False)["expense_amount"].sum()
    fig = px.bar(
        agg, x="expense_amount", y=kolom, orientation="h", title=judul,
        labels={"expense_amount": "", kolom: ""},
    )
    fig.update_traces(
        marker_color=warna,
        hovertemplate="<b>%{y}</b><br>Rp %{x:,.0f}<extra></extra>",
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_xaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)


def bar_horizontal_warna(data: pd.DataFrame, kolom: str, judul: str):
    """Bar horizontal bertumpuk: warna berdasarkan kelompok (Foods atau Living)."""
    if data.empty:
        st.subheader(judul)
        st.caption("Belum ada data.")
        return
    agg = data.groupby([kolom, "kelompok"], as_index=False)["expense_amount"].sum()
    fig = px.bar(
        agg, x="expense_amount", y=kolom, color="kelompok", orientation="h",
        color_discrete_map=WARNA, category_orders={"kelompok": KELOMPOK},
        title=judul, labels={"expense_amount": "", kolom: ""},
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>%{fullData.name}<br>Rp %{x:,.0f}<extra></extra>"
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_xaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)


# ---------- Agregasi bulanan ----------
df["bulan"] = df["expense_date"].dt.to_period("M").dt.to_timestamp()
rentang = pd.date_range(df["bulan"].min(), df["bulan"].max(), freq="MS")
bulanan = (
    df.pivot_table(index="bulan", columns="kelompok", values="expense_amount",
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
        title="Foods, Living, dan Other Expense per Bulan",
        labels={"bulan": "", "nominal": ""},
    )
    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Rp %{y:,.0f}<extra></extra>"
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c2:
    komposisi = df.groupby("kelompok", as_index=False)["expense_amount"].sum()
    fig = px.pie(
        komposisi, names="kelompok", values="expense_amount", hole=0.5,
        color="kelompok", color_discrete_map=WARNA,
        category_orders={"kelompok": KELOMPOK},
        title="Komposisi Expense",
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
        title="Pertumbuhan All Expense per Bulan",
        labels={"bulan": "", "Total": ""},
    )
    fig.update_traces(
        line_color="#ef4444",
        hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c4:
    fig = px.area(
        bulanan.reset_index(), x="bulan", y="Kumulatif", markers=True,
        category_orders={"bulan": urutan_bulan},
        title="Pertumbuhan Kumulatif All Expense",
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
    bar_horizontal(df, "category", "Total All Expense berdasarkan Category", "#ef4444")
with c6:
    bar_horizontal(df, "subcategory", "Total All Expense berdasarkan Subcategory", "#f43f5e")

# ---------- Baris 4: Living + Foods & Other per subcategory ----------
c7, c8 = st.columns(2)
with c7:
    bar_horizontal_warna(
        df[df["kelompok"].isin(["Foods", "Living"])], "subcategory",
        "Total Living dan Foods Expense berdasarkan Subcategory",
    )
with c8:
    bar_horizontal(
        df[df["kelompok"] == "Other"], "subcategory",
        "Total Other Expense berdasarkan Subcategory", WARNA["Other"],
    )

# ---------- Tabel 10 transaksi terakhir ----------
st.subheader("10 Transaksi Expense Terakhir")
kolom_tabel = ["expense_date", "category", "subcategory", "expense_amount"]
if is_admin:
    kolom_tabel.insert(0, "account_id")

terakhir = (
    df.sort_values(["expense_date", "id"], ascending=False).head(10)[kolom_tabel].copy()
)
terakhir["expense_date"] = terakhir["expense_date"].dt.strftime("%d-%m-%Y")
terakhir["expense_amount"] = terakhir["expense_amount"].apply(rupiah)
terakhir = terakhir.rename(
    columns={
        "account_id": "Account ID",
        "expense_date": "Tanggal",
        "category": "Category",
        "subcategory": "Subcategory",
        "expense_amount": "Nominal",
    }
)
st.dataframe(terakhir, hide_index=True, use_container_width=True)