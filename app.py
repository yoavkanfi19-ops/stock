import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime

# הגדרות דף
st.set_page_config(layout="wide", page_title="Financial Deep-Dive Pro")

# פונקציה ליצירת Session חזק שעוקף חסימות
def get_stable_ticker(symbol):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })
    return yf.Ticker(symbol, session=session)

def format_bn(val):
    if val is None or np.isnan(val): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    return f"${val/1e6:.2f}M"

# --- ממשק משתמש ---
st.title("📊 Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    try:
        with st.spinner(f"מושך נתונים עבור {symbol}..."):
            ticker = get_stable_ticker(symbol)
            
            # ניסיון משיכת נתונים בסיסיים
            info = ticker.info
            if not info or 'currentPrice' not in info:
                st.error("Yahoo Finance חסמו את הגישה זמנית. נסה שוב בעוד דקה או עם מניה אחרת.")
                st.stop()

            # משיכת דוחות
            is_stmt = ticker.financials
            bs = ticker.balance_sheet
            cf = ticker.cashflow
            
            # 1. תקציר כללי
            st.header(f"{info.get('longName')} ({symbol})")
            st.write(f"**מחיר נוכחי:** ${info.get('currentPrice')} | **מגזר:** {info.get('sector')}")
            
            # תאריך דוח
            report_date = is_stmt.columns[0].strftime('%d/%m/%Y') if not is_stmt.empty else "N/A"
            st.write(f"**תאריך דוח נבדק:** {report_date}")
            
            st.info(f"**תקציר החברה:** {info.get('longBusinessSummary', 'N/A')[:500]}...")

            # 2. בדיקת 12 החוקים
            st.subheader("🛡️ בדיקת 12 החוקים הפיננסיים")
            
            # משתני עזר עם ערכי ברירת מחדל למניעת קריסה
            rev = info.get('totalRevenue', 1)
            gp = info.get('grossProfits', 0)
            ni = info.get('netIncomeToCommon', 0)
            cash = info.get('totalCash', 0)
            debt = info.get('totalDebt', 0)
            equity = info.get('totalStockholderEquity', 1)
            op_inc = is_stmt.loc['Operating Income'][0] if 'Operating Income' in is_stmt.index else 1
            int_exp = abs(is_stmt.loc['Interest Expense'][0]) if 'Interest Expense' in is_stmt.index else 0
            tax_exp = abs(is_stmt.loc['Tax Provision'][0]) if 'Tax Provision' in is_stmt.index else 0
            pretax = is_stmt.loc['Pretax Income'][0] if 'Pretax Income' in is_stmt.index else 1
            sga = is_stmt.loc['Selling General Administrative'][0] if 'Selling General Administrative' in is_stmt.index else 0
            rnd = is_stmt.loc['Research Development'][0] if 'Research Development' in is_stmt.index else 0
            retained = bs.loc['Retained Earnings'][0] if 'Retained Earnings' in bs.index else 0

            rules = [
                {"חוק": "מזומן > חוב", "מצב": "✅" if cash > debt else "❌", "ערך": f"C: {format_bn(cash)} / D: {format_bn(debt)}"},
                {"חוק": "חוב/הון < 0.8", "מצב": "✅" if (debt/equity) < 0.8 else "❌", "ערך": f"{(debt/equity):.2f}"},
                {"חוק": "רווח גולמי > 40%", "מצב": "✅" if (gp/rev) > 0.4 else "❌", "ערך": f"{(gp/rev)*100:.1f}%"},
                {"חוק": "הנהלה וכלליות/גולמי < 30%", "מצב": "✅" if (sga/gp) < 0.3 else "❌", "ערך": f"{(sga/gp)*100:.1f}%"},
                {"חוק": "מו\"פ/גולמי < 30%", "מצב": "✅" if (rnd/gp) < 0.3 else "❌", "ערך": f"{(rnd/gp)*100:.1f}%"},
                {"חוק": "ריבית/רווח תפעולי < 15%", "מצב": "✅" if (int_exp/op_inc) < 0.15 else "❌", "ערך": f"{(int_exp/op_inc)*100:.1f}%"},
                {"חוק": "רווח נקי/הכנסות > 20%", "מצב": "✅" if (ni/rev) > 0.2 else "❌", "ערך": f"{(ni/rev)*100:.1f}%"},
                {"חוק": "מס הכנסה תקין (~20%)", "מצב": "✅" if 0.15 < (tax_exp/pretax) < 0.35 else "⚠️", "ערך": f"{(tax_exp/pretax)*100:.1f}%"},
                {"חוק": "רווחים צבורים בצמיחה", "מצב": "✅" if retained > (bs.loc['Retained Earnings'][1] if len(bs.columns)>1 else 0) else "❌", "ערך": format_bn(retained)},
                {"חוק": "מניות באוצר/Buybacks", "מצב": "✅" if 'Treasury Stock' in bs.index or 'Repurchase Of Capital Stock' in cf.index else "⚪", "ערך": "קיימת"},
                {"חוק": "צמיחת EPS (אנליסטים)", "מצב": "✅" if (info.get('earningsGrowth', 0) or 0) > 0 else "❌", "ערך": f"{(info.get('earningsGrowth', 0) or 0)*100:.1f}%"},
                {"חוק": "אין מניות בכורה", "מצב": "✅" if 'Preferred Stock' not in bs.index else "⚠️", "ערך": "תקין"}
            ]
            st.table(pd.DataFrame(rules))

            # 3. הערכת שווי (WACC & DCF)
            st.subheader("⚖️ מודל הערכת שווי (DCF)")
            
            # חישוב WACC
            rf = 0.043 # ריבית 10 שנים
            beta = info.get('beta', 1.2) or 1.2
            erp = 0.055 # פרמיית סיכון שוק
            cost_equity = rf + (beta * erp)
            cost_debt = (int_exp / debt) if debt > 1e6 else 0.05
            w_e = equity / (equity + debt)
            w_d = debt / (equity + debt)
            wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - 0.21))
            
            fcf = info.get('freeCashflow') or (ni * 1.1) # אם חסר FCF, נבצע הערכה לפי רווח
            growth = info.get('earningsGrowth') or 0.10
            
            # חישוב שווי פנימי
            terminal_growth = 0.025
            dcf_val = (fcf * (1 + growth)) / (wacc - terminal_growth)
            price_dcf = dcf_val / info.get('sharesOutstanding', 1)
            
            # חישוב מכפילים
            price_pe = (info.get('forwardPE') or 20) * (info.get('forwardEps') or 5)
            
            st.write(f"**נתוני מודל:** WACC: {wacc*100:.2f}%, צמיחה חזויה: {growth*100:.1f}%, FCF: {format_bn(fcf)}")
            
            # מגרש כדורגל
            st.write("**מגרש כדורגל (טווח מחירים):**")
            football = pd.DataFrame({
                "שיטה": ["DCF (תזרים מזומנים)", "Relative (מכפילים)", "NAV (שווי נכסי)"],
                "מחיר מוערך": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${equity/info.get('sharesOutstanding',1):.2f}"]
            })
            st.table(football)

            # 4. המלצה סופית
            fair_value = (price_dcf * 0.7 + price_pe * 0.3)
            mos = fair_value * 0.7 # מרווח ביטחון 30%
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("שווי הוגן משוקלל", f"${fair_value:.2f}")
            c2.metric("מחיר קנייה (MOS 30%)", f"${mos:.2f}")
            c3.metric("מחיר יעד אנליסטים", f"${info.get('targetMeanPrice', 'N/A')}")

            # 5. ניתוח טכני ו-Moat
            st.subheader("🏰 ניתוח איכותי")
            st.write("**סוגי Moat:** יתרון לגודל, עלויות מעבר, מותג.")
            
            hist = ticker.history(period="1y")
            if not hist.empty:
                fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"אירעה שגיאה: {e}. Yahoo Finance כרגע חוסמים את הבקשה, נסה שוב בעוד מספר דקות.")
