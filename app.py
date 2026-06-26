import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime

# הגדרות דף
st.set_page_config(layout="wide", page_title="Professional Stock Deep-Dive")

# --- פונקציות משיכת נתונים מ-Alpha Vantage ---
def get_data(symbol, function, api_key):
    url = f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={api_key}'
    r = requests.get(url)
    return r.json()

def fmt(val):
    try:
        v = float(val)
        if abs(v) >= 1e9: return f"${v/1e9:.2f}B"
        if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
        return f"${v:,.2f}"
    except: return "N/A"

# --- ממשק משתמש ---
st.title("🛡️ Financial Deep-Dive Pro (Alpha Vantage Edition)")
st.sidebar.info("כדי לעקוף חסימות, השתמש ב-API Key חינם מ-alphavantage.co")
api_key = st.sidebar.text_input("הכנס Alpha Vantage API Key:", type="password")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא") and api_key:
    try:
        with st.spinner("מושך נתונים פיננסיים עמוקים..."):
            # משיכת כל המודולים הנדרשים
            overview = get_data(symbol, 'OVERVIEW', api_key)
            income_stmt = get_data(symbol, 'INCOME_STATEMENT', api_key)
            balance_sheet = get_data(symbol, 'BALANCE_SHEET', api_key)
            cash_flow = get_data(symbol, 'CASH_FLOW', api_key)
            news = get_data(symbol, 'NEWS_SENTIMENT', api_key)
            
            if "Note" in overview:
                st.error("הגעת למכסה היומית של ה-API Key (בחינם זה 5 בקשות לדקה / 500 ליום).")
                st.stop()

            # נתונים מהדוחות האחרונים (Annual)
            is_last = income_stmt['annualReports'][0]
            bs_last = balance_sheet['annualReports'][0]
            cf_last = cash_flow['annualReports'][0]
            prev_is = income_stmt['annualReports'][1]
            prev_bs = balance_sheet['annualReports'][1]

            # --- חלק 1: פרטים כלליים ---
            st.header(f"שם מניה: {overview.get('Name')} ({symbol})")
            st.subheader(f"מחיר מניה (מכפיל נוכחי): {overview.get('PERatio')}")
            st.write(f"**תאריך דוח אחרון שנבדק:** {is_last.get('fiscalDateEnding')}")
            
            st.write("---")
            st.subheader("💡 תקציר על מה שהחברה עושה")
            st.write(overview.get('Description'))

            # --- חלק 2: בדיקת 12 החוקים ---
            st.header("⚖️ סיכום 12 החוקים (באפטולוגיה)")
            
            # משתנים לחישוב
            rev = float(is_last.get('totalRevenue', 0))
            gp = float(is_last.get('grossProfit', 0))
            ni = float(is_last.get('netIncome', 0))
            ebit = float(is_last.get('ebit', 1))
            int_exp = float(is_last.get('interestExpense', 0))
            sga = float(is_last.get('sellingGeneralAndAdministrative', 0))
            rnd = float(is_last.get('researchAndDevelopment', 0))
            pretax = float(is_last.get('incomeBeforeTax', 1))
            tax = float(is_last.get('incomeTaxExpense', 0))
            
            cash = float(bs_last.get('cashAndCashEquivalentsAtCarryingValue', 0))
            debt = float(bs_last.get('totalDebt', 0))
            equity = float(bs_last.get('totalShareholderEquity', 1))
            liabilities = float(bs_last.get('totalLiabilities', 0))
            retained = float(bs_last.get('retainedEarnings', 0))
            prev_retained = float(prev_bs.get('retainedEarnings', 0))
            
            laws = [
                ["מזומן > חוב", "✅" if cash > debt else "❌", f"C: {fmt(cash)} / D: {fmt(debt)}"],
                ["יחס חוב להון < 0.8", "✅" if (liabilities/equity) < 0.8 else "❌", f"{(liabilities/equity):.2f}"],
                ["אין מניות בכורה", "✅" if float(bs_last.get('preferredStock', 0)) == 0 else "⚠️", "תקין"],
                ["רווחים צבורים בצמיחה", "✅" if retained > prev_retained else "❌", f"צמיחה: {fmt(retained-prev_retained)}"],
                ["מניות באוצר (Buybacks)", "✅" if float(bs_last.get('treasuryStock', 1)) != 0 else "⚪", "קיימת פעילות"],
                ["רווח גולמי > 40%", "✅" if (gp/rev) > 0.4 else "❌", f"{(gp/rev)*100:.1f}%"],
                ["הנהלה/גולמי < 30%", "✅" if (sga/gp) < 0.3 else "❌", f"{(sga/gp)*100:.1f}%"],
                ["מו\"פ/גולמי < 30%", "✅" if (rnd/gp) < 0.3 else "❌", f"{(rnd/gp)*100:.1f}%"],
                ["ריבית/רווח תפעולי < 15%", "✅" if (int_exp/ebit) < 0.15 else "❌", f"{(int_exp/ebit)*100:.1f}%"],
                ["מס הכנסה/לפני מס ~ 20%", "✅" if 0.15 < (tax/pretax) < 0.3 else "⚠️", f"{(tax/pretax)*100:.1f}%"],
                ["רווח נקי/הכנסות > 20%", "✅" if (ni/rev) > 0.2 else "❌", f"{(ni/rev)*100:.1f}%"],
                ["צמיחת EPS (שנתי)", "✅" if float(overview.get('EPS', 0)) > 0 else "❌", overview.get('EPS')]
            ]
            st.table(pd.DataFrame(laws, columns=["חוק", "מצב", "נתון"]))

            # --- חלק 3: טבלאות וצמיחה ---
            st.subheader("📊 סיכום פיננסי וצמיחה")
            fcf = float(cf_last.get('operatingCashflow', 0)) - float(cf_last.get('capitalExpenditures', 0))
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**נתוני רווח (מיליארדים):**")
                st.table(pd.DataFrame({
                    "מדד": ["הכנסות", "רווח תפעולי", "רווח נקי", "FCF", "מזומן", "חוב"],
                    "ערך": [fmt(rev), fmt(ebit), fmt(ni), fmt(fcf), fmt(cash), fmt(debt)]
                }))
            
            with c2:
                ni_growth = (ni / float(prev_is.get('netIncome', 1))) - 1
                buyback_shares = float(cf_last.get('paymentsForRepurchaseOfCommonStock', 0))
                st.write("**ניתוח צמיחה:**")
                st.write(f"- צמיחת רווח נקי: {ni_growth*100:.1f}%")
                st.write(f"- סכום רכישה עצמית: {fmt(buyback_shares)}")
                st.write(f"- מכפיל רווח (P/E): {overview.get('PERatio')}")

            # --- חלק 4: שווי פנימי (DCF & WACC) ---
            st.write("---")
            st.header("⚖️ חישוב שווי פנימי")
            
            # WACC Calculation
            beta = float(overview.get('Beta', 1.2))
            rf = 0.043 # 10Y Treasury
            erp = 0.055 # Risk Premium
            cost_equity = rf + (beta * erp)
            cost_debt = (int_exp / debt) if debt > 0 else 0.05
            w_e = equity / (equity + debt)
            w_d = debt / (equity + debt)
            wacc = (w_e * cost_equity) + (w_d * cost_debt * 0.79)
            
            st.subheader("1. פירוט WACC (ריבית היוון)")
            st.code(f"Cost Equity = {cost_equity*100:.2f}% | WACC = {wacc*100:.2f}%")
            
            # DCF
            growth = float(overview.get('QuarterlyEarningsGrowthYOY', 0.1))
            if growth == 0: growth = 0.1
            intrinsic_dcf = ((fcf * (1 + growth)) / (wacc - 0.025)) / float(overview.get('SharesOutstanding', 1))
            
            # Football Field
            price_pe = float(overview.get('ForwardPE', 20)) * float(overview.get('EPS', 5))
            price_nav = equity / float(overview.get('SharesOutstanding', 1))
            
            st.subheader("2. מגרש כדורגל (Football Field Valuation)")
            football = pd.DataFrame({
                "שיטה": ["DCF", "מכפילים (Forward P/E)", "שווי נכסי (NAV)"],
                "שווי למניה": [f"${intrinsic_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
            })
            st.table(football)

            final_val = (intrinsic_dcf * 0.7 + price_pe * 0.3)
            st.title(f"שווי פנימי סופי מוערך: ${final_val:.2f}")
            st.subheader(f"מחיר קנייה (מרווח ביטחון 30%): ${final_val * 0.7:.2f}")

            # --- חלק 5: חדשות ו-Moat ---
            st.write("---")
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("🏰 ניתוח Moat")
                st.write(f"- חברה מסוג: {overview.get('Industry')}")
                st.write("- יתרונות: מותג, אפקט רשת, יתרון לגודל.")
            with col_b:
                st.subheader("📰 חדשות עדכניות")
                for article in news.get('feed', [])[:3]:
                    st.write(f"- [{article['title']}]({article['url']})")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הנתונים: {e}")
else:
    if not api_key:
        st.warning("אנא הכנס API Key של Alpha Vantage (בחינם) כדי להתחיל.")
