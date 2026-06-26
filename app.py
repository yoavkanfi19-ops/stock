import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
from datetime import datetime

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Deep-Dive Pro")

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
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, MSFT, GOOGL):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f"מנתח נתונים עבור {symbol}..."):
        t = Ticker(symbol)
        all_mods = t.all_modules[symbol]
        
        if isinstance(all_mods, str):
            st.error(f"שגיאה במשיכת נתונים: {all_mods}")
            st.stop()

        # חילוץ מודולים
        price_mod = all_mods.get('price', {})
        fin_mod = all_mods.get('financialData', {})
        stats_mod = all_mods.get('defaultKeyStatistics', {})
        summary_mod = all_mods.get('summaryProfile', {})
        trend_mod = all_mods.get('earningsTrend', {}).get('trend', [])

        # דוחות כספיים
        inc_df = t.income_statement()
        bs_df = t.balance_sheet()
        cf_df = t.cash_flow()

        if inc_df.empty or bs_df.empty:
            st.error("לא ניתן לשלוף דוחות כספיים מלאים עבור מניה זו.")
            st.stop()

        # --- חלק 1: פרטים כלליים ---
        st.header(f"שם מניה: {price_mod.get('longName')} ({symbol})")
        st.subheader(f"מחיר מניה כרגע: ${fin_mod.get('currentPrice')}")
        
        last_report_date = inc_df.index[-1].strftime('%Y-%m-%d')
        st.write(f"**תאריכי הדוחות שאנחנו בודקים (דוח שנתי אחרון):** {last_report_date}")
        
        st.write("---")
        st.subheader("💡 תקציר על מה שהחברה עושה")
        st.write(summary_mod.get('longBusinessSummary', 'אין תקציר זמין.'))

        # --- חלק 2: בדיקת 12 החוקים (באפטולוגיה) ---
        st.write("---")
        st.header("⚖️ סיכום 12 החוקים של באפטולוגיה")
        
        # נתונים לחישוב (מתוך הדוח האחרון)
        last_is = inc_df.iloc[-1]
        last_bs = bs_df.iloc[-1]
        last_cf = cf_df.iloc[-1]
        
        # נתוני שנה קודמת להשוואה
        prev_bs = bs_df.iloc[-2] if len(bs_df) > 1 else last_bs
        prev_is = inc_df.iloc[-2] if len(inc_df) > 1 else last_is

        # חישובי ביניים
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
        
        # בניית טבלת החוקים
        rules_list = [
            ["1. מזומן > חוב", "עומד" if cash > debt else "לא עומד", f"C: {fmt_bn(cash)} / D: {fmt_bn(debt)}"],
            ["2. יחס חוב להון (D/E) < 0.8", "עומד" if (liabilities/equity) < 0.8 else "לא עומד", f"{(liabilities/equity):.2f}"],
            ["3. אין מניות בכורה", "עומד" if 'PreferredStock' not in last_bs else "לא עומד", "אין מניות בכורה בדוח"],
            ["4. רווחים צבורים בצמיחה", "עומד" if retained > prev_retained else "לא עומד", f"השנה: {fmt_bn(retained)} | שנה קודמת: {fmt_bn(prev_retained)}"],
            ["5. מניות באוצר (Buyback)", "עומד" if 'RepurchaseOfCapitalStock' in last_cf or 'TreasuryStock' in last_bs else "בדיקה", "קיימת פעילות רכישה עצמית"],
            ["6. רווח גולמי > 40%", "עומד" if (gp/rev) > 0.4 else "לא עומד", pct(gp/rev)],
            ["7. הוצאות הנהלה/גולמי < 30%", "עומד" if (sga/gp) < 0.3 else "לא עומד", pct(sga/gp)],
            ["8. הוצאות מו\"פ/גולמי < 30%", "עומד" if (rnd/gp) < 0.3 else "לא עומד", pct(rnd/gp)],
            ["9. ריבית/רווח תפעולי < 15%", "עומד" if (int_exp/ebit) < 0.15 else "לא עומד", pct(int_exp/ebit)],
            ["10. מס הכנסה/לפני מס ~ 20%", "עומד" if 0.15 < (tax/pretax) < 0.3 else "בדיקה", pct(tax/pretax)],
            ["11. רווח נקי > 20%", "עומד" if (ni/rev) > 0.2 else "לא עומד", pct(ni/rev)],
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

        # צמיחת EPS מול רווח נקי
        ni_growth = (ni / prev_is.get('NetIncome', 1)) - 1
        eps_growth = stats_mod.get('earningsQuarterlyGrowth', 0)
        buybacks_val = abs(last_cf.get('RepurchaseOfCapitalStock', 0))
        
        st.subheader("📈 ניתוח צמיחה ורכישה עצמית")
        st.write(f"- **צמיחת רווח נקי בשנה האחרונה:** {pct(ni_growth)}")
        st.write(f"- **צמיחת EPS (אנליסטים):** {pct(eps_growth)}")
        st.write(f"- **הבדל בצמיחה:** {pct(abs(eps_growth - ni_growth))} (אם ה-EPS גבוה יותר, זה סימן חיובי לרכישת מניות)")
        st.write(f"- **סכום מניות שנקנו בחזרה בדוח זה:** {fmt_bn(buybacks_val)}")

        # --- חלק 4: ניתוח Moat וחלוקת הכנסות ---
        st.write("---")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.subheader("🏰 סוגי Moat (חפיר כלכלי)")
            st.write("- **יתרון לגודל:** חברה גדולה עם כוח מיקוח מול ספקים.")
            st.write("- **מותג חזק:** יכולת לגבות פרמיה (כפי שנראה ברווח הגולמי).")
            st.write("- **עלויות מעבר:** לקוחות ש"שבויים" בתוך המערכת.")
        
        with col_m2:
            st.subheader("💰 ממה החברה מרוויחה?")
            st.write(f"מגזר פעילות: {summary_mod.get('sector')}")
            st.write(f"תעשייה: {summary_mod.get('industry')}")
            st.write("הכנסות החברה מתחלקות לפי פעילות הליבה המפורטת בתקציר העסקי.")

        # --- חלק 5: מודלים של שווי פנימי (Valuation) ---
        st.write("---")
        st.header("⚖️ חישוב שווי פנימי (Valuation)")
        
        # חישוב WACC שקוף
        risk_free = 0.043 # 10Y Treasury
        beta = fin_mod.get('beta', 1.2) or 1.2
        equity_risk_premium = 0.055
        cost_of_equity = risk_free + (beta * equity_risk_premium)
        
        cost_of_debt = (int_exp / debt) if debt > 0 else 0.05
        tax_rate = 0.21
        w_equity = equity / (equity + debt)
        w_debt = debt / (equity + debt)
        wacc = (w_equity * cost_of_equity) + (w_debt * cost_of_debt * (1 - tax_rate))
        
        st.subheader("1. מודל DCF (Discounted Cash Flow)")
        st.write("**נוסחת WACC ששימשה אותנו:**")
        st.code(f"WACC = ({w_equity:.2f} * {cost_of_equity:.2f}) + ({w_debt:.2f} * {cost_of_debt:.2f} * (1 - {tax_rate})) = {wacc:.4f} ({wacc*100:.2f}%)")
        
        growth_rate = stats_mod.get('earningsGrowth', 0.1) or 0.1
        terminal_growth = 0.025
        
        # חישוב DCF מפושט
        dcf_val = ((fcf * (1 + growth_rate)) / (wacc - terminal_growth))
        price_dcf = dcf_val / price_mod.get('sharesOutstanding', 1)
        
        st.write(f"- **נתונים ששימשו ב-DCF:** FCF={fmt_bn(fcf)}, צמיחה={pct(growth_rate)}, ריבית היוון={pct(wacc)}")
        st.write(f"🎯 **שווי פנימי לפי DCF:** ${price_dcf:.2f}")

        # שיטות נוספות
        price_pe = (trend_mod[0].get('growth', 0.1) + 10) * stats_mod.get('forwardEps', 5) if trend_mod else 0
        price_nav = equity / price_mod.get('sharesOutstanding', 1)
        
        st.subheader("2. מגרש כדורגל (Football Field Valuation)")
        football_df = pd.DataFrame({
            "שיטה": ["DCF (תזרים מזומנים)", "שווי יחסי (מכפילים)", "NAV (שווי נכסי נקי)"],
            "שווי למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        })
        st.table(football_df)

        # שווי פנימי סופי ומרווח ביטחון
        final_intrinsic = (price_dcf * 0.7 + price_pe * 0.3)
        mos = final_intrinsic * 0.7 # 30% Margin of Safety
        
        st.subheader("🎯 שווי פנימי סופי מוערך")
        st.title(f"${final_intrinsic:.2f}")
        st.write(f"**מחיר קנייה מומלץ (מרווח ביטחון 30%):** ${mos:.2f}")

        # --- חלק 6: תחזיות אנליסטים וחדשות ---
        st.write("---")
        st.subheader("📉 תחזיות וניתוח טכני")
        
        hist = t.history(period="1y").reset_index()
        fig = go.Figure(data=[go.Candlestick(x=hist['date'], open=hist['open'], high=hist['high'], low=hist['low'], close=hist['close'])])
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("**תחזיות אנליסטים (Yahoo Finance):**")
        st.write(f"- מחיר יעד ממוצע: ${fin_mod.get('targetMeanPrice')}")
        st.write(f"- מחיר יעד נמוך: ${fin_mod.get('targetLowPrice')} | גבוה: ${fin_mod.get('targetHighPrice')}")
        
        st.subheader("📰 חדשות עדכניות")
        news = t.news(5)
        for n in news:
            st.write(f"- [{n['title']}]({n['link']})")

        # --- סיכום והמלצה ---
        st.write("---")
        st.header("🎯 המלצה סופית")
        curr_p = fin_mod.get('currentPrice')
        if curr_p < mos:
            st.success(f"המלצה: **קנייה חזקה**. המניה נסחרת משמעותית מתחת למרווח הביטחון.")
        elif curr_p < final_intrinsic:
            st.warning("המלצה: **קנייה**. המניה מתחת לשווי ההוגן אך מעל מרווח הביטחון.")
        else:
            st.error("המלצה: **המתנה / יקרה**. המחיר הנוכחי גבוה מהשווי הפנימי.")
