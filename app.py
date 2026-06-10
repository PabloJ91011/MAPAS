import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="OTIF Dashboard",
    layout="wide"
)

# =========================================================
# CARGA DESDE GITHUB
# =========================================================

@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/PabloJ91011/MAPAS/main/otif_h3.csv"
    r = requests.get(url)
    r.raise_for_status()

    df = pd.read_csv(StringIO(r.text))

    return df, datetime.now()

df, last_update = load_data()

# =========================================================
# BOTÓN DE ACTUALIZACIÓN
# =========================================================

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.rerun()

# =========================================================
# LIMPIEZA DPS
# =========================================================

df["dps"] = df["dps"].astype(str)

# =========================================================
# HEADER
# =========================================================

st.title("📊 OTIF Dashboard")

st.caption(
    f"🕒 Última actualización: {last_update.strftime('%Y-%m-%d %H:%M:%S')}"
)

# =========================================================
# FILTRO DPS
# =========================================================

st.sidebar.title("Filtros")

dps_list = sorted(
    df["dps"]
    .dropna()
    .unique()
)

selected_dps = st.sidebar.multiselect(
    "DPS",
    dps_list,
    default=dps_list
)

df = df[df["dps"].isin(selected_dps)]

# =========================================================
# KPIs
# =========================================================

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("Clientes", f"{df['cliente'].nunique():,}")
c2.metric("Pedidos", f"{df['entregas_totales'].sum():,.0f}")
c3.metric("OK", f"{df['entregas_ok'].sum():,.0f}")
c4.metric("RECH", f"{df['entregas_rech'].sum():,.0f}")
c5.metric("SUS", f"{df['entregas_sus'].sum():,.0f}")
c6.metric("FLEX", f"{df['entregas_flex'].sum():,.0f}")

# =========================================================
# DESCARGA BASE FILTRADA
# =========================================================

csv = df.to_csv(index=False)

st.download_button(
    "📥 Descargar Base Filtrada",
    csv,
    "OTIF_Filtrado.csv",
    "text/csv"
)

# =========================================================
# BUSQUEDA CLIENTE
# =========================================================

st.subheader("Buscar Cliente")

cliente = st.text_input("Nombre Cliente")

detalle = df.copy()

if cliente:
    detalle = detalle[
        detalle["cliente_nombre"]
        .astype(str)
        .str.contains(cliente, case=False, na=False)
    ]

# =========================================================
# TABLA
# =========================================================

st.subheader("Detalle")

st.dataframe(
    detalle,
    use_container_width=True,
    height=700
)

# =========================================================
# DESCARGA DETALLE
# =========================================================

csv_detalle = detalle.to_csv(index=False)

st.download_button(
    "📥 Descargar Vista Actual",
    csv_detalle,
    "Detalle_OTIF.csv",
    "text/csv"
)
