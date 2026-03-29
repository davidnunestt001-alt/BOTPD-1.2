from flask import Flask, request
from binance.client import Client
import time
import threading

# 🔐 COLOCA SUAS CHAVES DA BINANCE AQUI
API_KEY = "FRq0f5GFl7u6KHn7SVZ38VeOE8lBEvolvHfCpy1a0pY38JO0Spsdf75zgM0LghO9"
API_SECRET = "ys92MsLcWk2tsMw1mGbIF1Vx3buqBCKWyi7p7mT96PQhuH97r90z4XI1eZvZ2a94"

SYMBOL = "BTCUSDT"
RISK_PERCENT = 0.025   # 2.5%
MIN_QTY = 0.001        # mínimo BTC

client = Client(API_KEY, API_SECRET)
app = Flask(__name__)

# 📊 ESTADO DO TRADE
trade = {
    "ativo": False,
    "lado": None,
    "entry": 0,
    "sl": 0,
    "tp1": 0,
    "tp2": 0,
    "tp3": 0,
    "qty": 0,
    "tp1_hit": False,
    "tp2_hit": False,
    "be": False
}

# ============================
# 📊 PEGAR SALDO
# ============================
def get_balance():
    try:
        balance = client.futures_account_balance()
        for b in balance:
            if b['asset'] == 'USDT':
                return float(b['balance'])
    except:
        return 0

# ============================
# 📊 CALCULAR QUANTIDADE
# ============================
def calc_qty(price, sl):
    balance = get_balance()
    risk = balance * RISK_PERCENT

    stop_distance = abs(price - sl)

    if stop_distance == 0:
        return MIN_QTY

    qty = risk / stop_distance

    # garante mínimo
    return round(max(qty, MIN_QTY), 3)

# ============================
# 🚀 ABRIR TRADE
# ============================
def abrir_trade(data):

    if trade["ativo"]:
        print("Já em trade")
        return

    confidence = data.get("confidence", 0)

    if confidence < 70:
        print("Ignorado (baixa confiança)")
        return

    price = float(client.futures_symbol_ticker(symbol=SYMBOL)['price'])
    qty = calc_qty(price, data["sl"])

    side = "BUY" if data["signal"] == "BUY" else "SELL"

    try:
        client.futures_create_order(
            symbol=SYMBOL,
            side=side,
            type="MARKET",
            quantity=qty
        )

        trade.update({
            "ativo": True,
            "lado": data["signal"],
            "entry": price,
            "sl": data["sl"],
            "tp1": data["tp1"],
            "tp2": data["tp2"],
            "tp3": data["tp3"],
            "qty": qty,
            "tp1_hit": False,
            "tp2_hit": False,
            "be": False
        })

        print("TRADE ABERTO:", trade)

    except Exception as e:
        print("Erro ao abrir trade:", e)

# ============================
# 🧠 GERENCIAMENTO
# ============================
def gerenciar_trade():

    if not trade["ativo"]:
        return

    price = float(client.futures_symbol_ticker(symbol=SYMBOL)['price'])

    # 🎯 TP1
    if not trade["tp1_hit"]:
        if (trade["lado"] == "BUY" and price >= trade["tp1"]) or \
           (trade["lado"] == "SELL" and price <= trade["tp1"]):

            fechar_parcial(0.3)
            trade["tp1_hit"] = True
            print("TP1")

    # 🧠 BE
    if trade["tp1_hit"] and not trade["be"]:
        trade["sl"] = trade["entry"]
        trade["be"] = True
        print("BE ativado")

    # 🎯 TP2
    if trade["tp1_hit"] and not trade["tp2_hit"]:
        if (trade["lado"] == "BUY" and price >= trade["tp2"]) or \
           (trade["lado"] == "SELL" and price <= trade["tp2"]):

            fechar_parcial(0.3)
            trade["tp2_hit"] = True
            print("TP2")

    # 🎯 TP3
    if trade["tp2_hit"]:
        if (trade["lado"] == "BUY" and price >= trade["tp3"]) or \
           (trade["lado"] == "SELL" and price <= trade["tp3"]):

            fechar_total()
            print("TP3 FINAL")

    # ❌ STOP
    if (trade["lado"] == "BUY" and price <= trade["sl"]) or \
       (trade["lado"] == "SELL" and price >= trade["sl"]):

        fechar_total()
        print("STOP")

# ============================
def fechar_parcial(percent):

    qty = trade["qty"] * percent
    side = "SELL" if trade["lado"] == "BUY" else "BUY"

    client.futures_create_order(
        symbol=SYMBOL,
        side=side,
        type="MARKET",
        quantity=round(qty, 3)
    )

# ============================
def fechar_total():

    side = "SELL" if trade["lado"] == "BUY" else "BUY"

    client.futures_create_order(
        symbol=SYMBOL,
        side=side,
        type="MARKET",
        quantity=trade["qty"]
    )

    trade["ativo"] = False

# ============================
# 📡 WEBHOOK
# ============================
@app.route('/webhook', methods=['POST'])
def webhook():

    data = request.json
    abrir_trade(data)

    return "ok"

# ============================
# 🔁 LOOP
# ============================
def loop():
    while True:
        gerenciar_trade()
        time.sleep(1)

# ============================
if __name__ == "__main__":
    t = threading.Thread(target=loop)
    t.start()

    app.run(host="0.0.0.0", port=5000)