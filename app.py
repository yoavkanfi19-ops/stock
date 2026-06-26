import streamlit as st
import yfinance as yf
import pandas as pd

st.title("מנתח המניות האישי שלך")
symbol = st.text_input("הזן סימול מניה:", "AMZN")

if st.button("נתח"):
    ticker = yf.Ticker(symbol)
    info = ticker.info
    
    # חישוב FCF לוגיקה משופרת
    fcf = info.get('freeCashflow')
    if fcf is None or fcf < 0:
        st.warning("ה-FCF שלילי או לא זמין, משתמש ב-Operating Cash Flow במקום")
        fcf = info.get('operatingCashflow', 0)
    
    # חישוב שווי פנימי
    dcf = (fcf * 1.05) / (0.10 - 0.03) / info.get('sharesOutstanding', 1)
    
    col1, col2 = st.columns(2)
    col1.metric("שווי פנימי (DCF)", f"${dcf:.2f}")
    col2.metric("מחיר נוכחי", f"${info.get('currentPrice', 0):.2f}")
    
    # טבלת חוקים
    data = {"מדד": ["חוב/הון", "רווח גולמי"], "ערך": [info.get('debtToEquity', 0), f"{info.get('grossMargins', 0)*100:.1f}%"]}
    st.table(pd.DataFrame(data))
