import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
from datetime import datetime

# הגדרות עמוד ותצוגה
st.set_page_config(page_title="Professional Stock Deep-Dive", layout="wide")
st.markdown("""<style> .main { direction: rtl; text-align: right; } </style>""", unsafe_allow_html=True)

# פונקציות עזר לעיצוב נתונים
def fmt(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    return f"{val*100:.2f}%"

# פונקציה למשיכת נתונים (עמידה בשרתים חיצוניים)
@st.cache_resource(ttl=3600)
def get_stock_data_pro(symbol):
    t = Ticker(symbol, asynchronous=True)
    all_mods = t.all_modules[symbol]
    if isinstance(all_mods, str): return None, None, None, None, None
    
    # שליפת דוחות
    inc = t.income_statement().transpose()
    bal = t.balance_sheet().transpose()
    cf = t.cash_flow().transpose()
    return t, all_mods, inc, bal, cf

# --- ממשק משתמש ---
st.title("🛡️ Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, NVDA, AAPL):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    try: # הבלוק שמתקן את שגיאת ה-Syntax
        with st.spinner(f"מנתח נתונים עמוקים עבור {symbol}..."):
            t_obj, data, inc, bal, cf = get_stock_data_pro(symbol)
            
            if not data or inc.empty:
                st.error("לא ניתן למשוך נתונים. בדוק את הסימול או נסה שוב בעוד דקה.")
                st.stop()

            # חילוץ מודולים
            price_m = data.get('price', {})
            fin_m = data.get('financialData', {})
            stats_m = data.get('defaultKeyStatistics', {})
            summary_m = data.get('summaryProfile', {})

            # --- 1. פרטים כלליים ---
            st.header(f"שם מניה: {price_m.get('longName')} ({symbol})")
            st.subheader(f"מחיר מניה כרגע: ${fin_m.get('currentPrice')}")
            
            last_report_date = inc.columns[-1].strftime('%d/%m/%Y')
            st.write(f"**תאריכי הדוחות שאנחנו בודקים:** {last_report_date} (דוח אחרון)")
            
            st.write("---")
            st.subheader("💡 תקציר על מה שהחברה עושה")
            st.write(summary_m.get('longBusinessSummary', 'N/A'))

            # --- 2. בדיקת 12 החוקים (באפטולוגיה) ---
            st.write("---")
            st.header("⚖️ סיכום 12 החוקים של באפטולוגיה")
            
            last_is = inc[inc.columns[-1]]
            last_bs = bal[bal.columns[-1]]
            last_cf = cf[cf.columns[-1]]
            prev_bs = bal[bal.columns[-2]] if len(bal.columns) > 1 else last_bs
            prev_is = inc[inc.columns[-2]] if len(inc.columns) > 1 else last_is

            # חישובי באפטולוגיה
            rev = last_is.get('TotalRevenue', 1)
            gp = last_is.get('GrossProfit', 0)
            ni = last_is.get('NetIncome', 0)
            ebit = last_is.get('Ebit', 1)
            int_exp = abs(last_is.get('InterestExpense', 0))
            sga = last_is.get('SellingGeneralAdministrative', 0)
            rnd = last_is.get('ResearchDevelopment', 0)
            pretax = last_is.get('PretaxIncome', 1)
            tax = abs(last_is.get('TaxProvision', 0))
            
            cash = last_bs.get('CashAndCashEquivalents', 0)
            debt = last_bs.get('TotalDebt', 0)
            equity = last_bs.get('StockholdersEquity', 1)
            retained = last_bs.get('RetainedEarnings', 0)
            
            laws_data = [
                ["1. מזומן > חוב", "✅" if cash > debt else "❌", f"C: {fmt(cash)} / D: {fmt(debt)}"],
                ["2. יחס חוב להון < 0.8", "✅" if (debt/equity) < 0.8 else "❌", f"{(debt/equity):.2f}"],
                ["3. אין מניות בכורה", "✅" if 'PreferredStock' not in last_bs else "⚠️", "תקין"],
                ["4. רווחים צבורים בצמיחה", "✅" if retained > prev_bs.get('RetainedEarnings', 0) else "❌", f"נוכחי: {fmt(retained)}"],
                ["5. מניות באוצר (Buybacks)", "✅" if 'RepurchaseOfCapitalStock' in last_cf else "⚪", "קיימת פעילות"],
                ["6. רווח גולמי > 40%", "✅" if (gp/rev) > 0.4 else "❌", pct(gp/rev)],
                ["7. הנהלה וכלליות / גולמי < 30%", "✅" if (sga/gp) < 0.3 else "❌", pct(sga/gp)],
                ["8. מו\"פ / גולמי < 30%", "✅" if (rnd/gp) < 0.3 else "❌", pct(rnd/gp)],
                ["9. ריבית / רווח תפעולי < 15%", "✅" if (int_exp/ebit) < 0.15 else "❌", pct(int_exp/ebit)],
                ["10. מס הכנסה תקין (~20%)", "✅" if 0.15 < (tax/pretax) < 0.35 else "⚠️", pct(tax/pretax)],
                ["11. רווח נקי / הכנסות > 20%", "✅" if (ni/rev) > 0.2 else "❌", pct(ni/rev)],
                ["12. EPS במגמת צמיחה", "✅" if stats_m.get('earningsGrowth', 0) > 0 else "❌", pct(stats_m.get('earningsGrowth', 0))]
            ]
            st.table(pd.DataFrame(laws_data, columns=["חוק", "מצב", "נתון נמדד"]))

            # --- 3. טבלאות פיננסיות וצמיחה ---
            st.write("---")
            st.subheader("📊 נתונים פיננסיים (מיליארדים)")
            c1, c2 = st.columns(2)
            with c1:
                st.table(pd.DataFrame({
                    "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומן", "חוב"],
                    "ערך": [fmt(rev), fmt(fin_m.get('ebitda')), fmt(ebit), fmt(ni), fmt(cash), fmt(debt)]
                }))
            with c2:
                buyback_val = abs(last_cf.get('RepurchaseOfCapitalStock', 0))
                st.write(f"**Free Cash Flow (FCF):** {fmt(fin_m.get('freeCashflow'))}")
                st.write(f"**כמות מניות שנקנו בחזרה בדוח זה:** {fmt(buyback_val)}")
                
                ni_growth = (ni / prev_is.get('NetIncome', 1)) - 1 if len(inc.columns)>1 else 0
                eps_growth = stats_m.get('earningsQuarterlyGrowth', 0)
                st.write(f"**צמיחת רווח נקי:** {pct(ni_growth)} | **צמיחת EPS:** {pct(eps_growth)}")
                st.info("💡 פער שבו ה-EPS גדל מהר יותר מהרווח הנקי מעיד על רכישת מניות חזקה שמעלה את ערך המניה.")

            # --- 4. ניתוח Moat וחלוקת רווחים ---
            st.write("---")
            st.subheader("🏰 ניתוח Moat (חפיר כלכלי)")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.write("**סוגי Moat פוטנציאליים:**")
                st.markdown("- **יתרון לגודל:** יכולת ייצור והפצה מאסיבית.")
                st.markdown("- **מותג חזק:** כוח תמחור המשתקף ברווח הגולמי.")
                st.markdown("- **עלויות מעבר:** לקוחות המחוברים לאקו-סיסטם של החברה.")
            with col_m2:
                st.write(f"**ממה החברה מרוויחה (מגזר):** {summary_m.get('sector')}")
                st.write(f"**תעשייה:** {summary_m.get('industry')}")

            # --- 5. הערכת שווי (Valuation) ---
            st.write("---")
            st.header("⚖️ חישוב שווי פנימי")
            
            # WACC שקוף
            rf = 0.043 
            beta = fin_m.get('beta', 1.1) or 1.1
            erp = 0.055
            cost_equity = rf + (beta * erp)
            cost_debt = (int_exp / debt) if debt > 0 else 0.05
            w_e = equity / (equity + debt)
            w_d = debt / (equity + debt)
            wacc = (w_e * cost_equity) + (w_d * cost_debt * 0.79)
            
            st.write("**פירוט חישוב WACC (ריבית היוון):**")
            st.latex(f"WACC = ({w_e:.2f} \\times {cost_equity*100:.1f}\\%) + ({w_d:.2f} \\times {cost_debt*100:.1f}\\% \\times 0.79) = {wacc*100:.2f}\\%")

            # DCF
            fcf_val = fin_m.get('freeCashflow', 1e9)
            growth = stats_m.get('earningsGrowth', 0.1) or 0.1
            price_dcf = ((fcf_val * (1 + growth)) / (wacc - 0.025)) / price_m.get('sharesOutstanding', 1)
            
            # Relative
            price_pe = (growth * 100 + 10) * stats_m.get('forwardEps', 5)
            price_nav = equity / price_m.get('sharesOutstanding', 1)

            st.subheader("🏈 מגרש כדורגל (Football Field Valuation)")
            st.table(pd.DataFrame({
                "שיטת הערכה": ["DCF (תזרים מזומנים)", "Relative (מכפילים)", "NAV (שווי נכסי)"],
                "מחיר מוערך למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
            }))

            final_val = (price_dcf * 0.7 + price_pe * 0.3)
            st.title(f"שווי פנימי סופי: ${final_val:.2f}")
            st.subheader(f"מחיר קנייה (מרווח ביטחון 30%): ${final_val * 0.7:.2f}")

            # --- 6. ניתוח טכני ותחזיות ---
            st.write("---")
            st.subheader("📈 ניתוח טכני ותחזיות אנליסטים")
            hist = t_obj.history(period="1y").reset_index()
            fig = go.Figure(data=[go.Candlestick(x=hist['date'], open=hist['open'], high=hist['high'], low=hist['low'], close=hist['close'])])
            st.plotly_chart(fig, use_container_width=True)
            
            st.write(f"**מחיר יעד ממוצע (אנליסטים):** ${fin_m.get('targetMeanPrice')}")
            st.write(f"**המלצה כללית:** {fin_m.get('recommendationKey', 'N/A')}")
            
            st.subheader("📰 חדשות עדכניות")
            for n in t_obj.news(3):
                st.write(f"- [{n['title']}]({n['link']})")

    except Exception as e:
        st.error(f"אירעה שגיאה בעיבוד הנתונים: {e}")
        st.info("טיפ: אם Yahoo חוסמת, נסה שוב בעוד דקה.")
