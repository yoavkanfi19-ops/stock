import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
import time

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Pro Analyzer")

# פונקציית עזר להמרת מספרים גדולים
def format_val(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

st.title("📊 Financial Deep-Dive Pro")
st.markdown("---")

symbol = st.sidebar.text_input("הכנס סימול מניה (למשל TSLA, AMZN, AAPL):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f"מושך נתונים עבור {symbol}... (זה עשוי לקחת כמה שניות)"):
        # שימוש ב-yahooquery במקום yfinance לעקיפת חסימות IP
        t = Ticker(symbol)
        
        # משיכת כל הנתונים הנדרשים במכה אחת
        all_data = t.all_modules[symbol]
        
        if isinstance(all_data, str): # אם Yahoo החזירה שגיאה
            st.error(f"שגיאה מ-Yahoo Finance: {all_data}")
            st.stop()

        # חילוץ נתונים למשתנים נוחים
        summary = all_data.get('summaryProfile', {})
        price = all_data.get('price', {})
        fin = all_data.get('financialData', {})
        stats = all_data.get('defaultKeyStatistics', {})
        
        # דוחות (בשביל ה-12 חוקים)
        income_df = t.income_statement()
        balance_df = t.balance_sheet()
        cashflow_df = t.cash_flow()

        # 1. תקציר חברה
        st.header(f"{price.get('longName')} ({symbol})")
        col1, col2, col3 = st.columns(3)
        col1.metric("מחיר נוכחי", f"${fin.get('currentPrice')}")
        col2.metric("שווי שוק", format_val(price.get('marketCap')))
        col3.metric("מגזר", summary.get('sector', 'N/A'))
        
        st.info(f"**תקציר:** {summary.get('longBusinessSummary', 'אין תקציר זמין.')[:500]}...")

        # 2. בדיקת 12 החוקים
        st.subheader("🛡️ בדיקת 12 החוקים הפיננסיים")
        
        try:
            # נתונים מהדוח האחרון
            last_income = income_df.iloc[-1]
            last_balance = balance_df.iloc[-1]
            last_cf = cashflow_df.iloc[-1]
            
            rev = last_income.get('TotalRevenue', 1)
            gp = last_income.get('GrossProfit', 0)
            ni = last_income.get('NetIncome', 0)
            ebit = last_income.get('Ebit', 1)
            int_exp = abs(last_income.get('InterestExpense', 0))
            sga = last_income.get('SellingGeneralAdministrative', 0)
            rnd = last_income.get('ResearchDevelopment', 0)
            pretax = last_income.get('PretaxIncome', 1)
            tax = abs(last_income.get('TaxProvision', 0))
            
            cash = last_balance.get('CashAndCashEquivalents', 0)
            debt = last_balance.get('TotalDebt', 0)
            equity = last_balance.get('StockholdersEquity', 1)
            retained = last_balance.get('RetainedEarnings', 0)
            
            rules = [
                {"חוק": "מזומן > חוב", "מצב": "✅" if cash > debt else "❌", "ערך": f"C: {format_val(cash)} / D: {format_val(debt)}"},
                {"חוק": "יחס חוב להון < 0.8", "מצב": "✅" if (debt/equity) < 0.8 else "❌", "ערך": f"{(debt/equity):.2f}"},
                {"חוק": "אין מניות בכורה", "מצב": "✅" if 'PreferredStock' not in last_balance else "⚠️", "ערך": "בדיקה"},
                {"חוק": "רווח גולמי > 40%", "מצב": "✅" if (gp/rev) > 0.4 else "❌", "ערך": f"{(gp/rev)*100:.1f}%"},
                {"חוק": "הנהלה וכלליות / גולמי < 30%", "מצב": "✅" if (sga/gp) < 0.3 else "❌", "ערך": f"{(sga/gp)*100:.1f}%"},
                {"חוק": "מו\"פ / גולמי < 30%", "מצב": "✅" if (rnd/gp) < 0.3 else "❌", "ערך": f"{(rnd/gp)*100:.1f}%"},
                {"חוק": "ריבית / רווח תפעולי < 15%", "מצב": "✅" if (int_exp/ebit) < 0.15 else "❌", "ערך": f"{(int_exp/ebit)*100:.1f}%"},
                {"חוק": "רווח נקי / הכנסות > 20%", "מצב": "✅" if (ni/rev) > 0.2 else "❌", "ערך": f"{(ni/rev)*100:.1f}%"},
                {"חוק": "שיעור מס תקין (~20%)", "מצב": "✅" if 0.15 < (tax/pretax) < 0.3 else "⚠️", "ערך": f"{(tax/pretax)*100:.1f}%"},
                {"חוק": "רווחים צבורים בצמיחה", "מצב": "✅" if retained > balance_df.iloc[-2].get('RetainedEarnings', 0) else "❌", "ערך": format_val(retained)},
                {"חוק": "רכישת מניות (Buybacks)", "מצב": "✅" if 'RepurchaseOfCapitalStock' in last_cf else "⚪", "ערך": "קיימת"},
                {"חוק": "צמיחת EPS חיובית", "מצב": "✅" if stats.get('earningsQuarterlyGrowth', 0) > 0 else "❌", "ערך": f"{stats.get('earningsQuarterlyGrowth', 0)*100:.1f}%"}
            ]
            st.table(pd.DataFrame(rules))
        except Exception as e:
            st.warning("חלק מהנתונים להשוואת ה-12 חוקים חסרים ב-Yahoo כרגע.")

        # 3. הערכת שווי (WACC & DCF)
        st.subheader("⚖️ הערכת שווי פנימי (Valuation Models)")
        
        # חישוב WACC
        beta = fin.get('beta', 1.2)
        rf = 0.043 # 10Y Treasury
        erp = 0.05 # Equity Risk Premium
        cost_equity = rf + (beta * erp)
        cost_debt = (int_exp / debt) if debt > 1e6 else 0.05
        w_e = equity / (equity + debt)
        w_d = debt / (equity + debt)
        wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - 0.21))
        
        st.write(f"**נתוני חישוב WACC:** Beta: {beta}, Cost of Equity: {cost_equity*100:.1f}%, WACC: {wacc*100:.2f}%")

        fcf = fin.get('freeCashflow', 1e9)
        growth = stats.get('earningsGrowth', 0.1)
        if growth is None: growth = 0.1
        
        price_dcf = ((fcf * (1 + growth)) / (wacc - 0.02)) / price.get('sharesOutstanding', 1)
        price_pe = fin.get('forwardPE', 20) * stats.get('forwardEps', 5)
        price_nav = equity / price.get('sharesOutstanding', 1)

        # 4. מגרש כדורגל (Football Field)
        st.write("**מגרש כדורגל (טווח שווי):**")
        football = pd.DataFrame({
            "שיטה": ["DCF (תזרים מזומנים)", "שווי יחסי (P/E)", "שווי נכסי (NAV)"],
            "מחיר מוערך": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        })
        st.table(football)

        # 5. המלצה ומרחב ביטחון
        fair_value = (price_dcf * 0.7 + price_pe * 0.3)
        mos = fair_value * 0.7 # 30% Margin of Safety
        
        st.divider()
        c_res1, c_res2 = st.columns(2)
        c_res1.metric("שווי הוגן סופי (משוקלל)", f"${fair_value:.2f}")
        c_res2.metric("מחיר כניסה (MOS 30%)", f"${mos:.2f}")

        # 6. גרף טכני
        st.subheader("📈 גרף טכני (שנה אחרונה)")
        history = t.history(period="1y")
        if not history.empty:
            fig = go.Figure(data=[go.Candlestick(x=history.index.get_level_values('date'),
                            open=history['open'], high=history['high'],
                            low=history['low'], close=history['close'])])
            st.plotly_chart(fig, use_container_width=True)

        # 7. חדשות
        st.subheader("📰 חדשות")
        news = t.news(5)
        for n in news:
            st.write(f"- [{n['title']}]({n['link']})")
