from flask import Flask, jsonify, request

app = Flask(__name__)

# Datos historicos simulados de gastos mensuales
historico_gastos = {
    "Ventas": [12000, 12800, 13400, 14250, 14900, 15520, 16000, 16850, 17500, 18100, 18750, 19400],
    "Finanzas": [9800, 10150, 10900, 11120, 11480, 11890, 12250, 12540, 12870, 13120, 13600, 14050],
    "IT": [15000, 15850, 16200, 17100, 17650, 18120, 18800, 19650, 20350, 21400, 22100, 22950],
    "People": [8200, 8600, 9000, 9400, 9900, 10150, 10800, 11200, 11650, 12080, 12750, 13250],
}

# Nombres de meses para respuestas
meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def calcular_regresion_lineal(valores, periodos=3):
    """Calcula forecast con regresion lineal simple."""
    x = list(range(1, len(valores) + 1))
    y = valores

    n = len(x)
    media_x = sum(x) / n
    media_y = sum(y) / n

    numerador = sum((xi - media_x) * (yi - media_y) for xi, yi in zip(x, y))
    denominador = sum((xi - media_x) ** 2 for xi in x)

    if denominador == 0:
        pendiente = 0
    else:
        pendiente = numerador / denominador

    intercepto = media_y - pendiente * media_x

    forecast = []
    for i in range(1, periodos + 1):
        x_futuro = len(x) + i
        valor = intercepto + pendiente * x_futuro
        forecast.append(round(valor, 2))

    return forecast


@app.route("/")
def index():
    # Ruta base de salud del servicio
    return jsonify({
        "mensaje": "Servidor Flask de forecast de gastos activo",
        "departamentos": list(historico_gastos.keys())
    })


@app.route("/api/forecast", methods=["GET"])
def forecast():
    # Nombre del departamento recibido por query param
    departamento = (
        request.args.get("departamento")
        or request.args.get("department")
        or request.args.get("nombre")
        or ""
    ).strip()

    if not departamento:
        return jsonify({"error": "Falta el parametro 'departamento'"}), 400

    nombre_normalizado = departamento.lower()
    departamento_encontrado = None

    for nombre, valores in historico_gastos.items():
        if nombre.lower() == nombre_normalizado:
            departamento_encontrado = nombre
            datos = valores
            break

    if departamento_encontrado is None:
        return jsonify({
            "error": "Departamento no encontrado",
            "departamentos_validos": list(historico_gastos.keys())
        }), 404

    forecast_3_meses = calcular_regresion_lineal(datos, periodos=3)

    return jsonify({
        "departamento": departamento_encontrado,
        "metodo": "regresion_lineal_simple",
        "historico": datos,
        "forecast_proximos_3_meses": [
            {
                "mes": f"Mes {len(datos) + i}",
                "valor_estimado": forecast_3_meses[i - 1]
            }
            for i in range(1, 4)
        ],
        "mensaje": "Forecast calculado para los proximos 3 meses"
    })


if __name__ == "__main__":
    # Ejecuta el servidor en el puerto 5000
    app.run(host="0.0.0.0", port=5000, debug=False)
