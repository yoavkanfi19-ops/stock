import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import time

st.set_page_config(page_title="Financial Deep-Dive Pro", layout="wide")

def get_stock_data(symbol):
    filename = f"{symbol}.json"
    if os.path.exists(filename) and (time.time() - os.path.getmtime(filename) < 3600):
        with open(filename, 'r') as f:
            return json.load(f)
    ticker = yf.Ticker(symbol)
    data = ticker.info
    with open(filename, 'w') as f:
        json.dump(data, f)
    return data

def safe_div(a, b):
    return (a / b) if b and b is not None and b != 0 else 0

st.title("🛡️ Financial Deep-Dive Pro (Buffett Edition)")
symbol = st.sidebar.text_input("סימול מניה:", "NVDA").upper()

if 'data' not in st.session_state:
    st.session_state.data = None

if st.sidebar.button("הפק דוח ניתוח"):
    st.session_state.data = get_stock_data(symbol)

if st.session_state.data:
    data = st.session_state.data
    
    st.header(f"ניתוח עבור {data.get('longName', symbol)}")
    
    # חישוב נתונים בטוח - מנסה למשוך מה-API, אם אין נתון משתמש ב-0
    gp = data.get('grossProfit') or 0
    rev = data.get('totalRevenue') or 1
    sga = data.get('sellingGeneralAdministrative') or 0
    rd = data.get('researchDevelopment') or 0
    op_inc = data.get('operatingIncome') or 1
    int_exp = data.get('interestExpense') or 0
    pretax = data.get('pretaxIncome') or 1
    tax = data.get('taxProvision') or 0
    
    st.subheader("📊 ניתוח 12 החוקים (באפטולוגיה)")
    
    rules = [
        {"חוק": "רווח גולמי > 40%", "מצב": "✅" if safe_div(gp, rev) > 0.4 else "❌", "נתון": f"{safe_div(gp, rev)*100:.1f}%"},
        {"חוק": "הנהלה/גולמי < 30%", "מצב": "✅" if safe_div(sga, gp) < 0.3 else "❌", "נתון": f"{safe_div(sga, gp)*100:.1f}%"},
        {"חוק": "מו\"פ/גולמי < 30%", "מצב": "✅" if safe_div(rd, gp) < 0.3 else "❌", "נתון": f"{safe_div(rd, gp)*100:.1f}%"},
        {"חוק": "ריבית/רווח תפעולי < 15%", "מצב": "✅" if safe_div(int_exp, op_inc) < 0.15 else "❌", "נתון": f"{safe_div(int_exp, op_inc)*100:.1f}%"},
        {"חוק": "מס/לפני מס ~ 20%", "מצב": "✅" if safe_div(tax, pretax) > 0.15 else "❌", "נתון": f"{safe_div(tax, pretax)*100:.1f}%"},
        {"חוק": "רווח נקי/הכנסות > 20%", "מצב": "✅" if data.get('profitMargins', 0) > 0.2 else "❌", "נתון": f"{data.get('profitMargins', 0)*100:.1f}%"},
        {"חוק": "מזומן > חוב", "מצב": "✅" if data.get('totalCash', 0) > data.get('totalDebt', 0) else "❌", "נתון": f"{data.get('totalCash', 0)/1e9:.1f}B / {data.get('totalDebt', 0)/1e9:.1f}B"},
        {"חוק": "חוב/הון < 0.8", "מצב": "✅" if safe_div(data.get('debtToEquity', 100), 100) < 0.8 else "❌", "נתון": f"{safe_div(data.get('debtToEquity', 100), 100):.2f}"}
    ]
    st.table(pd.DataFrame(rules))
    
    # DCF
    st.subheader("⚖️ מודל הערכת שווי (DCF)")
    c1, c2 = st.columns(2)
    growth = c1.number_input("צמיחה (%)", 1.0, 50.0, 10.0) / 100
    wacc = c2.number_input("ריבית היוון (%)", 1.0, 30.0, 10.0) / 100
    
    fcf = data.get('freeCashflow') or 0
    shares = data.get('sharesOutstanding') or 1
    
    if fcf and wacc > growth:
        intrinsic = ((fcf * (1 + growth)) / (wacc - growth)) / shares
        st.metric("שווי פנימי למניה", f"${intrinsic:,.2f}")
        if intrinsic > data.get('currentPrice', 0):
            st.success("המניה זולה מהשווי הפנימי!")
        else:
            st.error("המניה יקרה מהשווי הפנימי.")
    else:
        st.warning("לא ניתן לחשב DCF (חסר FCF או שריבית ההיוון נמוכה מהצמיחה).")
