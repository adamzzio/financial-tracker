from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import Date, delete, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from utils.auth import can_input_data, render_sidebar, require_login
from utils.db import get_engine, get_table

st.set_page_config(page_title="Input Data Master | FinTrack", page_icon="🗂️", layout="wide")

user = require_login()
render_sidebar(user)

if not can_input_data(user):
    st.error("Akun ini tidak memiliki akses ke halaman input data.")
    st.stop()

TABLE_NAME = "master_category"
DATE_COL = "insert_date"  # diisi otomatis dengan tanggal perubahan

st.title("🗂️ Input Data Master")
st.caption(
    f"Kelola data pada tabel `{TABLE_NAME}`. Ubah sel, tambah baris, atau hapus baris, lalu klik Simpan."
)

# ---------- Load tabel ----------
try:
    tabel = get_table(TABLE_NAME)
    with get_engine().connect() as conn:
        df = pd.read_sql(select(tabel).order_by(*tabel.primary_key.columns), conn)
except Exception as e:
    st.error(f"Gagal membaca tabel `{TABLE_NAME}`: {e}")
    st.stop()

pk_cols = [c.name for c in tabel.primary_key.columns]

if not pk_cols:
    st.warning("Tabel tidak memiliki primary key, jadi hanya bisa ditampilkan (read-only).")
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.stop()


def is_auto(col) -> bool:
    """Kolom terisi otomatis oleh database (serial, identity, default)."""
    return col.server_default is not None or getattr(col, "identity", None) is not None


auto_pk = [c.name for c in tabel.primary_key.columns if is_auto(c)]
has_date_col = DATE_COL in tabel.c
auto_cols = auto_pk + ([DATE_COL] if has_date_col else [])


def to_py(v):
    """Ubah nilai pandas/numpy menjadi tipe Python biasa (NaN menjadi None)."""
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def nilai_insert_date():
    """Waktu perubahan (WIB), disesuaikan dengan tipe kolom insert_date."""
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    tipe = tabel.c[DATE_COL].type
    if isinstance(tipe, Date):
        return now.date()
    return now if getattr(tipe, "timezone", False) else now.replace(tzinfo=None)


# ---------- Info ----------
m1, m2 = st.columns([1, 3])
m1.metric("Jumlah Baris", len(df))
if auto_cols:
    m2.info(f"Kolom {', '.join(auto_cols)} terisi otomatis dan tidak dapat diedit.", icon="ℹ️")

# ---------- Editor ----------
if "master_ver" not in st.session_state:
    st.session_state["master_ver"] = 0

editor_key = f"master_editor_{st.session_state['master_ver']}"

st.data_editor(
    df,
    key=editor_key,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    disabled=auto_cols,
)

state = st.session_state.get(editor_key, {})
edited = state.get("edited_rows", {})
added = [r for r in state.get("added_rows", []) if any(to_py(v) is not None for v in r.values())]
deleted = state.get("deleted_rows", [])
jumlah_perubahan = len(edited) + len(added) + len(deleted)

b1, b2, b3 = st.columns([1, 1, 4])
simpan = b1.button("Simpan", type="primary", disabled=jumlah_perubahan == 0, use_container_width=True)
muat = b2.button("Muat Ulang", use_container_width=True)
b3.caption(
    f"Perubahan belum disimpan: {len(edited)} ubah, {len(added)} tambah, {len(deleted)} hapus"
    if jumlah_perubahan
    else "Tidak ada perubahan."
)

if muat:
    st.session_state["master_ver"] += 1
    st.rerun()

# ---------- Simpan ke database ----------
if simpan:
    try:
        with get_engine().begin() as conn:  # satu transaksi, rollback jika ada error
            # Hapus
            for idx in deleted:
                row = df.iloc[idx]
                kondisi = [tabel.c[k] == to_py(row[k]) for k in pk_cols]
                conn.execute(delete(tabel).where(*kondisi))

            # Ubah
            for idx, perubahan in edited.items():
                if int(idx) in deleted:
                    continue
                row = df.iloc[int(idx)]
                kondisi = [tabel.c[k] == to_py(row[k]) for k in pk_cols]
                nilai = {k: to_py(v) for k, v in perubahan.items() if k not in auto_cols}
                if nilai:
                    if has_date_col:
                        nilai[DATE_COL] = nilai_insert_date()
                    conn.execute(update(tabel).where(*kondisi).values(**nilai))

            # Tambah
            for baris in added:
                nilai = {
                    k: to_py(v)
                    for k, v in baris.items()
                    if k not in auto_cols and to_py(v) is not None
                }
                if has_date_col:
                    nilai[DATE_COL] = nilai_insert_date()
                conn.execute(insert(tabel).values(**nilai))

        st.session_state["master_ver"] += 1
        st.toast("Perubahan berhasil disimpan.", icon="✅")
        st.rerun()

    except IntegrityError as e:
        st.error(
            "Gagal menyimpan: data melanggar constraint database "
            "(contoh: nilai duplikat, kolom wajib kosong, atau baris masih dipakai tabel lain)."
        )
        st.caption(str(e.orig))
    except SQLAlchemyError as e:
        st.error(f"Gagal menyimpan: {e}")