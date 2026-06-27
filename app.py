import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

# הגדרות דף
st.set_page_config(layout="wide", page_title="Professional Stock Deep-Dive")

# פונקציית המרה בטוחה למניעת קריסות
def safe_float(val, default=0.0):
    try:
        if val is None or val == "None" or val == "":
            return default
        return float(val)
    except:
        return default

def fmt(val):
    try:
        v = float(val)
        if abs(v) >= 1e9: return f"${v/1e9:.2f}B"
        if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
        return f"${v:,.2f}"
    except:
        return "N/A"

# שימוש ב-Cache למניעת חסימות ה-API של Alpha Vantage
@st.cache_data(ttl=3600)
def get_cached_data(symbol, function, api_key):
    url = f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={api_key}'
    try:
        r = requests.get(url)
        data = r.json()
        return data
    except Exception as e:
        return {"Error": str(e)}

# --- ממשק משתמש ---
st.title("🛡️ Financial Deep-Dive Pro (Alpha Vantage Optimized)")
st.sidebar.info("כדי לעקוף חסימות, האפליקציה שומרת את הנתונים בזיכרון המטמון לשעה.")
api_key = st.sidebar.text_input("הכנס Alpha Vantage API Key:", type="password")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא") and api_key:
    try:
        with st.spinner("מושך נתונים פיננסיים ומנתח..."):
            # משיכת נתונים מוגנת ב-Cache
            overview = get_cached_data(symbol, 'OVERVIEW', api_key)
            
            if "Note" in overview or "Information" in overview:
                st.error("הגעת למכסה של ה-API Key. אנא המתן דקה או השתמש במפתח אחר.")
                st.stop()
                
            income_stmt = get_cached_data(symbol, 'INCOME_STATEMENT', api_key)
            balance_sheet = get_cached_data(symbol, 'BALANCE_SHEET', api_key)
            cash_flow = get_cached_data(symbol, 'CASH_FLOW', api_key)
            news = get_cached_data(symbol, 'NEWS_SENTIMENT', api_key)

            # חילוץ דוחות
            is_last = income_stmt.get('annualReports', [{}])[0]
            bs_last = balance_sheet.get('annualReports', [{}])[0]
            cf_last = cash_flow.get('annualReports', [{}])[0]
            prev_is = income_stmt.get('annualReports', [{}, {}])[1]
            prev_bs = balance_sheet.get('annualReports', [{}, {}])[1]

            # --- חלק 1: פרטים כלליים ---
            st.header(f"שם מניה: {overview.get('Name', symbol)} ({symbol})")
            st.subheader(f"מכפיל רווח נוכחי (P/E): {overview.get('PERatio', 'N/A')}")
            st.write(f"**תאריך דוח אחרון שנבדק:** {is_last.get('fiscalDateEnding', 'N/A')}")
            
            st.write("---")
            st.subheader("💡 תקציר על מה שהחברה עושה")
            st.write(overview.get('Description', 'אין תיאור זמין'))

            # --- חלק 2: בדיקת 12 החוקים ---
            st.header("⚖️ סיכום 12 החוקים (באפטולוגיה)")
            
            rev = safe_float(is_last.get('totalRevenue'))
            gp = safe_float(is_last.get('grossProfit'))
            ni = safe_float(is_last.get('netIncome'))
            ebit = safe_float(is_last.get('ebit', 1.0))
            int_exp = safe_float(is_last.get('interestExpense'))
            sga = safe_float(is_last.get('sellingGeneralAndAdministrative'))
            rnd = safe_float(is_last.get('researchAndDevelopment'))
            pretax = safe_float(is_last.get('incomeBeforeTax', 1.0))
            tax = safe_float(is_last.get('incomeTaxExpense'))
            
            cash = safe_float(bs_last.get('cashAndCashEquivalentsAtCarryingValue')) + safe_float(bs_last.get('shortTermInvestments'))
            debt = safe_float(bs_last.get('shortLongTermDebtTotal')) or safe_float(bs_last.get('longTermDebt', 0))
            equity = safe_float(bs_last.get('totalShareholderEquity', 1.0))
            liabilities = safe_float(bs_last.get('totalLiabilities'))
            retained = safe_float(bs_last.get('retainedEarnings'))
            prev_retained = safe_float(prev_bs.get('retainedEarnings'))
            
            laws = [
                ["מזומן > חוב", "✅" if cash > debt else "❌", f"C: {fmt(cash)} / D: {fmt(debt)}"],
                ["יחס חוב להון < 0.8", "✅" if equity > 0 and (liabilities/equity) < 0.8 else "❌", f"{(liabilities/equity):.2f}" if equity > 0 else "N/A"],
                ["אין מניות בכורה", "✅" if safe_float(bs_last.get('preferredStock')) == 0 else "⚠️", "תקין"],
                ["רווחים צבורים בצמיחה", "✅" if retained > prev_retained else "❌", f"צמיחה: {fmt(retained-prev_retained)}"],
                ["רווח גולמי > 40%", "✅" if rev > 0 and (gp/rev) > 0.4 else "❌", f"{(gp/rev)*100:.1f}%" if rev > 0 else "N/A"],
                ["הנהלה/גולמי < 30%", "✅" if gp > 0 and (sga/gp) < 0.3 else "❌", f"{(sga/gp)*100:.1f}%" if gp > 0 else "N/A"],
                ["מו\"פ/גולמי < 30%", "✅" if gp > 0 and (rnd/gp) < 0.3 else "❌", f"{(rnd/gp)*100:.1f}%" if gp > 0 else "N/A"],
                ["ריבית/רווח תפעולי < 15%", "✅" if ebit > 0 and (int_exp/ebit) < 0.15 else "❌", f"{(int_exp/ebit)*100:.1f}%" if ebit > 0 else "N/A"],
                ["רווח נקי/הכנסות > 20%", "✅" if rev > 0 and (ni/rev) > 0.2 else "❌", f"{(ni/rev)*100:.1f}%" if rev > 0 else "N/A"]
            ]
            st.table(pd.DataFrame(laws, columns=["חוק", "מצב", "נתון"]))

            # --- חלק 3: טבלאות וצמיחה ---
            st.subheader("📊 סיכום פיננסי וצמיחה")
            fcf = safe_float(cf_last.get('operatingCashflow')) - safe_float(cf_last.get('capitalExpenditures'))
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**נתוני מפתח:**")
                st.table(pd.DataFrame({
                    "מדד": ["הכנסות", "רווח תפעולי", "רווח נקי", "FCF", "מזומן", "חוב"],
                    "ערך": [fmt(rev), fmt(ebit), fmt(ni), fmt(fcf), fmt(cash), fmt(debt)]
                }))
            
            with c2:
                prev_ni = safe_float(prev_is.get('netIncome', 1.0))
                ni_growth = (ni / prev_ni) - 1 if prev_ni != 0 else 0
                buyback_shares = safe_float(cf_last.get('paymentsForRepurchaseOfCommonStock'))
                st.write("**ניתוח צמיחה מנורמל:**")
                st.write(f"- צמיחת רווח נקי שנתי: {ni_growth*100:.1f}%")
                st.write(f"- סכום רכישה עצמית (Buybacks): {fmt(buyback_shares)}")

            # --- חלק 4: שווי פנימי (DCF) ---
            st.write("---")
            st.header("⚖️ חישוב שווי פנימי וריבית היוון")
            
            beta = safe_float(overview.get('Beta', 1.2))
            rf, erp = 0.043, 0.055
            cost_equity = rf + (beta * erp)
            cost_debt = (int_exp / debt) if debt > 0 else 0.05
            wacc = (cost_equity * 0.85) + (cost_debt * 0.15 * 0.79)
            
            st.code(f"Cost of Equity: {cost_equity*100:.2f}% | WACC: {wacc*100:.2f}%")
            
            growth = safe_float(overview.get('QuarterlyEarningsGrowthYOY', 0.1))
            growth = max(0.05, min(growth, 0.20)) # הגבלה לטווח הגיוני של 5%-20%
            
            shares = safe_float(overview.get('SharesOutstanding', 1.0))
            if shares > 0 and (wacc - 0.025) > 0:
                intrinsic_dcf = ((fcf * (1 + growth)) / (wacc - 0.025)) / shares
            else:
                intrinsic_dcf = 0
                
            price_pe = safe_float(overview.get('ForwardPE', 20)) * safe_float(overview.get('EPS', 5))
            price_nav = equity / shares if shares > 0 else 0
            
            football = pd.DataFrame({
                "שיטה": ["DCF (תזרים מהוון)", "מכפילים (Forward P/E)", "שווי נכסי (NAV)"],
                "שווי למניה": [f"${intrinsic_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
            })
            st.table(football)

            final_val = (intrinsic_dcf * 0.6 + price_pe * 0.4)
            st.title(f"שווי פנימי סופי מוערך: ${final_val:.2f}")
            st.subheader(f"מחיר קנייה מבוקש (מרווח ביטחון 30%): ${final_val * 0.7:.2f}")

    except Exception as e:
        st.error(f"שגיאה בעיבוד הנתונים: {e}")
