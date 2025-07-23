import os
from flask import Flask, request
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Configuración
TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# Conectar con Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
cred_file = os.environ.get("GOOGLE_SHEETS_JSON", "credenciales.json")
creds = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
client = gspread.authorize(creds)

sheet_mov = client.open("Almacen").worksheet("Movimientos")
sheet_inv = client.open("Almacen").worksheet("Inventario")

# Manejo de mensajes
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "¡Hola! Envíame un mensaje tipo:\n\nENTRADA: Producto, cantidad, origen\nSALIDA: Producto, cantidad, origen")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.strip().upper()
    tipo = None

    if text.startswith("ENTRADA:"):
        tipo = "ENTRADA"
    elif text.startswith("SALIDA:"):
        tipo = "SALIDA"

    if tipo:
        try:
            partes = message.text.split(":", 1)[1].strip().split(",")
            producto = partes[0].strip()
            cantidad = int(partes[1].strip())
            origen = partes[2].strip()

            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Registrar en hoja de movimientos
            sheet_mov.append_row([fecha, producto, cantidad, tipo, origen])

            # Actualizar stock
            celda = sheet_inv.find(producto)
            fila = celda.row
            stock_actual = int(sheet_inv.cell(fila, 2).value)
            nuevo_stock = stock_actual + cantidad if tipo == "ENTRADA" else stock_actual - cantidad
            sheet_inv.update_cell(fila, 2, nuevo_stock)

            bot.reply_to(message, f"{tipo} registrada para {producto} ({cantidad} unidades). Stock actualizado.")

        except Exception as e:
            bot.reply_to(message, f"Error en el formato o producto no encontrado. Detalle: {e}")
    else:
        bot.reply_to(message, "Formato incorrecto. Usa:\nENTRADA: Producto, cantidad, origen\nSALIDA: Producto, cantidad, origen")

# Endpoint para Webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

# Endpoint base
@app.route("/", methods=["GET"])
def index():
    return "Bot de inventario activo", 200

if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    # Configurar Webhook
    url_webhook = os.environ.get("URL_RENDER")  # ej: https://inventario-c-guido.onrender.com
    if url_webhook:
        bot.remove_webhook()
        bot.set_webhook(url=f"{url_webhook}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
