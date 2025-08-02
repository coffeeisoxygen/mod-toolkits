"""moudle ini terakit dataframe voucher yang digunakan untuk laporan voucher.

sumber data berasa dari database mssql get > save as df > simpan ke state (agar tidak re run) > berikan fungsi refresh (untuk mengambil data terbaru)
"""

import streamlit as st

from config.database import read_query
from utils.mlogger import logger


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
