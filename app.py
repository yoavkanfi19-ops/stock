import streamlit as st
import yfinance as yf
import json
import os
import time

st.set_page_config(page_title="Professional Stock Deep-Dive", layout="wide")

def get_stock_data(symbol):
    filename = f"{symbol}.json"
    # משיכת נתונים עם בדיקת זמן (רענון פעם בשעה)
    if os.path.exists(filename):
        file_time = os.path.getmtime(filename)
        if (time.time() - file_time) < 3600:
            with open(filename, 'r') as f:
                return json.load(f)
    
    ticker = yf.Ticker(symbol)
    data = ticker.info
    with open(filename, 'w') as f:
        json.dump(data, f)
    return data

st.title("🛡️ Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("סימול מניה (למשל NVDA):", "NVDA").upper()

if st.sidebar.button("נתח מניה"):
    try:
        data = get_stock_data(symbol)
        
        # אזור מדדים ראשיים
        c1, c2, c3 = st.columns(3)
        c1.metric("מחיר נוכחי", f"${data.get('currentPrice', 0):.2f}")
        c2.metric("מכפיל רווח", f"{data.get('trailingPE', 0):.2f}")
        c3.metric("מרווח רווח נקי", f"{data.get('profitMargins', 0)*100:.1f}%")
        
        st.write("---")
        
        # ניתוח "באפטולוגיה" מורחב
        st.subheader("📊 ניתוח באפטולוגיה")
        col_a, col_b = st.columns(2)
        
        with col_a:
            is_good_margin = data.get('profitMargins', 0) > 0.2
            st.write(f"רווח נקי > 20%: {'✅ חיובי' if is_good_margin else '❌ דורש בדיקה'}")
            
            roa = data.get('returnOnAssets', 0)
            st.write(f"תשואה על נכסים (ROA): {roa*100:.1f}%")

        with col_b:
            debt_to_equity = data.get('debtToEquity', 100) / 100
            st.write(f"יחס חוב להון: {debt_to_equity:.2f} {'(טוב)' if debt_to_equity < 0.8 else '(גבוה)'}")
            
            st.info("💡 טיפ: באפט מחפש חברות עם 'Moat' (חפיר) רחב – מותג חזק, יתרון לגודל ועלויות מעבר גבוהות.")

        # סימולטור הערכת שווי פשוט
        st.write("---")
        st.subheader("🎯 הערכת שווי (לפי רווח עתידי משוער)")
        growth_rate = st.slider("קצב צמיחה שנתי משוער (%)", 5, 25, 12)
        eps = data.get('trailingEps', 1)
        future_val = eps * ((1 + growth_rate/100) ** 10)
        st.write(f"רווח למניה משוער בעוד 10 שנים: **${future_val:.2f}**")
            
    except Exception as e:
        st.error("לא ניתן למשוך נתונים כרגע. וודא שהסימול תקין.")
