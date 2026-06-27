import streamlit as st
import pandas as pd
import yfinance as yf
import requests

# הגדרות דף
st.set_page_config(layout="wide", page_title="Professional Stock Deep-Dive")

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or val == "":
            return default
        return float(val)
    except:
        return default

def fmt(val):
    if val == 0: return "N/A"
    if abs(val) >= 1e9: return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

st.title("🛡️ Financial Deep-Dive Pro (Yahoo Finance Engine)")
symbol = st.sidebar.text_input("הכנס סימול מניה (למשל AMZN):", "AMZN").upper()

if st.sidebar.button("הפק דוח ניתוח מלא"):
    with st.spinner("עוקף חסימות ומושך נתונים פיננסיים..."):
        try:
            # מנגנון עקיפת חסימות של יאהו פיננס
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            })
            
            ticker = yf.Ticker(symbol, session=session)
            info = ticker.info
            
            if 'shortName' not in info:
                st.error("הנתונים לא נמצאו. ייתכן שהסימול שגוי או שיש בעיית תקשורת קלה.")
                st.stop()

            # --- 1. פרטים כלליים ---
            st.header(f"שם מניה: {info.get('longName', symbol)} ({symbol})")
            st.subheader(f"מכפיל רווח נוכחי (P/E): {info.get('trailingPE', 'N/A')}")
            
            st.write("---")
            st.subheader("💡 תקציר על מה שהחברה עושה")
            st.write(info.get('longBusinessSummary', 'אין תיאור זמין'))

            # --- 2. 12 החוקים ---
            st.header("⚖️ סיכום 12 החוקים (באפטולוגיה)")
            
            cash = safe_float(info.get('totalCash'))
            debt = safe_float(info.get('totalDebt'))
            shares = safe_float(info.get('sharesOutstanding', 1.0))
            equity = safe_float(info.get('bookValue', 0)) * shares
            rev = safe_float(info.get('totalRevenue'))
            gross_margin = safe_float(info.get('grossMargins'))
            net_margin = safe_float(info.get('profitMargins'))
            fcf = safe_float(info.get('freeCashflow'))
            ebitda_margin = safe_float(info.get('ebitdaMargins'))
            
            laws = [
                ["מזומן > חוב", "✅" if cash > debt else "❌", f"C: {fmt(cash)} / D: {fmt(debt)}"],
                ["יחס חוב להון < 0.8", "✅" if equity > 0 and (debt/equity) < 0.8 else "❌", f"{(debt/equity):.2f}" if equity > 0 else "N/A"],
                ["רווח גולמי > 40%", "✅" if gross_margin > 0.4 else "❌", f"{gross_margin*100:.1f}%"],
                ["רווח נקי/הכנסות > 20%", "✅" if net_margin > 0.2 else "❌", f"{net_margin*100:.1f}%"]
            ]
            
            st.table(pd.DataFrame(laws, columns=["חוק", "מצב", "נתון"]))

            # --- 3. סיכום פיננסי ---
            st.subheader("📊 סיכום פיננסי מרכזי")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**נתוני מפתח:**")
                st.table(pd.DataFrame({
                    "מדד": ["הכנסות", "EBITDA", "מזומן", "חוב", "תזרים חופשי (FCF)"],
                    "ערך": [fmt(rev), fmt(rev * ebitda_margin), fmt(cash), fmt(debt), fmt(fcf)]
                }))
            
            # --- 4. חישוב שווי פנימי (DCF) ---
            st.write("---")
            st.header("⚖️ חישוב שווי פנימי (DCF)")
            
            beta = safe_float(info.get('beta', 1.15))
            rf, erp = 0.043, 0.055
            wacc = rf + (beta * erp) # CAPM פשוט לחברות טכנולוגיה
            
            st.code(f"Beta: {beta} | Risk Free: {rf*100}% | WACC: {wacc*100:.2f}%")
            
            growth = safe_float(info.get('earningsGrowth', 0.12))
            growth = max(0.05, min(growth, 0.20)) # הגבלה לטווח הגיוני
            
            if shares > 0 and fcf > 0 and (wacc - 0.03) > 0:
                terminal_value = (fcf * (1 + growth)) / (wacc - 0.03)
                intrinsic_dcf = (fcf + terminal_value) / shares
            else:
                intrinsic_dcf = 0
                st.warning("ה-FCF שלילי, נתונים חסרים או ה-WACC נמוך מדי לחישוב אוטומטי. יש לבצע התאמות ידניות.")
                
            price_pe = safe_float(info.get('forwardPE', 25)) * safe_float(info.get('forwardEps', 5))
            
            football = pd.DataFrame({
                "שיטה": ["DCF (תזרים מהוון)", "מכפילים (Forward P/E)"],
                "שווי למניה": [f"${intrinsic_dcf:.2f}", f"${price_pe:.2f}"]
            })
            st.table(football)

            final_val = (intrinsic_dcf * 0.6 + price_pe * 0.4)
            st.title(f"שווי פנימי סופי משוקלל: ${final_val:.2f}")
            st.subheader(f"מחיר קנייה מבוקש (מרווח ביטחון 30%): ${final_val * 0.7:.2f}")
            
            # --- 5. ניתוח טכני ---
            st.subheader("📉 ניתוח תנועת מחיר (שנה אחרונה)")
            hist = ticker.history(period="1y")
            st.line_chart(hist['Close'])

        except Exception as e:
            st.error(f"שגיאה מערכתית בניתוח: {e}")
