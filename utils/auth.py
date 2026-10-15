import hmac
import streamlit as st

MAX_ATTEMPTS = 5
SESSION_KEY = "auth_user"

# ---------- Secrets ----------
def _get_users() -> dict:
    try:
        return dict(st.secrets["users"])
    except (KeyError, FileNotFoundError):
        return {}


# ---------- Autentikasi ----------
def authenticate(username: str, password: str) -> dict | None:
    """Kembalikan dict {'username', 'name', 'role'} jika valid, selain itu None."""
    username = username.strip().lower()
    user = _get_users().get(username)

    # Tetap lakukan perbandingan walau user tidak ada, agar waktu respons seragam
    stored = str(user["password"]) if user else ""
    is_valid = hmac.compare_digest(password.encode(), stored.encode())

    if user and is_valid:
        return {
            "username": username,
            "name": user["name"],
            "role": user.get("role", "user"),
        }
    return None


def has_role(user: dict, *roles: str) -> bool:
    return user.get("role", "user") in roles


def can_input_data(user: dict) -> bool:
    """Admin tidak memiliki akses fitur input data."""
    return not has_role(user, "admin")


def is_locked() -> bool:
    return st.session_state.get("failed_attempts", 0) >= MAX_ATTEMPTS


def register_failed_attempt() -> int:
    st.session_state["failed_attempts"] = st.session_state.get("failed_attempts", 0) + 1
    return MAX_ATTEMPTS - st.session_state["failed_attempts"]


def login(user: dict) -> None:
    st.session_state[SESSION_KEY] = user
    st.session_state["failed_attempts"] = 0


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)


def current_user() -> dict | None:
    return st.session_state.get(SESSION_KEY)


def require_login() -> dict:
    """Panggil di baris awal setiap halaman yang butuh login."""
    user = current_user()
    if user is None:
        st.rerun()
        st.stop()
    return user


def render_sidebar(user: dict) -> None:
    """Sidebar standar untuk halaman setelah login."""
    with st.sidebar:
        st.markdown(f"**{user['name']}**")
        st.caption(f"@{user['username']}")
        if st.button("Keluar", use_container_width=True):
            logout()
            st.rerun()

# Mapping username ke account_id di database
ACCOUNT_IDS = {"adam": 1, "atikah": 2, "admin": 3}

def get_account_id(user: dict) -> int | None:
    return ACCOUNT_IDS.get(user["username"])