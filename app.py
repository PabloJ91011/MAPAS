import streamlit as st
import pandas as pd
import requests
from io import StringIO
import matplotlib.pyplot as plt
import html

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Centro de Oportunidades Operativas",
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
# LIMPIEZA GENERAL
# =========================================================

df.columns = df.columns.str.strip()

# Convertir IDs a texto limpio
df["cliente"] = df["cliente"].fillna(0).astype(int).astype(str)
df["dps"] = df["dps"].fillna(0).astype(int).astype(str)

# Texto seguro
text_cols = [
    "cliente_nombre",
    "madurez_cliente",
    "dia_entrega",
    "dias_flex",
    "motivo_rechazo_principal",
    "resumen_motivos_rechazo",
    "ventana_horaria_recepcion",
    "ventana_local_cerrado"
]

for col in text_cols:
    if col in df.columns:
        df[col] = df[col].fillna("SIN DATO").astype(str)

# Numéricos seguros
num_cols = [
    "entregas_totales", "entregas_rech", "entregas_sus", "entregas_ok",
    "entregas_flex", "entregas_fee", "rech_flex", "sus_flex", "ok_flex",
    "rech_fee", "sus_fee", "ok_fee", "dias_activos", "x", "y",
    "hl_comprados", "hl_rechazados", "semanas_activas",
    "frecuencia_semanal", "codigo_motivo_principal"
]

for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# Evitar divisiones por cero
df["entregas_totales"] = df["entregas_totales"].replace(0, 1)
df["hl_comprados"] = df["hl_comprados"].replace(0, 1)
df["frecuencia_semanal"] = df["frecuencia_semanal"].replace(0, 0.1)

# Fechas
df["primera_fecha_entrega"] = pd.to_datetime(
    df["primera_fecha_entrega"],
    errors="coerce",
    dayfirst=True
)

# =========================================================
# FEATURES OPERATIVAS
# =========================================================

df["rech_rate"] = df["entregas_rech"] / df["entregas_totales"]
df["hl_impacto"] = df["hl_rechazados"] / df["hl_comprados"]
df["hl_entregados_estimados"] = df["hl_comprados"] - df["hl_rechazados"]

# Normalizaciones seguras
max_hl_rech = max(df["hl_rechazados"].max(), 0.01)
max_rech_rate = max(df["rech_rate"].max(), 0.01)
max_freq = max(df["frecuencia_semanal"].max(), 0.01)

df["hl_norm"] = df["hl_rechazados"] / max_hl_rech
df["rech_norm"] = df["rech_rate"] / max_rech_rate
df["freq_norm"] = df["frecuencia_semanal"] / max_freq

# Score de oportunidad: volumen + rechazo + frecuencia
df["score_oportunidad"] = (
    df["hl_norm"] * 0.60 +
    df["rech_norm"] * 0.25 +
    df["freq_norm"] * 0.15
)

def clasificar_prioridad(score):
    if score >= 0.75:
        return "🔥 CRÍTICA"
    elif score >= 0.50:
        return "🟠 ALTA"
    elif score >= 0.25:
        return "🟡 MEDIA"
    else:
        return "🟢 BAJA"

df["prioridad"] = df["score_oportunidad"].apply(clasificar_prioridad)

# =========================================================
# MOTOR DE ACCIONES
# =========================================================

def accion_operativa(row):
    motivo = str(row["motivo_rechazo_principal"]).upper()
    ventana_ok = str(row["ventana_horaria_recepcion"])
    ventana_cerrado = str(row["ventana_local_cerrado"])

    if "LOCAL CERRADO" in motivo:
        return (
            f"Revisar ventana de entrega. Cliente suele recibir en {ventana_ok}. "
            f"Los rechazos por local cerrado aparecen en {ventana_cerrado}. "
            f"Contactar cliente y ajustar la visita a la ventana más efectiva."
        )

    elif "SIN DINERO" in motivo or "DINERO" in motivo:
        return (
            "Contactar cliente antes del despacho para confirmar disponibilidad de pago. "
            "Si no puede recibir, reprogramar antes de cargar ruta."
        )

    elif "NO RECIBE" in motivo or "RECHAZA" in motivo:
        return (
            "Realizar llamada preventiva antes del despacho para confirmar recepción. "
            "Validar responsable del local y horario disponible."
        )

    elif "DIRECCION" in motivo or "DIRECCIÓN" in motivo:
        return (
            "Validar geolocalización, referencias del domicilio y datos del cliente. "
            "Actualizar ubicación antes de volver a programar."
        )

    elif "PEDIDO" in motivo:
        return (
            "Revisar consistencia del pedido con ventas. Confirmar cantidades y productos "
            "antes de despacho."
        )

    elif row["entregas_rech"] >= 5 and row["hl_rechazados"] > 0:
        return (
            "Cliente con rechazos recurrentes. Coordinar gestión conjunta entre reparto, "
            "ventas y contacto preventivo."
        )

    else:
        return (
            "Revisar historial operativo del cliente y validar causa real del rechazo."
        )

df["accion_recomendada"] = df.apply(accion_operativa, axis=1)

def tipo_gestion(row):
    motivo = str(row["motivo_rechazo_principal"]).upper()

    if "LOCAL CERRADO" in motivo:
        return "Ajuste de ventana"
    elif "DINERO" in motivo:
        return "Confirmación de pago"
    elif "NO RECIBE" in motivo or "RECHAZA" in motivo:
        return "Llamada preventiva"
    elif "DIRECCION" in motivo or "DIRECCIÓN" in motivo:
        return "Validación de ubicación"
    elif row["score_oportunidad"] >= 0.5:
        return "Gestión prioritaria"
    else:
        return "Monitoreo"

df["tipo_gestion"] = df.apply(tipo_gestion, axis=1)

# =========================================================
# SIDEBAR FILTROS
# =========================================================

st.sidebar.title("🔎 Filtros")

dps_sel = st.sidebar.multiselect(
    "DPS",
    sorted(df["dps"].unique())
)

cliente_sel_filtro = st.sidebar.multiselect(
    "Cliente",
    sorted(df["cliente_nombre"].unique())
)

motivo_sel = st.sidebar.multiselect(
    "Motivo rechazo",
    sorted(df["motivo_rechazo_principal"].unique())
)

madurez_sel = st.sidebar.multiselect(
    "Madurez",
    sorted(df["madurez_cliente"].unique())
)

prioridad_sel = st.sidebar.multiselect(
    "Prioridad",
    sorted(df["prioridad"].unique())
)

df_filtrado = df.copy()

if dps_sel:
    df_filtrado = df_filtrado[df_filtrado["dps"].isin(dps_sel)]

if cliente_sel_filtro:
    df_filtrado = df_filtrado[df_filtrado["cliente_nombre"].isin(cliente_sel_filtro)]

if motivo_sel:
    df_filtrado = df_filtrado[df_filtrado["motivo_rechazo_principal"].isin(motivo_sel)]

if madurez_sel:
    df_filtrado = df_filtrado[df_filtrado["madurez_cliente"].isin(madurez_sel)]

if prioridad_sel:
    df_filtrado = df_filtrado[df_filtrado["prioridad"].isin(prioridad_sel)]

# =========================================================
# HEADER
# =========================================================

st.title("🚀 Centro de Oportunidades Operativas")
st.caption("Priorización de clientes para recuperar HL, reducir rechazos y mejorar entregas.")

if df_filtrado.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# =========================================================
# KPIs
# =========================================================

st.subheader("📊 Resumen Ejecutivo")

total_clientes = df_filtrado["cliente"].nunique()
total_entregas = df_filtrado["entregas_totales"].sum()
total_rechazos = df_filtrado["entregas_rech"].sum()
total_ok = df_filtrado["entregas_ok"].sum()
hl_comprados = df_filtrado["hl_comprados"].sum()
hl_rechazados = df_filtrado["hl_rechazados"].sum()
rechazo_pct = total_rechazos / max(total_entregas, 1)
impacto_hl = hl_rechazados / max(hl_comprados, 1)
freq_prom = df_filtrado["frecuencia_semanal"].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Clientes", f"{total_clientes:,}")
c2.metric("Entregas", f"{int(total_entregas):,}")
c3.metric("Rechazos", f"{int(total_rechazos):,}", f"{rechazo_pct:.1%}")
c4.metric("Entregas OK", f"{int(total_ok):,}")

c5, c6, c7, c8 = st.columns(4)
c5.metric("HL Comprados", f"{hl_comprados:,.1f}")
c6.metric("HL Rechazados", f"{hl_rechazados:,.1f}", f"{impacto_hl:.1%}")
c7.metric("Frecuencia Prom.", f"{freq_prom:.2f}")
c8.metric("Clientes Críticos/Alta", int(df_filtrado["prioridad"].isin(["🔥 CRÍTICA", "🟠 ALTA"]).sum()))

# =========================================================
# TOP 10 OPORTUNIDADES
# =========================================================

st.subheader("🎯 Top 10 Clientes a Intervenir")

top10 = (
    df_filtrado
    .sort_values("score_oportunidad", ascending=False)
    .head(10)
    .copy()
)

hl_top10 = top10["hl_rechazados"].sum()
participacion_top10 = hl_top10 / max(df_filtrado["hl_rechazados"].sum(), 1)

a1, a2, a3 = st.columns(3)
a1.metric("HL Recuperable Top 10", f"{hl_top10:,.1f}")
a2.metric("Participación Top 10", f"{participacion_top10:.1%}")
a3.metric("Rechazos Top 10", int(top10["entregas_rech"].sum()))

cols_top = [
    "cliente",
    "cliente_nombre",
    "dps",
    "score_oportunidad",
    "prioridad",
    "hl_rechazados",
    "hl_comprados",
    "rech_rate",
    "entregas_rech",
    "frecuencia_semanal",
    "motivo_rechazo_principal",
    "tipo_gestion",
    "accion_recomendada"
]

st.dataframe(
    top10[cols_top].style.format({
        "score_oportunidad": "{:.2f}",
        "hl_rechazados": "{:.2f}",
        "hl_comprados": "{:.2f}",
        "rech_rate": "{:.1%}",
        "frecuencia_semanal": "{:.2f}"
    }),
    use_container_width=True,
    height=360
)

# =========================================================
# PLAN AUTOMÁTICO
# =========================================================

st.subheader("🧠 Plan de Acción Recomendado")

for _, row in top10.iterrows():
    st.markdown(
        f"""
        **{row['prioridad']} | {row['cliente_nombre']} | DPS {row['dps']}**  
        HL rechazados: **{row['hl_rechazados']:.2f}** | Rechazos: **{int(row['entregas_rech'])}** | Score: **{row['score_oportunidad']:.2f}**  
        👉 {row['accion_recomendada']}
        """
    )

# =========================================================
# GRÁFICOS
# =========================================================

st.subheader("📈 Análisis Visual")

g1, g2 = st.columns(2)

with g1:
    st.markdown("#### Pareto HL Rechazados")
    pareto = (
        df_filtrado
        .sort_values("hl_rechazados", ascending=False)
        .head(20)
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(pareto["cliente_nombre"], pareto["hl_rechazados"])
    ax.invert_yaxis()
    ax.set_xlabel("HL Rechazados")
    ax.set_ylabel("Cliente")
    st.pyplot(fig)

with g2:
    st.markdown("#### Motivos de Rechazo")
    motivos = (
        df_filtrado["motivo_rechazo_principal"]
        .value_counts()
        .head(10)
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(motivos.index, motivos.values)
    ax.invert_yaxis()
    ax.set_xlabel("Cantidad de clientes")
    ax.set_ylabel("Motivo")
    st.pyplot(fig)

g3, g4 = st.columns(2)

with g3:
    st.markdown("#### HL Rechazados por DPS")
    dps_hl = (
        df_filtrado
        .groupby("dps", as_index=False)["hl_rechazados"]
        .sum()
        .sort_values("hl_rechazados", ascending=False)
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(dps_hl["dps"], dps_hl["hl_rechazados"])
    ax.set_xlabel("DPS")
    ax.set_ylabel("HL Rechazados")
    st.pyplot(fig)

with g4:
    st.markdown("#### Frecuencia vs % Rechazo")
    fig, ax = plt.subplots(figsize=(10, 5))
    size = (df_filtrado["hl_rechazados"].clip(lower=0.1) * 30)
    ax.scatter(
        df_filtrado["frecuencia_semanal"],
        df_filtrado["rech_rate"],
        s=size,
        alpha=0.6
    )
    ax.set_xlabel("Frecuencia semanal")
    ax.set_ylabel("% Rechazo")
    st.pyplot(fig)

# =========================================================
# MAPA GENERAL
# =========================================================

st.subheader("🗺️ Ubicación de Clientes")

map_df = df_filtrado[
    (df_filtrado["x"] != 0) &
    (df_filtrado["y"] != 0)
][["y", "x", "cliente_nombre", "hl_rechazados", "score_oportunidad"]].copy()

map_df = map_df.rename(columns={"y": "lat", "x": "lon"})

if not map_df.empty:
    st.map(map_df, latitude="lat", longitude="lon")
else:
    st.info("No hay coordenadas válidas para mostrar en mapa.")

# =========================================================
# TABLA COMPLETA
# =========================================================

st.subheader("📋 Base Completa Filtrada")

tabla_cols = [
    "cliente",
    "cliente_nombre",
    "dps",
    "prioridad",
    "score_oportunidad",
    "tipo_gestion",
    "accion_recomendada",
    "entregas_totales",
    "entregas_rech",
    "entregas_sus",
    "entregas_ok",
    "rech_rate",
    "hl_comprados",
    "hl_rechazados",
    "hl_impacto",
    "frecuencia_semanal",
    "madurez_cliente",
    "motivo_rechazo_principal",
    "resumen_motivos_rechazo",
    "ventana_horaria_recepcion",
    "ventana_local_cerrado",
    "dia_entrega",
    "dias_flex",
    "x",
    "y"
]

tabla_cols = [c for c in tabla_cols if c in df_filtrado.columns]

st.dataframe(
    df_filtrado[tabla_cols].sort_values("score_oportunidad", ascending=False),
    use_container_width=True,
    height=520
)

csv = df_filtrado[tabla_cols].to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "📥 Descargar base filtrada CSV",
    csv,
    "clientes_oportunidad_operativa.csv",
    "text/csv"
)

# =========================================================
# FICHA CLIENTE
# =========================================================

st.subheader("🧾 Ficha Cliente")

clientes_disponibles = (
    df_filtrado
    .sort_values("score_oportunidad", ascending=False)["cliente_nombre"]
    .unique()
)

cliente_sel = st.selectbox(
    "Selecciona cliente",
    clientes_disponibles
)

c = df_filtrado[df_filtrado["cliente_nombre"] == cliente_sel].iloc[0]

f1, f2, f3, f4 = st.columns(4)
f1.metric("Prioridad", c["prioridad"])
f2.metric("Score", f"{c['score_oportunidad']:.2f}")
f3.metric("HL Rechazados", f"{c['hl_rechazados']:.2f}")
f4.metric("% Rechazo", f"{c['rech_rate']:.1%}")

st.markdown(f"""
### 📌 {c['cliente_nombre']}

**Cliente:** {c['cliente']}  
**DPS:** {c['dps']}  
**Madurez:** {c['madurez_cliente']}  
**Primera entrega:** {c['primera_fecha_entrega'].date() if pd.notnull(c['primera_fecha_entrega']) else 'SIN DATO'}

---

### 📦 Volumen

- **HL Comprados:** {c['hl_comprados']:.2f}
- **HL Rechazados:** {c['hl_rechazados']:.2f}
- **HL Entregados estimados:** {c['hl_entregados_estimados']:.2f}
- **Impacto HL:** {c['hl_impacto']:.1%}

---

### 🚚 Operación

- **Entregas Totales:** {int(c['entregas_totales'])}
- **Entregas OK:** {int(c['entregas_ok'])}
- **Entregas Rechazadas:** {int(c['entregas_rech'])}
- **Entregas Suspendidas:** {int(c['entregas_sus'])}
- **Frecuencia semanal:** {c['frecuencia_semanal']:.2f}
- **Semanas activas:** {c['semanas_activas']:.2f}
- **Días activos:** {int(c['dias_activos'])}

---

### 🚨 Rechazos

- **Motivo principal:** {c['motivo_rechazo_principal']}
- **Código motivo:** {c['codigo_motivo_principal']}
- **Resumen motivos:** {c['resumen_motivos_rechazo']}

---

### ⏰ Ventanas

- **Ventana horaria de recepción:** {c['ventana_horaria_recepcion']}
- **Ventana local cerrado:** {c['ventana_local_cerrado']}
- **Día entrega:** {c['dia_entrega']}
- **Días flex:** {c['dias_flex']}

---

### ✅ Acción Recomendada

{c['accion_recomendada']}
""")

if c["x"] != 0 and c["y"] != 0:
    cliente_map = pd.DataFrame({
        "lat": [c["y"]],
        "lon": [c["x"]]
    })
    st.map(cliente_map, latitude="lat", longitude="lon")

# =========================================================
# EXPORTAR FICHA HTML
# =========================================================

def generar_html_cliente(row):
    nombre = html.escape(str(row["cliente_nombre"]))
    accion = html.escape(str(row["accion_recomendada"]))
    motivo = html.escape(str(row["motivo_rechazo_principal"]))
    resumen = html.escape(str(row["resumen_motivos_rechazo"]))
    ventana_rec = html.escape(str(row["ventana_horaria_recepcion"]))
    ventana_cerrado = html.escape(str(row["ventana_local_cerrado"]))

    google_maps_url = (
        f"https://www.google.com/maps?q={row['y']},{row['x']}"
        if row["x"] != 0 and row["y"] != 0
        else "#"
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ficha Cliente - {nombre}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 30px;
                background: #f6f8fa;
                color: #222;
            }}
            .card {{
                background: white;
                padding: 22px;
                border-radius: 14px;
                margin-bottom: 18px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}
            h1, h2 {{
                margin-bottom: 8px;
            }}
            .kpi-container {{
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
            }}
            .kpi {{
                background: #f0f3f6;
                padding: 16px;
                border-radius: 12px;
                min-width: 180px;
            }}
            .kpi-title {{
                font-size: 13px;
                color: #666;
            }}
            .kpi-value {{
                font-size: 24px;
                font-weight: bold;
                margin-top: 6px;
            }}
            .action {{
                background: #fff4d6;
                padding: 18px;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            td {{
                padding: 9px;
                border-bottom: 1px solid #ddd;
            }}
            td:first-child {{
                font-weight: bold;
                width: 280px;
            }}
        </style>
    </head>
    <body>

        <div class="card">
            <h1>Ficha Cliente Operativa</h1>
            <h2>{nombre}</h2>
            <p><b>Cliente:</b> {row['cliente']} | <b>DPS:</b> {row['dps']} | <b>Prioridad:</b> {row['prioridad']}</p>
        </div>

        <div class="card">
            <h2>Resumen Ejecutivo</h2>
            <div class="kpi-container">
                <div class="kpi">
                    <div class="kpi-title">Score oportunidad</div>
                    <div class="kpi-value">{row['score_oportunidad']:.2f}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">HL rechazados</div>
                    <div class="kpi-value">{row['hl_rechazados']:.2f}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">% rechazo</div>
                    <div class="kpi-value">{row['rech_rate']:.1%}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">Frecuencia semanal</div>
                    <div class="kpi-value">{row['frecuencia_semanal']:.2f}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Acción Recomendada</h2>
            <div class="action">{accion}</div>
        </div>

        <div class="card">
            <h2>Información del Cliente</h2>
            <table>
                <tr><td>Cliente</td><td>{row['cliente']}</td></tr>
                <tr><td>Nombre</td><td>{nombre}</td></tr>
                <tr><td>DPS</td><td>{row['dps']}</td></tr>
                <tr><td>Madurez</td><td>{row['madurez_cliente']}</td></tr>
                <tr><td>Ubicación</td><td><a href="{google_maps_url}" target="_blank">Abrir en Google Maps</a></td></tr>
                <tr><td>Longitud</td><td>{row['x']}</td></tr>
                <tr><td>Latitud</td><td>{row['y']}</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>Operación</h2>
            <table>
                <tr><td>Entregas totales</td><td>{int(row['entregas_totales'])}</td></tr>
                <tr><td>Entregas OK</td><td>{int(row['entregas_ok'])}</td></tr>
                <tr><td>Entregas rechazadas</td><td>{int(row['entregas_rech'])}</td></tr>
                <tr><td>Entregas suspendidas</td><td>{int(row['entregas_sus'])}</td></tr>
                <tr><td>Entregas FLEX</td><td>{int(row['entregas_flex'])}</td></tr>
                <tr><td>Entregas FEE</td><td>{int(row['entregas_fee'])}</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>Volumen</h2>
            <table>
                <tr><td>HL comprados</td><td>{row['hl_comprados']:.2f}</td></tr>
                <tr><td>HL rechazados</td><td>{row['hl_rechazados']:.2f}</td></tr>
                <tr><td>HL entregados estimados</td><td>{row['hl_entregados_estimados']:.2f}</td></tr>
                <tr><td>Impacto HL</td><td>{row['hl_impacto']:.1%}</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>Rechazos y Ventanas</h2>
            <table>
                <tr><td>Motivo principal</td><td>{motivo}</td></tr>
                <tr><td>Resumen motivos</td><td>{resumen}</td></tr>
                <tr><td>Ventana recepción</td><td>{ventana_rec}</td></tr>
                <tr><td>Ventana local cerrado</td><td>{ventana_cerrado}</td></tr>
                <tr><td>Día entrega</td><td>{row['dia_entrega']}</td></tr>
                <tr><td>Días flex</td><td>{row['dias_flex']}</td></tr>
            </table>
        </div>

    </body>
    </html>
    """

html_cliente = generar_html_cliente(c)

st.download_button(
    "📄 Descargar ficha cliente HTML",
    html_cliente.encode("utf-8"),
    f"ficha_cliente_{c['cliente']}.html",
    "text/html"
)
