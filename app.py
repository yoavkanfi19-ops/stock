import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(layout="wide", page_title="Professional Stock Analyzer")

st.title("📊 Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה:", "AMZN")

if st.sidebar.button("הפק דוח ניתוח מלא"):
    ticker = yf.Ticker(symbol)
    info = ticker.info
    bs = ticker.balance_sheet
    is_stmt = ticker.financials
    
    # נתונים בסיסיים
    cash = info.get('totalCash', 0)
    debt = info.get('totalDebt', 0)
    market_cap = info.get('marketCap', 0)
    rev = info.get('totalRevenue', 1)
    gross_profit = info.get('grossProfits', 0)
    net_income = info.get('netIncomeToCommon', 0)
    
    # 1. בדיקת 12 החוקים
    st.subheader("📋 סיכום 12 החוקים")
    rules = [
        {"חוק": "מזומן > חוב", "מצב": "עומד" if cash > debt else "לא עומד", "ערך": f"{cash/1e9:.1f}B / {debt/1e9:.1f}B"},
        {"חוק": "חוב/הון < 0.8", "מצב": "עומד" if (info.get('debtToEquity', 999)) < 80 else "לא עומד", "ערך": f"{info.get('debtToEquity', 0)}%"},
        {"חוק": "רווח גולמי > 40%", "מצב": "עומד" if (gross_profit/rev) > 0.4 else "לא עומד", "ערך": f"{(gross_profit/rev)*100:.1f}%"},
        {"חוק": "רווח נקי > 20%", "מצב": "עומד" if (net_income/rev) > 0.2 else "לא עומד", "ערך": f"{(net_income/rev)*100:.1f}%"},
        {"חוק": "EPS בצמיחה", "מצב": "בדיקה ידנית", "ערך": "בדוק בדוח השנתי"}
    ]
    st.table(pd.DataFrame(rules))

    # 2. טבלת נתונים פיננסיים מסכמת
    st.subheader("💰 נתונים פיננסיים מרכזיים")
    fin_data = {
        "מדד": ["הכנסות", "רווח תפעולי", "רווח נקי", "מזומן", "חוב"],
        "ערך (מיליארדים)": [f"{rev/1e9:.1f}B", f"{info.get('operatingMargins', 0)*rev/1e9:.1f}B", 
                          f"{net_income/1e9:.1f}B", f"{cash/1e9:.1f}B", f"{debt/1e9:.1f}B"]
    }
    st.table(pd.DataFrame(fin_data))

    # 3. מודל DCF (חישוב)
    st.subheader("⚖️ מודל הערכת שווי (DCF)")
    wacc = 0.10 # WACC בסיסי
    fcf = info.get('freeCashflow', 0)
    
    st.write(f"**נתוני חישוב:**")
    st.write(f"- ריבית היוון (WACC): {wacc*100}%")
    st.write(f"- תזרים מזומנים חופשי (FCF): ${fcf/1e9:.2f}B")
    
    dcf_val = (fcf * 1.10) / (wacc - 0.03) / info.get('sharesOutstanding', 1)
    st.metric("שווי פנימי למניה (DCF)", f"${dcf_val:.2f}")

    # 4. ניתוח טכני
    st.subheader("📉 ניתוח טכני")
    hist = ticker.history(period="1y")
    st.line_chart(hist['Close'])
    st.write("ניתוח מגמה: בצע הצלבה עם ה-ATR והממוצעים הנעים.")

    # 5. חדשות
    st.subheader("📰 חדשות אחרונות")
    for news in ticker.news[:3]:
        st.write(f"[{news['title']}]({news['link']})")
