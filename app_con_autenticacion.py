import streamlit as st
st.set_page_config(page_title="Resumen Financiero Inteligente", layout="centered")

import pdfplumber
import os
import pandas as pd
from weasyprint import HTML, CSS
from dotenv import load_dotenv
from openai import OpenAI
import json
from babel.numbers import format_currency
import altair as alt  # <--- Necesario para las gráficas

# --- AUTENTICACIÓN SIMPLE ---
USUARIOS = {
    "admin": "ninja1929",
    "cliente1": "ninja1929"
}

def login():
    st.title("🔐 Acceso")
    usuario = st.text_input("Usuario")
    contraseña = st.text_input("Contraseña", type="password")
    if st.button("Iniciar sesión"):
        if USUARIOS.get(usuario) == contraseña:
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

# --- Selector de sección ---
opcion = st.sidebar.radio("Navegación:", ["📤 Procesar PDF", "📊 Dashboard Analítico"])

# Configuración inicial
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logo_path = "ninjas_logo_md.jpg"
output_folder = "reportes"
os.makedirs(output_folder, exist_ok=True)

# === Sección: Procesar PDF ===
if opcion == "📤 Procesar PDF":
    st.image(logo_path, width=100)
    st.title("📤 Procesar Estado de Cuenta")

    uploaded_file = st.file_uploader("📤 Sube tu archivo PDF", type="pdf")

    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        st.subheader("📚 Texto extraído")
        st.text_area("Contenido del PDF", text, height=300)

        if st.button("🔍 Extraer datos clave y analizar"):
            with st.spinner("Analizando con IA..."):
                prompt = f"""
A partir del siguiente texto de un estado de cuenta en español, realiza lo siguiente:

1. Extrae los siguientes datos si están presentes:
- Nombre completo
- RFC
- Número de cuenta
- Saldo total al corte
- Tema general del documento (por ejemplo: resumen financiero mensual)

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
                try:
                    datos = json.loads(content)
                except:
                    st.error("⚠️ Error al interpretar la respuesta como JSON.")
                    st.code(content)
                    st.stop()

                # Formatear saldo a MXN
                if datos["saldo"] != "No encontrado":
                    try:
                        monto = float(datos["saldo"].replace(",", "").replace("$", ""))
                        datos["saldo"] = format_currency(monto, "MXN", locale="es_MX")
                    except:
                        datos["saldo"] = "No encontrado"

                # Mostrar datos clave
                st.success("✅ Datos extraídos por IA:")
                for clave, valor in datos.items():
                    st.write(f"**{clave.capitalize()}:** {valor}")

                # Guardar CSV general
                csv_path = "resumen_datos.csv"
                df = pd.DataFrame([datos])
                if os.path.exists(csv_path):
                    df.to_csv(csv_path, mode='a', header=False, index=False)
                else:
                    df.to_csv(csv_path, index=False)

                with open(csv_path, "rb") as f:
                    st.download_button("📥 Descargar CSV completo", f, file_name="resumen_datos.csv", mime="text/csv")

                # Crear tabla HTML para el PDF
                tabla = "".join([f"<tr><td><strong>{k.capitalize()}</strong></td><td>{v}</td></tr>" for k, v in datos.items() if k not in ["riesgos", "recomendaciones"]])
                html_content = f"""
                <html>
                <body>
                    <img src="{logo_path}" width="100">
                    <h1>Resumen Financiero Inteligente</h1>
                    <h3>Datos extraídos:</h3>
                    <table border="1" cellpadding="6" cellspacing="0">
                        {tabla}
                    </table>
                    <br><h3>Riesgos detectados:</h3>
                    <p>{datos['riesgos']}</p>
                    <br><h3>Recomendaciones:</h3>
                    <p>{datos['recomendaciones']}</p>
                </body>
                </html>
                """

                # Crear nombre único de PDF
                base_filename = f"resumen_{datos['nombre'].replace(' ', '_')}"
                filename = f"{base_filename}.pdf"
                count = 1
                while os.path.exists(os.path.join(output_folder, filename)):
                    filename = f"{base_filename}_{count}.pdf"
                    count += 1
                pdf_path = os.path.join(output_folder, filename)

                HTML(string=html_content, base_url=".").write_pdf(pdf_path, stylesheets=[CSS(string="body { font-family: Arial, sans-serif; }")])
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button("📄 Descargar PDF generado", pdf_file, file_name=filename, mime="application/pdf")

# === Sección: Dashboard Analítico ===
elif opcion == "📊 Dashboard Analítico":
    st.title("📊 Dashboard Analítico")

    csv_path = "resumen_datos.csv"
    if not os.path.exists(csv_path):
        st.warning("No se ha generado ningún dato todavía.")
        st.stop()

    df = pd.read_csv(csv_path)

    # KPIs
    st.subheader("📌 Indicadores clave")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Documentos", len(df))
    col2.metric("👤 Personas únicas", df["nombre"].nunique())
    col3.metric("💰 Suma total de saldos", df["saldo"].sum() if df["saldo"].dtype != object else "—")
    col4.metric("💳 Saldo promedio", df["saldo"].mean() if df["saldo"].dtype != object else "—")

    # 📈 Gráfica de documentos por persona
    st.subheader("📈 Documentos procesados por persona (Top 10)")
    conteo = df["nombre"].value_counts().head(10).reset_index()
    conteo.columns = ["nombre", "documentos"]
    chart = alt.Chart(conteo).mark_bar().encode(
        x='documentos:Q',
        y=alt.Y('nombre:N', sort='-x'),
        tooltip=['nombre', 'documentos']
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)

    # Filtro por nombre o RFC
    st.subheader("🔎 Buscar registros")
    filtro = st.text_input("Buscar por nombre, RFC o cuenta:")
    if filtro:
        df_filtrado = df[df.apply(lambda row: filtro.lower() in str(row).lower(), axis=1)]
    else:
        df_filtrado = df

    st.dataframe(df_filtrado)
