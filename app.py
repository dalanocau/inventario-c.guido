from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from flask_cors import CORS
import telebot

# ==== CONFIGURACIÓN ====

app = Flask(__name__)
CORS(app)

# Bot de Telegram
TOKEN = "7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE"
bot = telebot.TeleBot(TOKEN)

# Credenciales Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)

# ==== LECTURA DE DATOS ====

# Leer hoja 'Inventario'
sheet = client.open("Almacen")
inventario_data = sheet.worksheet("Inventario").get_all_records()
df = pd.DataFrame(inventario_data)

# Formatear fechas si existe la columna
if "Última Actualización" in df.columns:
    df["Última Actualización"] = pd.to_datetime(df["Última Actualización"], errors='coerce')
else:
    df["Última Actualización"] = pd.NaT

# Leer hoja 'Movimientos'
movimientos_data = sheet.worksheet("Movimientos").get_all_records()
movimientos_df = pd.DataFrame(movimientos_data)

# Ventas diarias
ventas_diarias = movimientos_df.groupby("Fecha")["Cantidad"].sum().reset_index()
ventas_diarias.columns = ["fecha", "total"]
ventas_diarias = ventas_diarias.sort_values("fecha")

# Detalle por fecha
detalle_ventas = movimientos_df.groupby("Fecha").apply(
    lambda df: df[["Producto", "Cantidad"]].to_dict(orient="records")
).to_dict()

# ==== FLASK ROUTES ====

@app.route("/")
def home():
    return render_template("index.html", inventario=df)

@app.route("/data")
def data():
    return jsonify({"ventas_diarias": ventas_diarias.to_dict(orient="records")})

@app.route("/detalle/<fecha>")
def detalle(fecha):
    return jsonify(detalle_ventas.get(fecha, []))

# ==== TELEGRAM WEBHOOK ====

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ==== COMANDOS DEL BOT ====

@bot.message_handler(commands=['start', 'hola'])
def send_welcome(message):
    bot.reply_to(message, "¡Hola! Bot de inventario activo.")

@bot.message_handler(commands=['stock'])
def send_stock(message):
    mensaje = "📦 *Inventario Actual:*\n"
    for _, row in df.iterrows():
        mensaje += f"- {row['Producto']}: {row['Stock']} unidades\n"
    bot.send_message(message.chat.id, mensaje, parse_mode="Markdown")

# ==== MAIN ====

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
