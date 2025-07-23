from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from flask_cors import CORS
import time
import threading
import telegram

# --- Configuración Flask ---
app = Flask(__name__)
CORS(app)

# --- Autenticación con Google Sheets ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)

# Hojas
hoja_inv = client.open("Almacen").worksheet("Inventario")
hoja_mov = client.open("Almacen").worksheet("Movimientos")

# --- Telegram Bot ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telegram.Bot(token=TOKEN)
ultimo_update_id = None

# --- Función para actualizar stock ---
def actualizar_stock(producto, cantidad, tipo, origen):
    datos = hoja_inv.get_all_records()
    actualizado = False

    for i, fila in enumerate(datos):
        if fila['Producto'].strip().lower() == producto.strip().lower():
            stock_actual = int(fila['Stock'])
            nuevo_stock = stock_actual + cantidad if tipo == 'ENTRADA' else stock_actual - cantidad
            hoja_inv.update_cell(i + 2, 2, nuevo_stock)
            hoja_inv.update_cell(i + 2, 4, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            actualizado = True
            break

    # Registrar movimiento
    hoja_mov.append_row([
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        producto,
        cantidad,
        tipo,
        origen
    ])
    return actualizado

# --- Función para manejar mensajes del bot ---
def procesar_mensajes():
    global ultimo_update_id
    print("📡 Bot activo y esperando mensajes...")

    while True:
        updates = bot.get_updates(offset=ultimo_update_id, timeout=10)
        for update in updates:
            if not update.message:
                continue

            mensaje = update.message.text
            chat_id = update.message.chat.id
            update_id = update.update_id
            ultimo_update_id = update_id + 1

            try:
                if mensaje.strip() == "/start":
                    bot.send_message(chat_id=chat_id, text="🤖 ¡Hola! Envía un mensaje con el formato:\nENTRADA: Producto, cantidad, origen")
                    continue

                print(f"📩 Recibido: {mensaje}")
                if ':' not in mensaje:
                    bot.send_message(chat_id=chat_id, text="❌ Usa: ENTRADA: Producto, cantidad, origen")
                    continue

                tipo_raw, detalles = mensaje.split(':', 1)
                tipo = tipo_raw.strip().upper()

                if tipo not in ['ENTRADA', 'SALIDA']:
                    bot.send_message(chat_id=chat_id, text="❌ Especifica ENTRADA o SALIDA")
                    continue

                partes = [x.strip() for x in detalles.split(',')]
                if len(partes) != 3:
                    bot.send_message(chat_id=chat_id, text="❌ Usa: ENTRADA: Producto, cantidad, origen")
                    continue

                producto, cantidad_str, origen = partes
                cantidad = int(cantidad_str)

                if actualizar_stock(producto, cantidad, tipo, origen):
                    bot.send_message(chat_id=chat_id, text=f"✅ {tipo} registrada: {producto} x{cantidad}")
                else:
                    bot.send_message(chat_id=chat_id, text=f"⚠️ Producto no encontrado: {producto}")

            except Exception as e:
                print(f"⚠️ Error: {e}")
                bot.send_message(chat_id=chat_id, text="❌ Error procesando tu mensaje.")

        time.sleep(3)

# --- Iniciar hilo del bot ---
hilo_bot = threading.Thread(target=procesar_mensajes)
hilo_bot.daemon = True
hilo_bot.start()

# --- Interfaz Flask ---
@app.route("/")
def home():
    datos = hoja_inv.get_all_records()
    df = pd.DataFrame(datos)
    return render_template("index.html", inventario=df)

@app.route("/data")
def data():
    movimientos_data = hoja_mov.get_all_records()
    movimientos_df = pd.DataFrame(movimientos_data)
    ventas_diarias = movimientos_df.groupby("Fecha")["Cantidad"].sum().reset_index()
    ventas_diarias.columns = ["fecha", "total"]
    ventas_diarias = ventas_diarias.sort_values("fecha")

    return jsonify({
        "ventas_diarias": ventas_diarias.to_dict(orient="records")
    })

@app.route("/detalle/<fecha>")
def detalle(fecha):
    movimientos_data = hoja_mov.get_all_records()
    df = pd.DataFrame(movimientos_data)
    detalle = df[df["Fecha"].str.startswith(fecha)][["Producto", "Cantidad"]].to_dict(orient="records")
    return jsonify(detalle)

# --- Ejecutar Flask ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
