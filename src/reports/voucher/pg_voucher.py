import streamlit as st
from src.config import read_query

from utils.mlogger import logger

st.set_page_config(page_title="Halaman Laporan Voucher", layout="wide")
st.header(
    body="Halaman Laporan Voucher",
    divider=True,
)

if "voucher_data" not in st.session_state:
    logger.warning(
        "Voucher data not found in session state. Please refresh the page to load data."
    )
    st.toast(
        body="Data voucher tidak ditemukan. Silakan refresh halaman untuk memuat data.",
    )


def get_voucherdata() -> None:
    """Get voucher data from database and save to session state."""
    if "voucher_data" not in st.session_state:
        try:
            sql = """
                SELECT * FROM vouchers
                WHERE status = 'active'
            """
            df = read_query(sql)
            st.session_state.voucher_data = df
            logger.info("Voucher data loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load voucher data: {e}")
            st.error("Gagal memuat data voucher.")
    else:
        logger.debug("Voucher data already in session state.")
