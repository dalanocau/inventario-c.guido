import os
import time
import telegram
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# Configuración del bot de Telegram
TELEGRAM_TOKEN = os.environ.get("7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE")  # en Render debes definir esta variable
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Autenticación con Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
client = gspread.authorize(creds)

sheet = client.open("Almacen")
inventario_ws = sheet.worksheet("Inventario")
movimientos_ws = sheet.worksheet("Movimientos")

# Función para verificar nuevos mensajes
last_update_id = None
def revisar_mensajes():
    global last_update_id
    updates = bot.get_updates(offset=last_update_id, timeout=10)
    for update in updates:
        if update.message:
            texto = update.message.text
            chat_id = update.message.chat.id
            procesar_mensaje(texto, chat_id)
            last_update_id = update.update_id + 1

# Procesar comando
def procesar_mensaje(texto, chat_id):
    partes = texto.split()
    if len(partes) >= 3:
        operacion = partes[0].upper()
        producto = partes[1]
        try:
            cantidad = int(partes[2])
        except ValueError:
            bot.send_message(chat_id=chat_id, text="Cantidad inválida.")
            return

        fecha = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        movimientos_ws.append_row([fecha, operacion, producto, cantidad])

        # Actualizar inventario
        df = pd.DataFrame(inventario_ws.get_all_records())
        if producto not in df['Producto'].values:
            bot.send_message(chat_id=chat_id, text="Producto no encontrado.")
            return

        idx = df.index[df['Producto'] == producto][0]
        if operacion == "ENTRADA":
            df.at[idx, "Stock"] += cantidad
        elif operacion == "SALIDA":
            if df.at[idx, "Stock"] < cantidad:
                bot.send_message(chat_id=chat_id, text="Stock insuficiente.")
                return
            df.at[idx, "Stock"] -= cantidad
        else:
            bot.send_message(chat_id=chat_id, text="Operación no reconocida.")
            return

        df.at[idx, "Ultima Actualización"] = fecha
        inventario_ws.clear()
        inventario_ws.update([df.columns.values.tolist()] + df.values.tolist())
        bot.send_message(chat_id=chat_id, text="Inventario actualizado.")
    else:
        bot.send_message(chat_id=chat_id, text="Formato incorrecto. Usa: ENTRADA/SALIDA Producto Cantidad")

# Loop principal
if __name__ == "__main__":
    while True:
        try:
            revisar_mensajes()
        except Exception as e:
            print("Error:", e)
        time.sleep(5)
