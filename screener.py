import yfinance as yf 
import pandas as pd
import time
from supabase import create_client, Client
import os
from indicators import (
    calculate_additional_indicators,
    advanced_strategy_score,
    send_telegram,
    detect_candle_pattern,
    SCORE_THRESHOLD,
    SUPABASE_URL,
    SUPABASE_KEY
)

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------------------------
# List of stocks (can later be dynamic from NSE CSV)
# ------------------------------------------------------------------

def fetch_nifty_stocks():
    try:
        response = supabase.table("master_stocks") \
            .select("ticker") \
            .eq("status", "Active") \
            .eq("exchange", "NSE") \
            .limit(2999) \
            .execute()

        tickers = [row["ticker"] for row in response.data]
        print(f"✅ Loaded {len(tickers)} tickers from Supabase")
        return tickers
    except Exception as e:
        print(f"❌ Failed to fetch tickers: {e}")
        return []

def fetch_nifty_100_old():
    try:
        return [
           #  "VMM.NS", "NTPCGREEN.NS", "MCX.NS", "CREDITACC.NS", "RELIANCE.NS","TCS.NS"
            # "AADHARHFC.NS",	"AARTIIND.NS",	"ACE.NS",	"ABREL.NS",	"AEGISLOG.NS",	"AFCONS.NS",	"AFFLE.NS",	"ARE&M.NS",	"AMBER.NS",	"ANANTRAJ.NS",	"ANGELONE.NS",	"ASTERDM.NS",	"ATUL.NS",	"BEML.NS",	"BLS.NS",	"BATAINDIA.NS",	"BSOFT.NS",	"FIRSTCRY.NS",	"BRIGADE.NS",	"CESC.NS",	"CASTROLIND.NS",	"CDSL.NS",	"CHAMBLFERT.NS",	"CAMS.NS",	"CREDITACC.NS",	"CROMPTON.NS",	"CYIENT.NS",	"DATAPATTNS.NS",	"DELHIVERY.NS",	"DEVYANI.NS",	"LALPATHLAB.NS",	"FSL.NS",	"FIVESTAR.NS",	"GRSE.NS",	"GODIGIT.NS",	"GODFRYPHLP.NS",	"GESHIP.NS",	"GSPL.NS",	"HBLENGINE.NS",	"HFCL.NS",	"HSCL.NS",	"HINDCOPPER.NS",	"IDBI.NS",	"IFCI.NS",	"IIFL.NS",	"IRCON.NS",	"ITI.NS",	"INDIAMART.NS",	"IEX.NS",	"INOXWIND.NS",	"IGIL.NS",	"IKS.NS",	"JBMA.NS",	"JWL.NS",	"KPIL.NS",	"KARURVYSYA.NS",	"KAYNES.NS",	"KEC.NS",	"KFINTECH.NS",	"LAURUSLABS.NS",	"MGL.NS",	"MANAPPURAM.NS",	"MCX.NS",	"NATCOPHARM.NS",	"NBCC.NS",	"NCC.NS",	"NH.NS",	"NAVINFLUOR.NS",	"NEULANDLAB.NS",	"NEWGEN.NS",	"NUVAMA.NS",	"PCBL.NS",	"PGEL.NS",	"PNBHOUSING.NS",	"PVRINOX.NS",	"PEL.NS",	"PPLPHARMA.NS",	"POONAWALLA.NS",	"RITES.NS",	"RADICO.NS",	"RAILTEL.NS",	"RKFORGE.NS",	"REDINGTON.NS",	"RPOWER.NS",	"SAGILITY.NS",	"SHYAMMETL.NS",	"SIGNATURE.NS",	"SONATSOFTW.NS",	"SWANENERGY.NS",	"TATACHEM.NS",	"TTML.NS",	"TEJASNET.NS",	"RAMCOCEM.NS",	"TITAGARH.NS",	"TRIDENT.NS",	"TRITURBINE.NS",	"WELCORP.NS",	"WELSPUNLIV.NS",	"ZENTEC.NS",	"ZENSARTECH.NS",	"ACC.NS",	"APLAPOLLO.NS",	"AUBANK.NS",	"ATGL.NS",	"ABCAPITAL.NS",	"ABFRL.NS",	"ALKEM.NS",	"APOLLOTYRE.NS",	"ASHOKLEY.NS",	"ASTRAL.NS",	"AUROPHARMA.NS",	"BSE.NS",	"BANDHANBNK.NS",	"BANKINDIA.NS",	"MAHABANK.NS",	"BDL.NS",	"BHARATFORG.NS",	"BHEL.NS",	"BHARTIHEXA.NS",	"BIOCON.NS",	"COCHINSHIP.NS",	"COFORGE.NS",	"COLPAL.NS",	"CONCOR.NS",	"CUMMINSIND.NS",	"DIXON.NS",	"ESCORTS.NS",	"EXIDEIND.NS",	"NYKAA.NS",	"FEDERALBNK.NS",	"GMRAIRPORT.NS",	"GLENMARK.NS",	"GODREJPROP.NS",	"HDFCAMC.NS",	"HINDPETRO.NS",	"HINDZINC.NS",	"HUDCO.NS",	"IDFCFIRSTB.NS",	"IRB.NS",	"INDIANB.NS",	"IRCTC.NS",	"IREDA.NS",	"IGL.NS",	"INDUSTOWER.NS",	"JUBLFOOD.NS",	"KPITTECH.NS",	"KALYANKJIL.NS",	"LTF.NS",	"LICHSGFIN.NS",	"LUPIN.NS",	"MRF.NS",	"M&MFIN.NS",	"MANKIND.NS",	"MARICO.NS",	"MFSL.NS",	"MAXHEALTH.NS",	"MAZDOCK.NS",	"MOTILALOFS.NS",	"MPHASIS.NS",	"MUTHOOTFIN.NS",	"NHPC.NS",	"NMDC.NS",	"NTPCGREEN.NS",	"NATIONALUM.NS",	"OBEROIRLTY.NS",	"OIL.NS",	"OLAELEC.NS",	"PAYTM.NS",	"OFSS.NS",	"POLICYBZR.NS",	"PIIND.NS",	"PAGEIND.NS",	"PATANJALI.NS",	"PERSISTENT.NS",	"PETRONET.NS",	"PHOENIXLTD.NS",	"POLYCAB.NS",	"PREMIERENE.NS",	"PRESTIGE.NS",	"RVNL.NS",	"SBICARD.NS",	"SJVN.NS",	"SRF.NS",	"SOLARINDS.NS",	"SONACOMS.NS",	"SAIL.NS",	"SUPREMEIND.NS",	"SUZLON.NS",	"TATACOMM.NS",	"TATAELXSI.NS",	"TATATECH.NS",	"TORNTPOWER.NS",	"TIINDIA.NS",	"UPL.NS",	"UNIONBANK.NS",	"VMM.NS",	"IDEA.NS",	"VOLTAS.NS",	"WAAREEENER.NS",	"YESBANK.NS",	"ABB.NS",	"ADANIENSOL.NS",	"ADANIENT.NS",	"ADANIGREEN.NS",	"ADANIPORTS.NS",	"ADANIPOWER.NS",	"AMBUJACEM.NS",	"APOLLOHOSP.NS",	"ASIANPAINT.NS",	"DMART.NS",	"AXISBANK.NS",	"BAJAJ-AUTO.NS",	"BAJFINANCE.NS",	"BAJAJFINSV.NS",	"BAJAJHLDNG.NS",	"BAJAJHFL.NS",	"BANKBARODA.NS",	"BEL.NS",	"BPCL.NS",	"BHARTIARTL.NS",	"BOSCHLTD.NS",	"BRITANNIA.NS",	"CGPOWER.NS",	"CANBK.NS",	"CHOLAFIN.NS",	"CIPLA.NS",	"COALINDIA.NS",	"DLF.NS",	"DABUR.NS",	"DIVISLAB.NS",	"DRREDDY.NS",	"EICHERMOT.NS",	"ETERNAL.NS",	"GAIL.NS",	"GODREJCP.NS",	"GRASIM.NS",	"HCLTECH.NS",	"HDFCBANK.NS",	"HDFCLIFE.NS",	"HAVELLS.NS",	"HEROMOTOCO.NS",	"HINDALCO.NS",	"HAL.NS",	"HINDUNILVR.NS",	"HYUNDAI.NS",	"ICICIBANK.NS",	"ICICIGI.NS",	"ICICIPRULI.NS",	"ITC.NS",	"INDHOTEL.NS",	"IOC.NS",	"IRFC.NS",	"INDUSINDBK.NS",	"NAUKRI.NS",	"INFY.NS",	"INDIGO.NS",	"JSWENERGY.NS",	"JSWSTEEL.NS",	"JINDALSTEL.NS",	"JIOFIN.NS",	"KOTAKBANK.NS",	"LTIM.NS",	"LT.NS",	"LICI.NS",	"LODHA.NS",	"M&M.NS",	"MARUTI.NS",	"NTPC.NS",	"NESTLEIND.NS",	"ONGC.NS",	"PIDILITIND.NS",	"PFC.NS",	"POWERGRID.NS",	"PNB.NS",	"RECLTD.NS",	"RELIANCE.NS",	"SBILIFE.NS",	"MOTHERSON.NS",	"SHREECEM.NS",	"SHRIRAMFIN.NS",	"SIEMENS.NS",	"SBIN.NS",	"SUNPHARMA.NS",	"SWIGGY.NS",	"TVSMOTOR.NS",	"TCS.NS",	"TATACONSUM.NS",	"TATAMOTORS.NS",	"TATAPOWER.NS",	"TATASTEEL.NS",	"TECHM.NS",	"TITAN.NS",	"TORNTPHARM.NS",	"TRENT.NS",	"ULTRACEMCO.NS",	"UNITDSPR.NS",	"VBL.NS",	"VEDL.NS",	"WIPRO.NS",	"ZYDUSLIFE.NS"
        # ]
        "GLENMARK.NS", "BHARTIARTL.NS", "TCS.NS", "EIEL.NS", "HINDUNILVR.NS"]

    except Exception as e:
        print(f"⚠️ Could not fetch NIFTY 100: {e}")
        return ["RELIANCE.NS", "TCS.NS"]

# ------------------------------------------------------------------
# Analyze a single stock
# ------------------------------------------------------------------
def analyze_stock(ticker):
    print(f"\n📊 Analyzing: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        df = df.astype(float)

        if df.empty or len(df) < 50:
            print("⚠️ Not enough data.")
            return None

        df = calculate_additional_indicators(df)
        df.dropna(inplace=True)

        # Attach candle pattern
        df['Candle'] = "None"
        df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        score, matched_indicators = advanced_strategy_score(latest, previous)
        print(f"🧠 {ticker} Strategy Score: {score:.2f}")

        if score < SCORE_THRESHOLD:
            return None

        print(f"\n📊 Matched : {ticker}")

        history = df.tail(30).copy()
        history_json = [
            {
                "date": str(idx.date()),
                "close": round(row.Close, 2),
                "ema": round(row.EMA_50, 2),
                "rsi": round(row.RSI, 2),
                "macd": round(row.MACD, 2),
                "signal": round(row.Signal, 2),
                "hist": round(row.MACD_Hist, 2),
                "volume": int(row.Volume),
                "volumeAvg": int(row.Volume_avg),
                "willr": round(row.WilliamsR, 2),
                "atr": round(row.ATR, 2),
                "bb_pos": round(row.BB_Position, 2),
                "priceChange1D": round(row.Price_Change_1D, 2),
                "priceChange3D": round(row.Price_Change_3D, 2),
                "priceChange5D": round(row.Price_Change_5D, 2),
                "stochK": round(row.Stoch_K, 2),
                "stochD": round(row.Stoch_D, 2),
                "signal_trigger": bool(row.get("Signal_Trigger", False)),
                "sell_trigger": bool(row.get("Sell_Trigger", False)),
            }
            for idx, row in history.iterrows()
        ]

        return {
            "ticker": ticker,
            "close": round(latest['Close'], 2),
            "ema": round(latest['EMA_50'], 2),
            "rsi": round(latest['RSI'], 2),
            "macd": round(latest['MACD'], 2),
            "signal": round(latest['Signal'], 2),
            "hist": round(latest['MACD_Hist'], 2),
            "volume": int(latest['Volume']),
            "volumeAvg": int(latest['Volume_avg']),
            "willr": round(latest['WilliamsR'], 2),
            "atr": round(latest['ATR'], 2),
            "bb_pos": round(latest['BB_Position'], 2),
            "priceChange1D": round(latest['Price_Change_1D'], 2),
            "priceChange3D": round(latest['Price_Change_3D'], 2),
            "priceChange5D": round(latest['Price_Change_5D'], 2),
            "stochK": round(latest['Stoch_K'], 2),
            "stochD": round(latest['Stoch_D'], 2),
            "pattern": latest['Candle'],
            "score": round(score, 2),
            "matched_indicators": matched_indicators,
            "history": history_json
        }

    except Exception as e:
        print(f"❌ Error analyzing {ticker}: {e}")
        return None

# ------------------------------------------------------------------
# Run Screener
# ------------------------------------------------------------------
def run_screener():
    matches = []
    tickers = fetch_nifty_stocks()

    for ticker in tickers:
        stock = analyze_stock(ticker)
        if stock:
            matches.append(stock)
        time.sleep(0.2)

    if matches:
        for stock in matches:
            msg = (
                f"🎯 *{stock['ticker']}*\n"
                f"Price: ₹{stock['close']} | EMA50: {stock['ema']}\n"
                f"RSI: {stock['rsi']} | Williams %R: {stock['willr']}\n"
                f"MACD: {stock['macd']} | Signal: {stock['signal']} | Hist: {stock['hist']}\n"
                f"Volume: {stock['volume']} | Avg: {stock['volumeAvg']}\n"
                f"BB Pos: {stock['bb_pos']} | ATR: {stock['atr']}\n"
                f"% Change: 1D {stock['priceChange1D']}%, 3D {stock['priceChange3D']}%, 5D {stock['priceChange5D']}%\n"
                f"Stoch %K: {stock['stochK']} | %D: {stock['stochD']}\n"
                f"Candle: {stock['pattern']} | Score: {stock['score']}\n"
            )
            send_telegram(msg)
    else:
        send_telegram("🚫 *No stocks matched advanced criteria today.*")

if __name__ == "__main__":
    run_screener()
