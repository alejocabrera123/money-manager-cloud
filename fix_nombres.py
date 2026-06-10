import os
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf
import re

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ⚠️ Necesitas el access_token de tu sesión para que RLS te deje hacer UPDATE.
# Inicia sesión igual que en la app:
EMAIL = "david.cg93@hotmail.com"
PASSWORD = input("Contraseña Supabase: ")

auth = supabase.auth.sign_in_with_password({"email": EMAIL, "password": PASSWORD})
supabase.postgrest.auth(auth.session.access_token)
user_id = auth.user.id

def convertir_ticker_yfinance(ticker_original):
    if not ticker_original:
        return None
    t = str(ticker_original).strip()
    if t.lower() in ("cash", "efectivo", ""):
        return None
    if t.upper().startswith("LON:"):
        return t[4:].upper() + ".L"
    if t.upper() == "BRK.B":
        return "BRK-B"
    ETFS_LONDON = {"GLDV", "CSPX", "IGLN"}
    if t.upper() in ETFS_LONDON:
        return t.upper() + ".L"
    return t

result = supabase.table("cartera_tickers").select("id, ticker, nombre").eq("user_id", user_id).execute()

for row in result.data:
    ticker = row["ticker"]
    ticker_yf = convertir_ticker_yfinance(ticker)
    if not ticker_yf:
        print(f"⏭️  {ticker} — saltado (cash/efectivo)")
        continue
    try:
        info = yf.Ticker(ticker_yf).info
        nombre_nuevo = info.get("longName") or info.get("shortName")
        if nombre_nuevo:
            supabase.table("cartera_tickers").update({"nombre": nombre_nuevo}).eq("id", row["id"]).execute()
            print(f"✅ {ticker} ({ticker_yf}): '{row['nombre']}' → '{nombre_nuevo}'")
        else:
            print(f"⚠️  {ticker} ({ticker_yf}): sin nombre disponible")
    except Exception as e:
        print(f"❌ {ticker} ({ticker_yf}): error — {e}")