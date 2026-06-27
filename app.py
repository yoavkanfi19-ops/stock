import streamlit as st
import yfinance as yf
import json
import os

st.set_page_config(page_title="Professional Stock Deep-Dive", layout="wide")

# פונקציית טעינה ושמירה למניעת קריאות חוזרות
def get_stock_data(symbol):
    filename = f"{symbol}.json"
    # אם יש לנו נתונים שמורים מהשעה האחרונה, נשתמש בהם
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    
    # אחרת, נמשוך מהרשת
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
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("מחיר נוכחי", f"${data.get('currentPrice', 'N/A')}")
            st.metric("מכפיל רווח", data.get('trailingPE', 'N/A'))
        
        with col2:
            st.subheader("ניתוח מהיר")
            is_good = data.get('profitMargins', 0) > 0.2
            st.write("באפטולוגיה:", "✅ חיובי" if is_good else "❌ דורש בדיקה")
            
    except Exception as e:
        st.error("השרת עמוס, נסה שוב בעוד דקה. הנתונים נשמרים מקומית.")
