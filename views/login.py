import streamlit as st

from utils.auth import (
    MAX_ATTEMPTS,
    authenticate,
    is_locked,
    login,
    register_failed_attempt,
)

st.set_page_config(
    page_title="FinTrack | Financial Planner",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none;}
        .hero-title {text-align:center; font-size:2.6rem; font-weight:800; margin-bottom:0;}
        .hero-sub {text-align:center; color:#6b7280; margin-bottom:1.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="hero-title">💰 FinTrack</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-sub">Rencanakan, catat, dan pantau keuanganmu dalam satu tempat.</p>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
col1.metric("Catat", "Transaksi")
col2.metric("Pantau", "Dashboard")
col3.metric("Rencanakan", "Investasi")

st.divider()

with st.container(border=True):
    st.subheader("Masuk ke Akun")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="contoh: adam")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button(
            "Masuk", use_container_width=True, type="primary"
        )

    if submitted:
        if is_locked():
            st.error(
                f"Terlalu banyak percobaan gagal ({MAX_ATTEMPTS}x). "
                "Muat ulang halaman untuk mencoba kembali."
            )
        elif not username or not password:
            st.warning("Username dan password wajib diisi.")
        else:
            user = authenticate(username, password)
            if user:
                login(user)
                st.rerun()
            else:
                sisa = register_failed_attempt()
                st.error(f"Username atau password salah. Sisa percobaan: {sisa}")

st.caption("Aplikasi ini masih dalam tahap pengembangan awal.")