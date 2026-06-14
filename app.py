import streamlit as st
import pandas as pd
import requests
from io import StringIO

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="OTIF - Control Operativo Clientes",
    layout="wide"
)

# =========================================================
# CARGA DATOS
# =========================================================

@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/PabloJ91011/MAPAS/main/otif_h3.csv"
    r = requests.get(url)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

df = load_data()

# =========================================================
# LIMPIEZA
# =========================================================

df["dps"] = df["dps"].astype(str)

# evitar divisiones por cero
df["entregas_totales"] = df["entregas_totales"].replace(0, 1)
df["hl_comprados"] = df["hl_comprados"].replace(0, 1)
df["frecuencia_semanal"] = df["frecuencia_semanal"].replace(0, 0.1)

# =========================================================
# MÉTRICAS CLAVE (INTELIGENTES)
# =========================================================

df["rech_rate"] = df["entregas_rech"] / df["entregas_totales"]

df["hl_impacto"] = df["hl_rechazados"] / df["hl_comprados"]

df["freq_score"] = 1 / df["frecuencia_semanal"]

# =========================================================
# MADUREZ FACTOR
# =========================================================

def madurez_factor(x):
    x = str(x).upper()
    if "BAJA" in x:
        return 1.2
    elif "MEDIA" in x:
        return 1.0
    else:
        return 0.8

df["madurez_factor"] = df["madurez_cliente"].apply(madurez_factor)

# =========================================================
# RISK SCORE (CORE DEL SISTEMA)
# =========================================================

df["risk_score"] = (
    df["rech_rate"] * 0.25 +
    df["hl_impacto"] * 0.45 +   # 🔥 MÁS IMPORTANTE
    df["freq_score"] * 0.15 +
    df["madurez_factor"] * 0.15
)

# =========================================================
# NIVEL DE RIESGO
# =========================================================

def nivel_riesgo(row):
    if row["risk_score"] > 0.6:
        return "CRÍTICO 🔴"
    elif row["risk_score"] > 0.35:
        return "ALTO 🟠"
    elif row["risk_score"] > 0.2:
        return "MEDIO 🟡"
    else:
        return "BAJO 🟢"

df["nivel_riesgo"] = df.apply(nivel_riesgo, axis=1)

# =========================================================
# ACCIONES AUTOMÁTICAS
# =========================================================

def accion(row):
    if row["hl_impacto"] > 0.3:
        return "🚨 URGENTE: impacto HL alto → revisar operación"
    if row["motivo_rechazo_principal"] == "LOCAL CERRADO":
        return "⏰ Ajustar ventana horaria"
    if row["freq_score"] > 0.8:
        return "📦 Reducir frecuencia / consolidar pedidos"
    if row["rech_rate"] > 0.2:
        return "🔍 Revisar logística general"
    return "🟢 Monitoreo"

df["accion_recomendada"] = df.apply(accion, axis=1)

# =========================================================
# SIDEBAR FILTROS
# =========================================================

st.sidebar.title("Filtros")

dps_list = sorted(df["dps"].dropna().unique())

selected_dps = st.sidebar.multiselect(
    "DPS",
    dps_list,
    default=dps_list
)

df = df[df["dps"].isin(selected_dps)]

nivel = st.sidebar.selectbox(
    "Nivel de riesgo",
    ["TODOS", "CRÍTICO 🔴", "ALTO 🟠", "MEDIO 🟡", "BAJO 🟢"]
)

if nivel != "TODOS":
    df = df[df["nivel_riesgo"] == nivel]

# =========================================================
# TÍTULO
# =========================================================

st.title("📊 OTIF - Control Operativo de Clientes")

# =========================================================
# KPIs
# =========================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric("Clientes", df["cliente"].nunique())

c2.metric("Clientes Críticos", (df["nivel_riesgo"] == "CRÍTICO 🔴").sum())

c3.metric("HL Rechazados", df["hl_rechazados"].sum())

c4.metric("Impacto HL Promedio", f"{df['hl_impacto'].mean():.2%}")

# =========================================================
# TOP CRÍTICOS
# =========================================================

st.subheader("🚨 Top Clientes Críticos")

top = df.sort_values("risk_score", ascending=False).head(10)

st.dataframe(
    top[[
        "cliente_nombre",
        "nivel_riesgo",
        "risk_score",
        "hl_rechazados",
        "hl_comprados",
        "hl_impacto",
        "entregas_rech",
        "rech_rate",
        "frecuencia_semanal",
        "motivo_rechazo_principal",
        "ventana_horaria_recepcion",
        "accion_recomendada"
    ]],
    use_container_width=True
)

# =========================================================
# TABLA COMPLETA OPERATIVA
# =========================================================

st.subheader("📌 Clientes - Vista Operativa")

tabla = df.sort_values("risk_score", ascending=False)[[
    "cliente_nombre",
    "nivel_riesgo",
    "risk_score",
    "hl_rechazados",
    "hl_impacto",
    "entregas_rech",
    "rech_rate",
    "frecuencia_semanal",
    "motivo_rechazo_principal",
    "ventana_horaria_recepcion",
    "accion_recomendada"
]]

st.dataframe(tabla, use_container_width=True, height=700)

# =========================================================
# DESCARGA
# =========================================================

csv = df.to_csv(index=False)

st.download_button(
    "📥 Descargar Base Filtrada",
    csv,
    "OTIF_Operativo.csv",
    "text/csv"
)
