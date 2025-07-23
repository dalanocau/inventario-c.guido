from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

# Cargar datos reales desde un archivo JSON
DATA_FILE = os.path.join(os.path.dirname(__file__), "datos.json")
with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

inventario = data["inventario"]
ventas_diarias = data["ventas_diarias"]
detalle_ventas = data["detalle_ventas"]

@app.route("/")
def home():
    return render_template("index.html", inventario=inventario)

@app.route("/data")
def data_route():
    return jsonify({
        "inventario": inventario,
        "ventas_diarias": ventas_diarias
    })

@app.route("/detalle/<fecha>")
def detalle(fecha):
    return jsonify(detalle_ventas.get(fecha, []))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)