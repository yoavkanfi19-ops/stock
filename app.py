import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
import time

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Deep-Dive Pro", page_icon="📈")

# פונקציות עזר לעיצוב
def fmt(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    return f"{val*100:.2f}%"

# --- ממשק משתמש ---
st.title("📊 Financial Deep-Dive Pro")
st.markdown("---")

symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, MSFT, NVDA):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f"מנתח נתונים עבור {symbol}..."):
        try:
            # שימוש ב-yahooquery עם הגדרות עקיפה
            t = Ticker(symbol, asynchronous=True, retry=3, timeout=10)
            
            # משיכת מודולים ספציפיים כדי למנוע חסימה
            all_data = t.all_modules[symbol]
            
            if isinstance(all_data, str):
                st.error("Yahoo Finance חוסמת את השרת הציבורי כרגע. נסה שוב בעוד כמה דקות או מקומית.")
                st.stop()

            # חילוץ נתונים
            price_m = all_data.get('price', {})
            fin_m = all_data.get('financialData', {})
            stats_m = all_data.get('defaultKeyStatistics', {})
            summary_m = all_data.get('summaryProfile', {})
            
            # שליפת דוחות (שיטה יציבה יותר)
            inc_df = t.income_statement().transpose()
            bs_df = t.balance_sheet().transpose()
            cf_df = t.cash_flow().transpose()

            if inc_df.empty:
                st.error("לא ניתן למשוך דוחות כספיים. בדוק את הסימול.")
                st.stop()

            # 1. פרטים כלליים
            st.header(f"שם מניה: {price_m.get('longName')} ({symbol})")
            st.subheader(f"מחיר מניה כרגע: ${fin_m.get('currentPrice')}")
            
            last_date = inc_df.columns[-1].strftime('%d/%m/%Y')
            st.write(f"**תאריכי הדוחות שאנחנו בודקים:** {last_date} (שנתי/רבעוני אחרון)")
            
            st.write("---")
            st.subheader("💡 תקציר על מה שהחברה עושה")
            st.write(summary_m.get('longBusinessSummary', 'אין תקציר זמין.'))

            # 2. בדיקת 12 החוקים (באפטולוגיה)
            st.write("---")
            st.header("⚖️ סיכום 12 החוקים של באפטולוגיה")
            
            # נתונים מהדוח האחרון
            last_is = inc_df[inc_df.columns[-1]]
            last_bs = bs_df[bs_df.columns[-1]]
            last_cf = cf_df[cf_df.columns[-1]]
            
            # נתוני צמיחה
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
            liabilities = last_bs.get('TotalLiabilitiesNetMinorityInterest', 0)
            retained = last_bs.get('RetainedEarnings', 0)
            prev_retained = bs_df[bs_df.columns[-2]].get('RetainedEarnings', 0) if len(bs_df.columns) > 1 else 0

            laws = [
                ["1. מזומן > חוב", "עומד" if cash > debt else "לא עומד", f"C: {fmt(cash)} / D: {fmt(debt)}"],
                ["2. יחס חוב להון < 0.8", "עומד" if (liabilities/equity) < 0.8 else "לא עומד", f"{(liabilities/equity):.2f}"],
                ["3. אין מניות בכורה", "עומד" if 'PreferredStock' not in last_bs else "לא עומד", "תקין"],
                ["4. רווחים צבורים בצמיחה", "עומד" if retained > prev_retained else "לא עומד", f"השנה: {fmt(retained)}"],
                ["5. מניות באוצר (Buybacks)", "עומד" if 'RepurchaseOfCapitalStock' in last_cf else "בדיקה", "קיימת פעילות"],
                ["6. רווח גולמי > 40%", "עומד" if (gp/rev) > 0.4 else "לא עומד", pct(gp/rev)],
                ["7. הנהלה/גולמי < 30%", "עומד" if (sga/gp) < 0.3 else "לא עומד", pct(sga/gp)],
                ["8. מו\"פ/גולמי < 30%", "עומד" if (rnd/gp) < 0.3 else "לא עומד", pct(rnd/gp)],
                ["9. ריבית/רווח תפעולי < 15%", "עומד" if (int_exp/ebit) < 0.15 else "לא עומד", pct(int_exp/ebit)],
                ["10. מס הכנסה/לפני מס ~ 20%", "עומד" if 0.15 < (tax/pretax) < 0.35 else "בדיקה", pct(tax/pretax)],
                ["11. רווח נקי > 20%", "עומד" if (ni/rev) > 0.2 else "לא עומד", pct(ni/rev)],
                ["12. EPS במגמת צמיחה", "עומד" if stats_m.get('earningsGrowth', 0) > 0 else "לא עומד", pct(stats_m.get('earningsGrowth', 0))]
            ]
            st.table(pd.DataFrame(laws, columns=["חוק", "מצב", "נתון"]))

            # 3. טבלאות נתונים
            st.write("---")
            st.subheader("💰 נתונים פיננסיים (מיליארדים)")
            ebitda = fin_m.get('ebitda', 0)
            fcf = fin_m.get('freeCashflow', 0)
            
            summary_table = pd.DataFrame({
                "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומן", "חוב"],
                "ערך": [fmt(rev), fmt(ebitda), fmt(ebit), fmt(ni), fmt(cash), fmt(debt)],
                "מרג'ין": ["100%", pct(ebitda/rev), pct(ebit/rev), pct(ni/rev), "-", "-"]
            })
            st.table(summary_table)

            # צמיחה ו-Buybacks
            prev_ni = inc_df[inc_df.columns[-2]].get('NetIncome', 1) if len(inc_df.columns) > 1 else ni
            ni_growth = (ni / prev_ni) - 1
            eps_growth = stats_m.get('earningsQuarterlyGrowth', 0)
            buyback_sum = abs(last_cf.get('RepurchaseOfCapitalStock', 0))

            st.subheader("📈 צמיחה ורכישה עצמית")
            st.write(f"- **צמיחת רווח נקי:** {pct(ni_growth)} | **צמיחת EPS:** {pct(eps_growth)}")
            st.write(f"- **כמה מניות נקנו בחזרה בדוח זה?** {fmt(buyback_sum)}")

            # 4. Moat וחלוקת רווחים
            st.write("---")
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("🏰 סוגי Moat")
                if (gp/rev) > 0.4: st.write("- מותג חזק (Pricing Power)")
                if rev > 10e10: st.write("- יתרון לגודל (Scale)")
                st.write("- אפקט רשת / עלויות מעבר")
            with col_b:
                st.subheader("💰 ממה החברה מרוויחה?")
                st.write(f"מגזר: {summary_m.get('sector')} | תעשייה: {summary_m.get('industry')}")

            # 5. הערכת שווי (WACC & DCF)
            st.write("---")
            st.header("⚖️ חישוב שווי פנימי")
            
            # WACC
            rf = 0.043 # 10Y
            beta = fin_m.get('beta', 1.1) or 1.1
            erp = 0.055
            cost_equity = rf + (beta * erp)
            cost_debt = (int_exp / debt) if debt > 0 else 0.05
            w_e = equity / (equity + debt)
            w_d = debt / (equity + debt)
            wacc = (w_e * cost_equity) + (w_d * cost_debt * 0.79) # tax-shield
            
            st.write("**פירוט חישוב WACC:**")
            st.code(f"Cost Equity = {pct(cost_equity)} | WACC = {pct(wacc)}")

            # DCF
            growth = stats_m.get('earningsGrowth', 0.1) or 0.1
            price_dcf = ((fcf * (1 + growth)) / (wacc - 0.025)) / price_m.get('sharesOutstanding', 1)
            # Relative
            price_pe = (growth * 100 + 10) * stats_m.get('forwardEps', 5)
            # NAV
            price_nav = equity / price_m.get('sharesOutstanding', 1)

            st.subheader("🏈 מגרש כדורגל (Football Field)")
            football = pd.DataFrame({
                "שיטה": ["DCF", "Relative Valuation", "NAV (שווי נכסי)"],
                "מחיר למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
            })
            st.table(football)

            final_intrinsic = (price_dcf * 0.7 + price_pe * 0.3)
            st.title(f"שווי פנימי סופי: ${final_intrinsic:.2f}")
            st.subheader(f"מחיר קנייה (מרווח ביטחון 30%): ${final_intrinsic * 0.7:.2f}")

            # 6. גרף וחדשות
            st.write("---")
            st.subheader("📈 ניתוח טכני ותחזיות")
            hist = t.history(period="1y").reset_index()
            fig = go.Figure(data=[go.Candlestick(x=hist['date'], open=hist['open'], high=hist['high'], low=hist['low'], close=hist['close'])])
            st.plotly_chart(fig, use_container_width=True)
            
            st.write(f"- **מחיר יעד אנליסטים:** ${fin_m.get('targetMeanPrice')}")
            
            st.subheader("📰 חדשות")
            for n in t.news(3):
                st.write(f"- [{n['title']}]({n['link']})")

        except Exception as e:
            st.error(f"אירעה שגיאה: {e}")
            st.info("Yahoo חוסמת את הבקשה. נסה שוב בעוד דקה.")
