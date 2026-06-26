import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
import time

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Analyzer PRO")

# פונקציית עזר להמרת מספרים
def fmt(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

st.title("📊 Financial Deep-Dive Pro (Anti-Block Version)")
st.write("מערכת ניתוח מניות מתקדמת - עוקפת חסימות Yahoo")

symbol = st.sidebar.text_input("הכנס סימול מניה (למשל TSLA, NVDA, AAPL):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    try:
        with st.spinner(f"מתחבר לשרתי הנתונים עבור {symbol}..."):
            # שימוש ב-yahooquery - היא הרבה יותר יציבה מ-yfinance בשרתי ענן
            t = Ticker(symbol, asynchronous=True)
            
            # משיכת מודולים ספציפיים (יותר יעיל ופחות סיכוי לחסימה)
            modules = t.all_modules[symbol]
            
            if isinstance(modules, str):
                st.error(f"שגיאה מהשרת: {modules}. נסה שוב בעוד דקה.")
                st.stop()

            # חילוץ נתונים למשתנים
            summary = modules.get('summaryProfile', {})
            price = modules.get('price', {})
            fin_data = modules.get('financialData', {})
            stats = modules.get('defaultKeyStatistics', {})
            
            # דוחות כספיים (עבור 12 החוקים)
            # yahooquery מחזירה DataFrame בצורה נוחה
            inc_df = t.income_statement().transpose()
            bs_df = t.balance_sheet().transpose()
            cf_df = t.cash_flow().transpose()

            # 1. תקציר חברה
            st.header(f"{price.get('longName', symbol)} | {price.get('quoteType', 'Stock')}")
            c1, c2, c3 = st.columns(3)
            curr_p = fin_data.get('currentPrice', 0)
            c1.metric("מחיר מניה", f"${curr_p}")
            c2.metric("שווי שוק", fmt(price.get('marketCap')))
            c3.metric("מגזר", summary.get('sector', 'N/A'))
            
            st.info(f"**תקציר:** {summary.get('longBusinessSummary', 'אין תקציר זמין.')[:600]}...")

            # 2. בדיקת 12 החוקים
            st.subheader("🛡️ בדיקת 12 החוקים (באפטולוגיה)")
            
            # נתונים מהדוחות (מטפלים במקרה שהדוח ריק)
            try:
                # לוקחים את העמודה האחרונה (השנה הכי עדכנית)
                last_is = inc_df[inc_df.columns[-1]]
                last_bs = bs_df[bs_df.columns[-1]]
                last_cf = cf_df[cf_df.columns[-1]]
                
                rev = last_is.get('TotalRevenue', 1)
                gp = last_is.get('GrossProfit', 0)
                ni = last_is.get('NetIncome', 0)
                ebit = last_is.get('Ebit', 1)
                int_exp = abs(last_is.get('InterestExpense', 0))
                sga = last_is.get('SellingGeneralAdministrative', 0)
                rnd = last_is.get('ResearchDevelopment', 0)
                
                cash = last_bs.get('CashAndCashEquivalents', 0)
                debt = last_bs.get('TotalDebt', 0)
                equity = last_bs.get('StockholdersEquity', 1)
                retained = last_bs.get('RetainedEarnings', 0)
                
                rules = [
                    {"חוק": "מזומן > חוב", "מצב": "✅" if cash > debt else "❌", "ערך": f"C: {fmt(cash)} / D: {fmt(debt)}"},
                    {"חוק": "חוב/הון < 0.8", "מצב": "✅" if (debt/equity) < 0.8 else "❌", "ערך": f"{(debt/equity):.2f}"},
                    {"חוק": "רווח גולמי > 40%", "מצב": "✅" if (gp/rev) > 0.4 else "❌", "ערך": f"{(gp/rev)*100:.1f}%"},
                    {"חוק": "הנהלה/גולמי < 30%", "מצב": "✅" if (sga/gp) < 0.3 else "❌", "ערך": f"{(sga/gp)*100:.1f}%"},
                    {"חוק": "מו\"פ/גולמי < 30%", "מצב": "✅" if (rnd/gp) < 0.3 else "❌", "ערך": f"{(rnd/gp)*100:.1f}%"},
                    {"חוק": "ריבית/רווח תפעולי < 15%", "מצב": "✅" if (int_exp/ebit) < 0.15 else "❌", "ערך": f"{(int_exp/ebit)*100:.1f}%"},
                    {"חוק": "רווח נקי/הכנסות > 20%", "מצב": "✅" if (ni/rev) > 0.2 else "❌", "ערך": f"{(ni/rev)*100:.1f}%"},
                    {"חוק": "רווחים צבורים בצמיחה", "מצב": "✅" if retained > bs_df[bs_df.columns[-2]].get('RetainedEarnings', 0) else "❌", "ערך": fmt(retained)},
                    {"חוק": "רכישת מניות (Buybacks)", "מצב": "✅" if 'RepurchaseOfCapitalStock' in last_cf else "⚪", "ערך": "קיים בדוח"},
                    {"חוק": "EPS בצמיחה", "מצב": "✅" if stats.get('earningsQuarterlyGrowth', 0) > 0 else "❌", "ערך": f"{stats.get('earningsQuarterlyGrowth', 0)*100:.1f}%"}
                ]
                st.table(pd.DataFrame(rules))
            except:
                st.warning("חלק מנתוני הדוחות חסרים ב-Yahoo כרגע, מציג ניתוח חלקי.")

            # 3. הערכת שווי (WACC & DCF)
            st.subheader("⚖️ מודל הערכת שווי פנימי")
            
            # חישוב WACC
            beta = fin_data.get('beta', 1.2) or 1.2
            rf = 0.043 # ריבית 10 שנים
            erp = 0.055 # פרמיית סיכון
            cost_equity = rf + (beta * erp)
            cost_debt = (int_exp / debt) if debt > 0 else 0.05
            w_e = equity / (equity + debt)
            w_d = debt / (equity + debt)
            wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - 0.21))
            
            fcf = fin_data.get('freeCashflow') or (ni * 1.1) # הערכה אם חסר
            growth = stats.get('earningsGrowth', 0.1) or 0.1
            
            # DCF
            price_dcf = ((fcf * (1 + growth)) / (wacc - 0.025)) / price.get('sharesOutstanding', 1)
            # מכפילים
            price_pe = fin_data.get('forwardPE', 20) * stats.get('forwardEps', 5)
            
            st.write(f"**נתוני מודל:** WACC: {wacc*100:.2f}%, צמיחה: {growth*100:.1f}%")
            
            # "מגרש כדורגל"
            football = pd.DataFrame({
                "שיטה": ["DCF (תזרים מזומנים)", "Relative (מכפילים)", "NAV (שווי נכסי)"],
                "מחיר למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${equity/price.get('sharesOutstanding',1):.2f}"]
            })
            st.table(football)

            # 4. המלצה סופית
            fair_value = (price_dcf * 0.7 + price_pe * 0.3)
            mos = fair_value * 0.7
            
            st.divider()
            res1, res2, res3 = st.columns(3)
            res1.metric("שווי הוגן סופי", f"${fair_value:.2f}")
            res2.metric("מחיר קנייה (30% MOS)", f"${mos:.2f}")
            res3.metric("מחיר יעד אנליסטים", f"${fin_data.get('targetMeanPrice', 'N/A')}")

            # 5. גרף טכני (Plotly)
            st.subheader("📈 גרף מחיר שנה אחרונה")
            history = t.history(period="1y")
            if not history.empty:
                # yahooquery מחזירה MultiIndex, אנחנו צריכים לסדר אותו
                history = history.reset_index()
                fig = go.Figure(data=[go.Candlestick(x=history['date'],
                                open=history['open'], high=history['high'],
                                low=history['low'], close=history['close'])])
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"שגיאה כללית: {e}. שרתי הנתונים עמוסים, נסה שוב בעוד מספר רגעים.")
