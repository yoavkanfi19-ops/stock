import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Analyzer Pro")

st.title("📊 Financial Deep-Dive Analyzer")
symbol = st.sidebar.text_input("הזן סימול מניה (למשל AMZN):", "AMZN")

if st.sidebar.button("התחל ניתוח מלא"):
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="1y")
    
    # --- 1. תמצית ונתונים כלליים ---
    st.header(f"ניתוח עבור: {info.get('longName', symbol)}")
    st.write(f"**מחיר נוכחי:** ${info.get('currentPrice')}")
    st.write(f"**פעילות:** {info.get('longBusinessSummary')}")
    
    # --- 2. 12 החוקים ---
    cash = info.get('totalCash', 0)
    debt = info.get('totalDebt', 0)
    equity = info.get('bookValue', 0) * info.get('sharesOutstanding', 1)
    rev = info.get('totalRevenue', 1)
    gross_profit = info.get('grossProfits', 0)
    net_income = info.get('netIncomeToCommon', 0)
    
    rules = [
        {"חוק": "מזומן > חוב", "מצב": "עומד" if cash > debt else "לא עומד", "ערך": f"{cash/1e9:.1f}B / {debt/1e9:.1f}B"},
        {"חוק": "חוב/הון < 0.8", "מצב": "עומד" if (debt/equity if equity>0 else 999) < 0.8 else "לא עומד", "ערך": f"{debt/equity:.2f}"},
        {"חוק": "רווח גולמי > 40%", "מצב": "עומד" if (gross_profit/rev) > 0.4 else "לא עומד", "ערך": f"{(gross_profit/rev)*100:.1f}%"},
        {"חוק": "רווח נקי > 20%", "מצב": "עומד" if (net_income/rev) > 0.2 else "לא עומד", "ערך": f"{(net_income/rev)*100:.1f}%"}
    ]
    st.subheader("בדיקת 12 החוקים")
    st.table(pd.DataFrame(rules))
    
    # --- 3. מודל DCF (עם חישוב WACC) ---
    st.subheader("מודל הערכת שווי (DCF)")
    risk_free = 0.045 # הנחת ריבית אג"ח 10 שנים
    beta = info.get('beta', 1.0)
    wacc = risk_free + (beta * 0.05) # נוסחת CAPM פשוטה ל-WACC
    
    fcf = info.get('freeCashflow', 0)
    growth_rate = 0.10 # צמיחה שנתית מוערכת
    
    # חישוב DCF
    terminal_value = (fcf * (1 + growth_rate)) / (wacc - 0.03)
    intrinsic_value = (fcf + terminal_value) / info.get('sharesOutstanding', 1)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("WACC (ריבית היוון)", f"{wacc*100:.2f}%")
    col2.metric("צמיחה מוערכת", f"{growth_rate*100:.2f}%")
    col3.metric("שווי פנימי (DCF)", f"${intrinsic_value:.2f}")
    
    st.caption("חישוב ה-DCF בוצע לפי מודל גורדון: (FCF * צמיחה) / (WACC - צמיחה טרמינלית)")

    # --- 4. גרף טכני ---
    st.subheader("ניתוח טכני")
    st.line_chart(hist['Close'])
