import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from yahooquery import Ticker
from datetime import datetime

# הגדרות עמוד
st.set_page_config(layout="wide", page_title="Financial Deep-Dive Pro")


# --- פונקציות עזר להמרת נתונים בטוחה ---
def fmt_curr(val):
    if val is None or pd.isna(val) or val == 0:
        return "N/A"
    val = float(val)
    if abs(val) >= 1e9:
        return f"${val / 1e9:.2f}B"
    if abs(val) >= 1e6:
        return f"${val / 1e6:.2f}M"
    return f"${val:,.2f}"


def fmt_pct(val):
    if val is None or pd.isna(val):
        return "N/A"
    return f"{float(val) * 100:.2f}%"


def safe_num(row, col_name, default=0.0):
    try:
        if col_name in row and pd.notna(row[col_name]):
            return float(row[col_name])
    except Exception:
        pass
    return default


# --- ממשק האפליקציה ---
st.title("📊 Financial Deep-Dive Pro")
symbol = st.sidebar.text_input(
    "הכנס סימול מניה (למשל AMZN, MSFT, AAPL):", "AMZN"
).upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner(f"מושך ומעבד את דוחות {symbol}..."):
        try:
            t = Ticker(symbol)

            # שליפת המילונים מתוך yahooquery (מגיעים עם מפתח של שם המניה)
            price_data = t.price.get(symbol, {})
            if not isinstance(price_data, dict) or "regularMarketPrice" not in price_data:
                st.error("לא ניתן למשוך את המניה. בדוק שהסימול תקין או נסה שוב בעוד דקה.")
                st.stop()

            fin_data = t.financial_data.get(symbol, {})
            key_stats = t.key_stats.get(symbol, {})
            summary_prof = t.summary_profile.get(symbol, {})

            # שליפת הדוחות הגולמיים
            inc_raw = t.income_statement()
            bs_raw = t.balance_sheet()
            cf_raw = t.cash_flow()

            if isinstance(inc_raw, str) or isinstance(bs_raw, str) or inc_raw.empty or bs_raw.empty:
                st.error("הדוחות הכספיים המלאים של חברה זו אינם זמינים בשרת.")
                st.stop()

            # השטחת הדוחות (הפיכת מולטי-אינדקס לטבלה רגילה ומיון לפי תאריך)
            inc_df = inc_raw.reset_index().sort_values("asOfDate")
            bs_df = bs_raw.reset_index().sort_values("asOfDate")
            cf_df = cf_raw.reset_index().sort_values("asOfDate")

            # חילוץ הדוח השנתי האחרון והלפני אחרון
            curr_is = inc_df.iloc[-1]
            prev_is = inc_df.iloc[-2] if len(inc_df) > 1 else curr_is

            curr_bs = bs_df.iloc[-1]
            prev_bs = bs_df.iloc[-2] if len(bs_df) > 1 else curr_bs

            curr_cf = cf_df.iloc[-1]

            # --- מידע בסיסי ותאריכים ---
            st.header(f"שם מניה: {price_data.get('longName', symbol)} ({symbol})")
            curr_price = price_data.get("regularMarketPrice", 0)
            st.subheader(f"מחיר מניה כרגע: ${curr_price}")

            report_date_str = str(curr_is["asOfDate"])[:10]
            st.write(f"**תאריך מדויק של הדוח השנתי שנבדק:** {report_date_str}")

            st.write("---")
            st.subheader("💡 תקציר על מה שהחברה עושה")
            st.write(summary_prof.get("longBusinessSummary", "אין תקציר זמין."))

            # --- חילוץ משתנים פיננסיים לחישובים ---
            rev = safe_num(curr_is, "TotalRevenue", 1.0)
            gp = safe_num(curr_is, "GrossProfit")
            ni = safe_num(curr_is, "NetIncome")
            ebit = safe_num(curr_is, "OperatingIncome") or safe_num(curr_is, "Ebit", 1.0)
            int_exp = abs(safe_num(curr_is, "InterestExpense"))
            sga = safe_num(curr_is, "SellingGeneralAndAdministration") or safe_num(curr_is, "SellingGeneralAdministrative")
            rnd = safe_num(curr_is, "ResearchAndDevelopment")
            pretax = safe_num(curr_is, "PretaxIncome", 1.0)
            tax = abs(safe_num(curr_is, "TaxProvision"))

            cash = safe_num(curr_bs, "CashAndCashEquivalents")
            debt = safe_num(curr_bs, "TotalDebt")
            equity = safe_num(curr_bs, "StockholdersEquity", 1.0)
            liabilities = safe_num(curr_bs, "TotalLiabilitiesNetMinorityInterest") or safe_num(curr_bs, "TotalLiabilities")

            retained = safe_num(curr_bs, "RetainedEarnings")
            prev_retained = safe_num(prev_bs, "RetainedEarnings")

            fcf = safe_num(curr_cf, "FreeCashFlow") or fin_data.get("freeCashflow", 0)
            buybacks = abs(safe_num(curr_cf, "RepurchaseOfCapitalStock"))

            # --- 1. סיכום 12 החוקים ---
            st.write("---")
            st.header("📋 סיכום 12 החוקים (באפטולוגיה)")

            gp_margin = (gp / rev) if rev else 0
            sga_ratio = (sga / gp) if gp else 0
            rnd_ratio = (rnd / gp) if gp else 0
            int_ratio = (int_exp / ebit) if ebit else 0
            tax_rate = (tax / pretax) if pretax else 0
            net_margin = (ni / rev) if rev else 0
            d_to_e = (liabilities / equity) if equity else 0

            rules_data = [
                ["1. מזומן גדול מהחוב", "עומד" if cash > debt else "לא עומד", f"C: {fmt_curr(cash)} | D: {fmt_curr(debt)}"],
                ["2. יחס חוב להון (D/E) מתחת ל-0.8", "עומד" if d_to_e < 0.8 else "לא עומד", f"{d_to_e:.2f}"],
                ["3. אין מניות בכורה בדוח", "עומד" if safe_num(curr_bs, "PreferredStock") == 0 else "לא עומד", "תקין"],
                ["4. רווחים צבורים בצמיחה", "עומד" if retained > prev_retained else "לא עומד", f"השנה: {fmt_curr(retained)}"],
                ["5. מניות באוצר (Buyback קיימות)", "עומד" if buybacks > 0 else "בדיקה", f"נרכשו: {fmt_curr(buybacks)}"],
                ["6. רווח גולמי מעל 40%", "עומד" if gp_margin > 0.4 else "לא עומד", fmt_pct(gp_margin)],
                ["7. הוצאות תפעול/גולמי מתחת 30%", "עומד" if sga_ratio < 0.3 else "לא עומד", fmt_pct(sga_ratio)],
                ["8. מו\"פ / רווח גולמי מתחת 30%", "עומד" if rnd_ratio < 0.3 else "לא עומד", fmt_pct(rnd_ratio)],
                ["9. הוצאות ריבית/תפעולי מתחת 15%", "עומד" if int_ratio < 0.15 else "לא עומד", fmt_pct(int_ratio)],
                ["10. מס הכנסה סביב 20%", "עומד" if 0.12 <= tax_rate <= 0.28 else "בדיקה", fmt_pct(tax_rate)],
                ["11. רווח נקי מהכנסות מעל 20%", "עומד" if net_margin > 0.2 else "לא עומד", fmt_pct(net_margin)],
                ["12. EPS במגמת צמיחה", "עומד" if key_stats.get("earningsQuarterlyGrowth", 0) > 0 else "לא עומד", fmt_pct(key_stats.get("earningsQuarterlyGrowth", 0))]
            ]

            st.table(pd.DataFrame(rules_data, columns=["החוק הפיננסי", "מצב", "נתון נמדד בפועל"]))

            # --- 2. טבלאות נתונים פיננסיים ---
            st.write("---")
            st.subheader("💰 נתונים פיננסיים מרכזיים ומדדים")

            ebitda_val = fin_data.get("ebitda", 0) or safe_num(curr_is, "NormalizedEBITDA")
            fin_table = pd.DataFrame({
                "סעיף בדוח": ["הכנסות", "EBITDA", "רווח תפעולי", "רווח נקי", "מזומנים ושווי מזומנים", "סך החוב"],
                "ערך כספי": [fmt_curr(rev), fmt_curr(ebitda_val), fmt_curr(ebit), fmt_curr(ni), fmt_curr(cash), fmt_curr(debt)],
                "אחוז מתוך ההכנסות": ["100%", fmt_pct(ebitda_val/rev), fmt_pct(ebit/rev), fmt_pct(ni/rev), "-", "-"]
            })
            st.table(fin_table)

            st.info(f"**כמה Free Cash Flow יש לחברה?** {fmt_curr(fcf)}")

            # --- 3. השוואת צמיחה ורכישה עצמית ---
            st.subheader("📈 צמיחת EPS לעומת רווח נקי")
            prev_ni = safe_num(prev_is, "NetIncome", 1.0)
            ni_growth = (ni / prev_ni) - 1 if prev_ni else 0
            eps_g = key_stats.get("earningsQuarterlyGrowth", 0) or 0

            col_g1, col_g2 = st.columns(2)
            col_g1.write(f"- **צמיחת רווח נקי:** {fmt_pct(ni_growth)}")
            col_g1.write(f"- **צמיחת EPS (רווח למניה):** {fmt_pct(eps_g)}")
            col_g2.write(f"- **כמה מניות קנתה בחזרה בדוח הזה?** {fmt_curr(buybacks)}")
            st.caption("הסבר: אם ה-EPS צומח בקצב מהיר יותר מהרווח הנקי עצמו, זה מוכיח שהחברה מקטינה את כמות המניות בשוק ומייצרת ערך למשקיעים.")

            # --- 4. ניתוח איכותי (Moat ומקורות הכנסה) ---
            st.write("---")
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                st.subheader("🏰 סוגי Moat (חפיר כלכלי) במניה")
                st.markdown("- **יתרון לגודל:** חברה בעלת פריסה ומשאבים שמקשים על מתחרים לחקות אותה.")
                st.markdown("- **כוח מותג:** נאמנות לקוחות המאפשרת לה לשמור על רווח גולמי גבוה.")
                st.markdown("- **עלויות מעבר:** חסם טכנולוגי או פסיכולוגי המקשה על הלקוח לנטוש למתחרה.")
            with col_q2:
                st.subheader("💼 ממה החברה מרוויחה כסף?")
                st.write(f"**מגזר:** {summary_prof.get('sector', 'כללי')}")
                st.write(f"**תעשייה:** {summary_prof.get('industry', 'כללי')}")
                st.write("ההכנסות מגיעות ממגזרי הליבה המפורטים בדוחות התפעוליים של החברה.")

            # --- 5. מודלי הערכת שווי (Valuation) ---
            st.write("---")
            st.header("⚖️ מודלים של הערכת שווי פנימי")

            # חישוב WACC מלא ושקוף
            beta_val = key_stats.get("beta", 1.1) or 1.1
            rf_rate = 0.043
            market_prem = 0.055
            cost_of_equity = rf_rate + (beta_val * market_prem)
            cost_of_debt_val = (int_exp / debt) if debt > 100000 else 0.05
            weight_e = equity / (equity + debt) if (equity + debt) else 1
            weight_d = debt / (equity + debt) if (equity + debt) else 0

            wacc = (weight_e * cost_of_equity) + (weight_d * cost_of_debt_val * (1 - 0.21))
            if wacc < 0.04: wacc = 0.08 # הגנה ממספרים לא הגיוניים

            shares_out = key_stats.get("sharesOutstanding", 1) or 1
            growth_proj = fin_data.get("earningsGrowth", 0.08) or 0.08

            st.subheader("1. היוון תזרים מזומנים (DCF) - שלבי החישוב המלאים:")
            st.code(
                f"Cost of Equity = {rf_rate} + ({beta_val} * {market_prem}) = {cost_of_equity*100:.2f}%\n"
                f"Cost of Debt (Net Tax) = {cost_of_debt_val*100:.2f}% * (1 - 0.21) = {cost_of_debt_val*0.79*100:.2f}%\n"
                f"WACC = ({weight_e:.2f} * {cost_of_equity*100:.2f}%) + ({weight_d:.2f} * {cost_of_debt_val*0.79*100:.2f}%) = {wacc*100:.2f}%"
            )

            # נוסחת DCF פשוטה עם צמיחה ל-5 שנים
            base_fcf = fcf if fcf > 0 else ni
            dcf_total = (base_fcf * (1 + growth_proj)) / (wacc - 0.025)
            price_dcf = dcf_total / shares_out

            # שיטות שווי נוספות
            forward_eps_val = key_stats.get("forwardEps", 0) or (ni / shares_out)
            price_relative = forward_eps_val * 22.0 # מכפיל 22 סביר
            price_nav = equity / shares_out

            st.subheader("2. שיטת 'מגרש הכדורגל' (Football Field)")
            football_df = pd.DataFrame({
                "מודל הערכה": ["DCF (תזרים מזומנים)", "Relative (מכפיל רווח 22)", "NAV (שווי נכסי מפרק)"],
                "שווי מוערך למניה": [f"${price_dcf:.2f}", f"${price_relative:.2f}", f"${price_nav:.2f}"]
            })
            st.table(football_df)

            # שווי משוקלל סופי ומרווח ביטחון
            final_intrinsic = (price_dcf * 0.65) + (price_relative * 0.35)
            mos_price = final_intrinsic * 0.70 # הנחת מרווח ביטחון של 30%

            st.title(f"🎯 שווי פנימי סופי מוערך: ${final_intrinsic:.2f}")
            st.subheader(f"🛡️ מודל מרווח ביטחון (מחיר קנייה אידיאלי): ${mos_price:.2f}")

            # --- 6. תחזיות, גרף והמלצה ---
            st.write("---")
            st.subheader("📉 נתונים חזויים וניתוח טכני")

            try:
                hist_df = t.history(period="1y").reset_index()
                fig = go.Figure(data=[go.Candlestick(x=hist_df['date'], open=hist_df['open'], high=hist_df['high'], low=hist_df['low'], close=hist_df['close'])])
                fig.update_layout(title="גרף טכני - שנה אחרונה", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                st.write("**ניתוח טכני קצר:** בדוק את התנהגות המחיר סביב הממוצע הנע ל-50 יום בגרף הנרות.")
            except Exception:
                st.warning("לא ניתן לטעון את הגרף הטכני כרגע.")

            st.write(f"- **תחזית אנליסטים (מחיר יעד ממוצע):** ${fin_data.get('targetMeanPrice', 'N/A')}")
            st.write(f"- **תחזית אנליסטים (מחיר יעד גבוה):** ${fin_data.get('targetHighPrice', 'N/A')}")

            st.subheader("📰 חדשות עדכניות על החברה")
            try:
                news = t.news(4)
                for n in news:
                    st.markdown(f"🔹 **[{n.get('title')}]({n.get('link')})**")
            except Exception:
                st.write("לא נמצאו עדכוני חדשות זמינים.")

            # שורה תחתונה
            st.write("---")
            st.header("📌 השורה התחתונה - המלצת המשקיע")
            if curr_price < mos_price:
                st.success(f"המלצה: **קנייה חזקה**. המחיר בשוק (${curr_price}) נמוך ממחיר מרווח הביטחון (${mos_price:.2f}).")
            elif curr_price < final_intrinsic:
                st.warning(f"המלצה: **קנייה זהירה / החזק**. המניה מתחת לשווי ההוגן (${final_intrinsic:.2f}) אך ללא מרווח ביטחון מלא.")
            else:
                st.error(f"המלצה: **המתנה / מכירה**. המניה נסחרת מעל השווי הפנימי שלה.")

        except Exception as e:
            st.error(f"אירעה שגיאה בעיבוד הנתונים: {e}")
