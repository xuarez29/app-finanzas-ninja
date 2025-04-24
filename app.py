import streamlit as st
st.set_page_config(page_title="Resumen Financiero Inteligente", layout="centered")

import pdfplumber
import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import json
from babel.numbers import format_currency
from xhtml2pdf import pisa
import altair as alt
from datetime import datetime
import re

# --- AUTENTICACIÓN SIMPLE ---
USUARIOS = {
    "admin": "ninja1929",
    "cliente1": "ninja1929"
}

def login():
    st.title("\U0001F510 Acceso")
    usuario = st.text_input("Usuario")
    contrasena = st.text_input("Contraseña", type="password")
    if st.button("Iniciar sesión"):
        if USUARIOS.get(usuario) == contrasena:
            st.session_state["autenticado"] = True
            st.session_state["usuario"] = usuario
        else:
            st.error("Credenciales incorrectas")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    login()
    st.stop()
else:
    st.sidebar.success(f"Sesión iniciada como: {st.session_state['usuario']}")

# Selector de vista
opcion = st.sidebar.radio("Navegación:", ["\U0001F4C4 Procesar PDF", "\U0001F4CA Dashboard Analítico"])

# Configuración
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logo_path = "ninjas_logo_md.jpg"
output_folder = "reportes"
os.makedirs(output_folder, exist_ok=True)

# Función para convertir HTML a PDF
def convertir_html_a_pdf(html_content, output_path):
    with open(output_path, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(src=html_content, dest=result_file)
    return pisa_status.err

# ========== Procesar PDF ==========
if opcion == "\U0001F4C4 Procesar PDF":
    st.image(logo_path, width=100)
    st.title("\U0001F4C4 Procesar Estado de Cuenta")

    uploaded_file = st.file_uploader("\U0001F4C4 Sube tu archivo PDF", type="pdf")

    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        st.subheader("\U0001F4DA Texto extraído")
        st.text_area("Contenido del PDF", text, height=300)

        if st.button("\U0001F50D Extraer datos clave y analizar"):
            with st.spinner("Analizando con IA..."):
                prompt = f"""
A partir del siguiente texto de un estado de cuenta en español, realiza lo siguiente:

1. Extrae los siguientes datos si están presentes:
- Nombre completo
- RFC
- Número de cuenta
- Saldo total al corte (busca explícitamente esta frase o sus componentes aunque estén separados)
- Tema general del documento

2. Después de leer y analizar todo el contenido, identifica posibles **riesgos financieros** y sugiere **recomendaciones**.

Devuelve todo en formato JSON con estas claves exactas:
nombre, rfc, cuenta, saldo, tema, riesgos, recomendaciones

Texto:
{text}
"""
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                content = response.choices[0].message.content

                # Limpieza para evitar errores con markdown JSON
                content_clean = content.strip().strip('`').replace("```json", "").replace("```", "").strip()

                try:
                    datos = json.loads(content_clean)
                except:
                    st.error("⚠️ Error al interpretar la respuesta como JSON.")
                    st.code(content)
                    st.stop()

                if datos["saldo"] != "No encontrado":
                    try:
                        monto = float(datos["saldo"].replace(",", "").replace("$", ""))
                        datos["saldo"] = format_currency(monto, "MXN", locale="es_MX")
                    except:
                        datos["saldo"] = "No encontrado"
                else:
                    texto_normalizado = text.replace("\n", " ").lower()
                    if "saldo total" in texto_normalizado and "al corte" in texto_normalizado:
                        match = re.search(r"saldo total.*al corte.*?\$([\d,]+\.\d{2})", texto_normalizado)
                        if match:
                            try:
                                monto = float(match.group(1).replace(",", ""))
                                datos["saldo"] = format_currency(monto, "MXN", locale="es_MX")
                            except:
                                datos["saldo"] = "No encontrado"

                fecha_actual = datetime.today().strftime("%Y-%m-%d")
                datos_completo = {
                    "nombre": datos.get("nombre", "No encontrado"),
                    "rfc": datos.get("rfc", "No encontrado"),
                    "cuenta": datos.get("cuenta", "No encontrado"),
                    "saldo": datos.get("saldo", "No encontrado"),
                    "tema": datos.get("tema", "No encontrado"),
                    "riesgos": datos.get("riesgos", "No encontrado"),
                    "recomendaciones": datos.get("recomendaciones", "No encontrado"),
                    "fecha": fecha_actual
                }

                st.success("✅ Datos extraídos por IA:")
                for clave, valor in datos_completo.items():
                    st.write(f"**{clave.capitalize()}:** {valor}")

                csv_path = "resumen_datos.csv"
                df = pd.DataFrame([datos_completo])
                if os.path.exists(csv_path):
                    df_existente = pd.read_csv(csv_path)
                    df_existente = pd.concat([df_existente, df], ignore_index=True)
                    df_existente.to_csv(csv_path, index=False)
                else:
                    df.to_csv(csv_path, index=False)

                with open(csv_path, "rb") as f:
                    st.download_button("\U0001F4C5 Descargar CSV completo", f, file_name="resumen_datos.csv", mime="text/csv")

                tabla = "".join([f"<tr><td><strong>{k.capitalize()}</strong></td><td>{v}</td></tr>" for k, v in datos_completo.items()])
                html_content = f"""
                <html>
                <body>
                    <img src="{logo_path}" width="100">
                    <h1>Resumen Financiero Inteligente</h1>
                    <h3>Datos extraídos:</h3>
                    <table border="1" cellpadding="6" cellspacing="0">
                        {tabla}
                    </table>
                </body>
                </html>
                """

                base_filename = f"resumen_{datos_completo['nombre'].replace(' ', '_')}"
                filename = f"{base_filename}.pdf"
                count = 1
                while os.path.exists(os.path.join(output_folder, filename)):
                    filename = f"{base_filename}_{count}.pdf"
                    count += 1
                pdf_path = os.path.join(output_folder, filename)

                error = convertir_html_a_pdf(html_content, pdf_path)
                if not error:
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button("\U0001F4C4 Descargar PDF generado", pdf_file, file_name=filename, mime="application/pdf")
                else:
                    st.error("❌ Error al generar el PDF.")
