import os
import telebot
from flask import Flask, request, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- TOKEN Y WEBHOOK ---
TOKEN = '7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE'
bot = telebot.TeleBot(TOKEN)
WEBHOOK_URL = f"https://inventario-c-guido.onrender.com/{TOKEN}"

bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# --- GOOGLE SHEETS ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
client = gspread.authorize(creds)

sheet_mov = client.open("Almacen").worksheet("Movimientos")
sheet_inv = client.open("Almacen").worksheet("Inventario")

# --- FLASK APP ---
app = Flask(__name__)

@app.route('/')
def index():
    inventario = sheet_inv.get_all_values()
    headers = inventario[0]
    rows = inventario[1:]

    template = """
    <!DOCTYPE html>
    <html><head>
        <title>Inventario</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f4f4f4; }
            table { border-collapse: collapse; width: 100%; background: #fff; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
            tr:hover { background-color: #f1f1f1; }
        </style>
    </head><body>
        <h2>Inventario</h2>
        <table>
            <thead><tr>{% for header in headers %}<th>{{ header }}</th>{% endfor %}</tr></thead>
            <tbody>
                {% for row in rows %}
                <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
                {% endfor %}
            </tbody>
        </table>
    </body></html>
    """
    return render_template_string(template, headers=headers, rows=rows)

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# --- DICCIONARIO DE SESIONES ---
usuarios = {}

# --- MANEJO MENSAJES ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    text = message.text.strip()

    if text.lower() == "hola run":
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("ENTRADA", "SALIDA")
        bot.send_message(user_id, "¿Qué deseas registrar?", reply_markup=markup)
        usuarios[user_id] = {"estado": "esperando_tipo"}
        return

    if user_id not in usuarios:
        bot.send_message(user_id, "Escribe 'Hola run' para empezar.")
        return

    estado = usuarios[user_id].get("estado")

    if estado == "esperando_tipo":
        if text.upper() in ["ENTRADA", "SALIDA"]:
            usuarios[user_id]["tipo"] = text.upper()
            productos = sheet_inv.col_values(1)[1:]
            markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for p in productos:
                markup.add(p)
            bot.send_message(user_id, "Selecciona un producto:", reply_markup=markup)
            usuarios[user_id]["estado"] = "esperando_producto"
        else:
            bot.send_message(user_id, "Por favor elige ENTRADA o SALIDA.")
        return

    if estado == "esperando_producto":
        usuarios[user_id]["producto"] = text
        usuarios[user_id]["estado"] = "esperando_cantidad"
        bot.send_message(user_id, "¿Cuántos deseas registrar?")
        return

    if estado == "esperando_cantidad":
        if not text.isdigit():
            bot.send_message(user_id, "Por favor ingresa un número válido.")
            return
        usuarios[user_id]["cantidad"] = int(text)
        usuarios[user_id]["estado"] = "esperando_origen"
        bot.send_message(user_id, "¿Cuál es el origen?")
        return

    if estado == "esperando_origen":
        usuarios[user_id]["origen"] = text
        datos = usuarios[user_id]

        # Registrar en hoja
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fila = [fecha, datos["producto"], datos["cantidad"], datos["tipo"], datos["origen"]]
        sheet_mov.append_row(fila)

        # Actualizar inventario
        celdas = sheet_inv.col_values(1)
        if datos["producto"] in celdas:
            idx = celdas.index(datos["producto"]) + 1
            stock_actual = int(sheet_inv.cell(idx, 2).value)
            nuevo_stock = stock_actual + datos["cantidad"] if datos["tipo"] == "ENTRADA" else stock_actual - datos["cantidad"]
            sheet_inv.update_cell(idx, 2, nuevo_stock)
        else:
            nuevo_stock = datos["cantidad"] if datos["tipo"] == "ENTRADA" else -datos["cantidad"]
            sheet_inv.append_row([datos["producto"], nuevo_stock])

        resumen = f"""✅ {datos['tipo']} registrada
📦 Producto: {datos['producto']}
🔢 Cantidad: {datos['cantidad']}
📍 Origen: {datos['origen']}
📆 Fecha: {fecha}
📊 Stock actual: {nuevo_stock}"""

        bot.send_message(user_id, resumen)
        usuarios.pop(user_id, None)
        return

    bot.send_message(user_id, "Escribe 'Hola run' para iniciar.")

# --- INICIO ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

