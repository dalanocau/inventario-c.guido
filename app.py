from flask import Flask, render_template, jsonify
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from flask_cors import CORS

# Configuración Flask
app = Flask(__name__)
CORS(app)

# Configuración de credenciales Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)

# Leer hoja 'Inventario'
sheet = client.open("Almacen")
inventario_data = sheet.worksheet("Inventario").get_all_records()
df = pd.DataFrame(inventario_data)

# Procesar columna 'Última Actualización' si existe
if "Última Actualización" in df.columns:
    df["Última Actualización"] = pd.to_datetime(df["Última Actualización"], errors='coerce')
else:
    df["Última Actualización"] = pd.NaT

# Leer hoja 'Movimientos' y simular ventas diarias
movimientos_data = sheet.worksheet("Movimientos").get_all_records()
movimientos_df = pd.DataFrame(movimientos_data)

# Agrupar ventas por fecha
ventas_diarias = movimientos_df.groupby("Fecha")["Cantidad"].sum().reset_index()
ventas_diarias.columns = ["fecha", "total"]
ventas_diarias = ventas_diarias.sort_values("fecha")

# Agrupar detalle por fecha
detalle_ventas = movimientos_df.groupby("Fecha").apply(
    lambda df: df[["Producto", "Cantidad"]].to_dict(orient="records")
).to_dict()

# Rutas
@app.route("/")
def home():
    return render_template("index.html", inventario=df)

@app.route("/data")
def data():
    return jsonify({
        "ventas_diarias": ventas_diarias.to_dict(orient="records")
    })

@app.route("/detalle/<fecha>")
def detalle(fecha):
    return jsonify(detalle_ventas.get(fecha, []))

# Ejecutar la app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
