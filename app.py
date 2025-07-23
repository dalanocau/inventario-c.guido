from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from flask_cors import CORS
import telebot

# === CONFIGURACIONES ===
TOKEN = '7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE'  # <-- REEMPLAZA con el token real
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
CORS(app)

# === GOOGLE SHEETS ===
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)

# Leer hoja Inventario
sheet = client.open("Almacen")
inventario_data = sheet.worksheet("Inventario").get_all_records()
df = pd.DataFrame(inventario_data)

# Procesar fecha
if "Última Actualización" in df.columns:
    df["Última Actualización"] = pd.to_datetime(df["Última Actualización"], errors='coerce')
else:
    df["Última Actualización"] = pd.NaT

# Leer hoja Movimientos
movimientos_data = sheet.worksheet("Movimientos").get_all_records()
movimientos_df = pd.DataFrame(movimientos_data)

ventas_diarias = movimientos_df.groupby("Fecha")["Cantidad"].sum().reset_index()
ventas_diarias.columns = ["fecha", "total"]
ventas_diarias = ventas_diarias.sort_values("fecha")

detalle_ventas = movimientos_df.groupby("Fecha").apply(
    lambda df: df[["Producto", "Cantidad"]].to_dict(orient="records")
).to_dict()

# === RUTAS WEB ===
@app.route("/")
def home():
    return render_template("index.html", inventario=df)

@app.route("/data")
def data():
    return jsonify({"ventas_diarias": ventas_diarias.to_dict(orient="records")})

@app.route("/detalle/<fecha>")
def detalle(fecha):
    return jsonify(detalle_ventas.get(fecha, []))

# === RUTA PARA WEBHOOK DEL BOT ===
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
    bot.process_new_updates([update])
    return '', 200

# === MANEJADORES DEL BOT ===
@bot.message_handler(commands=['start', 'hola'])
def saludo(message):
    bot.reply_to(message, "Hola 👋 soy el bot del inventario. ¿En qué te ayudo?")

@bot.message_handler(func=lambda message: message.text.lower() == "inventario")
def enviar_inventario(message):
    resumen = ""
    for index, row in df.iterrows():
        resumen += f"- {row['Producto']}: {row['Stock']} unidades\n"
    bot.reply_to(message, resumen)

# === MAIN ===
if __name__ == "__main__":
    bot.remove_webhook()
    webhook_url = f"https://inventario-c-guido.onrender.com/{TOKEN}"
    bot.set_webhook(url=webhook_url)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
