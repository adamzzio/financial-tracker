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
TARGET_DARURAT = 30_000_000
TARGET_WEDDING = 20_000_000

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


@st.cache_data(ttl=60, show_spinner=False)
def load_outvestment(account_id: int | None) -> pd.DataFrame:
    query = (
        "SELECT id, account_id, platform, outvestment, outvestment_amount, outvestment_date "
        "FROM master_outvestment"
    )
    params = {}
    if account_id is not None:
        query += " WHERE account_id = :account_id"
        params["account_id"] = account_id
    with get_engine().connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
    df["outvestment_date"] = pd.to_datetime(df["outvestment_date"])
    df["outvestment_amount"] = pd.to_numeric(df["outvestment_amount"]).fillna(0)
    return df


try:
    semua_inv = load_investment(account_id)
    semua_out = load_outvestment(account_id)
except Exception as e:
    st.error(f"Gagal membaca tabel `master_investment` atau `master_outvestment`: {e}")
    st.stop()

# ---------- Header & filter ----------
st.title("🏦 Dashboard Investment")
st.caption(
    "Ringkasan seluruh akun." if is_admin else f"Ringkasan investasi milik {user['name']}."
)

n_bulan = render_filter_periode()
df = terapkan_periode(semua_inv, "investment_date", n_bulan)
df_out = terapkan_periode(semua_out, "outvestment_date", n_bulan)


# ---------- Tabel 10 transaksi terakhir ----------
def tampil_riwayat() -> None:
    """10 transaksi terakhir: gabungan master_investment dan master_outvestment (UNION ALL)."""
    st.subheader("10 Transaksi Investment Terakhir")

    kolom = ["account_id", "Flow", "platform", "Category", "Amount", "Date"]

    inv = df.rename(
        columns={
            "investment": "Category",
            "investment_amount": "Amount",
            "investment_date": "Date",
        }
    ).assign(Flow="Investment")

    out = df_out.rename(
        columns={
            "outvestment": "Category",
            "outvestment_amount": "Amount",
            "outvestment_date": "Date",
        }
    ).assign(Flow="Outvestment")

    # UNION ALL kedua tabel
    bagian = [x[["id"] + kolom] for x in (inv, out) if not x.empty]
    if not bagian:
        st.caption("Belum ada data.")
        return
    gabungan = pd.concat(bagian, ignore_index=True)

    # Sort Date DESCENDING (id sebagai pemisah jika tanggal sama)
    tabel = gabungan.sort_values(["Date", "id"], ascending=False).head(10).copy()
    tabel["Date"] = tabel["Date"].dt.strftime("%d-%m-%Y")
    tabel["Amount"] = tabel["Amount"].apply(rupiah)

    tampil = ["Flow", "platform", "Category", "Amount", "Date"]
    if is_admin:
        tampil.insert(0, "account_id")
    tabel = tabel[tampil].rename(columns={"account_id": "Account ID", "platform": "Platform"})
    st.dataframe(tabel, hide_index=True, use_container_width=True)


if df.empty and df_out.empty:
    st.info("Belum ada data investment pada periode ini.")
    st.stop()

# ---------- Agregasi card ----------
total_all = df["investment_amount"].sum()
total_darurat = df.loc[df["investment"] == INV_DARURAT, "investment_amount"].sum()
total_wedding = df.loc[df["investment"] == INV_WEDDING, "investment_amount"].sum()
total_other = df.loc[
    ~df["investment"].isin([INV_DARURAT, INV_WEDDING]), "investment_amount"
].sum()

total_out = df_out["outvestment_amount"].sum()
total_sisa = total_all - total_out
usage_rate = f"{total_out / total_all * 100:.1f}%" if total_all else "N/A"


def tampil_target(nilai: float, target: int) -> None:
    """Progress bar capaian terhadap target (bar maksimal 100%, teks tetap menampilkan nilai asli)."""
    pct = nilai / target * 100
    st.progress(min(pct / 100, 1.0), text=f"{pct:.1f}% dari target {rupiah(target)}")


# ---------- Row 1: card investment ----------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total All Investment", rupiah(total_all), help="SUM investment_amount seluruh investment.")

with k2:
    st.metric(
        "Total Emergency Fund",
        rupiah(total_darurat),
        help=f"SUM investment_amount dengan investment = '{INV_DARURAT}'. "
        f"Target: {rupiah(TARGET_DARURAT)}.",
    )
    tampil_target(total_darurat, TARGET_DARURAT)

with k3:
    st.metric(
        "Total Wedding",
        rupiah(total_wedding),
        help=f"SUM investment_amount dengan investment = '{INV_WEDDING}'. "
        f"Target: {rupiah(TARGET_WEDDING)}.",
    )
    tampil_target(total_wedding, TARGET_WEDDING)

k4.metric(
    "Total Other Investment",
    rupiah(total_other),
    help=f"SUM investment_amount dengan investment selain '{INV_DARURAT}' dan '{INV_WEDDING}'.",
)

# ---------- Row 2: card outvestment ----------
o1, o2, o3, _ = st.columns(4)
o1.metric(
    "Total Outvestment",
    rupiah(total_out),
    help="SUM outvestment_amount pada master_outvestment.",
)
o2.metric(
    "Total Remaining Investment",
    rupiah(total_sisa),
    help="Total All Investment dikurangi Total Outvestment.",
)
o3.metric(
    "Investment Usage Rate",
    usage_rate,
    help="Persentase investasi yang sudah digunakan: Total Outvestment / Total All Investment x 100.",
)

st.divider()

if df.empty:
    st.info("Belum ada data investment pada periode ini, sehingga chart tidak ditampilkan.")
    tampil_riwayat()
    st.stop()


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
tampil_riwayat()