
from flask import Flask, request, jsonify, render_template_string
import pandas as pd
import gspread
import os
from google.oauth2.service_account import Credentials
import datetime

# Variables de entorno necesarias: GOOGLE_SHEETS_JSON
json_str = os.environ.get("GOOGLE_SHEETS_JSON")
with open("service_account.json", "w") as f:
    f.write(json_str)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credenciales = Credentials.from_service_account_file("service_account.json", scopes=scope)
cliente = gspread.authorize(credenciales)

sheet = cliente.open("INVENTARIO_MICROEMPRESA")
worksheet = sheet.worksheet("INVENTARIO")
data = worksheet.get_all_records()
df = pd.DataFrame(data)

df["Precio"] = df["Precio"].astype(float)
df["Stock"] = df["Stock"].astype(int)
df["Última Actualización"] = pd.to_datetime(df["Última Actualización"], errors='coerce')

TEMPLATE = """<!DOCTYPE html>
<html lang='es'>
<head>
    <meta charset='UTF-8'>
    <title>Inventario</title>
    <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
</head>
<body>
    <h1>📦 Inventario Actual</h1>
    <table border='1'>
        <thead>
            <tr><th>Producto</th><th>Stock</th><th>Precio</th><th>Última Actualización</th></tr>
        </thead>
        <tbody>
            {% for i in inventario.index %}
            <tr>
                <td>{{ inventario.loc[i, 'Producto'] }}</td>
                <td>{{ inventario.loc[i, 'Stock'] }}</td>
                <td>{{ inventario.loc[i, 'Precio'] }}</td>
                <td>{{ inventario.loc[i, 'Última Actualización'].strftime('%Y-%m-%d') if inventario.loc[i, 'Última Actualización'] is not none else '' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <h2>📈 Ventas Diarias</h2>
    <canvas id='ventasChart' width='400' height='200'></canvas>
    <script>
        fetch('/data')
            .then(response => response.json())
            .then(data => {
                const fechas = data.ventas_diarias.map(x => x.fecha);
                const totales = data.ventas_diarias.map(x => x.total);
                const totalGeneral = totales.reduce((a,b)=>a+b, 0);
                const ctx = document.getElementById('ventasChart').getContext('2d');
                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: fechas,
                        datasets: [{
                            label: 'Ventas por Día',
                            data: totales,
                            backgroundColor: 'rgba(54, 162, 235, 0.6)',
                        }]
                    },
                    options: {
                        plugins: {
                            title: {
                                display: true,
                                text: 'Ventas Diarias - Total: ' + totalGeneral
                            }
                        }
                    }
                });
            });
    </script>
</body>
</html>"""

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string(TEMPLATE, inventario=df)

@app.route('/data')
def data():
    ventas_diarias = []
    if "VENTAS" in [ws.title for ws in sheet.worksheets()]:
        ventas_ws = sheet.worksheet("VENTAS")
        ventas_data = ventas_ws.get_all_records()
        df_ventas = pd.DataFrame(ventas_data)
        if "Fecha" in df_ventas.columns and "Cantidad" in df_ventas.columns:
            df_ventas["Fecha"] = pd.to_datetime(df_ventas["Fecha"], errors='coerce')
            resumen = df_ventas.groupby(df_ventas["Fecha"].dt.date)["Cantidad"].sum().reset_index()
            resumen.columns = ["fecha", "total"]
            resumen["fecha"] = resumen["fecha"].astype(str)
            ventas_diarias = resumen.to_dict(orient="records")
    return jsonify({"ventas_diarias": ventas_diarias})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
