import re
import unicodedata

import pandas as pd
import requests
import streamlit as st


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:1.5b"
BACKEND_URL = "http://127.0.0.1:5000/api/forecast"
OLLAMA_TIMEOUT = (3, 35)
BACKEND_TIMEOUT = (2, 5)

DEPARTAMENTOS = ["ventas", "finanzas", "it", "people"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
HISTORICO_GASTOS = {
	"ventas": [12000, 12800, 13400, 14250, 14900, 15520, 16000, 16850, 17500, 18100, 18750, 19400],
	"finanzas": [9800, 10150, 10900, 11120, 11480, 11890, 12250, 12540, 12870, 13120, 13600, 14050],
	"it": [15000, 15850, 16200, 17100, 17650, 18120, 18800, 19650, 20350, 21400, 22100, 22950],
	"people": [8200, 8600, 9000, 9400, 9900, 10150, 10800, 11200, 11650, 12080, 12750, 13250],
}

SYSTEM_PROMPT = """
Eres un analista financiero ejecutivo. Responde en español sobre auditoria de gastos
y forecast del departamento seleccionado. La consulta ya fue validada.
Entrega un reporte conciso con tendencia, riesgo principal y recomendacion accionable.
Usa solo las cifras suministradas y no inventes datos.
"""


def calcular_forecast(valores, periodos=3):
	if not valores:
		return []
	x = list(range(1, len(valores) + 1))
	media_x = sum(x) / len(x)
	media_y = sum(valores) / len(valores)
	numerador = sum((xi - media_x) * (yi - media_y) for xi, yi in zip(x, valores))
	denominador = sum((xi - media_x) ** 2 for xi in x)
	pendiente = numerador / denominador if denominador else 0
	intercepto = media_y - pendiente * media_x
	return [round(intercepto + pendiente * (len(x) + i), 2) for i in range(1, periodos + 1)]


def obtener_forecast(departamento):
	nombre = str(departamento).strip().lower()
	historico_local = HISTORICO_GASTOS.get(nombre)
	if historico_local is None:
		return {"error": f"Departamento no reconocido: {departamento}"}, "Validacion local"

	try:
		response = requests.get(
			BACKEND_URL,
			params={"departamento": nombre},
			timeout=BACKEND_TIMEOUT,
		)
		response.raise_for_status()
		datos = response.json()
		if "historico" in datos and "forecast_proximos_3_meses" in datos:
			return datos, "Backend Flask"
	except (requests.RequestException, ValueError):
		pass

	valores_forecast = calcular_forecast(historico_local)
	return {
		"departamento": nombre,
		"historico": historico_local,
		"forecast_proximos_3_meses": [
			{"mes": f"Mes {len(historico_local) + indice}", "valor_estimado": valor}
			for indice, valor in enumerate(valores_forecast, start=1)
		],
	}, "Calculo local"


def consulta_ollama(mensaje, departamento, datos):
	payload = {
		"model": MODEL_NAME,
		"system": SYSTEM_PROMPT,
		"prompt": (
			f"Departamento: {departamento.upper()}\n"
			f"Consulta: {mensaje}\n"
			f"Datos financieros (historico y forecast): {datos}"
		),
		"stream": False,
		"options": {
			"temperature": 0.2,
			"num_predict": 120,
		},
	}
	try:
		response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
		response.raise_for_status()
		texto = response.json().get("response", "").strip()
		return texto or "Ollama respondio sin texto. Intenta de nuevo."
	except requests.Timeout:
		return "Ollama tardo demasiado en responder. Verifica que el modelo este cargado e intenta de nuevo."
	except requests.ConnectionError:
		return "No se pudo conectar con Ollama en 127.0.0.1:11434. Verifica que Ollama este iniciado."
	except (requests.RequestException, ValueError) as error:
		return f"Error al consultar Ollama: {error}"


def normalizar_texto(texto):
	texto = unicodedata.normalize("NFKD", str(texto))
	texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
	return re.sub(r"\s+", " ", texto.lower()).strip()


def es_consulta_valida(mensaje):
	texto = normalizar_texto(mensaje)
	prohibidas = ("receta", "cocina", "programacion", "codigo", "barco", "viaje", "pelicula", "musica")
	financieras = ("auditoria", "gasto", "egreso", "forecast", "pronostico", "presupuesto")
	return not any(palabra in texto for palabra in prohibidas) and any(
		palabra in texto for palabra in financieras
	)


def formato_departamento(departamento):
	return departamento.upper()


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
	departamento = st.selectbox(
		"DEPARTAMENTO",
		DEPARTAMENTOS,
		index=2,
		format_func=formato_departamento,
	)
	st.caption(f"Modelo: {MODEL_NAME}")
	st.caption("Ollama: 127.0.0.1:11434")

datos, origen_datos = obtener_forecast(departamento)
if "error" in datos:
	st.error(datos["error"])
	st.stop()

historico = datos.get("historico", [])
forecast_items = datos.get("forecast_proximos_3_meses", [])
forecast_valores = [item.get("valor_estimado", 0) for item in forecast_items]
nombre_departamento = datos.get("departamento", departamento).upper()

st.subheader(f"Resumen de {nombre_departamento}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ultimo gasto", f"${historico[-1]:,.0f}" if historico else "N/A")
col2.metric("Forecast mes 1", f"${forecast_valores[0]:,.0f}" if forecast_valores else "N/A")
col3.metric("Forecast mes 3", f"${forecast_valores[-1]:,.0f}" if forecast_valores else "N/A")
variacion = (
	(forecast_valores[-1] - historico[-1]) / historico[-1] * 100
	if historico and forecast_valores and historico[-1]
	else 0
)
col4.metric("Variacion proyectada", f"{variacion:.1f}%")

st.caption(f"Fuente de datos: {origen_datos}")

etiquetas = MESES[: len(historico)] + [item.get("mes", f"Mes {len(historico) + indice}") for indice, item in enumerate(forecast_items, start=1)]
grafico = pd.DataFrame(
	{
		"Historico": historico + [None] * len(forecast_valores),
		"Forecast": [None] * len(historico) + forecast_valores,
	},
	index=etiquetas,
)
st.subheader("📈 Evolucion y forecast")
st.line_chart(grafico, color=["#176b87", "#e76f51"], height=360)

st.subheader("💬 Analista financiero")
if "mensajes" not in st.session_state:
	st.session_state.mensajes = []

for mensaje in st.session_state.mensajes:
	with st.chat_message(mensaje["role"]):
		if mensaje["role"] == "assistant":
			st.info(mensaje["content"])
		else:
			st.markdown(mensaje["content"])

pregunta = st.chat_input(f"Consulta sobre {nombre_departamento}, gastos o forecast...")
if pregunta:
	st.session_state.mensajes.append({"role": "user", "content": pregunta})
	with st.chat_message("user"):
		st.markdown(pregunta)

	with st.chat_message("assistant"):
		if not es_consulta_valida(pregunta):
			respuesta = "Lo siento, solo puedo responder consultas sobre auditoria, gastos o forecast financiero."
		else:
			with st.spinner("Analizando el forecast..."):
				respuesta = consulta_ollama(pregunta, nombre_departamento, datos)
		st.info(respuesta)
	st.session_state.mensajes.append({"role": "assistant", "content": respuesta})
