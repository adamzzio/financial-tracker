import streamlit as st
from sqlalchemy import MetaData, Table, create_engine


def _normalize_url(url: str) -> str:
    """Paksa memakai driver psycopg2."""
    for awal in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(awal):
            return "postgresql+psycopg2://" + url[len(awal):]
    return url


@st.cache_resource
def get_engine():
    url = _normalize_url(st.secrets["auth"]["db"]["connection"])
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)


@st.cache_resource
def get_table(nama: str, schema: str | None = None) -> Table:
    """Reflect struktur tabel langsung dari database."""
    return Table(nama, MetaData(), autoload_with=get_engine(), schema=schema)