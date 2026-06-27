import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
from datetime import datetime

# הגדרות עמוד ותמיכה בעברית (RTL)
st.set_page_config(page_title="Professional Stock Deep-Dive", layout="wide")
st.markdown("""<style> .main { direction: rtl; text-align: right; } </style>""", unsafe_allow_html=True)

# פונקציות עזר לעיצוב
def fmt(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    return f"{val*100:.2f}%"

# --- מנוע משיכת נתונים ---
@st.cache_resource(ttl=3600)
def get_pro_data(symbol):
    t = Ticker(symbol, asynchronous=True)
    all_mods = t.all_modules[symbol]
    if isinstance(all_mods, str): return None, None, None, None
    
    # שליפת דוחות כספיים כ-DataFrames
    inc = t.income_statement().transpose()
    bal = t.balance_sheet().transpose()
    cf = t.cash_flow().transpose()
    return all_mods, inc, bal, cf

# --- ממשק משתמש ---
st.title("🛡️ Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, NVDA, TSLA):", "AMZN").upper()

if st.sidebar.button("הפק דוח אנליסט מלא"):
    with st.spinner(f"מנתח נתונים עמוקים עבור {symbol}..."):
        data, inc, bal, cf = get_pro_data(symbol)
        
        if not data:
            st.error("לא ניתן למשוך נתונים. Yahoo חוסמת את הבקשה או שהסימול שגוי.")
            st.stop()

        # חילוץ מודולים
        price_m = data.get('price', {})
        fin_m = data.get('financialData', {})
        stats_m = data.get('defaultKeyStatistics', {})
        summary_m = data.get('summaryProfile', {})

        # 1. תקציר כללי
        st.header(f"שם מניה: {price_m.get('longName')} ({symbol})")
        st.subheader(f"מחיר מניה כרגע: ${fin_m.get('currentPrice')}")
        
        last_date = inc.columns[-1].strftime('%Y-%m-%d')
        st.write(f"**תאריך דוח אחרון שנבדק:** {last_date}")
        st.info(f"**תקציר חברה:** {summary_m.get('longBusinessSummary', 'N/A')}")

        # 2. בדיקת 12 החוקים (באפטולוגיה)
        st.write("---")
        st.header("⚖️ סיכום 12 החוקים (באפטולוגיה)")
        
        # שליפת נתונים מדויקים מהדוחות
        last_is = inc[inc.columns[-1]]
        last_bs = bal[bal.columns[-1]]
        last_cf = cf[cf.columns[-1]]
        prev_bs = bal[bal.columns[-2]] if len(bal.columns) > 1 else last_bs
        
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
        
        laws = [
            ["1. מזומן > חוב", "✅" if cash > debt else "❌", f"C: {fmt(cash)} / D: {fmt(debt)}"],
            ["2. חוב להון < 0.8", "✅" if (debt/equity) < 0.8 else "❌", f"{(debt/equity):.2f}"],
            ["3. אין מניות בכורה", "✅" if 'PreferredStock' not in last_bs else "⚠️", "תקין"],
            ["4. רווחים צבורים בצמיחה", "✅" if retained > prev_bs.get('RetainedEarnings', 0) else "❌", fmt(retained)],
            ["5. מניות באוצר (Buybacks)", "✅" if 'RepurchaseOfCapitalStock' in last_cf else "⚪", "קיימת פעילות"],
            ["6. רווח גולמי > 40%", "✅" if (gp/rev) > 0.4 else "❌", pct(gp/rev)],
            ["7. הנהלה/גולמי < 30%", "✅" if (sga/gp) < 0.3 else "❌", pct(sga/gp)],
            ["8. מו\"פ/גולמי < 30%", "✅" if (rnd/gp) < 0.3 else "❌", pct(rnd/gp)],
            ["9. ריבית/תפעולי < 15%", "✅" if (int_exp/ebit) < 0.15 else "❌", pct(int_exp/ebit)],
            ["10. מס/לפני מס ~ 20%", "✅" if 0.15 < (tax/pretax) < 0.35 else "⚠️", pct(tax/pretax)],
            ["11. רווח נקי/הכנסות > 20%", "✅" if (ni/rev) > 0.2 else "❌", pct(ni/rev)],
            ["12. EPS בצמיחה", "✅" if stats_m.get('earningsGrowth', 0) > 0 else "❌", pct(stats_m.get('earningsGrowth', 0))]
        ]
        st.table(pd.DataFrame(laws, columns=["חוק", "מצב", "ערך נמדד"]))

        # 3. נתונים פיננסיים ו-Buybacks
        st.write("---")
        st.subheader("💰 נתונים פיננסיים וצמיחה")
        c1, c2 = st.columns(2)
        with c1:
            st.table(pd.DataFrame({
                "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומן", "חוב"],
                "ערך (B/M)": [fmt(rev), fmt(fin_m.get('ebitda')), fmt(ebit), fmt(ni), fmt(cash), fmt(debt)]
            }))
        with c2:
            buyback_amt = abs(last_cf.get('RepurchaseOfCapitalStock', 0))
            st.write(f"**Free Cash Flow (FCF):** {fmt(fin_m.get('freeCashflow'))}")
            st.write(f"**סכום מניות שנקנו בחזרה (Buyback):** {fmt(buyback_amt)}")
            
            ni_growth = (ni / inc[inc.columns[-2]].get('NetIncome', 1)) - 1 if len(inc.columns)>1 else 0
            eps_growth = stats_m.get('earningsQuarterlyGrowth', 0)
            st.write(f"**צמיחת רווח נקי:** {pct(ni_growth)} | **צמיחת EPS:** {pct(eps_growth)}")
            st.caption("פער לטובת ה-EPS מעיד על צמצום מניות אגרסיבי.")

        # 4. שווי פנימי (WACC & DCF)
        st.write("---")
        st.header("⚖️ חישוב שווי פנימי (Valuation)")
        
        # חישוב WACC שקוף
        rf = 0.043 # 10Y Treasury
        beta = fin_m.get('beta', 1.2) or 1.2
        erp = 0.055 
        cost_equity = rf + (beta * erp)
        cost_debt = (int_exp / debt) if debt > 0 else 0.05
        w_e = equity / (equity + debt)
        w_d = debt / (equity + debt)
        wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - 0.21))
        
        st.write("**פירוט חישוב WACC (ריבית היוון):**")
        st.latex(f"WACC = ({w_e:.2f} \\times {cost_equity*100:.1f}\\%) + ({w_d:.2f} \\times {cost_debt*100:.1f}\\% \\times 0.79) = {wacc*100:.2f}\\%")

        # DCF
        fcf = fin_m.get('freeCashflow', 1e9)
        g = stats_m.get('earningsGrowth', 0.1) or 0.1
        price_dcf = ((fcf * (1 + g)) / (wacc - 0.025)) / price_m.get('sharesOutstanding', 1)
        
        # מגרש כדורגל
        price_pe = (g*100 + 10) * stats_m.get('forwardEps', 5)
        price_nav = equity / price_m.get('sharesOutstanding', 1)
        
        st.subheader("🏈 מגרש כדורגל (Football Field)")
        st.table(pd.DataFrame({
            "שיטת הערכה": ["DCF (תזרים מזומנים)", "Relative (מכפילים)", "NAV (שווי נכסי)"],
            "שווי מוערך למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        }))

        # 5. ניתוח טכני וחדשות
        st.write("---")
        st.subheader("🏰 ניתוח Moat וטכני")
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            hist = t.history(period="1y").reset_index()
            fig = go.Figure(data=[go.Candlestick(x=hist['date'], open=hist['open'], high=hist['high'], low=hist['low'], close=hist['close'])])
            st.plotly_chart(fig, use_container_width=True)
        with col_t2:
            st.write("**סוגי Moat:** יתרון לגודל, מותג, עלויות מעבר.")
            st.write(f"**מחיר יעד אנליסטים:** ${fin_m.get('targetMeanPrice')}")
            st.write(f"**המלצה:** {fin_m.get('recommendationKey', 'N/A')}")

        st.subheader("📰 חדשות אחרונות")
        for n in t.news(3):
            st.write(f"- [{n['title']}]({n['link']})")

        # סיכום
        st.divider()
        final_intrinsic = (price_dcf * 0.7 + price_pe * 0.3)
        st.title(f"שווי פנימי סופי: ${final_intrinsic:.2f}")
        st.subheader(f"מחיר קנייה (מרווח ביטחון 30%): ${final_intrinsic * 0.7:.2f}")

except Exception as e:
    st.error(f"אירעה שגיאה: {e}")
