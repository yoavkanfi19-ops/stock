import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Ultimate Stock Pro")

# פונקציה ליצירת Session שעוקף חסימות (User-Agent משופר)
def get_safe_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive'
    })
    return session

@st.cache_resource(ttl=3600)
def fetch_data(symbol):
    try:
        session = get_safe_session()
        ticker = yf.Ticker(symbol, session=session)
        # טעינת נתונים בסיסיים כדי לבדוק חסימה
        info = ticker.info
        if not info or 'currentPrice' not in info:
            return None, "Yahoo Finance חסמו את הגישה מהשרת כרגע (Rate Limit). נסה שוב בעוד כמה דקות."
        return ticker, None
    except Exception as e:
        return None, str(e)

def format_val(val):
    if val is None or np.isnan(val): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

# --- ממשק משתמש ---
st.title("📈 Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AAPL, AMZN, MSFT):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f'מתחבר ל-Yahoo Finance ומנתח את {symbol}...'):
        ticker, error = fetch_data(symbol)
        
        if error:
            st.error(f"⚠️ שגיאה: {error}")
            st.info("טיפ: אם אתה ב-Streamlit Cloud, לפעמים Yahoo חוסמים את השרת הציבורי. נסה להריץ שוב או לבדוק מניה אחרת.")
            st.stop()

        info = ticker.info
        is_stmt = ticker.financials
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        # 1. תקציר חברה
        st.header(f"{info.get('longName')} ({symbol})")
        col_header1, col_header2, col_header3 = st.columns(3)
        col_header1.metric("מחיר נוכחי", f"${info.get('currentPrice')}")
        col_header2.metric("תאריך דוח נבדק", is_stmt.columns[0].strftime('%d/%m/%Y'))
        col_header3.metric("שווי שוק", format_val(info.get('marketCap')))
        
        st.subheader("📖 תקציר עסקי")
        st.write(info.get('longBusinessSummary'))

        # 2. בדיקת 12 החוקים
        st.subheader("🛡️ בדיקת 12 החוקים הפיננסיים (באפטולוגיה)")
        
        rev = info.get('totalRevenue', 1)
        gp = info.get('grossProfits', 0)
        ni = info.get('netIncomeToCommon', 0)
        cash = info.get('totalCash', 0)
        debt = info.get('totalDebt', 0)
        equity = info.get('totalStockholderEquity', 1)
        op_inc = is_stmt.loc['Operating Income'][0] if 'Operating Income' in is_stmt.index else 1
        int_exp = abs(is_stmt.loc['Interest Expense'][0]) if 'Interest Expense' in is_stmt.index else 0
        sga = is_stmt.loc['Selling General Administrative'][0] if 'Selling General Administrative' in is_stmt.index else 0
        rnd = is_stmt.loc['Research Development'][0] if 'Research Development' in is_stmt.index else 0
        
        rules = [
            {"חוק": "מזומן > חוב", "מצב": "✅" if cash > debt else "❌", "ערך": f"מזומן: {format_val(cash)} / חוב: {format_val(debt)}"},
            {"חוק": "חוב/הון < 0.8", "מצב": "✅" if (debt/equity) < 0.8 else "❌", "ערך": f"יחס: {(debt/equity):.2f}"},
            {"חוק": "אין מניות בכורה", "מצב": "✅" if 'Preferred Stock' not in bs.index else "⚠️", "ערך": "נקי"},
            {"חוק": "רווח גולמי > 40%", "מצב": "✅" if (gp/rev) > 0.4 else "❌", "ערך": f"{(gp/rev)*100:.1f}%"},
            {"חוק": "הוצאות הנהלה/גולמי < 30%", "מצב": "✅" if (sga/gp) < 0.3 else "❌", "ערך": f"{(sga/gp)*100:.1f}%"},
            {"חוק": "הוצאות מו\"פ/גולמי < 30%", "מצב": "✅" if (rnd/gp) < 0.3 else "❌", "ערך": f"{(rnd/gp)*100:.1f}%"},
            {"חוק": "ריבית/רווח תפעולי < 15%", "מצב": "✅" if (int_exp/op_inc) < 0.15 else "❌", "ערך": f"{(int_exp/op_inc)*100:.1f}%"},
            {"חוק": "רווח נקי/הכנסות > 20%", "מצב": "✅" if (ni/rev) > 0.2 else "❌", "ערך": f"{(ni/rev)*100:.1f}%"},
            {"חוק": "EPS בצמיחה חיובית", "מצב": "✅" if info.get('earningsGrowth', 0) > 0 else "❌", "ערך": f"{info.get('earningsGrowth', 0)*100:.1f}%"},
            {"חוק": "רווחים צבורים בצמיחה", "מצב": "✅" if bs.loc['Retained Earnings'][0] > bs.loc['Retained Earnings'][1] else "❌", "ערך": "בצמיחה"},
            {"חוק": "רכישת מניות עצמית (Buybacks)", "מצב": "✅" if 'Repurchase Of Capital Stock' in cf.index else "⚪", "ערך": "קיימת"},
            {"חוק": "מס הכנסה תקין (~20%)", "מצב": "✅" if 0.15 < abs(is_stmt.loc['Tax Provision'][0]/is_stmt.loc['Pretax Income'][0]) < 0.3 else "⚠️", "ערך": "תקין"}
        ]
        st.table(pd.DataFrame(rules))

        # 3. ניתוח צמיחה ו-Buybacks
        st.subheader("📊 צמיחה ורכישת מניות")
        eps_growth = info.get('earningsQuarterlyGrowth', 0)
        ni_growth = (ni / is_stmt.iloc[0, 1] - 1) if len(is_stmt.columns) > 1 else 0
        buybacks = abs(cf.loc['Repurchase Of Capital Stock'][0]) if 'Repurchase Of Capital Stock' in cf.index else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("צמיחת EPS", f"{eps_growth*100:.1f}%")
        c2.metric("צמיחת רווח נקי", f"{ni_growth*100:.1f}%")
        c3.metric("סכום Buyback", format_val(buybacks))
        st.write(f"💡 **הבדל בצמיחה:** {(eps_growth - ni_growth)*100:.1f}%. אם ה-EPS גדל מהר יותר מהרווח הנקי, זה סימן חזק שהחברה מקטינה את כמות המניות.")

        # 4. מודל WACC ו-DCF (הערכת שווי)
        st.subheader("⚖️ מודל הערכת שווי פנימי (Intrinsic Value)")
        
        # חישוב WACC
        rf = 0.042 # ריבית חסרת סיכון 10 שנים
        beta = info.get('beta', 1.2)
        erp = 0.05 # פרמיית סיכון שוק
        cost_equity = rf + (beta * erp)
        tax_rate = 0.21
        cost_debt = (int_exp / debt) if debt > 0 else 0.05
        w_e = equity / (equity + debt)
        w_d = debt / (equity + debt)
        wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - tax_rate))
        
        st.write(f"**פירוט חישוב WACC:**")
        st.latex(f"WACC = ({w_e:.2f} \\times {cost_equity*100:.1f}\\%) + ({w_d:.2f} \\times {cost_debt*100:.1f}\\% \\times (1-0.21)) = {wacc*100:.2f}\\%")

        fcf = info.get('freeCashflow', 1e9)
        growth_rate = info.get('earningsGrowth', 0.1)
        intrinsic_dcf = (fcf * (1 + growth_rate)) / (wacc - 0.02)
        price_dcf = intrinsic_dcf / info.get('sharesOutstanding', 1)

        # 5. מגרש כדורגל (Football Field)
        st.write("**מגרש כדורגל (Football Field Valuation):**")
        price_pe = info.get('forwardPE', 20) * info.get('forwardEps', 5)
        price_nav = equity / info.get('sharesOutstanding', 1)
        
        football_data = {
            "שיטת הערכה": ["DCF (תזרים מזומנים)", "Relative (מכפיל רווח)", "NAV (שווי נכסי נקי)"],
            "שווי למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        }
        st.table(pd.DataFrame(football_data))

        # 6. המלצה ומרחב ביטחון
        final_fair_value = (price_dcf * 0.7 + price_pe * 0.3)
        mos = final_fair_value * 0.7 # 30% Margin of Safety
        
        st.divider()
        col_res1, col_res2 = st.columns(2)
        col_res1.metric("שווי הוגן סופי (משוקלל)", f"${final_fair_value:.2f}")
        col_res2.metric("מחיר קנייה אידיאלי (MOS 30%)", f"${mos:.2f}")

        # 7. ניתוח טכני ו-Moat
        st.subheader("🏰 ניתוח איכותי וטכני")
        hist = ticker.history(period="1y")
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("**סוגי Moat:** יתרון לגודל, אפקט רשת, מותג חזק.")
        st.write(f"**תחזית אנליסטים:** מחיר יעד ממוצע: ${info.get('targetMeanPrice')} | המלצה: {info.get('recommendationKey')}")

        # 8. חדשות
        st.subheader("📰 חדשות אחרונות")
        for n in ticker.news[:3]:
            st.write(f"- [{n['title']}]({n['link']})")
