import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from indicators import calculate_rsi, calculate_macd, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RSI_THRESHOLD, VOLUME_MULTIPLIER, MACD_SIGNAL_DIFF
from indicators import check_strategy_match, send_telegram


# === DYNAMIC STOCK FETCHING ===
def fetch_nifty_100():
    try:
        return [
           "ASTERDM.NS", "GSPL.NS", "NATCOPHARM.NS", "MOTILALOFS.NS", "RELIANCE.NS","TCS.NS"
           #  "AADHARHFC.NS",	"AARTIIND.NS",	"ACE.NS",	"ABREL.NS",	"AEGISLOG.NS",	"AFCONS.NS",	"AFFLE.NS",	"ARE&M.NS",	"AMBER.NS",	"ANANTRAJ.NS",	"ANGELONE.NS",	"ASTERDM.NS",	"ATUL.NS",	"BEML.NS",	"BLS.NS",	"BATAINDIA.NS",	"BSOFT.NS",	"FIRSTCRY.NS",	"BRIGADE.NS",	"CESC.NS",	"CASTROLIND.NS",	"CDSL.NS",	"CHAMBLFERT.NS",	"CAMS.NS",	"CREDITACC.NS",	"CROMPTON.NS",	"CYIENT.NS",	"DATAPATTNS.NS",	"DELHIVERY.NS",	"DEVYANI.NS",	"LALPATHLAB.NS",	"FSL.NS",	"FIVESTAR.NS",	"GRSE.NS",	"GODIGIT.NS",	"GODFRYPHLP.NS",	"GESHIP.NS",	"GSPL.NS",	"HBLENGINE.NS",	"HFCL.NS",	"HSCL.NS",	"HINDCOPPER.NS",	"IDBI.NS",	"IFCI.NS",	"IIFL.NS",	"IRCON.NS",	"ITI.NS",	"INDIAMART.NS",	"IEX.NS",	"INOXWIND.NS",	"IGIL.NS",	"IKS.NS",	"JBMA.NS",	"JWL.NS",	"KPIL.NS",	"KARURVYSYA.NS",	"KAYNES.NS",	"KEC.NS",	"KFINTECH.NS",	"LAURUSLABS.NS",	"MGL.NS",	"MANAPPURAM.NS",	"MCX.NS",	"NATCOPHARM.NS",	"NBCC.NS",	"NCC.NS",	"NH.NS",	"NAVINFLUOR.NS",	"NEULANDLAB.NS",	"NEWGEN.NS",	"NUVAMA.NS",	"PCBL.NS",	"PGEL.NS",	"PNBHOUSING.NS",	"PVRINOX.NS",	"PEL.NS",	"PPLPHARMA.NS",	"POONAWALLA.NS",	"RITES.NS",	"RADICO.NS",	"RAILTEL.NS",	"RKFORGE.NS",	"REDINGTON.NS",	"RPOWER.NS",	"SAGILITY.NS",	"SHYAMMETL.NS",	"SIGNATURE.NS",	"SONATSOFTW.NS",	"SWANENERGY.NS",	"TATACHEM.NS",	"TTML.NS",	"TEJASNET.NS",	"RAMCOCEM.NS",	"TITAGARH.NS",	"TRIDENT.NS",	"TRITURBINE.NS",	"WELCORP.NS",	"WELSPUNLIV.NS",	"ZENTEC.NS",	"ZENSARTECH.NS",	"ACC.NS",	"APLAPOLLO.NS",	"AUBANK.NS",	"ATGL.NS",	"ABCAPITAL.NS",	"ABFRL.NS",	"ALKEM.NS",	"APOLLOTYRE.NS",	"ASHOKLEY.NS",	"ASTRAL.NS",	"AUROPHARMA.NS",	"BSE.NS",	"BANDHANBNK.NS",	"BANKINDIA.NS",	"MAHABANK.NS",	"BDL.NS",	"BHARATFORG.NS",	"BHEL.NS",	"BHARTIHEXA.NS",	"BIOCON.NS",	"COCHINSHIP.NS",	"COFORGE.NS",	"COLPAL.NS",	"CONCOR.NS",	"CUMMINSIND.NS",	"DIXON.NS",	"ESCORTS.NS",	"EXIDEIND.NS",	"NYKAA.NS",	"FEDERALBNK.NS",	"GMRAIRPORT.NS",	"GLENMARK.NS",	"GODREJPROP.NS",	"HDFCAMC.NS",	"HINDPETRO.NS",	"HINDZINC.NS",	"HUDCO.NS",	"IDFCFIRSTB.NS",	"IRB.NS",	"INDIANB.NS",	"IRCTC.NS",	"IREDA.NS",	"IGL.NS",	"INDUSTOWER.NS",	"JUBLFOOD.NS",	"KPITTECH.NS",	"KALYANKJIL.NS",	"LTF.NS",	"LICHSGFIN.NS",	"LUPIN.NS",	"MRF.NS",	"M&MFIN.NS",	"MANKIND.NS",	"MARICO.NS",	"MFSL.NS",	"MAXHEALTH.NS",	"MAZDOCK.NS",	"MOTILALOFS.NS",	"MPHASIS.NS",	"MUTHOOTFIN.NS",	"NHPC.NS",	"NMDC.NS",	"NTPCGREEN.NS",	"NATIONALUM.NS",	"OBEROIRLTY.NS",	"OIL.NS",	"OLAELEC.NS",	"PAYTM.NS",	"OFSS.NS",	"POLICYBZR.NS",	"PIIND.NS",	"PAGEIND.NS",	"PATANJALI.NS",	"PERSISTENT.NS",	"PETRONET.NS",	"PHOENIXLTD.NS",	"POLYCAB.NS",	"PREMIERENE.NS",	"PRESTIGE.NS",	"RVNL.NS",	"SBICARD.NS",	"SJVN.NS",	"SRF.NS",	"SOLARINDS.NS",	"SONACOMS.NS",	"SAIL.NS",	"SUPREMEIND.NS",	"SUZLON.NS",	"TATACOMM.NS",	"TATAELXSI.NS",	"TATATECH.NS",	"TORNTPOWER.NS",	"TIINDIA.NS",	"UPL.NS",	"UNIONBANK.NS",	"VMM.NS",	"IDEA.NS",	"VOLTAS.NS",	"WAAREEENER.NS",	"YESBANK.NS",	"ABB.NS",	"ADANIENSOL.NS",	"ADANIENT.NS",	"ADANIGREEN.NS",	"ADANIPORTS.NS",	"ADANIPOWER.NS",	"AMBUJACEM.NS",	"APOLLOHOSP.NS",	"ASIANPAINT.NS",	"DMART.NS",	"AXISBANK.NS",	"BAJAJ-AUTO.NS",	"BAJFINANCE.NS",	"BAJAJFINSV.NS",	"BAJAJHLDNG.NS",	"BAJAJHFL.NS",	"BANKBARODA.NS",	"BEL.NS",	"BPCL.NS",	"BHARTIARTL.NS",	"BOSCHLTD.NS",	"BRITANNIA.NS",	"CGPOWER.NS",	"CANBK.NS",	"CHOLAFIN.NS",	"CIPLA.NS",	"COALINDIA.NS",	"DLF.NS",	"DABUR.NS",	"DIVISLAB.NS",	"DRREDDY.NS",	"EICHERMOT.NS",	"ETERNAL.NS",	"GAIL.NS",	"GODREJCP.NS",	"GRASIM.NS",	"HCLTECH.NS",	"HDFCBANK.NS",	"HDFCLIFE.NS",	"HAVELLS.NS",	"HEROMOTOCO.NS",	"HINDALCO.NS",	"HAL.NS",	"HINDUNILVR.NS",	"HYUNDAI.NS",	"ICICIBANK.NS",	"ICICIGI.NS",	"ICICIPRULI.NS",	"ITC.NS",	"INDHOTEL.NS",	"IOC.NS",	"IRFC.NS",	"INDUSINDBK.NS",	"NAUKRI.NS",	"INFY.NS",	"INDIGO.NS",	"JSWENERGY.NS",	"JSWSTEEL.NS",	"JINDALSTEL.NS",	"JIOFIN.NS",	"KOTAKBANK.NS",	"LTIM.NS",	"LT.NS",	"LICI.NS",	"LODHA.NS",	"M&M.NS",	"MARUTI.NS",	"NTPC.NS",	"NESTLEIND.NS",	"ONGC.NS",	"PIDILITIND.NS",	"PFC.NS",	"POWERGRID.NS",	"PNB.NS",	"RECLTD.NS",	"RELIANCE.NS",	"SBILIFE.NS",	"MOTHERSON.NS",	"SHREECEM.NS",	"SHRIRAMFIN.NS",	"SIEMENS.NS",	"SBIN.NS",	"SUNPHARMA.NS",	"SWIGGY.NS",	"TVSMOTOR.NS",	"TCS.NS",	"TATACONSUM.NS",	"TATAMOTORS.NS",	"TATAPOWER.NS",	"TATASTEEL.NS",	"TECHM.NS",	"TITAN.NS",	"TORNTPHARM.NS",	"TRENT.NS",	"ULTRACEMCO.NS",	"UNITDSPR.NS",	"VBL.NS",	"VEDL.NS",	"WIPRO.NS",	"ZYDUSLIFE.NS"
        ]
    except Exception as e:
        print(f"⚠️ Could not fetch NIFTY 100 from NSE: {e}")
        return [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TORNTPHARM.NS"
        ]

# === SCREENING FUNCTION ===
def analyze_stock(ticker):
    print(f"\n📊 Analyzing: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        if df.empty or any(col not in df.columns for col in ['Close', 'Volume']) or len(df) < 50:
            print("⚠️ Missing data or columns")
            return None

        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['Signal'] = calculate_macd(df['Close'])
        df['Volume_avg'] = df['Volume'].rolling(window=20).mean()

        df['Signal_Trigger'] = (
            (df['Close'] > df['EMA_50']) &
            (df['RSI'] > 55) &
            (df['MACD'] > df['Signal']) &
            (df['Volume'] > 1.2 * df['Volume_avg'])
        )

        df['Sell_Trigger'] = False
        df.dropna(inplace=True)

        # ✅ Hybrid Exit + Stop Loss
        in_position = False
        entry_price = None

        for i in range(len(df)):
            row = df.iloc[i]

            if row['Signal_Trigger']:
                in_position = True
                entry_price = row['Close']

            elif in_position:
                sell_condition = (
                    (row['RSI'] < 50) or
                    (row['MACD'] < row['Signal']) or
                    (row['Close'] < row['EMA_50'])
                )
                stop_loss_hit = row['Close'] < entry_price * 0.97  # 3% loss

                if (sell_condition and row['Close'] > entry_price) or stop_loss_hit:
                    df.at[df.index[i], 'Sell_Trigger'] = True
                    in_position = False

        latest = df.iloc[-1]

        # Count how many of 4 conditions are True on the latest day
        match_type = check_strategy_match(latest)

                        
        if match_type is None:
            return None

        history = df.tail(30).copy()
        history_json = [
            {
                "date": str(idx.date()),
                "close": round(row.Close, 2),
                "ema": round(row.EMA_50, 2),
                "rsi": round(row.RSI, 2),
                "macd": round(row.MACD, 2),
                "signal": round(row.Signal, 2),
                "volume": int(row.Volume),
                "volumeAvg": int(row.Volume_avg),
                "signal_trigger": bool(row.Signal_Trigger),
                "sell_trigger": bool(row.Sell_Trigger)
            }
            for idx, row in history.iterrows()
        ]
        
        stock_info = {
            "ticker": ticker,
            "close": round(latest['Close'], 2),
            "rsi": round(latest['RSI'], 2),
            "macd": round(latest['MACD'], 2),
            "volume": int(latest['Volume']),
            "match_type": match_type,
            "history": history_json
        }

        return stock_info

    except Exception as e:
        print(f"❌ Error for {ticker}: {e}")
        return None
        
# === FORMAT & SEND RESULTS ===
def format_stock_list(title, stock_list):
    message = f"*{title}*\n"
    for stock in stock_list:
        message += f"🔹 `{stock['ticker']}`  | 💰 {stock['close']}  | 💹 RSI: {stock['rsi']}\n"
    return message

def run_screener():
    full_matches = []
    partial_matches = []

    tickers = fetch_nifty_100()
    for ticker in tickers:
        stock = analyze_stock(ticker)
        if not stock:
            continue

        latest = stock["history"][-1]
        conditions = [
            latest["close"] > latest["ema"],
            latest["rsi"] > RSI_THRESHOLD,
            latest["macd"] > latest["signal"] + MACD_SIGNAL_DIFF,
            latest["volume"] > VOLUME_MULTIPLIER * latest["volumeAvg"]
        ]
        matched_count = sum(conditions)

        if matched_count == 4:
            full_matches.append(stock)
        elif matched_count == 3:
            partial_matches.append(stock)

        time.sleep(0.2)

    if full_matches:
        message = format_stock_list("🎯 *Full Match Stocks*", full_matches)
        send_telegram(message)
    else:
        send_telegram("🚫 *No full-match stocks today.*")

    if partial_matches:
        message = format_stock_list("🟡 *Partial Match Stocks (3/4)*", partial_matches)
        send_telegram(message)

# === RUN ===
if __name__ == "__main__":
    run_screener()
