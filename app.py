import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
from datetime import datetime

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Deep-Dive Pro")

# פונקציות עזר לעיצוב מספרים
def fmt_bn(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    return f"{val*100:.2f}%"

# --- ממשק משתמש ---
st.title("📊 Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, MSFT, TSLA):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f"מנתח נתונים עבור {symbol}..."):
        t = Ticker(symbol)
        all_mods = t.all_modules[symbol]
        
        if isinstance(all_mods, str):
            st.error(f"שגיאה במשיכת נתונים: {all_mods}. נסה שוב בעוד דקה.")
            st.stop()

        # חילוץ מודולים פיננסיים
        price_mod = all_mods.get('price', {})
        fin_mod = all_mods.get('financialData', {})
        stats_mod = all_mods.get('defaultKeyStatistics', {})
        summary_mod = all_mods.get('summaryProfile', {})
        trend_mod = all_mods.get('earningsTrend', {}).get('trend', [])

        # דוחות כספיים - yahooquery
        inc_df = t.income_statement().transpose()
        bs_df = t.balance_sheet().transpose()
        cf_df = t.cash_flow().transpose()

        if inc_df.empty or bs_df.empty:
            st.error("לא ניתן לשלוף דוחות כספיים מלאים עבור מניה זו כרגע.")
            st.stop()

        # --- חלק 1: פרטים כלליים ---
        st.header(f"שם מניה: {price_mod.get('longName')} ({symbol})")
        st.subheader(f"מחיר מניה כרגע: ${fin_mod.get('currentPrice')}")
        
        # תאריך דוח
        last_report_date = inc_df.columns[-1].strftime('%Y-%m-%d')
        st.write(f"**תאריכי הדוחות שאנחנו בודקים (דוח אחרון):** {last_report_date}")
        
        st.write("---")
        st.subheader("💡 תקציר על מה שהחברה עושה")
        st.write(summary_mod.get('longBusinessSummary', 'אין תקציר זמין.'))

        # --- חלק 2: בדיקת 12 החוקים (באפטולוגיה) ---
        st.write("---")
        st.header("⚖️ סיכום 12 החוקים של באפטולוגיה")
        
        # נתונים מהדוח האחרון
        last_is = inc_df[inc_df.columns[-1]]
        last_bs = bs_df[bs_df.columns[-1]]
        last_cf = cf_df[cf_df.columns[-1]]
        
        # שנה קודמת להשוואה
        prev_bs = bs_df[bs_df.columns[-2]] if len(bs_df.columns) > 1 else last_bs
        prev_is = inc_df[inc_df.columns[-2]] if len(inc_df.columns) > 1 else last_is

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
        liabilities = last_bs.get('TotalLiabilitiesNetMinorityInterest', 0)
        retained = last_bs.get('RetainedEarnings', 0)
        prev_retained = prev_bs.get('RetainedEarnings', 0)
        
        rules_list = [
            ["1. מזומן > חוב", "עומד" if cash > debt else "לא עומד", f"C: {fmt_bn(cash)} / D: {fmt_bn(debt)}"],
            ["2. יחס חוב להון (D/E) < 0.8", "עומד" if (liabilities/equity) < 0.8 else "לא עומד", f"{(liabilities/equity):.2f}"],
            ["3. אין מניות בכורה", "עומד" if 'PreferredStock' not in last_bs else "לא עומד", "תקין"],
            ["4. רווחים צבורים בצמיחה", "עומד" if retained > prev_retained else "לא עומד", f"השנה: {fmt_bn(retained)} | קודמת: {fmt_bn(prev_retained)}"],
            ["5. מניות באוצר (Buyback)", "עומד" if 'RepurchaseOfCapitalStock' in last_cf else "בדיקה", "קיימת פעילות"],
            ["6. רווח גולמי > 40%", "עומד" if (gp/rev) > 0.4 else "לא עומד", pct(gp/rev)],
            ["7. הוצאות הנהלה/גולמי < 30%", "עומד" if (sga/gp) < 0.3 else "לא עומד", pct(sga/gp)],
            ["8. הוצאות מו\"פ/גולמי < 30%", "עומד" if (rnd/gp) < 0.3 else "לא עומד", pct(rnd/gp)],
            ["9. ריבית/רווח תפעולי < 15%", "עומד" if (int_exp/ebit) < 0.15 else "לא עומד", pct(int_exp/ebit)],
            ["10. מס הכנסה/לפני מס ~ 20%", "עומד" if 0.15 < (tax/pretax) < 0.3 else "בדיקה", pct(tax/pretax)],
            ["11. רווח נקי/הכנסות > 20%", "עומד" if (ni/rev) > 0.2 else "לא עומד", pct(ni/rev)],
            ["12. EPS במגמת צמיחה", "עומד" if stats_mod.get('earningsGrowth', 0) > 0 else "לא עומד", pct(stats_mod.get('earningsGrowth', 0))]
        ]
        
        st.table(pd.DataFrame(rules_list, columns=["חוק", "מצב", "נתון נמדד"]))

        # --- חלק 3: טבלאות פיננסיות וצמיחה ---
        st.write("---")
        st.subheader("📊 נתונים פיננסיים מרכזיים")
        fcf = fin_mod.get('freeCashflow', 0)
        ebitda = fin_mod.get('ebitda', 0)
        
        fin_summary = pd.DataFrame({
            "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומן", "חוב"],
            "ערך": [fmt_bn(rev), fmt_bn(ebitda), fmt_bn(ebit), fmt_bn(ni), fmt_bn(cash), fmt_bn(debt)],
            "אחוז מהכנסות": ["100%", pct(ebitda/rev), pct(ebit/rev), pct(ni/rev), "-", "-"]
        })
        st.table(fin_summary)
        st.write(f"**Free Cash Flow (תזרים מזומנים חופשי):** {fmt_bn(fcf)}")

        # צמיחה ורכישה עצמית
        ni_growth = (ni / prev_is.get('NetIncome', 1)) - 1
        eps_growth = stats_mod.get('earningsQuarterlyGrowth', 0)
        buybacks_val = abs(last_cf.get('RepurchaseOfCapitalStock', 0))
        
        st.subheader("📈 ניתוח צמיחה ורכישה עצמית")
        st.write(f"- **צמיחת רווח נקי (שנתי):** {pct(ni_growth)}")
        st.write(f"- **צמיחת EPS:** {pct(eps_growth)}")
        st.write(f"- **הבדל:** {pct(abs(eps_growth - ni_growth))} (פער חיובי לטובת EPS מעיד על צמצום מניות)")
        st.write(f"- **סכום מניות שנקנו בחזרה בדוח זה:** {fmt_bn(buybacks_val)}")

        # --- חלק 4: ניתוח Moat ---
        st.write("---")
        st.subheader("🏰 סוגי Moat וחלוקת רווחים")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.write("**ניתוח חפיר כלכלי:**")
            st.write("- **יתרון לגודל:** כוח קנייה ומיקוח משמעותי.")
            st.write("- **מותג:** נאמנות לקוחות המאפשרת רווח גולמי גבוה.")
            st.write('- **עלויות מעבר:** לקוחות ש"שבויים" בתוך האקו-סיסטם.')
        with col_m2:
            st.write(f"**מגזר:** {summary_mod.get('sector')}")
            st.write(f"**תעשייה:** {summary_mod.get('industry')}")

        # --- חלק 5: מודלים של שווי פנימי ---
        st.write("---")
        st.header("⚖️ חישוב שווי פנימי (Valuation)")
        
        # WACC Calculation
        rf = 0.043 # 10Y Treasury
        beta = fin_mod.get('beta', 1.1) or 1.1
        erp = 0.055
        cost_equity = rf + (beta * erp)
        cost_debt = (int_exp / debt) if debt > 0 else 0.05
        w_e = equity / (equity + debt)
        w_d = debt / (equity + debt)
        wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - 0.21))
        
        st.write("**פירוט חישוב WACC (ריבית היוון):**")
        st.code(f"Cost Equity: {pct(cost_equity)} | WACC: {pct(wacc)}")
        
        # DCF Model
        growth = stats_mod.get('earningsGrowth', 0.1) or 0.1
        price_dcf = ((fcf * (1 + growth)) / (wacc - 0.025)) / price_mod.get('sharesOutstanding', 1)
        
        # Relative Valuation
        price_pe = (growth * 100 + 10) * stats_mod.get('forwardEps', 5)
        price_nav = equity / price_mod.get('sharesOutstanding', 1)

        st.subheader("🎯 מגרש כדורגל (טווח מחירים)")
        football = pd.DataFrame({
            "שיטה": ["DCF", "מכפילים (Relative)", "שווי נכסי (NAV)"],
            "שווי למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        })
        st.table(football)

        final_val = (price_dcf * 0.7 + price_pe * 0.3)
        st.title(f"שווי פנימי סופי: ${final_val:.2f}")
        st.subheader(f"מחיר קנייה (מרווח ביטחון 30%): ${final_val * 0.7:.2f}")

        # --- חלק 6: תחזיות וגרף ---
        st.write("---")
        st.subheader("📈 תחזיות אנליסטים וגרף טכני")
        
        hist = t.history(period="1y").reset_index()
        fig = go.Figure(data=[go.Candlestick(x=hist['date'], open=hist['open'], high=hist['high'], low=hist['low'], close=hist['close'])])
        st.plotly_chart(fig, use_container_width=True)
        
        st.write(f"- **מחיר יעד ממוצע (אנליסטים):** ${fin_mod.get('targetMeanPrice')}")
        st.write(f"- **מחיר יעד גבוה:** ${fin_mod.get('targetHighPrice')}")
        
        st.subheader("📰 חדשות עדכניות")
        news = t.news(3)
        for n in news:
            st.write(f"- [{n['title']}]({n['link']})")
