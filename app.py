import os
import telebot
from flask import Flask, request, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURACIÓN ---
TOKEN = '7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE'  # Reemplaza con tu token real
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

# --- FLASK ---
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

# --- ESTADO DE USUARIOS ---
user_states = {}

# --- MANEJADOR PRINCIPAL ---
@bot.message_handler(func=lambda m: True)
def bot_handler(message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text.lower() == "hola total":
        mostrar_totales(message)
        return

    if user_id in user_states:
        manejar_flujo(message, user_id, text)
        return

    if text.lower() == "hola run":
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("ENTRADA", "SALIDA")
        bot.send_message(user_id, "¿Qué operación deseas realizar?", reply_markup=markup)
        user_states[user_id] = {"estado": "tipo"}
        return

    bot.send_message(user_id, "Escribe 'Hola run' para comenzar o 'Hola Total' para ver el inventario.")

def manejar_flujo(message, user_id, text):
    estado = user_states[user_id]
    
    if estado["estado"] == "tipo":
        if text not in ["ENTRADA", "SALIDA"]:
            bot.send_message(user_id, "Selecciona ENTRADA o SALIDA.")
            return
        estado["tipo"] = text
        estado["estado"] = "producto"
        productos = list(set(sheet_inv.col_values(1)[1:]))  # Únicos sin encabezado
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for p in productos:
            markup.add(p)
        bot.send_message(user_id, "Selecciona el producto:", reply_markup=markup)
    
    elif estado["estado"] == "producto":
        estado["producto"] = text
        estado["estado"] = "cantidad"
        bot.send_message(user_id, f"¿Cuántas unidades de '{text}'?")
    
    elif estado["estado"] == "cantidad":
        try:
            cantidad = int(text)
            estado["cantidad"] = cantidad
            estado["estado"] = "origen"
            bot.send_message(user_id, "¿Cuál es el origen?")
        except ValueError:
            bot.send_message(user_id, "Ingresa una cantidad válida (número entero).")

    elif estado["estado"] == "origen":
        estado["origen"] = text
        producto = estado["producto"]
        cantidad = estado["cantidad"]
        origen = estado["origen"]
        tipo = estado["tipo"]
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        productos = sheet_inv.col_values(1)

        if producto in productos:
            idx = productos.index(producto) + 1
            stock_actual = int(sheet_inv.cell(idx, 2).value)
            nuevo_stock = stock_actual + cantidad if tipo == "ENTRADA" else stock_actual - cantidad
            sheet_inv.update_cell(idx, 2, nuevo_stock)
            sheet_mov.append_row([fecha, producto, cantidad, tipo, origen])
            bot.send_message(user_id, f"{tipo} registrada para {producto}. Stock actual: {nuevo_stock}")
            del user_states[user_id]
        else:
            if tipo == "ENTRADA":
                bot.send_message(user_id, f"El producto '{producto}' no existe. ¿Deseas agregarlo? (sí / no)")
                estado["estado"] = "confirmar_nuevo"
            else:
                bot.send_message(user_id, f"El producto '{producto}' no existe en el inventario. No se puede registrar salida.")
                del user_states[user_id]

    elif estado["estado"] == "confirmar_nuevo":
        if text.lower() in ["sí", "si"]:
            p = estado["producto"]
            c = estado["cantidad"]
            o = estado["origen"]
            f = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet_inv.append_row([p, c])
            sheet_mov.append_row([f, p, c, "ENTRADA", o])
            bot.send_message(user_id, f"Producto '{p}' agregado al inventario con {c} unidades.")
        else:
            bot.send_message(user_id, "Operación cancelada. No se agregó el producto.")
        del user_states[user_id]

def mostrar_totales(message):
    datos = sheet_inv.get_all_records()
    total = 0
    detalle = []
    for fila in datos:
        nombre = fila['Producto'] if 'Producto' in fila else fila.get('producto', '¿?')
        stock = int(fila['Stock']) if 'Stock' in fila else int(fila.get('stock', 0))
        total += stock
        detalle.append(f"{nombre}: {stock}")
    mensaje = f"📦 *Total stock:* {total}\n\n" + "\n".join(detalle)
    bot.send_message(message.chat.id, mensaje, parse_mode="Markdown")

# --- INICIO ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

