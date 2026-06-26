import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import requests

# הגדרת דף
st.set_page_config(layout="wide", page_title="Deep Financial Analysis Pro")

# פונקציה לעקיפת חסימת ה-Rate Limit של Yahoo
@st.cache_data(ttl=3600)
def get_ticker_data(symbol):
    session = requests.Session()
    # הגדרת User-Agent כדי להיראות כמו דפדפן
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    ticker = yf.Ticker(symbol, session=session)
    return ticker

def format_bn(val):
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    return f"${val/1e6:.2f}M"

# --- ממשק משתמש ---
st.title("🛡️ ניתוח ערך עמוק ומודלים פיננסיים")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל TSLA, AAPL, AMZN):", "AMZN").upper()

if st.sidebar.button("הפק דוח אנליסט מלא"):
    try:
        with st.spinner('מנתח דוחות כספיים...'):
            ticker = get_ticker_data(symbol)
            info = ticker.info
            
            # בדיקה בסיסית אם הנתונים הגיעו
            if 'currentPrice' not in info:
                st.error("לא ניתן למשוך נתונים. Yahoo Finance חסמו את הגישה זמנית. נסה שוב בעוד כמה דקות.")
                st.stop()

            # שליפת דוחות
            is_stmt = ticker.financials
            bs = ticker.balance_sheet
            cf = ticker.cashflow
            
            # 1. פרטים כלליים
            st.header(f"שם מניה: {info.get('longName')} ({symbol})")
            st.write(f"**מחיר נוכחי:** ${info.get('currentPrice')}")
            report_date = is_stmt.columns[0].strftime('%d/%m/%Y')
            st.write(f"**תאריך דוח נבדק:** {report_date}")
            
            st.subheader("📝 תקציר החברה")
            st.info(info.get('longBusinessSummary', "אין תקציר זמין."))

            # 2. בדיקת 12 החוקים
            st.subheader("⚖️ בדיקת 12 חוקי הברזל של וורן באפט")
            
            # נתונים לחישובים
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
            rnd = is_stmt.loc['Research Development'][0] if 'Research Development' in is_stmt.index else 0
            sga = is_stmt.loc['Selling General Administrative'][0] if 'Selling General Administrative' in is_stmt.index else 0
            
            rules = [
                {"חוק": "מזומן > חוב", "מצב": "✅" if cash > debt else "❌", "הסבר": f"מזומן: {format_bn(cash)} | חוב: {format_bn(debt)}"},
                {"חוק": "יחס חוב להון < 0.8", "מצב": "✅" if (debt/equity) < 0.8 else "❌", "הסבר": f"יחס: {(debt/equity):.2f}"},
                {"חוק": "אין מניות בכורה", "מצב": "✅" if info.get('totalStockholderEquity') == info.get('bookValue', 0)*info.get('sharesOutstanding', 1) else "⚠️", "הסבר": "בדיקת מבנה הון"},
                {"חוק": "רווחים צבורים בצמיחה", "מצב": "✅" if bs.loc['Retained Earnings'][0] > bs.loc['Retained Earnings'][1] else "❌", "הסבר": "צמיחה משנה שעברה"},
                {"חוק": "מניות באוצר (Buybacks)", "מצב": "✅" if 'Treasury Stock' in bs.index or (info.get('sharesOutstanding') < info.get('impliedSharesOutstanding', 0)) else "⚪", "הסבר": "החברה קונה את עצמה"},
                {"חוק": "רווח גולמי > 40%", "מצב": "✅" if (gp/rev) > 0.4 else "❌", "הסבר": f"{(gp/rev)*100:.1f}%"},
                {"חוק": "הוצאות תפעול/גולמי < 30%", "מצב": "✅" if (sga/gp) < 0.3 else "❌", "הסבר": f"{(sga/gp)*100:.1f}%"},
                {"חוק": "הוצאות מו\"פ/גולמי < 30%", "מצב": "✅" if (rnd/gp) < 0.3 else "❌", "הסבר": f"{(rnd/gp)*100:.1f}%"},
                {"חוק": "ריבית/רווח תפעולי < 15%", "מצב": "✅" if (int_exp/op_inc) < 0.15 else "❌", "הסבר": f"{(int_exp/op_inc)*100:.1f}%"},
                {"חוק": "מס הכנסה תקין (~20%)", "מצב": "✅" if 0.15 < (tax_exp/pretax) < 0.3 else "⚠️", "הסבר": f"{(tax_exp/pretax)*100:.1f}%"},
                {"חוק": "רווח נקי/הכנסות > 20%", "מצב": "✅" if (ni/rev) > 0.2 else "❌", "הסבר": f"{(ni/rev)*100:.1f}%"},
                {"חוק": "EPS בצמיחה", "מצב": "✅" if info.get('earningsGrowth', 0) > 0 else "❌", "הסבר": f"{info.get('earningsGrowth', 0)*100:.1f}%"}
            ]
            st.table(pd.DataFrame(rules))

            # 3. טבלאות נתונים
            st.subheader("📊 סיכום פיננסי")
            fcf = info.get('freeCashflow', 0)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**מדדי רווחיות וצמיחה:**")
                summary_data = {
                    "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "Free Cash Flow"],
                    "ערך": [format_bn(rev), format_bn(info.get('ebitda', 0)), format_bn(op_inc), format_bn(ni), format_bn(fcf)]
                }
                st.table(pd.DataFrame(summary_data))
            
            with col2:
                st.write("**ניתוח צמיחה ו-Buybacks:**")
                # חישוב רכישת מניות
                buyback = abs(cf.loc['Repurchase Of Capital Stock'][0]) if 'Repurchase Of Capital Stock' in cf.index else 0
                eps_growth = info.get('earningsQuarterlyGrowth', 0)
                ni_growth = (ni / is_stmt.iloc[0, 1]) - 1 if len(is_stmt.columns) > 1 else 0
                
                st.write(f"- **מניות שנקנו בחזרה (בדוח זה):** {format_bn(buyback)}")
                st.write(f"- **צמיחת EPS:** {eps_growth*100:.1f}%")
                st.write(f"- **צמיחת רווח נקי:** {ni_growth*100:.1f}%")
                st.caption("הבדל ביניהם מעיד על השפעת רכישת המניות על הערך למחזיק המניה.")

            # 4. מודלים של שווי פנימי (Valuation)
            st.subheader("💎 חישוב שווי פנימי (Intrinsic Value)")
            
            # חישוב WACC פשוט
            risk_free = 0.042
            market_premium = 0.05
            beta = info.get('beta', 1.2)
            cost_of_equity = risk_free + (beta * market_premium)
            wacc = cost_of_equity # לצורך הפשטות במודל מהיר
            
            # א. מודל DCF
            growth_est = info.get('earningsGrowth', 0.10)
            if growth_est is None: growth_est = 0.1
            
            dcf_val = (fcf * (1 + growth_est)) / (wacc - 0.02)
            price_dcf = dcf_val / info.get('sharesOutstanding', 1)
            
            # ב. שיטת המכפילים
            price_relative = info.get('forwardPE', 20) * info.get('forwardEps', 5)
            
            # ג. שווי נכסי (NAV)
            price_nav = equity / info.get('sharesOutstanding', 1)

            # ד. מרווח ביטחון (Margin of Safety)
            final_fair_value = (price_dcf * 0.7 + price_relative * 0.3)
            mos_price = final_fair_value * 0.7 # 30% discount

            v_col1, v_col2 = st.columns(2)
            with v_col1:
                st.write("**פירוט חישובים:**")
                st.latex(r"WACC = R_f + \beta(R_m - R_f)")
                st.write(f"WACC: {wacc*100:.2f}% | Beta: {beta}")
                st.write(f"DCF Calculation: ({format_bn(fcf)} * {1+growth_est}) / ({wacc:.2f} - 0.02)")
            
            with v_col2:
                st.metric("שווי הוגן סופי (משוקלל)", f"${final_fair_value:.2f}")
                st.metric("מחיר קנייה (מרווח ביטחון 30%)", f"${mos_price:.2f}")

            # 5. ניתוח טכני וחדשות
            st.subheader("📈 ניתוח טכני וגרף")
            hist = ticker.history(period="1y")
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
            st.plotly_chart(fig, use_container_width=True)
            st.write("**ניתוח קצר:** לפי הגרף, יש לבדוק תמיכה בממוצע נע 50 יום. אם המחיר מעל הממוצע - מגמה חיובית.")

            # 6. Moat וסיכונים
            st.subheader("🏰 ניתוח Moat וסיכונים")
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("**סוגי Moat:**")
                st.write("1. יתרון לגודל (Cost Advantage)")
                st.write("2. אפקט רשת (Network Effect)")
                st.write("3. מותג חזק (Brand Loyalty)")
            with col_b:
                st.write("**גורמים משפיעים:**")
                st.markdown("- **ירידה:** עליית ריבית, תחרות מצד סין, רגולציה.")
                st.markdown("- **עליה:** אימוץ AI, שיפור במרווח התפעולי.")

            # 7. המלצה סופית ותחזיות
            st.divider()
            st.subheader("🎯 סיכום והמלצה")
            target = info.get('targetMeanPrice', 0)
            st.write(f"**תחזית אנליסטים (Yahoo):** ${target}")
            
            if info.get('currentPrice') < mos_price:
                st.success(f"המלצה: **קנייה חזקה** (מתחת למרווח ביטחון). מחיר יעד: ${target}")
            elif info.get('currentPrice') < final_fair_value:
                st.warning(f"המלצה: **קנייה זהירה** (קרוב לשווי הוגן).")
            else:
                st.error("המלצה: **המתנה** - המניה יקרה מדי כרגע.")

            st.subheader("📰 חדשות אחרונות")
            for n in ticker.news[:3]:
                st.write(f"- [{n['title']}]({n['link']})")

    except Exception as e:
        st.error(f"אירעה שגיאה: {e}")
    
     
