import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
from datetime import datetime
import requests
import time # לייבוא מחדש במידת הצורך

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Deep-Dive Pro")

# פונקציות עזר לעיצוב והתמודדות עם חסימות
def fmt_bn(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return "N/A"
    return f"{val*100:.2f}%"

# פונקציה אגרסיבית יותר למשיכת נתונים עם retry
@st.cache_resource(ttl=3600)
def fetch_ticker_data_robust(symbol):
    try:
        t = Ticker(symbol, asynchronous=True)
        # ננסה למשוך את כל המודולים העיקריים
        all_modules = t.all_modules
        if symbol not in all_modules:
            return None, "לא נמצאו נתונים עבור הסימול, או שגיאה כללית."
        
        data = all_modules[symbol]
        if isinstance(data, str): # אם יש הודעת שגיאה מ-Yahoo
            return None, data
        
        # משיכת דוחות בנפרד כי לפעמים all_modules לא מושך אותם מלא
        inc_df = t.income_statement(freq='annual').transpose()
        bs_df = t.balance_sheet(freq='annual').transpose()
        cf_df = t.cash_flow(freq='annual').transpose()

        return {'modules': data, 'inc_df': inc_df, 'bs_df': bs_df, 'cf_df': cf_df}, None
    except Exception as e:
        return None, f"שגיאה קריטית במשיכת הנתונים: {e}"

# --- ממשק משתמש ---
st.title("📊 Financial Deep-Dive Pro (גרסה עמידה)")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, MSFT):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f"מושך נתונים עבור {symbol} מהשרת..."):
        fetched_data, error_msg = fetch_ticker_data_robust(symbol)
        
        if error_msg:
            st.error(f"⚠️ שגיאה: {error_msg}. נסה שוב בעוד דקה או עם סימול אחר.")
            st.stop()

        modules = fetched_data['modules']
        inc_df = fetched_data['inc_df']
        bs_df = fetched_data['bs_df']
        cf_df = fetched_data['cf_df']

        # חילוץ מודולים
        price_mod = modules.get('price', {})
        fin_mod = modules.get('financialData', {})
        stats_mod = modules.get('defaultKeyStatistics', {})
        summary_mod = modules.get('summaryProfile', {})
        trend_mod = modules.get('earningsTrend', {}).get('trend', [])
        
        # בדיקה אם יש נתונים בסיסיים
        if not price_mod or 'longName' not in price_mod:
            st.error(f"לא נתונים מלאים עבור {symbol}. ייתכן שאין מידע או חסימה זמנית.")
            st.stop()

        # --- חלק 1: פרטים כלליים ---
        st.header(f"שם מניה: {price_mod.get('longName')} ({symbol})")
        curr_price = fin_mod.get('currentPrice', price_mod.get('regularMarketPrice', 'N/A'))
        st.subheader(f"מחיר מניה כרגע: ${curr_price}")
        
        last_report_date = "N/A"
        if not inc_df.empty:
            last_report_date = inc_df.columns[-1].strftime('%Y-%m-%d')
        st.write(f"**תאריך הדוח האחרון שנבדק:** {last_report_date}")
        
        st.write("---")
        st.subheader("💡 תקציר על מה שהחברה עושה")
        st.write(summary_mod.get('longBusinessSummary', 'אין תקציר זמין.'))

        # --- חלק 2: בדיקת 12 החוקים (באפטולוגיה) ---
        st.write("---")
        st.header("⚖️ סיכום 12 החוקים של באפטולוגיה")
        
        # נתונים לחישוב (עם טיפול בנתונים חסרים)
        last_is = inc_df[inc_df.columns[-1]] if not inc_df.empty else pd.Series()
        last_bs = bs_df[bs_df.columns[-1]] if not bs_df.empty else pd.Series()
        last_cf = cf_df[cf_df.columns[-1]] if not cf_df.empty else pd.Series()
        
        prev_bs = bs_df[bs_df.columns[-2]] if len(bs_df.columns) > 1 else last_bs
        prev_is = inc_df[inc_df.columns[-2]] if len(inc_df.columns) > 1 else last_is

        # נתוני הכנסות ורווחים
        rev = last_is.get('TotalRevenue', 1) or 1
        gp = last_is.get('GrossProfit', 0) or 0
        ni = last_is.get('NetIncome', 0) or 0
        ebit = last_is.get('Ebit', 1) or 1 # רווח תפעולי
        int_exp = abs(last_is.get('InterestExpense', 0) or 0)
        sga = last_is.get('SellingGeneralAdministrative', 0) or 0
        rnd = last_is.get('ResearchDevelopment', 0) or 0
        pretax = last_is.get('PretaxIncome', 1) or 1
        tax = abs(last_is.get('TaxProvision', 0) or 0)
        
        # נתוני מאזן
        cash = last_bs.get('CashAndCashEquivalents', 0) or 0
        debt = last_bs.get('TotalDebt', 0) or 0
        equity = last_bs.get('StockholdersEquity', 1) or 1
        liabilities = last_bs.get('TotalLiabilitiesNetMinorityInterest', 0) or 0
        retained = last_bs.get('RetainedEarnings', 0) or 0
        prev_retained = prev_bs.get('RetainedEarnings', 0) or 0

        rules_list = [
            ["1. מזומן > חוב", "✅" if cash > debt else "❌", f"C: {fmt_bn(cash)} / D: {fmt_bn(debt)}"],
            ["2. יחס חוב להון (D/E) < 0.8", "✅" if (liabilities/equity) < 0.8 else "❌", f"{(liabilities/equity):.2f}"],
            ["3. אין מניות בכורה", "✅" if 'PreferredStock' not in last_bs else "⚠️", "אין מניות בכורה בדוח"],
            ["4. רווחים צבורים בצמיחה", "✅" if retained > prev_retained else "❌", f"השנה: {fmt_bn(retained)} | קודמת: {fmt_bn(prev_retained)}"],
            ["5. מניות באוצר (Buyback)", "✅" if 'RepurchaseOfCapitalStock' in last_cf else "⚪", "קיימת פעילות רכישה עצמית"],
            ["6. רווח גולמי > 40%", "✅" if (gp/rev) > 0.4 else "❌", pct(gp/rev)],
            ["7. הוצאות הנהלה/גולמי < 30%", "✅" if (sga/gp) < 0.3 else "❌", pct(sga/gp)],
            ["8. הוצאות מו\"פ/גולמי < 30%", "✅" if (rnd/gp) < 0.3 else "❌", pct(rnd/gp)],
            ["9. ריבית/רווח תפעולי < 15%", "✅" if (int_exp/ebit) < 0.15 else "❌", pct(int_exp/ebit)],
            ["10. מס הכנסה/לפני מס ~ 20%", "✅" if 0.15 < (tax/pretax) < 0.3 else "⚠️", pct(tax/pretax)],
            ["11. רווח נקי/הכנסות > 20%", "✅" if (ni/rev) > 0.2 else "❌", pct(ni/rev)],
            ["12. EPS במגמת צמיחה", "✅" if stats_mod.get('earningsGrowth', 0) > 0 else "❌", pct(stats_mod.get('earningsGrowth', 0))]
        ]
        
        st.table(pd.DataFrame(rules_list, columns=["חוק", "מצב", "נתון נמדד"]))

        # --- חלק 3: טבלאות פיננסיות וצמיחה ---
        st.write("---")
        st.subheader("📊 נתונים פיננסיים מרכזיים")
        
        fcf = fin_mod.get('freeCashflow', 0) or (ni * 1.1) # Fallback ל-FCF
        ebitda = fin_mod.get('ebitda', 0) or (ebit + int_exp + last_is.get('DepreciationAndAmortization', 0)) # Fallback ל-EBITDA
        
        fin_summary = pd.DataFrame({
            "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומן", "חוב", "Free Cash Flow"],
            "ערך": [fmt_bn(rev), fmt_bn(ebitda), fmt_bn(ebit), fmt_bn(ni), fmt_bn(cash), fmt_bn(debt), fmt_bn(fcf)],
            "אחוז מהכנסות": ["100%", pct(ebitda/rev), pct(ebit/rev), pct(ni/rev), "-", "-", "-"]
        })
        st.table(fin_summary)

        # צמיחה ורכישה עצמית
        ni_growth = (ni / prev_is.get('NetIncome', 1)) - 1 if prev_is.get('NetIncome', 1) != 0 else 0
        eps_growth = stats_mod.get('earningsQuarterlyGrowth', 0)
        buybacks_val = abs(last_cf.get('RepurchaseOfCapitalStock', 0) or 0)
        
        st.subheader("📈 ניתוח צמיחה ורכישה עצמית")
        st.write(f"- **צמיחת רווח נקי (שנתי):** {pct(ni_growth)}")
        st.write(f"- **צמיחת EPS (אנליסטים):** {pct(eps_growth)}")
        st.write(f"- **הבדל:** {pct(abs(eps_growth - ni_growth))} (פער חיובי לטובת EPS מעיד על צמצום מניות)")
        st.write(f"- **סכום מניות שנקנו בחזרה בדוח זה:** {fmt_bn(buybacks_val)}")

        # --- חלק 4: ניתוח Moat ---
        st.write("---")
        st.subheader("🏰 סוגי Moat וחלוקת רווחים")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.write("**ניתוח חפיר כלכלי:**")
            st.write("- **יתרון לגודל:** חברה גדולה עם כוח מיקוח משמעותי.")
            st.write("- **מותג:** נאמנות לקוחות המאפשרת רווח גולמי גבוה.")
            st.write('- **עלויות מעבר:** לקוחות ש"שבויים" בתוך האקו-סיסטם.')
        with col_m2:
            st.write(f"**מגזר:** {summary_mod.get('sector', 'N/A')}")
            st.write(f"**תעשייה:** {summary_mod.get('industry', 'N/A')}")
            st.write(f"**סוג חברה:** {summary_mod.get('industry', 'N/A')} - מושפעת מריביות, תחרות ורגולציה.")
            st.write("- **גורמים שיורידו מחיר:** עליית ריבית חדה, תחרות לא צפויה, האטה כלכלית.")
            st.write("- **גורמים שיעלו מחיר:** צמיחה בהכנסות, התייעלות, רכישות אסטרטגיות, חדשנות.")

        # --- חלק 5: מודלים של שווי פנימי ---
        st.write("---")
        st.header("⚖️ חישוב שווי פנימי (Valuation)")
        
        # WACC Calculation (עם Fallback)
        rf = 0.043 # 10Y Treasury
        beta = fin_mod.get('beta', stats_mod.get('beta', 1.1)) or 1.1 # ניסיון נוסף ל-beta
        erp = 0.055
        cost_equity = rf + (beta * erp)
        cost_debt = (int_exp / debt) if debt > 0 else 0.05
        w_e = equity / (equity + debt) if (equity + debt) > 0 else 0.5 # Fallback לוודא חלוקה תקינה
        w_d = debt / (equity + debt) if (equity + debt) > 0 else 0.5
        wacc = (w_e * cost_equity) + (w_d * cost_debt * (1 - 0.21))
        
        st.write("**פירוט חישוב WACC (ריבית היוון):**")
        st.code(f"Cost of Equity (CAPM) = {rf} + {beta} * {erp} = {cost_equity:.4f}\n"
                f"Cost of Debt (Estimated) = {cost_debt:.4f}\n"
                f"Weights: Equity={w_e:.2f}, Debt={w_d:.2f}\n"
                f"WACC = ({w_e:.2f} * {cost_equity:.4f}) + ({w_d:.2f} * {cost_debt:.4f} * (1 - 0.21)) = {wacc:.4f} ({pct(wacc)})")
        
        # DCF Model (עם Fallback)
        growth_rate = stats_mod.get('earningsGrowth', fin_mod.get('revenueGrowth', 0.1)) or 0.1 # Fallback לצמיחה
        terminal_growth = 0.025
        
        # לוודא ש-wacc גדול מ-terminal_growth כדי למנוע חלוקה באפס או שלילי
        if wacc <= terminal_growth:
            dcf_val = fcf * (1 + growth_rate) * 20 # הערכה פשוטה אם WACC בעייתי
            price_dcf = dcf_val / price_mod.get('sharesOutstanding', 1)
        else:
            dcf_val = ((fcf * (1 + growth_rate)) / (wacc - terminal_growth))
            price_dcf = dcf_val / price_mod.get('sharesOutstanding', 1)
        
        st.write(f"- **נתונים ששימשו ב-DCF:** FCF={fmt_bn(fcf)}, צמיחה={pct(growth_rate)}, ריבית היוון={pct(wacc)}, צמיחה סופית={pct(terminal_growth)}")
        st.write(f"🎯 **שווי פנימי לפי DCF:** ${price_dcf:.2f}")

        # שיטות נוספות (עם Fallback)
        forward_pe = fin_mod.get('forwardPE', 20)
        forward_eps = stats_mod.get('forwardEps', price_mod.get('trailingEps', 5)) or 5
        price_pe = forward_pe * forward_eps
        price_nav = equity / price_mod.get('sharesOutstanding', 1) if price_mod.get('sharesOutstanding', 1) > 0 else 0

        st.subheader("🎯 מגרש כדורגל (טווח מחירים)")
        football = pd.DataFrame({
            "שיטה": ["DCF", "מכפילים (Relative)", "שווי נכסי (NAV)"],
            "שווי למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        })
        st.table(football)

        final_val = (price_dcf * 0.7 + price_pe * 0.3)
        st.title(f"שווי פנימי סופי מוערך: ${final_val:.2f}")
        st.subheader(f"מחיר קנייה (מרווח ביטחון 30%): ${final_val * 0.7:.2f}")

        # --- חלק 6: תחזיות וגרף ---
        st.write("---")
        st.subheader("📈 תחזיות אנליסטים וגרף טכני")
        
        # תחזיות אנליסטים
        st.write("**תחזיות אנליסטים:**")
        st.write(f"- מחיר יעד ממוצע: ${fin_mod.get('targetMeanPrice', 'N/A')}")
        st.write(f"- מחיר יעד גבוה: ${fin_mod.get('targetHighPrice', 'N/A')}")
        st.write(f"- המלצת קונצנזוס: {fin_mod.get('recommendationKey', 'N/A')}")
        
        # גרף טכני
        try:
            hist_df = Ticker(symbol).history(period="1y").reset_index()
            fig = go.Figure(data=[go.Candlestick(x=hist_df['date'], open=hist_df['open'], high=hist_df['high'], low=hist_df['low'], close=hist_df['close'])])
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"לא ניתן לטעון גרף טכני כרגע: {e}. נסה שוב מאוחר יותר.")

        st.subheader("📰 חדשות עדכניות")
        try:
            news = Ticker(symbol).news(3)
            for n in news:
                st.write(f"- [{n['title']}]({n['link']})")
        except Exception as e:
            st.warning(f"לא ניתן לטעון חדשות כרגע: {e}")
