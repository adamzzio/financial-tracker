from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from utils.auth import render_sidebar, require_login
from utils.auth import can_input_data, render_sidebar, require_login

st.set_page_config(page_title="Welcome | FinTrack", page_icon="👋", layout="wide")

user = require_login()
render_sidebar(user)

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# Placeholder untuk halaman yang belum dibuat
PLACEHOLDER_URL = "https://www.google.com"
CARD_HEIGHT = 260  # tinggi seragam semua card (px)

# Format: (ikon, judul, deskripsi, path halaman atau None)
FITUR_DASHBOARD = [
    ("📊", "Dashboard Overall", "Ringkasan arus kas dan saldo.", "pages/2_Dashboard_Overall.py"),
    ("💵", "Dashboard Income", "Analisis sumber dan tren pemasukan.", "pages/7_Dashboard_Income.py"),
    ("💸", "Dashboard Expense", "Analisis pola dan kategori belanja.", "pages/8_Dashboard_Expense.py"),
    ("🏦", "Dashboard Investment", "Pantau alokasi dan pertumbuhan portofolio.", "pages/9_Dashboard_Investment.py"),
]

FITUR_INPUT = [
    ("🗂️", "Input Data Master", "Kelola kategori, akun, dan data referensi.", "pages/3_Input_Data_Master.py"),
    ("📝", "Input Data Income", "Catat pemasukan harian dengan cepat.", "pages/4_Input_Data_Income.py"),
    ("🧾", "Input Data Expense", "Catat pengeluaran harian dengan cepat.", "pages/5_Input_Data_Expense.py"),
    ("📈", "Input Data Investment", "Catat pembelian dan penjualan aset investasi.", "pages/6_Input_Data_Investment.py"),
]

st.markdown(
    """
    <style>
        .card-desc {
            min-height: 3.2em;      /* ruang untuk 2 baris, agar tombol selalu sejajar */
            font-size: 0.875rem;
            opacity: 0.6;
            line-height: 1.6;
            margin-bottom: 0.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_greeting(now: datetime) -> str:
    jam = now.hour
    if 4 <= jam < 11:
        return "pagi"
    if 11 <= jam < 15:
        return "siang"
    if 15 <= jam < 18:
        return "sore"
    return "malam"


def format_tanggal(now: datetime) -> str:
    return (
        f"{HARI[now.weekday()]}, {now.day} {BULAN[now.month - 1]} {now.year} "
        f"| {now:%H:%M} WIB"
    )


def render_card_row(items: list[tuple], row_key: str) -> None:
    """Render satu baris card dengan ukuran seragam."""
    cols = st.columns(len(items))
    for col, (ikon, judul, deskripsi, halaman) in zip(cols, items):
        with col:
            with st.container(border=True, height=CARD_HEIGHT):
                st.markdown(f"### {ikon}")
                st.markdown(f"**{judul}**")
                st.markdown(
                    f'<div class="card-desc">{deskripsi}</div>',
                    unsafe_allow_html=True,
                )
                key = f"{row_key}_{judul}"
                if halaman:
                    if st.button("Buka Halaman", key=key, use_container_width=True):
                        st.switch_page(halaman)
                else:
                    st.link_button(
                        "Buka Halaman",
                        url=PLACEHOLDER_URL,
                        use_container_width=True,
                        key=key,
                    )


# Zona waktu WIB
sekarang = datetime.now(ZoneInfo("Asia/Jakarta"))

st.title(f"Selamat {get_greeting(sekarang)}, {user['name']} 👋")
st.caption(format_tanggal(sekarang))

st.markdown(
    "Selamat datang di **FinTrack**. Mulai kelola keuanganmu dengan "
    "mencatat transaksi dan memantau perkembangannya lewat dashboard."
)

st.divider()
st.subheader("Fitur Tersedia")

render_card_row(FITUR_DASHBOARD, row_key="dash")
if can_input_data(user):
    render_card_row(FITUR_INPUT, row_key="input")