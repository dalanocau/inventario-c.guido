from flask import Flask, request, jsonify, render_template_string
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = '7603600989:AAEFQdFpuC_1UF2VMegurjt8xHLGlmJkGQE'
bot = telebot.TeleBot(TOKEN)
SHEET_NAME = 'Almacen'

# --- CONEXIÓN GOOGLE SHEETS ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)

sheet_inv = client.open(SHEET_NAME).worksheet("Inventario")
sheet_mov = client.open(SHEET_NAME).worksheet("Movimientos")

# --- TEMPLATE HTML ---
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Inventario</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        table, th, td { border: 1px solid black; border-collapse: collapse; padding: 5px; }
        table { width: 100%; margin-bottom: 30px; }
        canvas { margin: 20px 0; }
        .flex-container {
            display: flex;
            gap: 30px;
            height: 400px;
        }
        .chart-small { height: 200px !important; }
        .chart-tall { height: 300px !important; }
    </style>
</head>
<body>
    <h2>📦 Inventario Comercial Guido</h2>
    <table>
        <tr><th>Producto</th><th>Stock</th><th>Precio</th><th>Última Actualización</th></tr>
        {% for row in inventario %}
        <tr>
            <td>{{ row['Producto'] }}</td>
            <td>{{ row['Stock'] }}</td>
            <td>{{ row['Precio'] }}</td>
            <td>{{ row['Ultima Actualización'] }}</td>
        </tr>
        {% endfor %}
    </table>

    <div class="flex-container">
        <div style="flex: 3;">
            <canvas id="barrasInventario"></canvas>
        </div>
        <div style="flex: 1; display: flex; justify-content: center; align-items: center;">
            <canvas id="totalInventario"></canvas>
        </div>
    </div>

    <h2>📈 Ventas Diarias</h2>
    <canvas id="lineaVentas" height="120"></canvas>

    <h3>Detalle del día seleccionado:</h3>
    <div style="overflow-x: auto;">
        <canvas id="detallePorProducto" class="chart-tall" style="min-width: 600px; width: 100%;"></canvas>
    </div>

<script>
async function cargarDatos() {
    const resp = await fetch('/data');
    const datos = await resp.json();

    const productos = datos.inventario.map(x => x.Producto);
    const stocks = datos.inventario.map(x => x.Stock);
    const totalInventario = stocks.reduce((acc, s) => acc + s, 0);
    const maxStock = Math.max(...stocks);
    const maxAjustado = Math.ceil(maxStock * 1.1);

    new Chart(document.getElementById('barrasInventario'), {
        type: 'bar',
        data: {
            labels: productos,
            datasets: [{ label: 'Stock', data: stocks, backgroundColor: 'skyblue' }]
        },
        options: {
            indexAxis: 'y',
            layout: {
                padding: { top: 20, bottom: 20, left: 10, right: 10 }
            },
            plugins: {
                datalabels: {
                    anchor: 'end',
                    align: 'right',
                    formatter: value => value,
                    color: '#333',
                    font: { weight: 'bold' }
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { beginAtZero: true, max: maxAjustado }
            }
        },
        plugins: [ChartDataLabels]
    });

    new Chart(document.getElementById('totalInventario'), {
        type: 'bar',
        data: {
            labels: ['Total Inventario'],
            datasets: [{
                label: 'Unidades',
                data: [totalInventario],
                backgroundColor: 'green'
            }]
        },
        options: {
            indexAxis: 'x',
            layout: {
                padding: { top: 20, bottom: 20, left: 10, right: 10 }
            },
            plugins: {
                datalabels: {
                    anchor: 'end',
                    align: 'end',
                    formatter: value => value,
                    color: '#fff',
                    font: { weight: 'bold', size: 16 }
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: Math.ceil(totalInventario * 1.1)
                }
            }
        },
        plugins: [ChartDataLabels]
    });

    const fechas = datos.ventas_diarias.map(x => x.fecha);
    const unidades = datos.ventas_diarias.map(x => x.total);

    const chartLine = new Chart(document.getElementById('lineaVentas'), {
        type: 'line',
        data: {
            labels: fechas,
            datasets: [{
                label: 'Unidades vendidas',
                data: unidades,
                borderColor: 'blue',
                fill: false
            }]
        },
        options: {
            onClick: (evt, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const fechaSeleccionada = fechas[index];
                    actualizarDetalle(fechaSeleccionada);
                }
            }
        }
    });

    if (fechas.length > 0) {
        actualizarDetalle(fechas[fechas.length - 1]);
    }
}

async function actualizarDetalle(fecha) {
    const resp = await fetch('/detalle/' + fecha);
    const datos = await resp.json();

    const ctx = document.getElementById('detallePorProducto').getContext('2d');
    if (window.detalleChart) {
        window.detalleChart.destroy();
    }

    window.detalleChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.map(x => x.producto),
            datasets: [{
                label: 'Unidades vendidas',
                data: datos.map(x => x.cantidad),
                backgroundColor: 'orange'
            }]
        },
        options: {
            layout: {
                padding: { top: 20, bottom: 20, left: 10, right: 10 }
            },
            plugins: {
                datalabels: {
                    anchor: 'end',
                    align: 'top',
                    formatter: value => value,
                    color: '#000',
                    font: { weight: 'bold' }
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        },
        plugins: [ChartDataLabels]
    });
}

cargarDatos();
</script>

</body>
</html>
"""

# --- FUNCIONES AUXILIARES ---
def get_inventario():
    rows = sheet_inv.get_all_records()
    return [
        {
            "Producto": row.get("Producto", ""),
            "Stock": int(row.get("Stock", 0)),
            "Precio": float(row.get("Precio", 0)),
            "Ultima Actualización": row.get("Ultima Actualización", "")
        }
        for row in rows
    ]

def get_ventas_diarias():
    rows = sheet_mov.get_all_records()
    ventas = defaultdict(int)
    for row in rows:
        if row.get("Tipo", "").upper() == "SALIDA":
            fecha = row.get("Fecha", "").split()[0]
            ventas[fecha] += int(row.get("Cantidad", 0))
    return [{"fecha": f, "total": t} for f, t in sorted(ventas.items())]

def get_detalle_por_fecha(fecha):
    rows = sheet_mov.get_all_records()
    resumen = defaultdict(int)
    for row in rows:
        if row.get("Tipo", "").upper() == "SALIDA" and fecha in row.get("Fecha", ""):
            resumen[row["Producto"]] += int(row["Cantidad"])
    return [{"producto": k, "cantidad": v} for k, v in resumen.items()]

def actualizar_inventario(producto, cantidad, tipo):
    productos = sheet_inv.col_values(1)
    if producto in productos:
        idx = productos.index(producto) + 1
        stock = int(sheet_inv.cell(idx, 2).value)
        nuevo_stock = stock + cantidad if tipo == 'ENTRADA' else stock - cantidad
        sheet_inv.update_cell(idx, 2, nuevo_stock)
        sheet_inv.update_cell(idx, 4, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

# --- RUTAS FLASK ---
@app.route('/')
def home():
    return render_template_string(TEMPLATE, inventario=get_inventario())

@app.route('/data')
def data():
    return jsonify({
        "inventario": get_inventario(),
        "ventas_diarias": get_ventas_diarias()
    })

@app.route('/detalle/<fecha>')
def detalle(fecha):
    return jsonify(get_detalle_por_fecha(fecha))

# --- BOT TELEGRAM ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    texto = message.text.strip().upper()
    if texto.startswith("ENTRADA:") or texto.startswith("SALIDA:"):
        try:
            tipo, datos = texto.split(":", 1)
            producto, cantidad, origen = [x.strip() for x in datos.split(",")]
            cantidad = int(cantidad)
            fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Guardar en hoja 'Movimientos'
            sheet_mov.append_row([fecha, producto, cantidad, tipo, origen])

            # Actualizar hoja 'Inventario'
            actualizar_inventario(producto, cantidad, tipo)

            bot.reply_to(message, f"{tipo} registrada: {producto} ({cantidad}) desde {origen}")
        except Exception as e:
            bot.reply_to(message, f"Error al procesar el mensaje. Formato: ENTRADA/SALIDA: Producto, cantidad, origen")
    else:
        bot.reply_to(message, "Formato incorrecto. Usa ENTRADA: Producto, cantidad, origen")

# --- INICIAR BOT EN BACKGROUND ---
import threading
def iniciar_bot():
    bot.infinity_polling()

threading.Thread(target=iniciar_bot).start()

# --- EJECUCIÓN LOCAL ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
