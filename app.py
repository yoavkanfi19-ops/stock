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

# פונקציה בטוחה לחילוק למניעת ZeroDivisionError
def safe_div(a, b):
    return (a / b) if b and b != 0 else 0

st.title("🛡️ Financial Deep-Dive Pro (Full Buffett Edition)")
symbol = st.sidebar.text_input("סימול מניה:", "NVDA").upper()

if 'data' not in st.session_state:
    st.session_state.data = None

if st.sidebar.button("הפק דוח ניתוח"):
    st.session_state.data = get_stock_data(symbol)

if st.session_state.data:
    data = st.session_state.data
    
    st.header(f"ניתוח עבור {data.get('longName', symbol)}")
    
    st.subheader("📊 ניתוח 12 החוקים המלא")
    
    # חישוב בטוח של משתנים
    gp = data.get('grossProfit', 0)
    rev = data.get('totalRevenue', 1)
    sga = data.get('sellingGeneralAdministrative', 0)
    rd = data.get('researchDevelopment', 0)
    op_inc = data.get('operatingIncome', 1)
    int_exp = data.get('interestExpense', 0)
    pretax = data.get('pretaxIncome', 1)
    tax = data.get('taxProvision', 0)
    
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
    
    st.subheader("⚖️ מודל הערכת שווי (DCF) חופשי")
    col1, col2 = st.columns(2)
    growth = col1.number_input("צמיחה שנתית (%)", min_value=1.0, max_value=50.0, value=10.0) / 100
    wacc = col2.number_input("ריבית היוון (WACC) (%)", min_value=1.0, max_value=30.0, value=10.0) / 100
    
    fcf = data.get('freeCashflow', 0)
    shares = data.get('sharesOutstanding', 1)
    
    if fcf and shares and wacc > growth:
        terminal_val = (fcf * (1 + growth)) / (wacc - growth)
        intrinsic_val = terminal_val / shares
        st.table(pd.DataFrame({"פרמטר": ["תזרים מזומנים חופשי", "צמיחה", "ריבית היוון", "שווי פנימי למניה"], "ערך": [f"${fcf:,.0f}", f"{growth*100}%", f"{wacc*100}%", f"${intrinsic_val:,.2f}"]}))
        if intrinsic_val > data.get('currentPrice', 0):
            st.success(f"המניה נסחרת ב-${data.get('currentPrice'):.2f} - היא זולה מהשווי הפנימי!")
        else:
            st.error("המניה נסחרת מעל השווי הפנימי המשוער.")
    else:
        st.warning("החישוב לא אפשרי (וודא שריבית ההיוון > הצמיחה).")
