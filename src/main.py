import streamlit as st

from utils.mlogger import LogConfig, LoggerManager, logger


def setup_logger() -> None:
    """Initialize the logger for the application."""
    log_config = LogConfig(
        level="INFO",
        to_terminal=True,
        to_file=False,
        format_style="simple",
        bind_context={"app": "mod-toolkits"},
    )
    LoggerManager(log_config).setup()
    st.session_state.logger_initialized = True


if "logger_initialized" not in st.session_state:
    setup_logger()
    logger.info(f"Log diinisialisasi: {st.session_state.logger_initialized}")
else:
    logger.debug("Log sudah ter-setup : skipping.")

# --- Init state default ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = "guest"
if "current_page" not in st.session_state:
    st.session_state.current_page = "login"


# --- Login Page ---
def login():
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

        if submitted:
            if username == "admin" and password == "admin":
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.current_page = "login"
                st.success("Login berhasil!")
                st.rerun()
            else:
                st.error("Username atau password salah.")


# --- Logout Page ---
def logout():
    if st.button("Log out"):
        st.session_state.logged_in = False
        st.session_state.username = "guest"
        st.session_state.current_page = "logout"
        st.rerun()


# --- Page Setup ---
login_page = st.Page(login, title="Log in", icon=":material/login:")
logout_page = st.Page(logout, title="Log out", icon=":material/logout:")

dashboard = st.Page(
    "reports/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True
)
voucher = st.Page(
    "reports/voucher/pg_voucher.py", title="Voucher", icon=":material/sell:"
)
reseller = st.Page(
    "reports/reseller/pg_reseller.py", title="Reseller", icon=":material/person_add:"
)


# --- Navigation ---
if st.session_state.logged_in:
    pg = st.navigation({
        "Account": [logout_page],
        "Reports": [dashboard, voucher, reseller],
    })
else:
    pg = st.navigation([login_page])


# --- Tracking Page Transition ---
current_page = getattr(pg, "title", "Unknown Page")
previous_page = st.session_state.get("current_page", "unknown")

# Update state
st.session_state.current_page = current_page

# Bind & log
user = st.session_state.get("username", "guest")
logger_ctx = logger.bind(user=user, navigasi=f"{previous_page} -> {current_page}")
logger_ctx.info("User membuka halaman")

# --- Run Page ---
pg.run()
