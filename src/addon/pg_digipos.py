"""Digipos API Helper Page for Streamlit.

This module provides a Streamlit-based UI for interacting with the Digipos API.
It includes login, OTP verification, profile and balance retrieval, and logout functionality.
Session state is used to persist user credentials and API responses across interactions.

Usage:
    Run this module as part of a Streamlit app to provide a helper interface for Digipos API operations.
"""

from typing import Any

import requests
import streamlit as st

from utils.mlogger import logger

# --- Default (sementara hardcoded) ---
BASEURL = "http://10.0.0.3:10003"
DEFAULTS = {
    "username": "WIR6289504",
    "password": "BDigital90",
    "pin": 123456,
    "msisdn": "081222249504",
}

# --- Init session state default ---
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)
for key in [
    "digipos_login_response",
    "digipos_otp_response",
    "digipos_profile_response",
    "digipos_balance_response",
    "digipos_logout_response",
]:
    st.session_state.setdefault(key, None)


# --- Helper Call API ---
def call_api(
    url: str, method: str = "GET", username: str = "", action: str = ""
) -> dict[str, Any]:
    """Call an API endpoint and return the response as a dictionary.

    Args:
        url (str): The API endpoint URL.
        method (str, optional): HTTP method to use. Defaults to "GET".
        username (str, optional): Username for logging context. Defaults to "".
        action (str, optional): Action name for logging context. Defaults to "".

    Returns:
        dict[str, Any]: The parsed JSON response or error information.
    """
    log_ctx = logger.bind(username=username, action=action)
    log_ctx.info(f"Call API: {url}")
    try:
        resp = requests.request(method, url, timeout=10)
        resp.raise_for_status()
        log_ctx.success(f"API success: {url}")
        return (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {"text": resp.text}
        )
    except Exception as e:
        log_ctx.exception("API error")
        return {"error": str(e)}


# --- UI: Header ---
st.title(":material/api: Digipos API Helper")
st.caption("Helper untuk akses API Digipos secara cepat.")


# --- Fragment: Login ---
@st.fragment
def login_block():
    """Streamlit fragment for Digipos login form and response display.

    Allows the user to input username and password, submit to the API,
    and view the login response.
    """
    st.subheader("1. Login Akun Digipos")
    with st.form("login_form"):
        st.session_state.username = st.text_input(
            "Username", value=st.session_state.username, key="digipos_username_input"
        )
        st.session_state.password = st.text_input(
            "Password",
            type="password",
            value=st.session_state.password,
            key="digipos_password_input",
        )
        submitted = st.form_submit_button("Login")

    if submitted:
        url = f"{BASEURL}/add_account?username={st.session_state.username}&password={st.session_state.password}"
        st.session_state.digipos_login_response = call_api(
            url, username=st.session_state.username or "", action="login"
        )

    if st.session_state.digipos_login_response:
        st.subheader("Response Login")
        st.json(st.session_state.digipos_login_response)


login_block()


# --- Fragment: OTP Verification ---
@st.fragment
def otp_block():
    """Streamlit fragment for Digipos OTP verification.

    Allows the user to input an OTP, submit to the API,
    and view the OTP verification response.
    """
    st.subheader("2. Verifikasi OTP (Jika Diperlukan)")
    with st.form("otp_form"):
        otp = st.text_input("OTP", key="digipos_otp_input")
        submitted = st.form_submit_button("Verifikasi OTP")

    if submitted:
        url = (
            f"{BASEURL}/add_account_otp?username={st.session_state.username}&otp={otp}"
        )
        st.session_state.digipos_otp_response = call_api(
            url, username=st.session_state.username, action="otp"
        )

    if st.session_state.digipos_otp_response:
        st.subheader("Response OTP")
        st.json(st.session_state.digipos_otp_response)


otp_block()


# --- Fragment: Info Akun (Profile / Balance) ---
@st.fragment
def info_block():
    """Streamlit fragment for displaying Digipos account profile and balance.

    Provides buttons to fetch and display profile and balance information
    from the Digipos API.
    """
    st.subheader("3. Info Akun (Profile & Balance)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(":material/person: Profile"):
            url = f"{BASEURL}/profile?username={st.session_state.username}"
            st.session_state.digipos_profile_response = call_api(
                url, username=st.session_state.username, action="profile"
            )
        if st.session_state.digipos_profile_response:
            st.json(st.session_state.digipos_profile_response)

    with col2:
        if st.button(":material/paid: Balance"):
            url = f"{BASEURL}/balance?username={st.session_state.username}"
            st.session_state.digipos_balance_response = call_api(
                url, username=st.session_state.username, action="balance"
            )
        if st.session_state.digipos_balance_response:
            st.json(st.session_state.digipos_balance_response)


info_block()


# --- Fragment: Logout ---
@st.fragment
def logout_block():
    """Streamlit fragment for logging out from Digipos account.

    Provides a button to log out and displays the logout response.
    """
    st.subheader("4. Logout Akun Digipos")
    if st.button(":material/logout: Logout"):
        url = f"{BASEURL}/logout?username={st.session_state.username}"
        st.session_state.digipos_logout_response = call_api(
            url, username=st.session_state.username, action="logout"
        )

    if st.session_state.digipos_logout_response:
        st.json(st.session_state.digipos_logout_response)


logout_block()
