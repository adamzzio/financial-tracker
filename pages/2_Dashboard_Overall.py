from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from utils.auth import get_account_id, has_role, render_sidebar, require_login
from utils.db import get_engine
from utils.formatting import BULAN_SINGKAT, rupiah

st.set_page_config(page_title="Dashboard Overall | FinTrack", page_icon="📊", layout="wide")

user = require_login()
render_sidebar(user)

TIPE = ["Income", "Expense", "Investment"]
WARNA = {"Income": "#22c55e", "Expense": "#ef4444", "Investment": "#3b82f6"}
WARNA_ALOKASI = {"Expense": "#ef4444", "Investment": "#3b82f6", "Sisa Kas": "#a855f7"}
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
def load_transaksi(account_id: int | None) -> pd.DataFrame:
    """Gabungan income, expense, dan investment dalam satu format."""
    query = """
        SELECT * FROM (
            SELECT 'Income' AS tipe, id, account_id, category AS kategori,
                   subcategory AS subkategori, income_amount AS nominal, income_date AS tanggal
            FROM master_income
            UNION ALL
            SELECT 'Expense', id, account_id, category, subcategory, expense_amount, expense_date
            FROM master_expense
            UNION ALL
            SELECT 'Investment', id, account_id, platform, investment, investment_amount, investment_date
            FROM master_investment
        ) t
    """
    params = {}
    if account_id is not None:
        query += " WHERE account_id = :account_id"
        params["account_id"] = account_id
    with get_engine().connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["nominal"] = pd.to_numeric(df["nominal"]).fillna(0)
    return df


try:
    semua = load_transaksi(account_id)
except Exception as e:
    st.error(f"Gagal membaca data transaksi: {e}")
    st.stop()

# ---------- Header & filter ----------
st.title("📊 Dashboard Overall")
st.caption(
    "Ringkasan seluruh akun." if is_admin else f"Ringkasan keuangan milik {user['name']}."
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
    df = df[df["tanggal"] >= hari_ini - pd.DateOffset(months=n_bulan)]

if df.empty:
    st.info("Belum ada data transaksi pada periode ini.")
    st.stop()

# ---------- Agregasi ----------
total = df.groupby("tipe")["nominal"].sum().reindex(TIPE, fill_value=0)
income, expense, investasi = total["Income"], total["Expense"], total["Investment"]
sisa_kas = income - expense - investasi


def persen(bagian: float, dasar: float) -> str:
    return f"{bagian / dasar * 100:.1f}%" if dasar else "N/A"


def persen_id(nilai: float) -> str:
    """Format persen gaya Indonesia, contoh: 44,0%"""
    return f"{nilai:.1f}".replace(".", ",") + "%"


# ---------- Row 1: card nominal ----------
r1a, r1b, r1c = st.columns(3)
r1a.metric("Total All Income", rupiah(income), help="SUM income_amount pada master_income.")
r1b.metric("Total All Expense", rupiah(expense), help="SUM expense_amount pada master_expense.")
r1c.metric("Total All Investment", rupiah(investasi), help="SUM investment_amount pada master_investment.")

# ---------- Row 2: card persentase ----------
r2a, r2b, r2c, r2d = st.columns(4)
r2a.metric(
    "Investment Rate",
    persen(investasi, income),
    help="Persentase investment_amount terhadap income_amount: Total Investment / Total Income x 100.",
)
r2b.metric(
    "Expense Rate",
    persen(expense, income),
    help="Persentase expense_amount terhadap income_amount: Total Expense / Total Income x 100.",
)
r2c.metric(
    "Saving Rate",
    persen(income - expense, income),
    help="Persentase income yang tidak dibelanjakan: (Income - Expense) / Income x 100. "
    "Investasi dihitung sebagai tabungan, bukan pengurang.",
)
r2d.metric(
    "Net Cash Flow Rate",
    persen(sisa_kas, income),
    help="Persentase sisa kas setelah expense dan investasi: (Income - Expense - Investment) / Income x 100. "
    "Bernilai negatif jika pengeluaran dan investasi melebihi income tercatat.",
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
df["bulan"] = df["tanggal"].dt.to_period("M").dt.to_timestamp()
rentang = pd.date_range(df["bulan"].min(), df["bulan"].max(), freq="MS")
bulanan = (
    df.pivot_table(index="bulan", columns="tipe", values="nominal",
                   aggfunc="sum", fill_value=0)
    .reindex(rentang, fill_value=0)
    .reindex(columns=TIPE, fill_value=0)
)
bulanan["Saldo Bersih"] = bulanan["Income"] - bulanan["Expense"] - bulanan["Investment"]

inc_valid = bulanan["Income"].replace(0, np.nan)
bulanan["Expense Rate"] = bulanan["Expense"] / inc_valid * 100
bulanan["Investment Rate"] = bulanan["Investment"] / inc_valid * 100
bulanan["Saving Rate"] = (bulanan["Income"] - bulanan["Expense"]) / inc_valid * 100
bulanan["Net Cash Flow Rate"] = bulanan["Saldo Bersih"] / inc_valid * 100

urutan_bulan = [f"{BULAN_SINGKAT[b.month - 1]} {b.year}" for b in bulanan.index]
bulanan.index = urutan_bulan
bulanan.index.name = "bulan"

# ---------- Baris 1: bar per bulan & donut alokasi ----------
c1, c2 = st.columns([3, 2])

with c1:
    long = bulanan[TIPE].reset_index().melt(
        id_vars="bulan", var_name="tipe", value_name="nominal"
    )
    fig = px.bar(
        long, x="bulan", y="nominal", color="tipe", barmode="group",
        color_discrete_map=WARNA,
        category_orders={"bulan": urutan_bulan, "tipe": TIPE},
        title="Income, Expense, dan Investment per Bulan",
        labels={"bulan": "", "nominal": ""},
    )
    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Rp %{y:,.0f}<extra></extra>"
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c2:
    alokasi = pd.DataFrame(
        {
            "komponen": ["Expense", "Investment", "Sisa Kas"],
            "nominal": [expense, investasi, max(sisa_kas, 0)],
        }
    )
    fig = px.pie(
        alokasi, names="komponen", values="nominal", hole=0.5,
        color="komponen", color_discrete_map=WARNA_ALOKASI,
        category_orders={"komponen": list(WARNA_ALOKASI)},
        title="Alokasi Income",
    )
    fig.update_traces(
        textinfo="percent",
        sort=False,
        hovertemplate="<b>%{label}</b><br>Rp %{value:,.0f}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(rapikan(fig), use_container_width=True)
    if sisa_kas < 0:
        st.caption("Expense dan Investment melebihi Income, sehingga Sisa Kas tidak ditampilkan.")

# ---------- Baris 2: saldo bersih & heatmap proporsi ----------
c3, c4 = st.columns(2)

with c3:
    fig = px.line(
        bulanan.reset_index(), x="bulan", y="Saldo Bersih", markers=True,
        category_orders={"bulan": urutan_bulan},
        title="Saldo Bersih per Bulan (Income - Expense - Investment)",
        labels={"bulan": "", "Saldo Bersih": ""},
    )
    fig.update_traces(
        line_color="#0ea5e9",
        hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c4:
    # Heatmap proporsi (treemap): luas tile sebanding dengan nominal
    prop = pd.DataFrame(
        {"tipe": ["Income", "Investment", "Expense"], "nominal": [income, investasi, expense]}
    )
    prop = prop[prop["nominal"] > 0].reset_index(drop=True)
    total_prop = prop["nominal"].sum()

    if prop.empty:
        st.subheader("Proporsi Income, Investment, dan Expense")
        st.caption("Belum ada data.")
    else:
        prop["persen"] = prop["nominal"] / total_prop * 100
        prop["label_teks"] = [
            f"{persen_id(p)}<br>{rupiah(n)}" for p, n in zip(prop["persen"], prop["nominal"])
        ]
        prop["vs_income"] = [
            f"{persen_id(n / income * 100)} dari Income" if income else "N/A"
            for n in prop["nominal"]
        ]

        fig = go.Figure(
            go.Treemap(
                labels=prop["tipe"],
                parents=[""] * len(prop),
                values=prop["nominal"],
                text=prop["label_teks"],
                textinfo="label+text",
                textposition="middle center",
                textfont=dict(size=20, color="white"),
                marker=dict(
                    colors=[WARNA[t] for t in prop["tipe"]],
                    line=dict(width=3, color="#0e1117"),
                ),
                customdata=np.column_stack([prop["nominal"], prop["persen"], prop["vs_income"]]),
                hovertemplate=(
                    "<b>%{label}</b><br>Rp %{customdata[0]:,.0f}"
                    "<br>%{customdata[1]:.1f}% dari total"
                    "<br>%{customdata[2]}<extra></extra>"
                ),
                tiling=dict(pad=0),
            )
        )
        fig.update_layout(title="Proporsi Income, Investment, dan Expense")
        st.plotly_chart(rapikan(fig), use_container_width=True)
        st.caption("Persentase dihitung terhadap total Income + Investment + Expense.")

# ---------- Baris 3: rate per bulan & top expense category ----------
c5, c6 = st.columns(2)

with c5:
    kolom_rate = ["Expense Rate", "Investment Rate", "Saving Rate", "Net Cash Flow Rate"]
    rate = bulanan[kolom_rate].reset_index().melt(
        id_vars="bulan", var_name="rate", value_name="persen"
    )
    fig = px.line(
        rate, x="bulan", y="persen", color="rate", markers=True,
        color_discrete_map={
            "Expense Rate": WARNA["Expense"],
            "Investment Rate": WARNA["Investment"],
            "Saving Rate": WARNA["Income"],
            "Net Cash Flow Rate": WARNA_ALOKASI["Sisa Kas"],
        },
        category_orders={"bulan": urutan_bulan, "rate": kolom_rate},
        title="Rate terhadap Income per Bulan",
        labels={"bulan": "", "persen": ""},
    )
    fig.update_traces(
        connectgaps=True,
        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>%{y:.1f}%<extra></extra>",
    )
    fig.update_yaxes(ticksuffix="%")
    st.plotly_chart(rapikan(fig), use_container_width=True)

with c6:
    top_exp = (
        df[df["tipe"] == "Expense"]
        .groupby("kategori", as_index=False)["nominal"].sum()
        .nlargest(10, "nominal")
    )
    if top_exp.empty:
        st.subheader("10 Category Expense Terbesar")
        st.caption("Belum ada data.")
    else:
        fig = px.bar(
            top_exp, x="nominal", y="kategori", orientation="h",
            title="10 Category Expense Terbesar",
            labels={"nominal": "", "kategori": ""},
        )
        fig.update_traces(
            marker_color=WARNA["Expense"],
            hovertemplate="<b>%{y}</b><br>Rp %{x:,.0f}<extra></extra>",
        )
        fig.update_yaxes(categoryorder="total ascending")
        fig.update_xaxes(tickprefix="Rp ", tickformat=",.0f")
        st.plotly_chart(rapikan(fig), use_container_width=True)

# ---------- Tabel 20 transaksi terakhir ----------
st.subheader("20 Transaksi Terakhir")
kolom_tabel = ["tanggal", "tipe", "kategori", "subkategori", "nominal"]
if is_admin:
    kolom_tabel.insert(0, "account_id")

terakhir = df.sort_values(["tanggal", "id"], ascending=False).head(20)[kolom_tabel].copy()
terakhir["tanggal"] = terakhir["tanggal"].dt.strftime("%d-%m-%Y")
terakhir["nominal"] = terakhir["nominal"].apply(rupiah)
terakhir = terakhir.rename(
    columns={
        "account_id": "Account ID",
        "tanggal": "Tanggal",
        "tipe": "Tipe",
        "kategori": "Kategori / Platform",
        "subkategori": "Subkategori / Investment",
        "nominal": "Nominal",
    }
)
st.dataframe(terakhir, hide_index=True, use_container_width=True)