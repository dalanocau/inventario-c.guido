import os
import telebot
from flask import Flask, request, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- TOKEN DEL BOT Y WEBHOOK ---
TOKEN = '7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE'
bot = telebot.TeleBot(TOKEN)

WEBHOOK_URL = f"https://inventario-c-guido.onrender.com/{TOKEN}"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# --- AUTENTICACIÓN GOOGLE SHEETS ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
client = gspread.authorize(creds)

# --- Acceso a hojas ---
sheet_mov = client.open("Almacen").worksheet("Movimientos")
sheet_inv = client.open("Almacen").worksheet("Inventario")

# --- APP FLASK ---
app = Flask(__name__)

@app.route('/')
def index():
    inventario = sheet_inv.get_all_values()
    headers = inventario[0]
    rows = inventario[1:]

    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Inventario</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f9f9f9; }
            table { border-collapse: collapse; width: 100%; background: white; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
            tr:hover { background-color: #f1f1f1; }
        </style>
    </head>
    <body>
        <h2>Inventario Actual</h2>
        <table>
            <thead>
                <tr>{% for header in headers %}<th>{{ header }}</th>{% endfor %}</tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """
    return render_template_string(template, headers=headers, rows=rows)

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# --- BOT MANEJA MENSAJES ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    tipo = None

    if text.upper().startswith("ENTRADA:"):
        tipo = "ENTRADA"
    elif text.upper().startswith("SALIDA:"):
        tipo = "SALIDA"

    if tipo:
        try:
            contenido = text.split(":", 1)[1].strip()
            partes = [x.strip() for x in contenido.split(",")]

            if len(partes) != 3:
                bot.reply_to(message, "Formato incorrecto. Usa:\nENTRADA: Producto, cantidad, origen")
                return

            producto, cantidad, origen = partes
            cantidad = int(cantidad)

            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fila = [fecha, producto, cantidad, tipo, origen]
            sheet_mov.append_row(fila)

            celdas = sheet_inv.col_values(1)
            if producto in celdas:
                idx = celdas.index(producto) + 1
                stock_actual = int(sheet_inv.cell(idx, 2).value)
                nuevo_stock = stock_actual + cantidad if tipo == "ENTRADA" else stock_actual - cantidad
                sheet_inv.update_cell(idx, 2, nuevo_stock)
            else:
                nuevo_stock = cantidad if tipo == "ENTRADA" else -cantidad
                sheet_inv.append_row([producto, nuevo_stock])

            bot.reply_to(message, f"{tipo} registrada correctamente para {producto}. Stock actual: {nuevo_stock}")

        except Exception as e:
            bot.reply_to(message, f"Error: {e}")
    else:
        bot.reply_to(message, "Formato no reconocido. Usa:\nENTRADA: Producto, cantidad, origen\nSALIDA: Producto, cantidad, origen")

# --- INICIO ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
