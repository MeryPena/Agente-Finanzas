import re
import unicodedata

import pandas as pd
import requests
import streamlit as st


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:1.5b"
BACKEND_URL = "http://127.0.0.1:5000/api/forecast"

DEPARTAMENTOS = ["VENTAS", "FINANZAS", "IT", "PEOPLE"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
HISTORICO_GASTOS = {
	"Ventas": [12000, 12800, 13400, 14250, 14900, 15520, 16000, 16850, 17500, 18100, 18750, 19400],
	"Finanzas": [9800, 10150, 10900, 11120, 11480, 11890, 12250, 12540, 12870, 13120, 13600, 14050],
	"IT": [15000, 15850, 16200, 17100, 17650, 18120, 18800, 19650, 20350, 21400, 22100, 22950],
	"People": [8200, 8600, 9000, 9400, 9900, 10150, 10800, 11200, 11650, 12080, 12750, 13250],
}

SYSTEM_PROMPT = """
Eres un analista financiero ejecutivo. Responde en español sobre auditoria de gastos
y forecast de Ventas, Finanzas, IT o People. La consulta ya fue validada.
Entrega un reporte breve con tendencia, riesgos y una recomendacion accionable.
No inventes cifras: usa solo los datos entregados.
"""


def calcular_forecast(valores, periodos=3):
	x = list(range(1, len(valores) + 1))
	media_x = sum(x) / len(x)
	media_y = sum(valores) / len(valores)
	numerador = sum((xi - media_x) * (yi - media_y) for xi, yi in zip(x, valores))
	denominador = sum((xi - media_x) ** 2 for xi in x)
	pendiente = numerador / denominador if denominador else 0
	intercepto = media_y - pendiente * media_x
	return [round(intercepto + pendiente * (len(x) + i), 2) for i in range(1, periodos + 1)]


def obtener_forecast(departamento):
	nombre_buscado = departamento.strip().lower()
	claves_normalizadas = {clave.lower(): clave for clave in HISTORICO_GASTOS}
	nombre = claves_normalizadas.get(nombre_buscado)
	if nombre is None:
		return {"error": f"Departamento no encontrado: {departamento}"}, "Validacion local"

	try:
		response = requests.get(BACKEND_URL, params={"departamento": nombre}, timeout=3)
		response.raise_for_status()
		return response.json(), "Backend Flask"
	except requests.RequestException:
		historico = HISTORICO_GASTOS.get(nombre)
		if historico is None:
			return {"error": f"No hay historico para: {nombre}"}, "Validacion local"
		forecast = calcular_forecast(historico)
		return {
			"departamento": nombre,
			"historico": historico,
			"forecast_proximos_3_meses": [
				{"mes": f"Mes {len(historico) + i}", "valor_estimado": valor}
				for i, valor in enumerate(forecast, start=1)
			],
		}, "Calculo local"


def consulta_ollama(mensaje, datos):
	payload = {
		"model": MODEL_NAME,
		"system": SYSTEM_PROMPT,
		"prompt": f"Consulta: {mensaje}\nDatos financieros: {datos}",
		"stream": False,
		"options": {
			"num_predict": 150,
			"temperature": 0.2,
		},
	}
	try:
		response = requests.post(OLLAMA_URL, json=payload, timeout=30)
		response.raise_for_status()
		return response.json().get("response", "Ollama no devolvio texto.")
	except requests.RequestException as error:
		return f"No se pudo conectar con Ollama: {error}"


def es_consulta_valida(mensaje, departamento):
	texto = mensaje.lower()
	prohibidas = ["receta", "cocina", "programacion", "codigo", "barco", "viaje", "pelicula", "musica"]
	financieras = ["auditoria", "gasto", "egreso", "forecast", "pronostico", "presupuesto", "departamento"]
	return not any(palabra in texto for palabra in prohibidas) and any(
		palabra in texto for palabra in financieras
	) and departamento.lower() in texto


def normalizar_texto(texto):
	texto = unicodedata.normalize("NFKD", texto)
	texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
	return re.sub(r"\s+", " ", texto.lower()).strip(" .!?")


st.set_page_config(page_title="Finanzas | Forecast", page_icon="📊", layout="wide")

st.markdown(
	"""
	<style>
	.stApp { background: #f4f7f9; }
	[data-testid="stSidebar"] { background: #12232e; }
	[data-testid="stSidebar"] * { color: #f4f7f9; }
	h1, h2, h3 { color: #12232e; letter-spacing: 0; }
	.hero { background: linear-gradient(110deg, #12343b, #1f6f78); color: white; padding: 2rem; border-radius: 8px; margin-bottom: 1.5rem; }
	.hero h1 { color: white; margin: 0; }
	.hero p { color: #d9f0ed; margin: .5rem 0 0; }
	</style>
	""",
	unsafe_allow_html=True,
)

st.markdown(
	'<div class="hero"><h1>📊 Centro de Inteligencia Financiera</h1>'
	'<p>Forecast operativo, tendencia de gastos y auditoria asistida por IA</p></div>',
	unsafe_allow_html=True,
)

with st.sidebar:
	st.header("🔎 Panel de control")
	departamento = st.selectbox("DEPARTAMENTO", DEPARTAMENTOS, index=2)
	st.caption(f"Modelo: {MODEL_NAME}")
	st.caption("Ollama: 127.0.0.1:11434")

datos, origen_datos = obtener_forecast(departamento)
historico = datos.get("historico", [])
forecast_items = datos.get("forecast_proximos_3_meses", [])
forecast_valores = [item.get("valor_estimado", 0) for item in forecast_items]
nombre_departamento = datos.get("departamento", departamento.title())

st.subheader(f"Resumen de {nombre_departamento}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ultimo gasto", f"${historico[-1]:,.0f}" if historico else "N/A")
col2.metric("Forecast mes 1", f"${forecast_valores[0]:,.0f}" if forecast_valores else "N/A")
col3.metric("Forecast mes 3", f"${forecast_valores[-1]:,.0f}" if forecast_valores else "N/A")
variacion = ((forecast_valores[-1] - historico[-1]) / historico[-1] * 100) if historico and forecast_valores else 0
col4.metric("Variacion proyectada", f"{variacion:.1f}%")

st.caption(f"Fuente de datos: {origen_datos}")

grafico = pd.DataFrame(
	{"Historico": historico + [None] * 3, "Forecast": [None] * len(historico) + forecast_valores},
	index=MESES + ["Mes 13", "Mes 14", "Mes 15"],
)
st.subheader("📈 Evolucion y forecast")
st.line_chart(grafico, color=["#176b87", "#e76f51"], height=360)

st.subheader("💬 Analista financiero")
if "mensajes" not in st.session_state:
	st.session_state.mensajes = []

for mensaje in st.session_state.mensajes:
	with st.chat_message(mensaje["role"]):
		st.markdown(mensaje["content"])

pregunta = st.chat_input(f"Consulta sobre {nombre_departamento}, gastos o forecast...")
if pregunta:
	st.session_state.mensajes.append({"role": "user", "content": pregunta})
	with st.chat_message("user"):
		st.markdown(pregunta)

	with st.chat_message("assistant"):
		if not es_consulta_valida(pregunta, nombre_departamento):
			respuesta = "Lo siento, solo puedo responder sobre auditoria y forecast financiero de este departamento."
		else:
			with st.spinner("Analizando datos con Ollama..."):
				respuesta = consulta_ollama(pregunta, datos)
		st.info(respuesta)
	st.session_state.mensajes.append({"role": "assistant", "content": respuesta})
