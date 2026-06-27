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

st.title("🛡️ Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("סימול מניה (למשל NVDA):", "NVDA").upper()

# שמירת מצב הלחיצה בזיכרון כדי למנוע איפוס
if 'data' not in st.session_state:
    st.session_state.data = None

if st.sidebar.button("הפק דוח ניתוח"):
    st.session_state.data = get_stock_data(symbol)

if st.session_state.data:
    data = st.session_state.data
    
    # --- חלק 1: מדדים מרכזיים ---
    st.header(f"ניתוח עבור {data.get('longName', symbol)}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("מחיר נוכחי", f"${data.get('currentPrice', 0):.2f}")
    c2.metric("מכפיל רווח (P/E)", f"{data.get('trailingPE', 0):.2f}")
    c3.metric("שווי שוק", f"{data.get('marketCap', 0)/1e9:.1f}B")
    c4.metric("מרווח רווח נקי", f"{data.get('profitMargins', 0)*100:.1f}%")
    
    st.write("---")
    
    # --- חלק 2: טבלת 12 החוקים ---
    st.subheader("📊 סיכום 12 החוקים (באפטולוגיה)")
    rules = [
        {"חוק": "מזומן > חוב", "מצב": "✅" if data.get('totalCash', 0) > data.get('totalDebt', 0) else "❌", "נתון": f"{data.get('totalCash', 0)/1e9:.1f}B / {data.get('totalDebt', 0)/1e9:.1f}B"},
        {"חוק": "יחס חוב להון < 0.8", "מצב": "✅" if (data.get('debtToEquity', 100)/100) < 0.8 else "❌", "נתון": f"{data.get('debtToEquity', 100)/100:.2f}"},
        {"חוק": "רווח נקי > 20%", "מצב": "✅" if data.get('profitMargins', 0) > 0.2 else "❌", "נתון": f"{data.get('profitMargins', 0)*100:.1f}%"},
        {"חוק": "תשואה על נכסים (ROA) > 10%", "מצב": "✅" if data.get('returnOnAssets', 0) > 0.1 else "❌", "נתון": f"{data.get('returnOnAssets', 0)*100:.1f}%"}
    ]
    st.table(pd.DataFrame(rules))
    
    # --- חלק 3: חישוב DCF חכם ---
    st.subheader("⚖️ מודל הערכת שווי (DCF)")
    
    growth_perc = st.slider("צמיחה שנתית מוערכת (%)", 1, 15, 8)
    growth = growth_perc / 100
    min_wacc = growth_perc + 2
    wacc_perc = st.slider("ריבית היוון (WACC) (%)", min_wacc, 20, max(min_wacc + 3, 10))
    wacc = wacc_perc / 100
    
    fcf = data.get('freeCashflow', 0)
    shares = data.get('sharesOutstanding', 1)
    
    if fcf and shares:
        terminal_val = (fcf * (1 + growth)) / (wacc - growth)
        intrinsic_val = terminal_val / shares
        
        st.metric("שווי פנימי למניה (Intrinsic Value)", f"${intrinsic_val:,.2f}")
        
        margin = (1 - (data.get('currentPrice', 1) / intrinsic_val)) * 100
        if margin > 0:
            st.success(f"מרווח ביטחון (Margin of Safety): {margin:.1f}%")
        else:
            st.error("הערכת שווי: המניה נסחרת מעל השווי הפנימי המשוער.")
    else:
        st.warning("אין נתוני תזרים מזומנים זמינים לחישוב.")
