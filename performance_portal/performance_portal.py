# --- IMPORTS ---
import os
import json
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
import pandas as pd
import plotly.express as px

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (PerformancePortal) %(message)s')

# --- SECRETS & API CONNECTION (Cloud Version) ---
# This version reads secrets from Streamlit's secrets manager instead of a local file.
try:
    API_KEY = st.secrets["alpaca"]["api_key"]
    API_SECRET = st.secrets["alpaca"]["secret_key"]
    BASE_URL = st.secrets["alpaca"].get("base_url", "https://paper-api.alpaca.markets")
    TOTAL_PORTFOLIO_CASH = float(st.secrets["account"]["total_portfolio_cash"])
    
    api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')
    logging.info("✅ Alpaca API connection successful.")
except Exception as e:
    st.error("FATAL: Could not connect to Alpaca API. Have you set your secrets in the Streamlit dashboard?")
    st.stop() # Stops the script from running further if secrets are missing

# --- HELPER FUNCTIONS ---
@st.cache_data(ttl=300) # Cache data for 5 minutes
def get_account_data():
    """Fetches account info, positions, and recent orders."""
    try:
        account = api.get_account()
        positions = api.list_positions()
        orders = api.list_orders(status='closed', limit=100, direction='desc')
        return account, positions, orders
    except APIError as e:
        st.error(f"Error fetching data from Alpaca: {e}")
        return None, [], []

@st.cache_data(ttl=3600) # Cache portfolio history for 1 hour
def get_portfolio_history():
    """Fetches portfolio history for the last 30 days."""
    try:
        history = api.get_portfolio_history(period='1M', timeframe='1D')
        df = pd.DataFrame({
            'timestamp': history.timestamp,
            'equity': history.equity,
            'profit_loss': history.profit_loss,
            'profit_loss_pct': history.profit_loss_pct
        })
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        return df
    except APIError as e:
        st.error(f"Error fetching portfolio history: {e}")
        return pd.DataFrame()

# --- STREAMLIT DASHBOARD LAYOUT ---
st.set_page_config(page_title="Alpaca Trading Performance", layout="wide")

st.title("📈 Alpaca Trading Performance Overview")

# --- AUTO-REFRESH ---
if st.button("Refresh Data"):
    st.cache_data.clear()

account, positions, orders = get_account_data()
history_df = get_portfolio_history()

if account:
    # --- KEY METRICS ---
    st.header("Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Value", f"${float(account.portfolio_value):,.2f}")
    col2.metric("Cash Balance", f"${float(account.cash):,.2f}")
    col3.metric("Today's P/L", f"${float(account.equity) - float(account.last_equity):,.2f}")
    col4.metric("Total P/L", f"${float(account.equity) - TOTAL_PORTFOLIO_CASH:,.2f}")

    # --- PORTFOLIO HISTORY CHART ---
    st.header("Portfolio Value Over Time (30 Days)")
    if not history_df.empty:
        fig = px.line(history_df, x='timestamp', y='equity', title='Portfolio Equity Over Time', labels={'equity': 'Portfolio Value ($)', 'timestamp': 'Date'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Could not load portfolio history chart.")

    # --- CURRENT POSITIONS ---
    st.header("Current Open Positions")
    if positions:
        positions_data = []
        for p in positions:
            positions_data.append({
                "Symbol": p.symbol,
                "Qty": float(p.qty),
                "Side": p.side.title(),
                "Market Value": f"${float(p.market_value):,.2f}",
                "Cost Basis": f"${float(p.cost_basis):,.2f}",
                "Unrealized P/L": f"${float(p.unrealized_pl):,.2f}",
                "Unrealized P/L (%)": f"{float(p.unrealized_plpc) * 100:.2f}%"
            })
        st.dataframe(pd.DataFrame(positions_data), use_container_width=True)
    else:
        st.info("No open positions.")

    # --- RECENT TRADES ---
    st.header("Recent Closed Orders (Last 100)")
    if orders:
        orders_data = []
        for o in orders:
            orders_data.append({
                "Symbol": o.symbol,
                "Qty": float(o.filled_qty),
                "Side": o.side.title(),
                "Type": o.order_type.title(),
                "Avg. Fill Price": f"${float(o.filled_avg_price):,.2f}",
                "Status": o.status.title(),
                "Filled At": pd.to_datetime(o.filled_at).strftime('%Y-%m-%d %H:%M:%S')
            })
        st.dataframe(pd.DataFrame(orders_data), use_container_width=True)
    else:
        st.info("No recent closed orders found.")

else:
    st.error("Could not connect to Alpaca to fetch account data.")