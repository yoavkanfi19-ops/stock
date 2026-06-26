import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Professional Stock Analyzer Pro")

# פונקציות עזר לחישובים
def format_billions(number):
    if abs(number) >= 1e9:
        return f"${number / 1e9:.2f}B"
    elif abs(number) >= 1e6:
        return f"${number / 1e6:.2f}M"
    return f"${number:,.2f}"

def safe_divide(n, d):
    return n / d if d and d != 0 else 0

# --- ממשק משתמש (Sidebar) ---
st.sidebar.header("🔍 הגדרות ניתוח")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN, AAPL, MSFT):", "AMZN").upper()
run_analysis = st.sidebar.button("הפק דוח ניתוח מלא")

if run_analysis:
    with st.spinner('מושך נתונים ומבצע חישובים...'):
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="2y")
        
        # משיכת דוחות כספיים
        income_stmt = ticker.financials
        balance_sheet = ticker.balance_sheet
        cash_flow = ticker.cashflow
        
        if income_stmt.empty or balance_sheet.empty:
            st.error("לא ניתן היה למשוך נתונים פיננסיים מלאים עבור סימול זה.")
            st.stop()

        # 1. נתונים בסיסיים
        curr_price = info.get('currentPrice', 0)
        company_name = info.get('longName', symbol)
        summary = info.get('longBusinessSummary', "אין תקציר זמין.")
        last_report_date = income_stmt.columns[0].strftime('%Y-%m-%d')
        
        st.title(f"📊 דוח ניתוח מעמיק: {company_name} ({symbol})")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("מחיר נוכחי", f"${curr_price}")
        col2.metric("תאריך דוח אחרון", last_report_date)
        col3.metric("שווי שוק", format_billions(info.get('marketCap', 0)))

        st.info(f"**תקציר חברה:** {summary}")

        # --- הכנת נתונים לחישובים ---
        rev = income_stmt.iloc[0, 0] if not income_stmt.empty else 0
        gross_profit = income_stmt.loc['Gross Profit', :][0] if 'Gross Profit' in income_stmt.index else 0
        net_income = income_stmt.loc['Net Income', :][0] if 'Net Income' in income_stmt.index else 0
        ebitda = info.get('ebitda', 0)
        op_income = income_stmt.loc['Operating Income', :][0] if 'Operating Income' in income_stmt.index else 0
        
        cash = balance_sheet.loc['Cash And Cash Equivalents', :][0] if 'Cash And Cash Equivalents' in balance_sheet.index else 0
        total_debt = info.get('totalDebt', 0)
        equity = balance_sheet.loc['Stockholders Equity', :][0] if 'Stockholders Equity' in balance_sheet.index else 1
        
        # --- 2. בדיקת 12 החוקים ---
        st.subheader("🛡️ בדיקת 12 החוקים (באפטולוגיה)")
        
        opex = (income_stmt.loc['Selling General Administrative', :][0] if 'Selling General Administrative' in income_stmt.index else 0)
        rnd = (income_stmt.loc['Research Development', :][0] if 'Research Development' in income_stmt.index else 0)
        interest_exp = abs(income_stmt.loc['Interest Expense', :][0] if 'Interest Expense' in income_stmt.index else 0)
        pretax_income = income_stmt.loc['Pretax Income', :][0] if 'Pretax Income' in income_stmt.index else 1
        tax_exp = abs(income_stmt.loc['Tax Provision', :][0] if 'Tax Provision' in income_stmt.index else 0)
        
        retained_earnings = balance_sheet.loc['Retained Earnings', :][0] if 'Retained Earnings' in balance_sheet.index else 0
        re_prev = balance_sheet.loc['Retained Earnings', :][1] if len(balance_sheet.columns) > 1 else 0
        treasury_stock = balance_sheet.loc['Treasury Stock', :][0] if 'Treasury Stock' in balance_sheet.index else 0
        pref_stock = balance_sheet.loc['Preferred Stock', :][0] if 'Preferred Stock' in balance_sheet.index else 0

        rules_data = [
            ["מזומן > חוב", "עומד" if cash > total_debt else "לא עומד", f"C: {format_billions(cash)} / D: {format_billions(total_debt)}"],
            ["יחס חוב להון < 0.8", "עומד" if (total_debt/equity) < 0.8 else "לא עומד", f"{(total_debt/equity):.2f}"],
            ["אין מניות בכורה", "עומד" if pref_stock == 0 else "לא עומד", f"${pref_stock}"],
            ["רווחים צבורים במגמת צמיחה", "עומד" if retained_earnings > re_prev else "לא עומד", f"צמיחה: {format_billions(retained_earnings - re_prev)}"],
            ["קיום מניות באוצר (Buybacks)", "עומד" if treasury_stock != 0 or info.get('sharesOutstanding') < info.get('impliedSharesOutstanding', 0) else "בדיקה", "מעיד על רכישה עצמית"],
            ["רווח גולמי > 40%", "עומד" if (gross_profit/rev) > 0.4 else "לא עומד", f"{(gross_profit/rev)*100:.1f}%"],
            ["הוצאות תפעול/גולמי < 30%", "עומד" if (opex/gross_profit) < 0.3 else "לא עומד", f"{(opex/gross_profit)*100:.1f}%"],
            ["הוצאות מו\"פ/גולמי < 30%", "עומד" if (rnd/gross_profit) < 0.3 else "לא עומד", f"{(rnd/gross_profit)*100:.1f}%"],
            ["ריבית/רווח תפעולי < 15%", "עומד" if (interest_exp/op_income) < 0.15 else "לא עומד", f"{(interest_exp/op_income)*100:.1f}%"],
            ["מס הכנסה תקין (~20%)", "עומד" if 0.15 < (tax_exp/pretax_income) < 0.30 else "דורש בדיקה", f"{(tax_exp/pretax_income)*100:.1f}%"],
            ["רווח נקי/הכנסות > 20%", "עומד" if (net_income/rev) > 0.2 else "לא עומד", f"{(net_income/rev)*100:.1f}%"],
            ["EPS במגמת צמיחה", "עומד" if info.get('earningsGrowth', 0) > 0 else "לא עומד", f"{info.get('earningsGrowth', 0)*100:.1f}% צמיחה"]
        ]
        st.table(pd.DataFrame(rules_data, columns=["החוק", "מצב", "ערך נמדד"]))

        # --- 3. נתונים פיננסיים מסכמים ---
        st.subheader("💰 ביצועים פיננסיים (מיליארדים/אחוזים)")
        fin_summary = {
            "מדד": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומן", "חוב"],
            "ערך": [format_billions(rev), format_billions(ebitda), format_billions(op_income), 
                    format_billions(net_income), format_billions(cash), format_billions(total_debt)],
            "מרג'ין/יחס": ["-", f"{(ebitda/rev)*100:.1f}%", f"{(op_income/rev)*100:.1f}%", 
                          f"{(net_income/rev)*100:.1f}%", "-", f"D/E: {total_debt/equity:.2f}"]
        }
        st.table(pd.DataFrame(fin_summary))

        # --- 4. צמיחת EPS מול רווח נקי ---
        st.subheader("📈 ניתוח צמיחה ורכישה עצמית")
        net_inc_growth = (net_income / income_stmt.iloc[1, 1] - 1) if len(income_stmt.columns) > 1 else 0
        eps_growth = info.get('earningsQuarterlyGrowth', 0)
        st.write(f"**צמיחת רווח נקי (שנתי):** {net_inc_growth*100:.2f}%")
        st.write(f"**צמיחת EPS:** {eps_growth*100:.2f}%")
        st.write(f"**הבדל:** {abs(eps_growth - net_inc_growth)*100:.2f}% (אם EPS גדל מהר יותר מהרווח הנקי, זה סימן לרכישת מניות אגרסיבית)")
        
        buyback_val = cash_flow.loc['Repurchase Of Capital Stock', :][0] if 'Repurchase Of Capital Stock' in cash_flow.index else 0
        st.write(f"**סכום רכישת מניות עצמית בדוח זה:** {format_billions(abs(buyback_val))}")

        # --- 5. הערכות שווי (Valuation Models) ---
        st.subheader("⚖️ מודלים להערכת שווי פנימי")
        
        # א. חישוב WACC
        risk_free_rate = 0.042 # 10Y Treasury
        beta = info.get('beta', 1.2)
        market_return = 0.09
        cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
        
        tax_rate = 0.21
        cost_of_debt = interest_exp / total_debt if total_debt > 0 else 0.05
        wacc = ((equity / (equity + total_debt)) * cost_of_equity) + ((total_debt / (equity + total_debt)) * cost_of_debt * (1 - tax_rate))
        
        # ב. DCF
        fcf = info.get('freeCashflow', 1)
        growth_rate = info.get('earningsGrowth', 0.10)
        terminal_growth = 0.02
        
        dcf_years = []
        projected_fcf = fcf
        for i in range(1, 6):
            projected_fcf *= (1 + growth_rate)
            dcf_years.append(projected_fcf / ((1 + wacc) ** i))
        
        terminal_value = (projected_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
        discounted_tv = terminal_value / ((1 + wacc) ** 5)
        intrinsic_value_total = sum(dcf_years) + discounted_tv
        dcf_per_share = intrinsic_value_total / info.get('sharesOutstanding', 1)

        v_col1, v_col2 = st.columns(2)
        with v_col1:
            st.write("**חישוב DCF:**")
            st.write(f"- WACC: {wacc*100:.2f}% (Equity Cost: {cost_of_equity*100:.1f}%)")
            st.write(f"- FCF בסיס: {format_billions(fcf)}")
            st.write(f"- צמיחה חזויה: {growth_rate*100:.1f}%")
            st.metric("שווי DCF", f"${dcf_per_share:.2f}")

        # ג. שיטות נוספות
        with v_col2:
            # מכפילים
            avg_pe = 25 # ממוצע תעשייתי משוער
            relative_val = info.get('forwardEps', 0) * avg_pe
            st.write(f"**שווי יחסי (P/E {avg_pe}):** ${relative_val:.2f}")
            
            # שווי פירוק (NAV)
            nav = (balance_sheet.loc['Total Assets', :][0] - balance_sheet.loc['Total Liabilities', :][0]) / info.get('sharesOutstanding', 1)
            st.write(f"**שווי נכסי נקי (NAV):** ${nav:.2f}")
            
            # מרווח ביטחון
            mos_30 = dcf_per_share * 0.7
            st.write(f"**מחיר כניסה עם מרווח ביטחון (30%):** ${mos_30:.2f}")

        # --- 6. ניתוח טכני ותחזיות ---
        st.subheader("📉 ניתוח טכני ומגמות")
        fig = go.Figure(data=[go.Candlestick(x=hist.index,
                open=hist['Open'], high=hist['High'],
                low=hist['Low'], close=hist['Close'])])
        fig.update_layout(title=f"גרף מחיר {symbol}", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("**תחזיות אנליסטים (Yahoo Finance):**")
        st.write(f"- מחיר יעד ממוצע: ${info.get('targetMeanPrice')}")
        st.write(f"- מחיר יעד גבוה: ${info.get('targetHighPrice')}")
        st.write(f"- המלצה: {info.get('recommendationKey', 'N/A')}")

        # --- 7. סיכום Moat וסיכונים ---
        st.subheader("🛡️ ניתוח איכותי")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**סוגי Moat פוטנציאליים:**")
            st.markdown("- יתרון לגודל (Economies of Scale)\n- אפקט רשת (Network Effect)\n- מותג חזק\n- עלויות מעבר גבוהות")
        with c2:
            st.write("**ממה החברה מושפעת?**")
            st.write(f"- סוג חברה: {info.get('sector', 'N/A')} - {info.get('industry', 'N/A')}")
            st.markdown("- **מה יוריד:** העלאות ריבית, תחרות אגרסיבית, ירידה במרג'ינים.")
            st.markdown("- **מה יעלה:** רכישות עצמיות, חדירה לשווקים חדשים, התייעלות תפעולית.")

        # --- 8. המלצה סופית ---
        st.divider()
        final_intrinsic = (dcf_per_share * 0.6 + relative_val * 0.4)
        st.subheader("🎯 שווי פנימי סופי מוערך")
        st.title(f"${final_intrinsic:.2f}")
        
        if curr_price < final_intrinsic * 0.8:
            st.success(f"המלצה: **קנייה (Buy)** - המניה נסחרת מתחת לשווי הפנימי עם מרווח ביטחון. מחיר יעד לכניסה: ${final_intrinsic*0.9:.2f}")
        elif curr_price < final_intrinsic:
            st.warning("המלצה: **החזק (Hold)** - המניה קרובה לשווי ההוגן שלה.")
        else:
            st.error("המלצה: **המתנה/מכירה** - המניה נראית כרגע מתומחרת ביתר.")

        # חדשות
        st.subheader("📰 חדשות אחרונות")
        for news in ticker.news[:3]:
            st.write(f"[{news['title']}]({news['link']})")

else:
    st.info("הכנס סימול מניה בצד ימין ולחץ על 'הפק דוח ניתוח מלא'.")
