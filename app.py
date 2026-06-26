import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests

# הגדרת דף
st.set_page_config(layout="wide", page_title="PRO Stock Analyzer")

# פונקציה לעקיפת חסימות ו-Cache נכון
@st.cache_resource(ttl=3600)
def get_ticker_resource(symbol):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    return yf.Ticker(symbol, session=session)

def format_bn(val):
    if val is None or np.isnan(val): return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    return f"${val/1e6:.2f}M"

# --- ממשק משתמש ---
st.title("📊 Financial Deep-Dive Pro")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    try:
        ticker = get_ticker_resource(symbol)
        info = ticker.info
        
        if 'currentPrice' not in info:
            st.error("לא ניתן למשוך נתונים. נסה שוב בעוד דקה (Yahoo Limit).")
            st.stop()

        # דוחות כספיים
        is_stmt = ticker.financials
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        # 1. פרטים כלליים
        st.header(f"שם מניה: {info.get('longName')} | מחיר נוכחי: ${info.get('currentPrice')}")
        last_date = is_stmt.columns[0].strftime('%Y-%m-%d')
        st.write(f"**תאריך דוח אחרון שנבדק:** {last_date}")
        st.info(f"**מה החברה עושה:** {info.get('longBusinessSummary')[:600]}...")

        # 2. בדיקת 12 החוקים
        st.subheader("🛡️ בדיקת 12 החוקים הפיננסיים")
        
        # שליפת נתונים למשתנים
        rev = info.get('totalRevenue', 1)
        gp = info.get('grossProfits', 0)
        ni = info.get('netIncomeToCommon', 0)
        cash = info.get('totalCash', 0)
        debt = info.get('totalDebt', 0)
        equity = info.get('totalStockholderEquity', 1)
        op_inc = is_stmt.loc['Operating Income'][0] if 'Operating Income' in is_stmt.index else 0
        int_exp = abs(is_stmt.loc['Interest Expense'][0]) if 'Interest Expense' in is_stmt.index else 0
        sga = is_stmt.loc['Selling General Administrative'][0] if 'Selling General Administrative' in is_stmt.index else 0
        rnd = is_stmt.loc['Research Development'][0] if 'Research Development' in is_stmt.index else 0
        tax = abs(is_stmt.loc['Tax Provision'][0]) if 'Tax Provision' in is_stmt.index else 0
        pretax = is_stmt.loc['Pretax Income'][0] if 'Pretax Income' in is_stmt.index else 1
        retained = bs.loc['Retained Earnings'][0] if 'Retained Earnings' in bs.index else 0
        
        rules = [
            {"חוק": "מזומן > חוב", "מצב": "✅" if cash > debt else "❌", "ערך": f"{format_bn(cash)} vs {format_bn(debt)}"},
            {"חוק": "חוב/הון < 0.8", "מצב": "✅" if (debt/equity) < 0.8 else "❌", "ערך": f"{(debt/equity):.2f}"},
            {"חוק": "אין מניות בכורה", "מצב": "✅" if 'Preferred Stock' not in bs.index else "⚠️", "ערך": "נקי"},
            {"חוק": "רווח גולמי > 40%", "מצב": "✅" if (gp/rev) > 0.4 else "❌", "ערך": f"{(gp/rev)*100:.1f}%"},
            {"חוק": "הוצאות הנהלה/גולמי < 30%", "מצב": "✅" if (sga/gp) < 0.3 else "❌", "ערך": f"{(sga/gp)*100:.1f}%"},
            {"חוק": "הוצאות מו\"פ/גולמי < 30%", "מצב": "✅" if (rnd/gp) < 0.3 else "❌", "ערך": f"{(rnd/gp)*100:.1f}%"},
            {"חוק": "ריבית/רווח תפעולי < 15%", "מצב": "✅" if (int_exp/op_inc) < 0.15 else "❌", "ערך": f"{(int_exp/op_inc)*100:.1f}%"},
            {"חוק": "רווח נקי > 20%", "מצב": "✅" if (ni/rev) > 0.2 else "❌", "ערך": f"{(ni/rev)*100:.1f}%"},
            {"חוק": "שיעור מס תקין (~20%)", "מצב": "✅" if 0.15 < (tax/pretax) < 0.3 else "⚠️", "ערך": f"{(tax/pretax)*100:.1f}%"},
            {"חוק": "רווחים צבורים בצמיחה", "מצב": "✅" if retained > (bs.loc['Retained Earnings'][1] if len(bs.columns)>1 else 0) else "❌", "ערך": format_bn(retained)},
            {"חוק": "מניות באוצר / Buybacks", "מצב": "✅" if 'Treasury Stock' in bs.index or (info.get('sharesOutstanding') < info.get('impliedSharesOutstanding', 0)) else "⚪", "ערך": "קיימות"},
            {"חוק": "EPS בצמיחה", "מצב": "✅" if info.get('earningsGrowth', 0) > 0 else "❌", "ערך": f"{info.get('earningsGrowth', 0)*100:.1f}%"}
        ]
        st.table(pd.DataFrame(rules))

        # 3. טבלאות נתונים וצמיחה
        st.subheader("💰 נתונים פיננסיים מסכמים")
        summary_table = {
            "מדד": ["הכנסות", "רווח תפעולי", "EBITDA", "רווח נקי", "מזומן", "חוב"],
            "ערך": [format_bn(rev), format_bn(op_inc), format_bn(info.get('ebitda', 0)), format_bn(ni), format_bn(cash), format_bn(debt)],
            "אחוז מהכנסות": ["100%", f"{(op_inc/rev)*100:.1f}%", f"{(info.get('ebitda',0)/rev)*100:.1f}%", f"{(ni/rev)*100:.1f}%", "-", "-"]
        }
        st.table(pd.DataFrame(summary_table))

        # השוואת צמיחה ו-Buybacks
        eps_g = info.get('earningsQuarterlyGrowth', 0)
        ni_g = (ni / is_stmt.iloc[0, 1] - 1) if len(is_stmt.columns) > 1 else 0
        buybacks = abs(cf.loc['Repurchase Of Capital Stock'][0]) if 'Repurchase Of Capital Stock' in cf.index else 0
        
        col_g1, col_g2 = st.columns(2)
        col_g1.metric("צמיחת EPS", f"{eps_g*100:.1f}%")
        col_g1.metric("צמיחת רווח נקי", f"{ni_g*100:.1f}%")
        col_g2.metric("מניות שנקנו בחזרה (Buybacks)", format_bn(buybacks))
        st.write(f"**הבדל בצמיחה:** {abs(eps_g - ni_g)*100:.1f}% (צמיחת EPS גבוהה יותר מעידה על רכישת מניות חזקה).")

        # 4. מודל DCF ו-WACC מפורט
        st.subheader("⚖️ הערכת שווי פנימי (Intrinsic Value)")
        
        # חישוב WACC
        rf = 0.042 # Risk free 10Y
        beta = info.get('beta', 1.1)
        erp = 0.05 # Equity Risk Premium
        cost_of_equity = rf + (beta * erp)
        tax_rate = 0.21
        cost_of_debt = (int_exp / debt) if debt > 0 else 0.05
        weight_e = equity / (equity + debt)
        weight_d = debt / (equity + debt)
        wacc = (weight_e * cost_of_equity) + (weight_d * cost_of_debt * (1 - tax_rate))
        
        st.write(f"**שלבי חישוב WACC:**")
        st.code(f"Cost of Equity = {rf} + ({beta} * {erp}) = {cost_of_equity:.2f}\nWeight Equity = {weight_e:.2f}, Weight Debt = {weight_d:.2f}\nWACC = {wacc*100:.2f}%")

        fcf = info.get('freeCashflow', 1e6)
        growth = info.get('earningsGrowth', 0.1)
        dcf_val = (fcf * (1 + growth)) / (wacc - 0.02)
        price_dcf = dcf_val / info.get('sharesOutstanding', 1)
        
        # שיטות נוספות
        price_pe = info.get('forwardPE', 20) * info.get('forwardEps', 1)
        price_nav = equity / info.get('sharesOutstanding', 1)
        
        # 5. טבלת מגרש כדורגל (Football Field)
        st.write("**מגרש כדורגל - טווחי שווי:**")
        football_data = {
            "שיטה": ["DCF", "מכפילים (P/E)", "שווי נכסי (NAV)"],
            "מחיר למניה": [f"${price_dcf:.2f}", f"${price_pe:.2f}", f"${price_nav:.2f}"]
        }
        st.table(pd.DataFrame(football_data))

        # מרווח ביטחון
        final_fair = (price_dcf * 0.6 + price_pe * 0.4)
        st.metric("שווי הוגן סופי", f"${final_fair:.2f}")
        st.metric("מחיר קנייה (מרווח ביטחון 30%)", f"${final_fair*0.7:.2f}")

        # 6. ניתוח טכני ו-Moat
        st.subheader("🏰 ניתוח איכותי וטכני")
        hist = ticker.history(period="1y")
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("**סוגי Moat:** יתרון לגודל, מותג, אפקט רשת.")
        st.write(f"**ממה החברה מרוויחה:** {info.get('sector')} - {info.get('industry')}")
        
        st.write("**תחזית אנליסטים:**")
        st.write(f"מחיר יעד ממוצע: ${info.get('targetMeanPrice')} | המלצה: {info.get('recommendationKey')}")

    except Exception as e:
        st.error(f"אירעה שגיאה בחישובים: {e}")
