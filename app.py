from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import os
import requests

# ========== Configuración ==========

app = Flask(__name__)
CORS(app)

TOKEN = os.getenv("TELEGRAM_TOKEN") or "7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# Configuración Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)
sheet = client.open("Almacen")

# ========== Funciones de utilidad ==========

def send_message(chat_id, text):
    data = {"chat_id": chat_id, "text": text}
    response = requests.post(TELEGRAM_API_URL, json=data)
    print(f"Mensaje enviado: {text} - Código: {response.status_code}")

# ========== Flask routes ==========

@app.route("/")
def home():
    inventario_data = sheet.worksheet("Inventario").get_all_records()
    df = pd.DataFrame(inventario_data)

    if "Última Actualización" in df.columns:
        df["Última Actualización"] = pd.to_datetime(df["Última Actualización"], errors='coerce')
    else:
        df["Última Actualización"] = pd.NaT

    return render_template("index.html", inventario=df)

@app.route("/data")
def data():
    movimientos_data = sheet.worksheet("Movimientos").get_all_records()
    movimientos_df = pd.DataFrame(movimientos_data)

    ventas_diarias = movimientos_df.groupby("Fecha")["Cantidad"].sum().reset_index()
    ventas_diarias.columns = ["fecha", "total"]
    ventas_diarias = ventas_diarias.sort_values("fecha")

    return jsonify({"ventas_diarias": ventas_diarias.to_dict(orient="records")})

@app.route("/detalle/<fecha>")
def detalle(fecha):
    movimientos_data = sheet.worksheet("Movimientos").get_all_records()
    df = pd.DataFrame(movimientos_data)

    detalle = df[df["Fecha"] == fecha][["Producto", "Cantidad"]].to_dict(orient="records")
    return jsonify(detalle)

# ========== Webhook para el bot ==========

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    print(f"Mensaje recibido: {update}")

    if "message" not in update:
        return "ok", 200

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        send_message(chat_id, "Hola 👋, puedes usar los comandos:\n\nENTRADA Producto, cantidad\nSALIDA Producto, cantidad")
    elif text.startswith("ENTRADA") or text.startswith("SALIDA"):
        tipo = "ENTRADA" if text.startswith("ENTRADA") else "SALIDA"
        try:
            _, resto = text.split(" ", 1)
            producto, cantidad = [x.strip() for x in resto.split(",", 1)]
            cantidad = int(cantidad)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fila = [now, tipo, producto, cantidad]

            print(f"Agregando fila: {fila}")
            sheet_mov = sheet.worksheet("Movimientos")
            sheet_mov.append_row(fila)

            send_message(chat_id, f"{tipo} registrada ✅\nProducto: {producto}\nCantidad: {cantidad}")
        except Exception as e:
            print(f"Error al registrar {tipo}: {e}")
            send_message(chat_id, f"❌ Error en el formato. Usa:\n{tipo} Producto, cantidad\n\nEjemplo:\n{tipo} Resma A4, 5")
    else:
        send_message(chat_id, "Comando no reconocido. Usa:\n/start\nENTRADA Producto, cantidad\nSALIDA Producto, cantidad")

    return "ok", 200

# ========== Iniciar servidor ==========

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
