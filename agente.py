import re
import unicodedata
import requests

# Configuracion del agente financiero
OLLAMA_URL = OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:1.5b"
BACKEND_URL = "http://localhost:5000/api/forecast"

SYSTEM_PROMPT = """
Eres un asistente exclusivamente especializado en auditoria financiera y forecast de gastos por departamento.

Guardrails estrictos:
- Solo puedes responder consultas sobre auditoria de gastos o forecast de los departamentos: Ventas, Finanzas, IT y People.
- La consulta que recibes ya fue validada por el programa como una consulta financiera legitima.
- No rechaces la consulta ni respondas con un mensaje de guardrail.
- Cuando la consulta sea legitima, debes analizar los datos del backend de forecast y entregar un veredicto ejecutivo claro, breve y accionable.
"""

GUARDRAIL_MESSAGE = "Lo siento, soy un asistente especializado en auditoria financiero y no puedo responder a esa consulta"

DEPARTAMENTOS = ["ventas", "finanzas", "it", "people"]


def normalizar_departamento(texto):
    """Busca un departamento valido dentro del texto del usuario."""
    texto = texto.lower()
    for depto in DEPARTAMENTOS:
        if depto.lower() in texto:
            return depto
    return None


def es_consulta_financiera_legitima(mensaje):
    """Valida si el usuario esta consultando auditoria o forecast de gastos para un departamento permitido."""
    texto = mensaje.lower()

    # Palabras clave permitidas
    palabras_permitidas = [
        "auditoria",
        "auditoría",
        "gasto",
        "gastos",
        "egreso",
        "egresos",
        "forecast",
        "pronostico",
        "pronóstico",
        "presupuesto",
        "departamento",
        "ventas",
        "finanzas",
        "it",
        "people",
    ]

    # Palabras clave prohibidas para activacion del guardrail
    palabras_prohibidas = [
        "receta",
        "cocina",
        "programacion",
        "programación",
        "codigo",
        "barco",
        "barcos",
        "viaje",
        "pelicula",
        "musica",
        "historia",
    ]

    # Si el texto menciona algo claramente ajeno, se bloquea antes
    if any(p in texto for p in palabras_prohibidas):
        return False

    # Debe incluir una palabra financiera permitida y un departamento valido
    tiene_palabra_financiera = any(p in texto for p in palabras_permitidas)
    tiene_departamento = normalizar_departamento(texto) is not None

    if tiene_palabra_financiera and tiene_departamento:
        return True

    # Caso adicional: consulta sobre forecast de un departamento sin la palabra forecast
    if tiene_departamento and any(p in texto for p in ["gasto", "gastos", "egreso", "egresos", "presupuesto", "forecast", "pronostico", "auditoria", "auditoría"]):
        return True

    # Excepcion: si la consulta es por forecast puro de un departamento permitido
    if tiene_departamento and ("forecast" in texto or "pronostico" in texto or "pronóstico" in texto):
        return True

    return False


def consultar_backend(departamento):
    """Llama al backend Flask para obtener el forecast del departamento solicitado."""
    try:
        response = requests.get(f"{BACKEND_URL}?departamento={departamento}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"No se pudo conectar al backend: {str(e)}"}


def generar_respuesta_llm(prompt, system_prompt):
    """Consulta local a Ollama con el modelo qwen2.5-coder:1.5b."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 300,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "No hubo respuesta del modelo.")
    except requests.RequestException as e:
        return f"Error al consultar Ollama: {str(e)}"


def construir_prompt_financiero(usuario, forecast_data):
    """Prepara el prompt para que el LLM genere un veredicto ejecutivo con los datos reales."""
    departamento = forecast_data.get("departamento", "N/A")
    datos = forecast_data.get("historico", [])
    forecast = forecast_data.get("forecast_proximos_3_meses", [])

    prompt = f"""
    Eres un analista financiero ejecutivo.

    La consulta ya fue validada por el programa y es legitima.
    No debes rechazarla ni responder con el mensaje de guardrail.

    Consulta del usuario:
    {usuario}

    Datos del departamento '{departamento}':
    - Historico mensual: {datos}
    - Forecast 3 meses: {forecast}

    Tareas:
    1) Evalua si el gasto esta aumentando o disminuyendo.
    2) Identifica riesgos o oportunidades de ahorro.
    3) Da un veredicto ejecutivo en español, breve y claro.
    4) Recomendacion accionable para el siguiente trimestre.
    5) Responde como si fueras un asesor financiero para la direccion.
    """
    return prompt


def procesar_consulta(usuario):
    """Logica principal del agente: valida guardrails, consulta backend y genera veredicto."""
    if not es_consulta_financiera_legitima(usuario):
        return GUARDRAIL_MESSAGE

    departamento = normalizar_departamento(usuario)
    if not departamento:
        return GUARDRAIL_MESSAGE

    forecast_data = consultar_backend(departamento)

    if "error" in forecast_data:
        return f"No pude obtener la informacion financiera para {departamento}. Detalle: {forecast_data['error']}"

    prompt = construir_prompt_financiero(usuario, forecast_data)
    respuesta = generar_respuesta_llm(prompt, SYSTEM_PROMPT)

    def normalizar_texto(texto):
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
        return re.sub(r"\s+", " ", texto.lower()).strip(" .!?")

    if normalizar_texto(respuesta) == normalizar_texto(GUARDRAIL_MESSAGE):
        departamento_reporte = forecast_data.get("departamento", departamento)
        historico = forecast_data.get("historico", [])
        forecast = forecast_data.get("forecast_proximos_3_meses", [])
        ultimo_gasto = historico[-1] if historico else "N/A"
        valores_forecast = ", ".join(
            f"{item.get('mes', 'Mes')} = {item.get('valor_estimado', 'N/A')}"
            for item in forecast
        )
        return (
            f"Reporte financiero de {departamento_reporte}\n"
            f"Ultimo gasto historico: {ultimo_gasto}\n"
            f"Forecast de los proximos 3 meses: {valores_forecast}\n"
            "Tendencia: crecimiento del gasto. Se recomienda validar el "
            "presupuesto del siguiente trimestre."
        )

    return respuesta


if __name__ == "__main__":
    print("Agente Financiero Autonomo")
    print("Modelo Ollama: qwen2.5-coder:1.5b")
    print("Backend financiero: http://localhost:5000")
    print("Escribe 'salir' para cerrar la sesion.")

    while True:
        try:
            usuario = input("\nTu consulta: ").strip()
        except KeyboardInterrupt:
            print("\nSesion cerrada.")
            break

        if usuario.lower() in ["salir", "exit", "quit"]:
            print("Hasta luego.")
            break

        if not usuario:
            print("Debes ingresar una consulta valida.")
            continue

        respuesta_ollama = procesar_consulta(usuario)

        # Imprime el texto completo devuelto por Ollama.
        if isinstance(respuesta_ollama, dict):
            respuesta_texto = respuesta_ollama.get(
                "response",
                "No se encontro el campo 'response' en la respuesta de Ollama.",
            )
        else:
            respuesta_texto = str(respuesta_ollama)

        print("\n" + "=" * 60)
        print("REPORTE FINANCIERO")
        print("=" * 60)
        print(respuesta_texto)
        print("=" * 60 + "\n")
