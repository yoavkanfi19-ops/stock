import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import time

st.set_page_config(page_title="Professional Stock Deep-Dive", layout="wide")

def get_stock_data(symbol):
    filename = f"{symbol}.json"
    if os.path.exists(filename):
        if (time.time() - os.path.getmtime(filename)) < 3600:
            with open(filename, 'r') as f:
                return json.load(f)
    ticker = yf.Ticker(symbol)
    data = ticker.info
    with open(filename, 'w') as f:
        json.dump(data, f)
    return data

st.title("🛡️ Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("סימול מניה:", "NVDA").upper()

if st.sidebar.button("נתח מניה"):
    try:
        data = get_stock_data(symbol)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("מחיר נוכחי", f"${data.get('currentPrice', 0):.2f}")
        c2.metric("מכפיל רווח", f"{data.get('trailingPE', 0):.2f}")
        c3.metric("מרווח רווח נקי", f"{data.get('profitMargins', 0)*100:.1f}%")
        
        st.write("---")
        
        st.subheader("📊 ניתוח 12 החוקים (באפטולוגיה)")
        rules_data = [
            {"חוק": "רווח נקי > 20%", "מצב": "✅" if data.get('profitMargins', 0) > 0.2 else "❌", "נתון": f"{data.get('profitMargins', 0)*100:.1f}%"},
            {"חוק": "יחס חוב להון < 0.8", "מצב": "✅" if (data.get('debtToEquity', 100)/100) < 0.8 else "❌", "נתון": f"{data.get('debtToEquity', 100)/100:.2f}"},
            {"חוק": "תשואה על נכסים (ROA)", "מצב": "✅" if data.get('returnOnAssets', 0) > 0.1 else "❌", "נתון": f"{data.get('returnOnAssets', 0)*100:.1f}%"}
        ]
        st.table(pd.DataFrame(rules_data))
        
        st.subheader("⚖️ ניתוח שווי פנימי (DCF)")
        growth = st.slider("צמיחה שנתית צפויה (%)", 1, 20, 10) / 100
        discount_rate = st.slider("ריבית היוון (WACC) (%)", 6, 20, 10) / 100
        
        fcf = data.get('freeCashflow', 0)
        shares = data.get('sharesOutstanding', 1)
        
        # הגנה מפני חילוק באפס
        if fcf and shares and discount_rate > growth:
            terminal_val = (fcf * (1 + growth)) / (discount_rate - growth)
            intrinsic_val = terminal_val / shares
            
            dcf_data = {
                "פרמטר": ["תזרים מזומנים חופשי (FCF)", "שיעור צמיחה", "ריבית היוון", "שווי פנימי למניה"],
                "ערך": [f"${fcf:,.0f}", f"{growth*100}%", f"{discount_rate*100}%", f"${intrinsic_val:,.2f}"]
            }
            st.table(pd.DataFrame(dcf_data))
            
            margin = (1 - (data.get('currentPrice', 1) / intrinsic_val)) * 100
            if margin > 0:
                st.success(f"מרווח ביטחון (Margin of Safety): {margin:.1f}%")
            else:
                st.error("המניה נסחרת מעל השווי הפנימי המשוער.")
        elif discount_rate <= growth:
            st.error("ריבית ההיוון חייבת להיות גבוהה משיעור הצמיחה כדי לבצע חישוב DCF תקין. אנא שנה את הפרמטרים.")
        else:
            st.warning("אין מספיק נתוני תזרים מזומנים לחישוב DCF.")
            
    except Exception as e:
        st.error(f"שגיאה: {e}")
