import streamlit as st
import pandas as pd
import requests
from io import StringIO
import matplotlib.pyplot as plt

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="OTIF - Control Operativo PRO",
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
df["entregas_totales"] = df["entregas_totales"].replace(0, 1)
df["hl_comprados"] = df["hl_comprados"].replace(0, 1)
df["frecuencia_semanal"] = df["frecuencia_semanal"].replace(0, 0.1)

# =========================================================
# FEATURES
# =========================================================

df["rech_rate"] = df["entregas_rech"] / df["entregas_totales"]
df["hl_impacto"] = df["hl_rechazados"] / df["hl_comprados"]
df["freq_score"] = 1 / df["frecuencia_semanal"]

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
# RISK SCORE
# =========================================================

df["risk_score"] = (
    df["rech_rate"] * 0.25 +
    df["hl_impacto"] * 0.45 +
    df["freq_score"] * 0.15 +
    df["madurez_factor"] * 0.15
)

# =========================================================
# NIVEL RIESGO
# =========================================================

def nivel_riesgo(score):
    if score > 0.6:
        return "CRÍTICO 🔴"
    elif score > 0.35:
        return "ALTO 🟠"
    elif score > 0.2:
        return "MEDIO 🟡"
    return "BAJO 🟢"

df["nivel_riesgo"] = df["risk_score"].apply(nivel_riesgo)

# =========================================================
# GATILLADOR PRO
# =========================================================

def accion_avanzada(row):
    acciones = []

    if row["hl_impacto"] > 0.35:
        acciones.append("🔥 PRIORIDAD MÁXIMA")

    if row["motivo_rechazo_principal"] == "LOCAL CERRADO":
        acciones.append("⏰ Ajustar horario")

    if row["rech_rate"] > 0.25:
        acciones.append("🚛 Revisar ruta")

    if row["frecuencia_semanal"] > 2:
        acciones.append("📦 Consolidar pedidos")

    if row["hl_impacto"] > 0.2 and row["rech_rate"] > 0.2:
        acciones.append("💣 Intervención conjunta")

    return " | ".join(acciones) if acciones else "🟢 OK"

df["accion_recomendada"] = df.apply(accion_avanzada, axis=1)

# =========================================================
# PRIORIZACIÓN SEMANAL 🔥🔥🔥
# =========================================================

st.title("🚀 Plan Operativo Semanal")

top_semana = df.sort_values("risk_score", ascending=False).head(20)

st.subheader("🔥 Top 20 Clientes a Intervenir")

st.dataframe(top_semana[[
    "cliente_nombre",
    "nivel_riesgo",
    "risk_score",
    "hl_rechazados",
    "hl_impacto",
    "rech_rate",
    "accion_recomendada"
]])

# PLAN AUTOMÁTICO
st.subheader("🧠 Plan de Acción Semanal")

plan = []

for i, row in top_semana.iterrows():
    plan.append(f"• {row['cliente_nombre']} → {row['accion_recomendada']}")

st.markdown("\n".join(plan))

# =========================================================
# KPIs
# =========================================================

st.subheader("📊 KPIs")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Clientes", df["cliente"].nunique())
c2.metric("Críticos", (df["nivel_riesgo"] == "CRÍTICO 🔴").sum())
c3.metric("HL Perdido", int(df["hl_rechazados"].sum()))
c4.metric("Impacto %", f"{df['hl_impacto'].mean():.2%}")

# =========================================================
# GRÁFICOS PRO
# =========================================================

st.subheader("📊 Matriz de Riesgo")

fig, ax = plt.subplots()
ax.scatter(df["rech_rate"], df["hl_impacto"], s=df["hl_comprados"]*5, alpha=0.6)
ax.set_xlabel("Rechazo")
ax.set_ylabel("Impacto HL")
st.pyplot(fig)

st.subheader("📉 Motivos")

st.bar_chart(df["motivo_rechazo_principal"].value_counts())

# =========================================================
# FICHA CLIENTE 🔥
# =========================================================

st.subheader("🧾 Ficha Cliente")

cliente_sel = st.selectbox("Selecciona cliente", df["cliente_nombre"].unique())
c = df[df["cliente_nombre"] == cliente_sel].iloc[0]

st.markdown(f"""
### 📌 {c['cliente_nombre']}

**Nivel:** {c['nivel_riesgo']}  
**Score:** {c['risk_score']:.2f}

---

### 📦 Negocio
- HL: {c['hl_comprados']:.2f}
- Rechazo HL: {c['hl_impacto']:.2%}

---

### 🚚 Operación
- Rechazos: {c['rech_rate']:.2%}
- Frecuencia: {c['frecuencia_semanal']:.2f}

---

### 🚨 Problema
{c['motivo_rechazo_principal']}

---

### ✅ Acción
{c['accion_recomendada']}
""")

st.progress(min(c["risk_score"], 1.0))

# =========================================================
# DESCARGA
# =========================================================

csv = df.to_csv(index=False)

st.download_button(
    "📥 Descargar",
    csv,
    "OTIF_PRO.csv",
    "text/csv"
)
