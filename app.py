
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

USUARIOS = {
    "admin": "ninja1929",
    "cliente1": "ninja1929"
}

def login():
    st.title("🔐 Acceso")
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

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logo_path = "ninjas_logo_md.jpg"
output_folder = "reportes"
csv_path = "resumen_finanzas_ninja.csv"
os.makedirs(output_folder, exist_ok=True)

if not os.path.exists(csv_path):
    columnas = ["nombre", "rfc", "cuenta", "saldo", "tema", "riesgos", "recomendaciones", "fecha"]
    pd.DataFrame(columns=columnas).to_csv(csv_path, index=False)

opcion = st.sidebar.radio("Navegación:", ["📄 Procesar PDF", "📊 Dashboard Analítico"])

if opcion == "📄 Procesar PDF":
    st.image(logo_path, width=100)
    st.title("📄 Procesar Estado de Cuenta")
    uploaded_file = st.file_uploader("📤 Sube tu archivo PDF", type="pdf")

    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        st.subheader("📃 Texto extraído")
        st.text_area("Contenido del PDF", text, height=300)

        if st.button("🔍 Extraer datos clave y analizar"):
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
                content_clean = content.strip().strip("`").replace("```json", "").replace("```", "").strip()

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
                    match = re.search(r"(saldo.*al corte.*?|saldo.*final.*?)\$?([\d,]+\.\d{2})", texto_normalizado)
                    if match:
                        try:
                            monto = float(match.group(2).replace(",", ""))
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

                df = pd.DataFrame([datos_completo])
                df_existente = pd.read_csv(csv_path)
                df_existente = pd.concat([df_existente, df], ignore_index=True)
                df_existente.to_csv(csv_path, index=False)

                with open(csv_path, "rb") as f:
                    st.download_button("📥 Descargar CSV completo", f, file_name="resumen_finanzas_ninja.csv", mime="text/csv")

                tabla = "".join([
                    f"<tr><td><strong>{k.capitalize()}</strong></td><td>{v}</td></tr>"
                    for k, v in datos_completo.items()
                ])
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

                def convertir_html_a_pdf(html_content, output_path):
                    with open(output_path, "w+b") as result_file:
                        pisa_status = pisa.CreatePDF(src=html_content, dest=result_file)
                    return pisa_status.err

                error = convertir_html_a_pdf(html_content, pdf_path)
                if not error:
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button("📄 Descargar PDF generado", pdf_file, file_name=filename, mime="application/pdf")
                else:
                    st.error("❌ Error al generar el PDF.")

elif opcion == "📊 Dashboard Analítico":
    st.title("📊 Dashboard Analítico")
    if not os.path.exists(csv_path):
        st.warning("Aún no se ha procesado ningún documento.")
        st.stop()
    df = pd.read_csv(csv_path)
    if df.empty:
        st.info("No hay datos disponibles aún. Procesa al menos un PDF para ver el análisis.")
        st.stop()
    st.subheader("📌 Indicadores clave")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Documentos", len(df))
    col2.metric("👤 Personas únicas", df["nombre"].nunique())
    try:
        df["saldo_num"] = df["saldo"].replace("[\$,MXN]", "", regex=True).str.replace(",", "").astype(float)
        col3.metric("💰 Suma total de saldos", f"${df['saldo_num'].sum():,.2f}")
        col4.metric("💳 Saldo promedio", f"${df['saldo_num'].mean():,.2f}")
    except:
        col3.metric("💰 Suma total de saldos", "—")
        col4.metric("💳 Saldo promedio", "—")

    st.subheader("📈 Documentos procesados por persona (Top 10)")
    top = df["nombre"].value_counts().head(10).reset_index()
    top.columns = ["nombre", "documentos"]
    chart = alt.Chart(top).mark_bar().encode(
        x="documentos:Q",
        y=alt.Y("nombre:N", sort="-x"),
        tooltip=["nombre", "documentos"]
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)

    if "fecha" in df.columns:
        st.subheader("🗓️ Evolución mensual de documentos")
        try:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df["mes"] = df["fecha"].dt.to_period("M").astype(str)
            evol = df.groupby("mes").size().reset_index(name="documentos")
            chart2 = alt.Chart(evol).mark_line(point=True).encode(
                x="mes:T",
                y="documentos:Q",
                tooltip=["mes", "documentos"]
            ).properties(height=400)
            st.altair_chart(chart2, use_container_width=True)
        except:
            st.warning("No se pudo graficar la evolución mensual (verifica formato de fechas).")

    st.subheader("🔎 Buscar registros")
    query = st.text_input("Buscar por nombre, RFC o cuenta:")
    if query:
        df_filtrado = df[df.apply(lambda row: query.lower() in str(row).lower(), axis=1)]
    else:
        df_filtrado = df
    st.dataframe(df_filtrado)
