import streamlit as st
import pandas as pd
import requests
from io import StringIO
import matplotlib.pyplot as plt
import html
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import base64
from io import BytesIO
# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="PROYECTO FENIX",
    layout="wide"
)

CSV_URL = "https://raw.githubusercontent.com/PabloJ91011/MAPAS/main/otif_h3.csv"
GITHUB_API_COMMITS_URL = "https://api.github.com/repos/PabloJ91011/MAPAS/commits"
GITHUB_REPO = "PabloJ91011/MAPAS"
GITHUB_BRANCH = "main"
GESTION_FILES = {
    "dashboard": "gestion_top10_dashboard.csv",
    "llamadas": "gestion_top10_llamadas.csv",
    "buffer": "gestion_comunicar_buffer.csv"
}


def github_contents_url(file_path):
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
PEDIDOS_PROGRAMADOS_URL = "https://raw.githubusercontent.com/PabloJ91011/MAPAS/main/otif_h3_15-06-2026_15h22.csv.gz"
PEDIDOS_PROGRAMADOS_FILENAME = "otif_h3_15-06-2026_15h22.csv.gz"
# =========================================================
# CARGA DATOS
# =========================================================

@st.cache_data
def load_data():
    r = requests.get(CSV_URL)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))


@st.cache_data(ttl=600)
def get_last_update():
    try:
        params = {
            "path": "otif_h3.csv",
            "per_page": 1
        }

        headers = {
            "User-Agent": "streamlit-otif-dashboard"
        }

        r = requests.get(
            GITHUB_API_COMMITS_URL,
            params=params,
            headers=headers,
            timeout=10
        )

        r.raise_for_status()
        data = r.json()

        if not data:
            return "Sin dato"

        fecha_utc = data[0]["commit"]["committer"]["date"]

        dt_utc = datetime.fromisoformat(
            fecha_utc.replace("Z", "+00:00")
        )

        dt_local = dt_utc.astimezone(
            ZoneInfo("America/La_Paz")
        )

        return dt_local.strftime("%d/%m/%Y %H:%M:%S")

    except Exception:
        return "No disponible"
        
@st.cache_data(ttl=600)
def get_last_update_pedidos():
    try:
        params = {
            "path": PEDIDOS_PROGRAMADOS_FILENAME,
            "per_page": 1
        }

        headers = {
            "User-Agent": "streamlit-pedidos-dashboard"
        }

        r = requests.get(
            GITHUB_API_COMMITS_URL,
            params=params,
            headers=headers,
            timeout=10
        )

        r.raise_for_status()
        data = r.json()

        if not data:
            return "Sin dato"

        fecha_utc = data[0]["commit"]["committer"]["date"]

        dt_utc = datetime.fromisoformat(
            fecha_utc.replace("Z", "+00:00")
        )

        dt_local = dt_utc.astimezone(
            ZoneInfo("America/La_Paz")
        )

        return dt_local.strftime("%d/%m/%Y %H:%M:%S")

    except Exception:
        return "No disponible"

df = load_data()

# =========================================================
# LIMPIEZA GENERAL
# =========================================================

df.columns = df.columns.str.strip()

df["cliente"] = (
    pd.to_numeric(df["cliente"], errors="coerce")
    .fillna(0)
    .astype(int)
    .astype(str)
)

df["dps"] = (
    pd.to_numeric(df["dps"], errors="coerce")
    .fillna(0)
    .astype(int)
    .astype(str)
)

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
        df[col] = df[col].fillna("SIN DATO").astype(str).str.strip()

num_cols = [
    "entregas_totales",
    "entregas_rech",
    "entregas_sus",
    "entregas_ok",
    "entregas_flex",
    "entregas_fee",
    "rech_flex",
    "sus_flex",
    "ok_flex",
    "rech_fee",
    "sus_fee",
    "ok_fee",
    "dias_activos",
    "x",
    "y",
    "hl_comprados",
    "hl_rechazados",
    "semanas_activas",
    "frecuencia_semanal",
    "codigo_motivo_principal"
]

for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

df["entregas_totales"] = df["entregas_totales"].replace(0, 1)
df["hl_comprados"] = df["hl_comprados"].replace(0, 1)
df["frecuencia_semanal"] = df["frecuencia_semanal"].replace(0, 0.1)

df["primera_fecha_entrega"] = pd.to_datetime(
    df["primera_fecha_entrega"],
    errors="coerce",
    dayfirst=True
)

# =========================================================
# FEATURES BASE
# =========================================================

df["pct_rechazo"] = df["entregas_rech"] / df["entregas_totales"]
df["pct_suspension"] = df["entregas_sus"] / df["entregas_totales"]
df["pct_hl_rechazado"] = df["hl_rechazados"] / df["hl_comprados"]
df["hl_entregados_estimados"] = df["hl_comprados"] - df["hl_rechazados"]

# =========================================================
# MOTOR DE ACCIONES
# =========================================================

def accion_operativa(row):
    motivo = str(row["motivo_rechazo_principal"]).upper()
    ventana_ok = str(row["ventana_horaria_recepcion"])
    ventana_cerrado = str(row["ventana_local_cerrado"])

    if "LOCAL CERRADO" in motivo:
        return (
            f"Revisar ventanas de entrega. El cliente normalmente recibe en {ventana_ok}. "
            f"La ventana de rechazo por local cerrado es {ventana_cerrado}. "
            f"Contactar al cliente y ajustar la entrega a la ventana más efectiva."
        )

    elif "SIN DINERO" in motivo or "DINERO" in motivo:
        return (
            "Contactar al cliente antes del despacho para confirmar disponibilidad de pago. "
            "Si no podrá recibir, reprogramar antes de cargar la ruta."
        )

    elif "NO RECIBE" in motivo or "RECHAZA" in motivo:
        return (
            "Realizar llamada preventiva antes de programar la entrega. "
            "Validar responsable de recepción, horario disponible y voluntad de recibir."
        )

    elif "DIRECCION" in motivo or "DIRECCIÓN" in motivo or "NO UBICADO" in motivo:
        return (
            "Validar ubicación, referencias del domicilio y geolocalización. "
            "Actualizar datos antes de volver a programar la entrega."
        )

    elif "MAL PEDIDO" in motivo or "PEDIDO" in motivo:
        return (
            "Revisar consistencia del pedido con ventas. Confirmar cantidades, productos "
            "y necesidad real antes del despacho."
        )

    elif "STOCK" in motivo:
        return (
            "Validar disponibilidad y causa de stock. Coordinar con planificación para evitar "
            "rechazos o incumplimientos por faltantes."
        )

    elif row["entregas_rech"] >= 5 and row["hl_rechazados"] > 0:
        return (
            "Cliente con rechazos recurrentes. Coordinar gestión conjunta entre reparto, "
            "ventas y contacto preventivo."
        )

    else:
        return (
            "Revisar historial operativo del cliente, validar causa real del rechazo "
            "y definir acción con reparto/ventas."
        )


def tipo_gestion(row):
    motivo = str(row["motivo_rechazo_principal"]).upper()

    if "LOCAL CERRADO" in motivo:
        return "Ajuste de ventana"
    elif "DINERO" in motivo:
        return "Confirmación de pago"
    elif "NO RECIBE" in motivo or "RECHAZA" in motivo:
        return "Llamada preventiva"
    elif "DIRECCION" in motivo or "DIRECCIÓN" in motivo or "NO UBICADO" in motivo:
        return "Validación de ubicación"
    elif "PEDIDO" in motivo:
        return "Validación pedido"
    elif "STOCK" in motivo:
        return "Validación stock"
    else:
        return "Revisión operativa"


df["accion_recomendada"] = df.apply(accion_operativa, axis=1)
df["tipo_gestion"] = df.apply(tipo_gestion, axis=1)

# =========================================================
# SCORE DE CRITICIDAD REPRESENTATIVO
# =========================================================

def normalizar_serie(s):
    max_val = s.max()
    if pd.isna(max_val) or max_val <= 0:
        return s * 0
    return s / max_val


def calcular_score_criticidad(data):
    base = data.copy()

    total_rechazos_filtro = max(base["entregas_rech"].sum(), 1)
    total_hl_rech_filtro = max(base["hl_rechazados"].sum(), 0.01)
    total_entregas_filtro = max(base["entregas_totales"].sum(), 1)
    total_hl_comprados_filtro = max(base["hl_comprados"].sum(), 0.01)

    base["participacion_rechazos"] = (
        base["entregas_rech"] / total_rechazos_filtro
    )

    base["participacion_hl_rechazado"] = (
        base["hl_rechazados"] / total_hl_rech_filtro
    )

    base["participacion_entregas"] = (
        base["entregas_totales"] / total_entregas_filtro
    )

    base["participacion_hl_comprados"] = (
        base["hl_comprados"] / total_hl_comprados_filtro
    )

    base["pct_rechazo_representativo"] = (
        base["pct_rechazo"] *
        (base["participacion_entregas"] ** 0.5)
    )

    base["pct_hl_rechazado_representativo"] = (
        base["pct_hl_rechazado"] *
        (base["participacion_hl_comprados"] ** 0.5)
    )

    base["comp_cantidad_rechazos"] = normalizar_serie(
        base["participacion_rechazos"]
    )

    base["comp_hl_rechazado"] = normalizar_serie(
        base["participacion_hl_rechazado"]
    )

    base["comp_pct_rechazo"] = normalizar_serie(
        base["pct_rechazo_representativo"]
    )

    base["comp_pct_hl"] = normalizar_serie(
        base["pct_hl_rechazado_representativo"]
    )

    base["score_criticidad"] = 100 * (
        base["comp_cantidad_rechazos"] * 0.30 +
        base["comp_hl_rechazado"] * 0.35 +
        base["comp_pct_rechazo"] * 0.20 +
        base["comp_pct_hl"] * 0.15
    )

    return base


def clasificar_prioridad(score):
    if score >= 75:
        return "🔥 CRÍTICA"
    elif score >= 50:
        return "🟠 ALTA"
    elif score >= 25:
        return "🟡 MEDIA"
    else:
        return "🟢 BAJA"

# =========================================================
# NAVEGACIÓN
# =========================================================

if "vista_actual" not in st.session_state:
    st.session_state["vista_actual"] = "dashboard"

if st.session_state["vista_actual"] not in ["dashboard", "informacion", "pedidos_manana"]:
    st.session_state["vista_actual"] = "dashboard"


def ir_a_informacion():
    st.session_state["vista_actual"] = "informacion"


def ir_a_pedidos_manana():
    st.session_state["vista_actual"] = "pedidos_manana"


def volver_al_dashboard():
    st.session_state["vista_actual"] = "dashboard"

# =========================================================
# GLOSARIO COMPACTO
# =========================================================

def mostrar_glosario():
    col_titulo, col_boton = st.columns([5, 1])

    with col_titulo:
        st.title("📘 Glosario de Medidas")
        st.caption(
            "Información para entender cómo se calculan las métricas, prioridades y sugerencias del dashboard."
        )

    with col_boton:
        st.write("")
        st.button(
            "⬅️ Volver al dashboard",
            on_click=volver_al_dashboard,
            use_container_width=True
        )

    st.divider()

    with st.expander("📊 Métricas principales", expanded=True):
        st.markdown("""
        | Métrica | Qué significa | Regla |
        |---|---|---|
        | **Clientes compradores** | Clientes únicos dentro del filtro actual. | `cliente.nunique()` |
        | **Clientes rechazadores** | Clientes con al menos un rechazo. | `entregas_rech > 0` |
        | **Clientes suspendidos** | Clientes con al menos una suspensión. | `entregas_sus > 0` |
        | **Entregas totales** | Total de entregas del filtro. | `sum(entregas_totales)` |
        | **Rechazos** | Total de entregas rechazadas. | `sum(entregas_rech)` |
        | **Suspensiones** | Total de entregas suspendidas. | `sum(entregas_sus)` |
        | **Entregas OK** | Entregas completadas correctamente. | `sum(entregas_ok)` |
        | **HL comprados** | Volumen comprado por los clientes. | `sum(hl_comprados)` |
        | **HL rechazados** | Volumen perdido por rechazo. | `sum(hl_rechazados)` |
        """)

    with st.expander("📦 Frecuencia, madurez y ventanas", expanded=False):
        st.markdown("""
        | Medida | Cómo se calcula / interpreta |
        |---|---|
        | **% rechazo** | `entregas_rech / entregas_totales` |
        | **% suspensión** | `entregas_sus / entregas_totales` |
        | **% HL rechazado** | `hl_rechazados / hl_comprados` |
        | **Frecuencia semanal** | `entregas_totales / semanas_activas` |
        | **Madurez BAJA** | Cliente con menos de 4 semanas activas. |
        | **Madurez MEDIA** | Cliente con 4 a menos de 8 semanas activas. |
        | **Madurez ALTA** | Cliente con 8 semanas activas o más. |
        | **Ventana horaria de recepción** | Horario donde el cliente normalmente recibe mejor. |
        | **Ventana de rechazo por local cerrado** | Horario donde se concentran más rechazos con motivo `LOCAL CERRADO`. |
        """)

        st.info(
            "Ejemplo operativo: si la ventana de recepción es NOCHE, pero la ventana de rechazo por local cerrado es TARDE, "
            "la recomendación será validar si conviene mover la entrega hacia la noche."
        )
        
    with st.expander("📞 Probabilidad de rechazo para pedidos próximos", expanded=False):
        st.markdown("""
        La **probabilidad de rechazo** se usa en la ventana **Pedidos para llamar**.

        Esta medida responde:

        > Si este cliente tiene un pedido programado para mañana o para los próximos días, ¿qué tan probable es que lo rechace?

        ---

        ### Fórmula usada

        No usamos simplemente:

        ```python
        entregas_rech / entregas_totales
        ```

        porque eso puede generar falsos críticos.

        Por ejemplo, un cliente con 1 entrega y 1 rechazo tendría:

        ```text
        1 / 1 = 100%
        ```

        Pero ese 100% no es tan confiable porque solo tiene una entrega histórica.

        Por eso usamos una fórmula suavizada:

        ```python
        probabilidad_rechazo = (
        entregas_rech + tasa_global_rechazo * 5
        ) / (
            entregas_totales + 5
        )
        ```

        Donde:

        ```python
        tasa_global_rechazo = total_rechazos_hist / total_entregas_hist
        ```

        ---

        ### ¿Qué significa el `5`?

        El `5` funciona como una base mínima estadística.

        Es como decir:

        > Si el cliente tiene poco historial, no confío totalmente en su propio porcentaje.  
        > Entonces mezclo su comportamiento con el promedio general de rechazo.

        Esto evita que clientes con muy pocos pedidos aparezcan como 100% críticos.

        ---

        ### Ejemplo 1: cliente con poco historial

        Supongamos que la tasa global de rechazo es 10%.

        Cliente A:

        ```text
        Entregas totales = 1
        Entregas rechazadas = 1
        ```

        Fórmula simple:

        ```text
        1 / 1 = 100%
        ```

        Fórmula suavizada:

        ```text
        (1 + 10% * 5) / (1 + 5)
        = (1 + 0.5) / 6
        = 25%
        ```

        Resultado:

        ```text
        Probabilidad de rechazo = 25%
        ```

        ---

        ### Ejemplo 2: cliente con más historial
    
        Cliente B:
    
        ```text
        Entregas totales = 20
        Entregas rechazadas = 8
        ```
    
        Fórmula simple:
    
        ```text
        8 / 20 = 40%
        ```
    
        Fórmula suavizada:
    
        ```text
        (8 + 10% * 5) / (20 + 5)
        = (8 + 0.5) / 25
        = 34%
        ```
    
        Resultado:
    
        ```text
        Probabilidad de rechazo = 34%
        ```
    
        Sigue siendo alto, pero más estable.
    
        ---
    
        ### Diferencia con el score de criticidad
    
        La **probabilidad de rechazo** mide:
    
        ```text
        Qué tan probable es que el cliente rechace.
        ```
    
        El **score de llamada preventiva** mide:
    
        ```text
        A quién conviene llamar primero.
        ```
    
        Por eso el score preventivo combina:
    
        | Componente | Peso |
        |---|---:|
        | Probabilidad histórica de rechazo | 50% |
        | Score de criticidad histórico | 25% |
        | Impacto del HL programado para la fecha | 15% |
        | % HL rechazado histórico | 10% |
    
        Fórmula:
    
        ```python
        score_llamada_preventiva = 100 * (
            probabilidad_rechazo * 0.50 +
            score_criticidad / 100 * 0.25 +
            impacto_hl_programado * 0.15 +
            pct_hl_rechazado * 0.10
        )
        ```
    
        En simple:
    
        > La probabilidad dice si puede rechazar.  
        > El score dice si además vale la pena llamarlo primero por impacto operativo.

        ---

### Prioridad llamada

La prioridad llamada se asigna con base en el `score_llamada_preventiva`.

| Score llamada | Prioridad |
|---:|---|
| `>= 70` | 🚨 LLAMAR URGENTE |
| `>= 50 y < 70` | 🟠 RIESGO ALTO |
| `>= 30 y < 50` | 🟡 MONITOREAR |
| `< 30` | 🟢 BAJO |

---

### Cómo interpretar cada campo

| Campo | Qué significa |
|---|---|
| **Prob. rechazo** | Probabilidad suavizada de que el cliente rechace, usando su historial y la tasa global. |
| **Score llamada** | Ranking preventivo que combina probabilidad, criticidad histórica, HL programados e impacto en volumen. |
| **Prioridad llamada** | Clasificación operativa para decidir a quién llamar primero. |
| **HL programados** | Volumen que está en riesgo para la fecha seleccionada. |
| **HL rechazados hist.** | Volumen que el cliente rechazó históricamente. |

---

### Gestión persistente

Cada pestaña guarda su propio historial en GitHub:

| Pestaña | Archivo |
|---|---|
| **Top 10 Dashboard** | `gestion_top10_dashboard.csv` |
| **Top llamadas preventivas** | `gestion_top10_llamadas.csv` |
| **Comunicar buffer** | `gestion_comunicar_buffer.csv` |

La lógica usa siempre el último registro del cliente:

| Último estado | Botón Atendido | Botón Re comunicación |
|---|---|---|
| Sin gestión | Habilitado | Bloqueado |
| ATENDIDO | Bloqueado | Habilitado |
| RECOMUNICACION | Habilitado | Bloqueado |
        """)

    with st.expander("🧮 16. Score de criticidad: cómo se arma exactamente", expanded=True):
        st.markdown("""
        El **score de criticidad** es el puntaje que usa el dashboard para ordenar a los clientes más importantes a revisar.

        La idea principal es que el ranking no dependa solo de un porcentaje.  
        Por ejemplo, un cliente con **1 entrega y 1 rechazo** tiene **100% de rechazo**, pero puede no ser tan importante si representa poco volumen y poca cantidad de rechazos dentro del universo filtrado.

        Por eso el score mezcla cuatro dimensiones:

        1. **Cantidad de rechazos**  
           Da peso a clientes que rechazan muchas veces.

        2. **HL rechazados**  
           Da peso a clientes donde se pierde más volumen.

        3. **% rechazo representativo**  
           Mide qué tan grave es el rechazo dentro de las entregas del cliente, pero ajustado por el tamaño del cliente dentro del filtro.

        4. **% HL rechazado representativo**  
           Mide qué tan grave es el rechazo dentro del volumen comprado por el cliente, también ajustado por su peso en el filtro.

        ---

        ### Paso 1: se toma el universo filtrado

        El score se recalcula cada vez que usas filtros.

        Si filtras por DPS 7, el score se calcula solo con los clientes del DPS 7.  
        Si filtras por motivo `LOCAL CERRADO`, el score se calcula solo contra clientes con ese motivo.  
        Si no filtras nada, se calcula contra toda la base.

        El primer paso es calcular los totales del filtro actual:

        ```python
        total_rechazos_filtro = sum(entregas_rech)
        total_hl_rech_filtro = sum(hl_rechazados)
        total_entregas_filtro = sum(entregas_totales)
        total_hl_comprados_filtro = sum(hl_comprados)
        ```

        Estos totales funcionan como la base de comparación.

        ---

        ### Paso 2: se calcula la participación de cada cliente

        Para cada cliente, se calcula cuánto representa dentro del filtro.

        #### Participación en rechazos

        ```python
        participacion_rechazos =
            entregas_rech_cliente / total_rechazos_filtro
        ```

        Esto responde:

        > De todos los rechazos del filtro, ¿qué porcentaje viene de este cliente?

        Ejemplo:  
        Si en el filtro hay 100 rechazos y el cliente tiene 10 rechazos:

        ```text
        participacion_rechazos = 10 / 100 = 10%
        ```

        #### Participación en HL rechazado

        ```python
        participacion_hl_rechazado =
            hl_rechazados_cliente / total_hl_rech_filtro
        ```

        Esto responde:

        > De todo el HL rechazado del filtro, ¿qué porcentaje viene de este cliente?

        Ejemplo:  
        Si en el filtro hay 500 HL rechazados y el cliente tiene 50 HL rechazados:

        ```text
        participacion_hl_rechazado = 50 / 500 = 10%
        ```

        #### Participación en entregas

        ```python
        participacion_entregas =
            entregas_totales_cliente / total_entregas_filtro
        ```

        Esto mide qué tan representativo es el cliente en cantidad de entregas.

        #### Participación en HL comprado

        ```python
        participacion_hl_comprados =
            hl_comprados_cliente / total_hl_comprados_filtro
        ```

        Esto mide qué tan representativo es el cliente en volumen comprado.

        ---

        ### Paso 3: se calculan los porcentajes propios del cliente

        #### % rechazo

        ```python
        pct_rechazo =
            entregas_rech_cliente / entregas_totales_cliente
        ```

        Esto mide qué tan problemático es el cliente en cantidad de entregas.

        Ejemplo:  
        Si tuvo 20 entregas y 5 rechazos:

        ```text
        pct_rechazo = 5 / 20 = 25%
        ```

        #### % HL rechazado

        ```python
        pct_hl_rechazado =
            hl_rechazados_cliente / hl_comprados_cliente
        ```

        Esto mide qué tan problemático es el cliente en volumen.

        Ejemplo:  
        Si compró 100 HL y rechazó 15 HL:

        ```text
        pct_hl_rechazado = 15 / 100 = 15%
        ```

        ---

        ### Paso 4: se ajustan los porcentajes para evitar falsos críticos

        Este es el punto más importante.

        Un cliente puede tener 100% de rechazo porque tuvo 1 entrega y rechazó 1.  
        Pero si ese cliente casi no pesa en el total del filtro, no debería ganarle a un cliente que rechaza muchas veces o pierde mucho volumen.

        Por eso el dashboard ajusta los porcentajes con representatividad.

        #### % rechazo representativo

        ```python
        pct_rechazo_representativo =
            pct_rechazo * sqrt(participacion_entregas)
        ```

        En el código esto está escrito así:

        ```python
        pct_rechazo_representativo =
            pct_rechazo * (participacion_entregas ** 0.5)
        ```

        #### % HL rechazado representativo

        ```python
        pct_hl_rechazado_representativo =
            pct_hl_rechazado * sqrt(participacion_hl_comprados)
        ```

        En el código:

        ```python
        pct_hl_rechazado_representativo =
            pct_hl_rechazado * (participacion_hl_comprados ** 0.5)
        ```

        #### ¿Por qué se usa raíz cuadrada?

        La raíz cuadrada suaviza el efecto del tamaño.

        Si usáramos la participación directa, castigaríamos demasiado a clientes medianos.  
        Si no usáramos participación, clientes muy pequeños podrían subir demasiado solo por tener porcentajes altos.

        La raíz cuadrada queda en un punto medio:

        - Baja el impacto de clientes muy pequeños.
        - Mantiene visibles a clientes medianos.
        - Da más peso a clientes realmente representativos.

        Ejemplo simplificado:

        Cliente pequeño:

        ```text
        pct_rechazo = 100%
        participacion_entregas = 0.1%
        sqrt(0.1%) = 3.16%

        pct_rechazo_representativo = 100% * 3.16% = 3.16%
        ```

        Cliente más representativo:

        ```text
        pct_rechazo = 30%
        participacion_entregas = 10%
        sqrt(10%) = 31.62%

        pct_rechazo_representativo = 30% * 31.62% = 9.49%
        ```

        Aunque el primer cliente tiene 100% de rechazo, el segundo queda más arriba porque representa mucho más dentro de la operación.

        ---

        ### Paso 5: se normaliza cada componente

        Después de calcular las variables, cada componente se normaliza contra el cliente más alto del filtro.

        Esto lleva cada componente a una escala de 0 a 1.

        #### Componente cantidad de rechazos

        ```python
        comp_cantidad_rechazos =
            participacion_rechazos / max(participacion_rechazos)
        ```

        #### Componente HL rechazado

        ```python
        comp_hl_rechazado =
            participacion_hl_rechazado / max(participacion_hl_rechazado)
        ```

        #### Componente % rechazo representativo

        ```python
        comp_pct_rechazo =
            pct_rechazo_representativo / max(pct_rechazo_representativo)
        ```

        #### Componente % HL representativo

        ```python
        comp_pct_hl =
            pct_hl_rechazado_representativo / max(pct_hl_rechazado_representativo)
        ```

        Ejemplo:

        Si el cliente con más HL rechazado tiene 50 HL y otro cliente tiene 25 HL:

        ```text
        comp_hl_rechazado = 25 / 50 = 0.50
        ```

        Eso significa que ese cliente tiene el 50% del peso del mayor cliente en ese componente.

        ---

        ### Paso 6: se aplica la fórmula final

        El score final combina los cuatro componentes con pesos.

        ```python
        score_criticidad = 100 * (
            comp_cantidad_rechazos * 0.30 +
            comp_hl_rechazado * 0.35 +
            comp_pct_rechazo * 0.20 +
            comp_pct_hl * 0.15
        )
        ```

        Los pesos suman 100%:

        ```text
        30% + 35% + 20% + 15% = 100%
        ```

        ---

        ### Paso 7: interpretación de los pesos

        | Componente | Peso | Qué prioriza |
        |---|---:|---|
        | `comp_hl_rechazado` | **35%** | Clientes donde se pierde más volumen. |
        | `comp_cantidad_rechazos` | **30%** | Clientes con más recurrencia de rechazo. |
        | `comp_pct_rechazo` | **20%** | Clientes con mala tasa de rechazo, ajustada por representatividad. |
        | `comp_pct_hl` | **15%** | Clientes con alto impacto en volumen rechazado, ajustado por representatividad. |

        El mayor peso está en **HL rechazados** porque el objetivo es recuperar volumen.  
        El segundo peso está en **cantidad de rechazos** porque también importa reducir recurrencia operativa.

        ---

        ### Paso 8: prioridad final

        Después de calcular el score, se clasifica así:

        | Score | Prioridad |
        |---:|---|
        | `>= 75` | 🔥 CRÍTICA |
        | `>= 50 y < 75` | 🟠 ALTA |
        | `>= 25 y < 50` | 🟡 MEDIA |
        | `< 25` | 🟢 BAJA |

        ---

        ### Ejemplo práctico completo

        Imagina que dentro de un filtro de DPS hay:

        ```text
        Total rechazos filtro = 100
        Total HL rechazados filtro = 500
        Total entregas filtro = 1,000
        Total HL comprados filtro = 5,000
        ```

        Cliente A:

        ```text
        Entregas totales = 40
        Entregas rechazadas = 8
        HL comprados = 200
        HL rechazados = 40
        ```

        Cálculos:

        ```text
        participacion_rechazos = 8 / 100 = 8%
        participacion_hl_rechazado = 40 / 500 = 8%
        participacion_entregas = 40 / 1000 = 4%
        participacion_hl_comprados = 200 / 5000 = 4%

        pct_rechazo = 8 / 40 = 20%
        pct_hl_rechazado = 40 / 200 = 20%

        pct_rechazo_representativo = 20% * sqrt(4%) = 20% * 20% = 4%
        pct_hl_rechazado_representativo = 20% * sqrt(4%) = 4%
        ```

        Luego esos valores se comparan contra los máximos del filtro y entran a la fórmula final.

        ---

        ### Resumen simple

        El score sube cuando un cliente:

        - Rechaza muchas veces.
        - Tiene mucho HL rechazado.
        - Tiene alto % de rechazo.
        - Tiene alto % de HL rechazado.
        - Además representa una parte importante del filtro actual.

        El score baja cuando:

        - El cliente tiene pocos eventos.
        - Tiene poco volumen.
        - Su porcentaje es alto pero no representa mucho dentro de la operación.
        """)

    with st.expander("✅ Sugerencias operativas", expanded=False):
        st.markdown("""
        | Motivo principal | Sugerencia generada |
        |---|---|
        | **LOCAL CERRADO** | Revisar ventanas, contactar cliente y ajustar horario. |
        | **SIN DINERO** | Contactar antes del despacho para confirmar disponibilidad de pago. |
        | **NO RECIBE / RECHAZA** | Llamada preventiva antes de programar entrega. |
        | **DIRECCIÓN / NO UBICADO** | Validar ubicación, referencias y geolocalización. |
        | **MAL PEDIDO** | Revisar pedido con ventas antes del despacho. |
        | **STOCK** | Validar disponibilidad y causa del faltante. |
        | **Otros motivos** | Revisar historial operativo y definir acción con reparto/ventas. |
        """)

    with st.expander("🔁 Top 10 y avance operativo", expanded=False):
        st.markdown("""
        El dashboard muestra los **10 clientes más críticos** según el score.

        Si el equipo ya gestionó esos 10 clientes, puede marcar:

        **✅ Ya atendí estos 10 clientes, mostrar los siguientes 10**

        Luego puede avanzar en bloques:

        - Clientes 1 al 10.
        - Clientes 11 al 20.
        - Clientes 21 al 30.
        - Clientes 31 al 40.
        """)

# =========================================================
# HTML EXPORT
# =========================================================

def generar_html_fichas(clientes_df):
    bloques = []

    for _, row in clientes_df.iterrows():
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

        primera_fecha = (
            row["primera_fecha_entrega"].date()
            if pd.notnull(row["primera_fecha_entrega"])
            else "SIN DATO"
        )

        bloque = f"""
        <div class="card">
            <h1>{row['cliente']} - {nombre}</h1>
            <p>
                <b>DPS:</b> {row['dps']} |
                <b>Prioridad:</b> {row['prioridad']} |
                <b>Score:</b> {row['score_criticidad']:.1f}
            </p>

            <div class="kpi-container">
                <div class="kpi">
                    <div class="kpi-title">HL comprados</div>
                    <div class="kpi-value">{row['hl_comprados']:.2f}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">HL rechazados</div>
                    <div class="kpi-value">{row['hl_rechazados']:.2f}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">% rechazo</div>
                    <div class="kpi-value">{row['pct_rechazo']:.1%}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">% HL rechazado</div>
                    <div class="kpi-value">{row['pct_hl_rechazado']:.1%}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-title">Frecuencia semanal</div>
                    <div class="kpi-value">{row['frecuencia_semanal']:.2f}</div>
                </div>
            </div>

            <h2>Acción Recomendada</h2>
            <div class="action">{accion}</div>

            <h2>Información General</h2>
            <table>
                <tr><td>Código cliente</td><td>{row['cliente']}</td></tr>
                <tr><td>Nombre cliente</td><td>{nombre}</td></tr>
                <tr><td>DPS</td><td>{row['dps']}</td></tr>
                <tr><td>Madurez</td><td>{row['madurez_cliente']}</td></tr>
                <tr><td>Primera fecha entrega</td><td>{primera_fecha}</td></tr>
                <tr><td>Ubicación</td><td><a href="{google_maps_url}" target="_blank">Abrir en Google Maps</a></td></tr>
                <tr><td>Longitud</td><td>{row['x']}</td></tr>
                <tr><td>Latitud</td><td>{row['y']}</td></tr>
            </table>

            <h2>Operación</h2>
            <table>
                <tr><td>Entregas totales</td><td>{int(row['entregas_totales'])}</td></tr>
                <tr><td>Entregas rechazadas</td><td>{int(row['entregas_rech'])}</td></tr>
                <tr><td>Entregas suspendidas</td><td>{int(row['entregas_sus'])}</td></tr>
                <tr><td>Entregas OK</td><td>{int(row['entregas_ok'])}</td></tr>
                <tr><td>Entregas FLEX</td><td>{int(row['entregas_flex'])}</td></tr>
                <tr><td>Entregas FEE</td><td>{int(row['entregas_fee'])}</td></tr>
                <tr><td>Días activos</td><td>{int(row['dias_activos'])}</td></tr>
                <tr><td>Semanas activas</td><td>{row['semanas_activas']:.2f}</td></tr>
                <tr><td>Frecuencia semanal</td><td>{row['frecuencia_semanal']:.2f}</td></tr>
            </table>

            <h2>Volumen</h2>
            <table>
                <tr><td>HL comprados</td><td>{row['hl_comprados']:.2f}</td></tr>
                <tr><td>HL rechazados</td><td>{row['hl_rechazados']:.2f}</td></tr>
                <tr><td>HL entregados estimados</td><td>{row['hl_entregados_estimados']:.2f}</td></tr>
                <tr><td>% HL rechazado</td><td>{row['pct_hl_rechazado']:.1%}</td></tr>
            </table>

            <h2>Rechazos y Ventanas</h2>
            <table>
                <tr><td>Motivo principal</td><td>{motivo}</td></tr>
                <tr><td>Código motivo</td><td>{row['codigo_motivo_principal']}</td></tr>
                <tr><td>Resumen motivos</td><td>{resumen}</td></tr>
                <tr><td>Ventana horaria recepción</td><td>{ventana_rec}</td></tr>
                <tr><td>Ventana de rechazo por local cerrado</td><td>{ventana_cerrado}</td></tr>
                <tr><td>Día entrega</td><td>{row['dia_entrega']}</td></tr>
                <tr><td>Días flex</td><td>{row['dias_flex']}</td></tr>
            </table>
        </div>
        """

        bloques.append(bloque)

    contenido = "\n".join(bloques)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Fichas Clientes Operativos</title>
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
                margin-bottom: 22px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}
            .kpi-container {{
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin: 16px 0;
            }}
            .kpi {{
                background: #f0f3f6;
                padding: 16px;
                border-radius: 12px;
                min-width: 170px;
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
                font-size: 16px;
                font-weight: bold;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 20px;
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
        <h1>Fichas Operativas de Clientes</h1>
        {contenido}
    </body>
    </html>
    """

# =========================================================
# MAPA BLANCO
# =========================================================

def mostrar_mapa_clientes(data, titulo):
    st.markdown(f"#### {titulo}")

    mapa = data[
        (data["x"] != 0) &
        (data["y"] != 0)
    ].copy()

    if mapa.empty:
        st.info("No hay coordenadas válidas para mostrar.")
        return

    mapa["lat"] = mapa["y"]
    mapa["lon"] = mapa["x"]
    mapa["label"] = mapa["cliente"] + " - " + mapa["cliente_nombre"]

    try:
        import pydeck as pdk

        layer_puntos = pdk.Layer(
            "ScatterplotLayer",
            data=mapa,
            get_position="[lon, lat]",
            get_radius=75,
            get_fill_color=[220, 30, 30, 190],
            get_line_color=[0, 0, 0, 255],
            line_width_min_pixels=1,
            pickable=True,
            opacity=0.85,
        )

        layer_texto = pdk.Layer(
            "TextLayer",
            data=mapa,
            get_position="[lon, lat]",
            get_text="cliente",
            get_size=14,
            get_color=[0, 0, 0, 255],
            get_text_anchor="'middle'",
            get_alignment_baseline="'bottom'",
        )

        zoom_mapa = 13 if len(mapa) <= 3 else 11

        view_state = pdk.ViewState(
            latitude=mapa["lat"].mean(),
            longitude=mapa["lon"].mean(),
            zoom=zoom_mapa,
            pitch=0,
        )

        deck = pdk.Deck(
            layers=[layer_puntos, layer_texto],
            initial_view_state=view_state,
            map_style=None,
            tooltip={
                "html": """
                <b>Cliente:</b> {cliente}<br/>
                <b>Nombre:</b> {cliente_nombre}<br/>
                <b>DPS:</b> {dps}<br/>
                <b>HL Rechazados:</b> {hl_rechazados}<br/>
                <b>Rechazos:</b> {entregas_rech}<br/>
                <b>Score:</b> {score_criticidad}
                """,
                "style": {
                    "backgroundColor": "white",
                    "color": "black"
                }
            }
        )

        st.pydeck_chart(deck, use_container_width=True)

    except Exception:
        st.warning("No se pudo cargar PyDeck. Mostrando mapa simple.")
        st.map(
            mapa.rename(columns={"lat": "latitude", "lon": "longitude"}),
            latitude="latitude",
            longitude="longitude"
        )

    st.dataframe(
        mapa[
            [
                "cliente",
                "cliente_nombre",
                "dps",
                "hl_rechazados",
                "entregas_rech",
                "score_criticidad",
                "accion_recomendada"
            ]
        ],
        use_container_width=True,
        column_config={
            "hl_rechazados": st.column_config.NumberColumn(
                "HL rechazados",
                format="%.2f"
            ),
            "score_criticidad": st.column_config.NumberColumn(
                "Score",
                format="%.1f"
            ),
        }
    )

# =========================================================
# GESTIÓN PERSISTENTE EN GITHUB
# =========================================================

COLUMNAS_GESTION = [
    "fecha_click",
    "cliente",
    "cliente_nombre",
    "dps",
    "usuario",
    "accion",
    "origen",
    "fecha_referencia"
]


def normalizar_cliente_dps_para_match(data, file_key=None):
    base = data.copy()

    base["cliente"] = (
        pd.to_numeric(base["cliente"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    base["dps"] = (
        pd.to_numeric(base["dps"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    if "fecha_referencia" not in base.columns:
        base["fecha_referencia"] = ""

    base["fecha_referencia"] = (
        base["fecha_referencia"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Solo en Pedidos para llamar usamos la fecha como parte de la clave.
    if file_key == "llamadas":
        base["clave_gestion"] = (
            base["cliente"] + "|" +
            base["dps"] + "|" +
            base["fecha_referencia"]
        )
    else:
        base["clave_gestion"] = base["cliente"] + "|" + base["dps"]

    return base


def leer_csv_gestion_github(file_key):
    token = st.secrets.get("GITHUB_TOKEN", None)

    if not token:
        st.error("No existe GITHUB_TOKEN en Streamlit Secrets.")
        st.stop()

    file_path = GESTION_FILES[file_key]
    url = github_contents_url(file_path)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "streamlit-proyecto-fenix"
    }

    params = {"ref": GITHUB_BRANCH}

    r = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20
    )

    if r.status_code == 404:
        return pd.DataFrame(columns=COLUMNAS_GESTION), None

    r.raise_for_status()

    data = r.json()
    sha = data["sha"]

    contenido_bytes = base64.b64decode(data["content"])

    df_existente = pd.read_csv(
        BytesIO(contenido_bytes),
        encoding="utf-8-sig"
    )

    for col in COLUMNAS_GESTION:
        if col not in df_existente.columns:
            df_existente[col] = ""

    return df_existente[COLUMNAS_GESTION].copy(), sha


def guardar_csv_gestion_github(df_nuevo, file_key):
    token = st.secrets.get("GITHUB_TOKEN", None)

    if not token:
        st.error("No existe GITHUB_TOKEN en Streamlit Secrets.")
        st.stop()

    file_path = GESTION_FILES[file_key]
    url = github_contents_url(file_path)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "streamlit-proyecto-fenix"
    }

    for col in COLUMNAS_GESTION:
        if col not in df_nuevo.columns:
            df_nuevo[col] = ""

    df_nuevo = df_nuevo[COLUMNAS_GESTION].copy()

    # Reintento simple por si dos personas guardan casi al mismo tiempo
    for intento in range(2):
        df_existente, sha = leer_csv_gestion_github(file_key)

        df_final = pd.concat(
            [df_existente, df_nuevo],
            ignore_index=True
        )

        # No eliminamos duplicados: queremos historial completo
        csv_texto = df_final.to_csv(index=False, encoding="utf-8-sig")

        csv_base64 = base64.b64encode(
            csv_texto.encode("utf-8-sig")
        ).decode("utf-8")

        payload = {
            "message": f"Actualizar gestión {file_path} desde Streamlit",
            "content": csv_base64,
            "branch": GITHUB_BRANCH
        }

        if sha:
            payload["sha"] = sha

        r = requests.put(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        if r.status_code in [200, 201]:
            return True

        # 409 = conflicto por SHA si alguien guardó al mismo tiempo
        if r.status_code == 409 and intento == 0:
            continue

        st.error("No se pudo actualizar el archivo de gestión.")
        st.write(r.status_code)
        st.write(r.text)
        st.stop()

    return False


def obtener_estado_gestion(file_key):
    df_gestion, _ = leer_csv_gestion_github(file_key)

    if df_gestion.empty:
        return pd.DataFrame(
            columns=[
                "clave_gestion",
                "ultima_accion",
                "ultima_fecha_click",
                "ultimo_usuario",
                "cantidad_clicks"
            ]
        )

    df_gestion = normalizar_cliente_dps_para_match(df_gestion, file_key=file_key)

    df_gestion["fecha_click_dt"] = pd.to_datetime(
        df_gestion["fecha_click"],
        errors="coerce"
    )

    df_gestion["accion"] = (
        df_gestion["accion"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df_gestion = df_gestion.sort_values(
        ["clave_gestion", "fecha_click_dt"]
    )

    ultimos = (
        df_gestion
        .groupby("clave_gestion", as_index=False)
        .tail(1)
        .copy()
    )

    df_gestion_atendidos = df_gestion[
        df_gestion["accion"].eq("ATENDIDO")
    ].copy()
    
    if df_gestion_atendidos.empty:
        conteos = pd.DataFrame(
            columns=[
                "clave_gestion",
                "cantidad_clicks"
            ]
        )
    else:
        conteos = (
            df_gestion_atendidos
            .groupby("clave_gestion", as_index=False)
            .size()
            .rename(columns={"size": "cantidad_clicks"})
        )

    estado = ultimos[
        [
            "clave_gestion",
            "accion",
            "fecha_click",
            "usuario"
        ]
    ].rename(
        columns={
            "accion": "ultima_accion",
            "fecha_click": "ultima_fecha_click",
            "usuario": "ultimo_usuario"
        }
    )

    estado = estado.merge(
        conteos,
        on="clave_gestion",
        how="left"
    )

    return estado


def anexar_estado_gestion(data, file_key, fecha_referencia=""):
    base = data.copy()

    if file_key == "llamadas":
        base["fecha_referencia"] = str(fecha_referencia)
    else:
        base["fecha_referencia"] = ""

    base = normalizar_cliente_dps_para_match(base, file_key=file_key)

    estado = obtener_estado_gestion(file_key)

    base = base.merge(
        estado,
        on="clave_gestion",
        how="left"
    )

    base["ultima_accion"] = base["ultima_accion"].fillna("SIN GESTIÓN")
    base["ultima_fecha_click"] = base["ultima_fecha_click"].fillna("SIN DATO")
    base["ultimo_usuario"] = base["ultimo_usuario"].fillna("SIN DATO")

    base["cantidad_clicks"] = (
        pd.to_numeric(base["cantidad_clicks"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    base["estado_gestion"] = np.select(
        [
            base["ultima_accion"].eq("ATENDIDO"),
            base["ultima_accion"].eq("RECOMUNICACION")
        ],
        [
            "Ya atendido ✅",
            "Re comunicación 🔁"
        ],
        default="Pendiente"
    )

    return base


def registrar_accion_gestion(row, file_key, origen, accion, fecha_referencia=""):
    usuario = st.session_state.get("usuario_gestion", "")
    usuario = str(usuario).strip()

    if usuario == "":
        usuario = "SIN_USUARIO"

    fecha_click = datetime.now(
        ZoneInfo("America/La_Paz")
    ).strftime("%Y-%m-%d %H:%M:%S")

    df_nuevo = pd.DataFrame(
        [
            {
                "fecha_click": fecha_click,
                "cliente": row["cliente"],
                "cliente_nombre": row["cliente_nombre"],
                "dps": row["dps"],
                "usuario": usuario,
                "accion": accion,
                "origen": origen,
                "fecha_referencia": str(fecha_referencia)
            }
        ]
    )

    guardar_csv_gestion_github(df_nuevo, file_key)

def obtener_detalle_skus_cliente(detalle_pedidos, cliente, dps):
    if detalle_pedidos is None or detalle_pedidos.empty:
        return pd.DataFrame()

    detalle = detalle_pedidos.copy()

    detalle["cliente"] = (
        pd.to_numeric(detalle["cliente"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    detalle["dps"] = (
        pd.to_numeric(detalle["dps"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    cliente = str(int(float(cliente))) if str(cliente).replace(".", "", 1).isdigit() else str(cliente)
    dps = str(int(float(dps))) if str(dps).replace(".", "", 1).isdigit() else str(dps)

    detalle = detalle[
        (detalle["cliente"].eq(cliente)) &
        (detalle["dps"].eq(dps))
    ].copy()

    if detalle.empty:
        return pd.DataFrame()

    for col in ["producto", "producto_nombre", "nro"]:
        if col not in detalle.columns:
            detalle[col] = "SIN DATO"

    for col in ["bultos", "hl"]:
        if col not in detalle.columns:
            detalle[col] = 0

        detalle[col] = pd.to_numeric(
            detalle[col],
            errors="coerce"
        ).fillna(0)

    detalle_sku = (
        detalle
        .groupby(
            [
                "producto",
                "producto_nombre"
            ],
            as_index=False
        )
        .agg(
            pedidos=("nro", lambda x: ", ".join(sorted(x.astype(str).unique()))),
            cantidad_bultos=("bultos", "sum"),
            hl=("hl", "sum")
        )
        .sort_values("hl", ascending=False)
    )

    detalle_sku = detalle_sku.rename(
        columns={
            "producto": "Código SKU",
            "producto_nombre": "Nombre SKU",
            "pedidos": "Pedidos",
            "cantidad_bultos": "Cantidad/Bultos",
            "hl": "HL"
        }
    )

    return detalle_sku
    
def mostrar_tabla_gestion(
    data,
    origen,
    file_key,
    key_base,
    column_config_extra=None,
    height=360,
    fecha_referencia="",
    detalle_pedidos=None
):
    tabla = anexar_estado_gestion(
        data,
        file_key,
        fecha_referencia=fecha_referencia
    )

    columnas_prioridad = [
        "estado_gestion",
        "ultima_accion",
        "ultima_fecha_click",
        "ultimo_usuario",
        "cantidad_clicks"
    ]

    columnas_ordenadas = columnas_prioridad + [
        c for c in tabla.columns
        if c not in columnas_prioridad + ["clave_gestion"]
    ]

    tabla = tabla[columnas_ordenadas].copy()

    column_config_base = {
        "estado_gestion": st.column_config.TextColumn("Estado gestión"),
        "ultima_accion": st.column_config.TextColumn("Última acción"),
        "ultima_fecha_click": st.column_config.TextColumn("Última fecha click"),
        "ultimo_usuario": st.column_config.TextColumn("Último usuario"),
        "cantidad_clicks": st.column_config.NumberColumn(
            "Cantidad atendidos",
            format="%d"
        )
    }

    if column_config_extra:
        column_config_base.update(column_config_extra)

    st.dataframe(
        tabla.drop(columns=["clave_gestion"], errors="ignore"),
        use_container_width=True,
        height=height,
        hide_index=True,
        column_config=column_config_base
    )

    st.markdown("#### ✅ Gestión de clientes")

    for i, row in tabla.iterrows():
        ultimo_estado = str(row["ultima_accion"]).upper().strip()

        atendido_bloqueado = ultimo_estado == "ATENDIDO"
        recomunicacion_bloqueada = ultimo_estado != "ATENDIDO"

        with st.container(border=True):
            c_info, c_atendido, c_recom = st.columns([4, 1.3, 1.5])

            with c_info:
                ventana_recomendada = row.get("ventana_horaria_recepcion", "SIN DATO")
            
                st.markdown(
                    f"""
                    **{row['cliente']} - {row['cliente_nombre']}**  
                    DPS: **{row['dps']}** | Estado: **{row['estado_gestion']}**  
                    Última fecha: **{row['ultima_fecha_click']}** | Usuario: **{row['ultimo_usuario']}** | Atendidos: **{row['cantidad_clicks']}**  
                    Ventana recomendada: **{ventana_recomendada}**
                    """
                )

            with c_atendido:
                if atendido_bloqueado:
                    st.button(
                        "Ya atendido ✅",
                        key=f"atendido_bloqueado_{key_base}_{i}_{row['cliente']}_{row['dps']}",
                        disabled=True,
                        use_container_width=True
                    )
                else:
                    if st.button(
                        "Atendido",
                        key=f"atendido_{key_base}_{i}_{row['cliente']}_{row['dps']}",
                        use_container_width=True
                    ):
                        registrar_accion_gestion(
                            row=row,
                            file_key=file_key,
                            origen=origen,
                            accion="ATENDIDO",
                            fecha_referencia=fecha_referencia
                        )
                        st.success("Cliente guardado como ATENDIDO.")
                        st.rerun()

            with c_recom:
                if st.button(
                    "🔁 Re comunicación",
                    key=f"recom_{key_base}_{i}_{row['cliente']}_{row['dps']}",
                    disabled=recomunicacion_bloqueada,
                    use_container_width=True
                ):
                    registrar_accion_gestion(
                        row=row,
                        file_key=file_key,
                        origen=origen,
                        accion="RECOMUNICACION",
                        fecha_referencia=fecha_referencia
                    )
                    st.success("Cliente guardado como RECOMUNICACION.")
                    st.rerun()
            if file_key == "llamadas":
                detalle_sku = obtener_detalle_skus_cliente(
                    detalle_pedidos=detalle_pedidos,
                    cliente=row["cliente"],
                    dps=row["dps"]
                )

                if not detalle_sku.empty:
                    with st.expander("📦 Ver detalle del pedido del día seleccionado", expanded=False):
                        st.dataframe(
                            detalle_sku,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Cantidad/Bultos": st.column_config.NumberColumn(
                                    "Cantidad/Bultos",
                                    format="%.2f"
                                ),
                                "HL": st.column_config.NumberColumn(
                                    "HL",
                                    format="%.2f"
                                )
                            }
                        )
                else:
                    st.caption("Sin detalle de SKUs para este cliente en la fecha seleccionada.")
# =========================================================
# PEDIDOS PARA MAÑANA / PRÓXIMOS DÍAS
# =========================================================

@st.cache_data(ttl=600)
def cargar_pedidos_programados():
    pedidos = pd.read_csv(
        PEDIDOS_PROGRAMADOS_URL,
        compression="gzip"
    )

    pedidos.columns = pedidos.columns.str.strip().str.lower()

    pedidos["cliente"] = (
        pd.to_numeric(pedidos["cliente"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    pedidos["dps"] = (
        pd.to_numeric(pedidos["dps"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    pedidos["nro"] = (
        pd.to_numeric(pedidos["nro"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )

    pedidos["fch_entrega"] = (
        pedidos["fch_entrega"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    pedidos["fecha_entrega"] = pd.to_datetime(
        pedidos["fch_entrega"],
        format="%Y%m%d",
        errors="coerce"
    ).dt.date

    text_cols_pedidos = [
        "cliente_nombre",
        "cod_desc",
        "sts",
        "mot_trn_desc",
        "producto_nombre",
        "domicilio",
        "zona_desc",
        "region_desc",
        "gerencia_desc",
        "trr_desc",
        "localidad"
    ]

    for col in text_cols_pedidos:
        if col in pedidos.columns:
            pedidos[col] = pedidos[col].fillna("SIN DATO").astype(str).str.strip()
            
    if "sts" in pedidos.columns:
        pedidos["sts"] = pedidos["sts"].fillna("SIN DATO").astype(str).str.upper().str.strip()
        pedidos = pedidos[pedidos["sts"].isin(["LIB", "RET"])].copy()
    
    num_cols_pedidos = [
        "hl",
        "bultos",
        "importe_total",
        "producto",
        "planilla"
    ]

    for col in num_cols_pedidos:
        if col in pedidos.columns:
            pedidos[col] = pd.to_numeric(pedidos[col], errors="coerce").fillna(0)

    return pedidos


def construir_base_pedidos_preventiva(pedidos, historico, fecha_objetivo):
    pedidos_fecha = pedidos[
        pedidos["fecha_entrega"].eq(fecha_objetivo)
    ].copy()

    if pedidos_fecha.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Base detalle por pedido/producto para mostrar abajo
    detalle_pedidos = pedidos_fecha.copy()

    # Agrupar a nivel cliente para evitar duplicación por SKU
    pedidos_cliente = (
        pedidos_fecha
        .groupby(
            [
                "cliente",
                "cliente_nombre",
                "dps",
                "fecha_entrega"
            ],
            as_index=False
        )
        .agg(
            pedidos_programados=("nro", "nunique"),
            lista_pedidos=("nro", lambda x: ", ".join(sorted(x.astype(str).unique()))),
            hl_programados=("hl", "sum"),
            bultos_programados=("bultos", "sum"),
            importe_programado=("importe_total", "sum"),
            productos_distintos=("producto", "nunique"),
            estado_pedido=("sts", "first"),
            zona_desc=("zona_desc", "first"),
            region_desc=("region_desc", "first"),
            gerencia_desc=("gerencia_desc", "first"),
            trr_desc=("trr_desc", "first"),
            domicilio=("domicilio", "first"),
            localidad=("localidad", "first")
        )
    )

    # Histórico ya viene de tu tabla principal otif_h3.csv
    hist = historico.copy()

    hist_cols = [
        "cliente",
        "entregas_totales",
        "entregas_rech",
        "entregas_sus",
        "entregas_ok",
        "hl_comprados",
        "hl_rechazados",
        "pct_rechazo",
        "pct_hl_rechazado",
        "frecuencia_semanal",
        "motivo_rechazo_principal",
        "ventana_horaria_recepcion",
        "ventana_local_cerrado",
        "accion_recomendada",
        "tipo_gestion",
        "score_criticidad",
        "prioridad"
    ]

    hist_cols = [c for c in hist_cols if c in hist.columns]

    hist = hist[hist_cols].drop_duplicates("cliente")

    base = pedidos_cliente.merge(
        hist,
        on="cliente",
        how="left"
    )

    # Completar clientes sin histórico
    fill_num = [
        "entregas_totales",
        "entregas_rech",
        "entregas_sus",
        "entregas_ok",
        "hl_comprados",
        "hl_rechazados",
        "pct_rechazo",
        "pct_hl_rechazado",
        "frecuencia_semanal",
        "score_criticidad"
    ]

    for col in fill_num:
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0)

    fill_text = [
        "motivo_rechazo_principal",
        "ventana_horaria_recepcion",
        "ventana_local_cerrado",
        "accion_recomendada",
        "tipo_gestion",
        "prioridad"
    ]

    for col in fill_text:
        if col in base.columns:
            base[col] = base[col].fillna("SIN HISTÓRICO").astype(str)

    # Tasa global histórica para suavizar probabilidad
    total_entregas_hist = max(historico["entregas_totales"].sum(), 1)
    total_rechazos_hist = historico["entregas_rech"].sum()

    tasa_global_rechazo = total_rechazos_hist / total_entregas_hist

    # Probabilidad suavizada:
    # Evita que un cliente con 1 entrega y 1 rechazo salga automáticamente como 100%
    base["probabilidad_rechazo"] = (
        base["entregas_rech"] + tasa_global_rechazo * 5
    ) / (
        base["entregas_totales"] + 5
    )

    base["probabilidad_rechazo_pct"] = (
        base["probabilidad_rechazo"] * 100
    ).round(1)

    # Impacto del pedido del día seleccionado
    max_hl_programado = base["hl_programados"].max()

    base["impacto_hl_programado"] = np.where(
        max_hl_programado > 0,
        base["hl_programados"] / max_hl_programado,
        0
    )

    # Score preventivo:
    # 50% probabilidad histórica de rechazo
    # 25% score de criticidad histórico
    # 15% impacto del HL programado para esa fecha
    # 10% % HL rechazado histórico
    base["score_llamada_preventiva"] = 100 * (
        base["probabilidad_rechazo"] * 0.50 +
        (base["score_criticidad"] / 100) * 0.25 +
        base["impacto_hl_programado"] * 0.15 +
        base["pct_hl_rechazado"].clip(0, 1) * 0.10
    )

    base["score_llamada_preventiva"] = base["score_llamada_preventiva"].round(1)

    base["prioridad_llamada"] = np.select(
        [
            base["score_llamada_preventiva"] >= 70,
            base["score_llamada_preventiva"] >= 50,
            base["score_llamada_preventiva"] >= 30
        ],
        [
            "🚨 LLAMAR URGENTE",
            "🟠 RIESGO ALTO",
            "🟡 MONITOREAR"
        ],
        default="🟢 BAJO"
    )

    def accion_preventiva(row):
        motivo = str(row.get("motivo_rechazo_principal", "")).upper()
        ventana_ok = str(row.get("ventana_horaria_recepcion", "SIN DATO"))
        ventana_cerrado = str(row.get("ventana_local_cerrado", "SIN DATO"))

        if "LOCAL CERRADO" in motivo:
            return (
                f"Llamar y confirmar horario de apertura. "
                f"Recepción habitual: {ventana_ok}. "
                f"Riesgo por local cerrado: {ventana_cerrado}."
            )

        if "DINERO" in motivo:
            return "Llamar y confirmar disponibilidad de pago antes del despacho."

        if "NO RECIBE" in motivo or "RECHAZA" in motivo:
            return "Llamar y confirmar voluntad de recibir el pedido."

        if "NO UBICADO" in motivo or "DIRECCION" in motivo or "DIRECCIÓN" in motivo:
            return "Validar dirección, referencia y ubicación antes de salir a ruta."

        if "MAL PEDIDO" in motivo or "PEDIDO" in motivo:
            return "Validar productos y cantidades con el cliente o ventas."

        if row["score_llamada_preventiva"] >= 70:
            return "Llamar antes de cargar o despachar por alto riesgo operativo."

        if row["score_llamada_preventiva"] >= 50:
            return "Realizar contacto preventivo para confirmar recepción."

        return "Monitorear. Contactar solo si hay capacidad operativa."

    base["accion_preventiva"] = base.apply(accion_preventiva, axis=1)

    base = base.sort_values(
        "score_llamada_preventiva",
        ascending=False
    ).reset_index(drop=True)

    return base, detalle_pedidos

def construir_comunicar_buffer(pedidos, historico, hoy):
    # Pedidos con fecha de entrega anterior a hoy
    # y que siguen pendientes en estado LIB o RET
    buffer = pedidos[
        (pedidos["fecha_entrega"] < hoy) &
        (pedidos["sts"].isin(["LIB", "RET"]))
    ].copy()

    if buffer.empty:
        return pd.DataFrame(), pd.DataFrame()

    buffer["dias_atraso"] = buffer["fecha_entrega"].apply(
        lambda x: (hoy - x).days if pd.notnull(x) else 0
    )

    detalle_buffer = buffer.copy()

    buffer_cliente = (
        buffer
        .groupby(
            [
                "cliente",
                "cliente_nombre",
                "dps"
            ],
            as_index=False
        )
        .agg(
            fecha_entrega_mas_antigua=("fecha_entrega", "min"),
            fecha_entrega_mas_reciente=("fecha_entrega", "max"),
            dias_atraso_max=("dias_atraso", "max"),
            pedidos_buffer=("nro", "nunique"),
            lista_pedidos=("nro", lambda x: ", ".join(sorted(x.astype(str).unique()))),
            hl_buffer=("hl", "sum"),
            bultos_buffer=("bultos", "sum"),
            importe_buffer=("importe_total", "sum"),
            estados=("sts", lambda x: ", ".join(sorted(x.astype(str).unique()))),
            zona_desc=("zona_desc", "first"),
            region_desc=("region_desc", "first"),
            gerencia_desc=("gerencia_desc", "first"),
            trr_desc=("trr_desc", "first"),
            domicilio=("domicilio", "first"),
            localidad=("localidad", "first")
        )
    )

    hist = historico.copy()

    hist_cols = [
        "cliente",
        "entregas_totales",
        "entregas_rech",
        "hl_rechazados",
        "pct_rechazo",
        "pct_hl_rechazado",
        "motivo_rechazo_principal",
        "ventana_horaria_recepcion",
        "ventana_local_cerrado",
        "accion_recomendada",
        "score_criticidad",
        "prioridad"
    ]

    hist_cols = [c for c in hist_cols if c in hist.columns]

    hist = hist[hist_cols].drop_duplicates("cliente")

    buffer_cliente = buffer_cliente.merge(
        hist,
        on="cliente",
        how="left"
    )

    fill_num = [
        "entregas_totales",
        "entregas_rech",
        "hl_rechazados",
        "pct_rechazo",
        "pct_hl_rechazado",
        "score_criticidad"
    ]

    for col in fill_num:
        if col in buffer_cliente.columns:
            buffer_cliente[col] = pd.to_numeric(
                buffer_cliente[col],
                errors="coerce"
            ).fillna(0)

    fill_text = [
        "motivo_rechazo_principal",
        "ventana_horaria_recepcion",
        "ventana_local_cerrado",
        "accion_recomendada",
        "prioridad"
    ]

    for col in fill_text:
        if col in buffer_cliente.columns:
            buffer_cliente[col] = buffer_cliente[col].fillna("SIN HISTÓRICO").astype(str)

    # Score buffer:
    # Prioriza más días de atraso, más HL pendiente, y clientes críticos históricamente
    max_dias = max(buffer_cliente["dias_atraso_max"].max(), 1)
    max_hl = max(buffer_cliente["hl_buffer"].max(), 0.01)

    buffer_cliente["impacto_dias_atraso"] = buffer_cliente["dias_atraso_max"] / max_dias
    buffer_cliente["impacto_hl_buffer"] = buffer_cliente["hl_buffer"] / max_hl

    buffer_cliente["score_comunicar_buffer"] = 100 * (
        buffer_cliente["impacto_dias_atraso"] * 0.40 +
        buffer_cliente["impacto_hl_buffer"] * 0.35 +
        (buffer_cliente["score_criticidad"] / 100) * 0.25
    )

    buffer_cliente["score_comunicar_buffer"] = (
        buffer_cliente["score_comunicar_buffer"]
        .round(1)
    )

    buffer_cliente["prioridad_buffer"] = np.select(
        [
            buffer_cliente["score_comunicar_buffer"] >= 70,
            buffer_cliente["score_comunicar_buffer"] >= 50,
            buffer_cliente["score_comunicar_buffer"] >= 30
        ],
        [
            "🚨 COMUNICAR URGENTE",
            "🟠 ALTO",
            "🟡 MONITOREAR"
        ],
        default="🟢 BAJO"
    )

    def accion_buffer(row):
        if row["dias_atraso_max"] >= 3:
            return "Comunicar al equipo: pedido con varios días de atraso y aún pendiente LIB/RET."

        if row["hl_buffer"] >= 10:
            return "Comunicar por alto volumen pendiente en buffer."

        if row["score_criticidad"] >= 50:
            return "Comunicar por cliente históricamente crítico con pedido vencido."

        return "Validar si corresponde reprogramar, liberar o depurar pedido pendiente."

    buffer_cliente["accion_buffer"] = buffer_cliente.apply(accion_buffer, axis=1)

    buffer_cliente = buffer_cliente.sort_values(
        ["score_comunicar_buffer", "dias_atraso_max", "hl_buffer"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    detalle_buffer = detalle_buffer.sort_values(
        ["cliente", "fecha_entrega", "nro", "producto_nombre"]
    )

    return buffer_cliente, detalle_buffer

def mostrar_pedidos_manana(historico_filtrado):
    col_titulo, col_boton = st.columns([5, 1])

    with col_titulo:
        ultima_actualizacion_pedidos = get_last_update_pedidos()

        st.caption(
            "Cruce preventivo entre pedidos programados y clientes con historial de rechazo. "
            f"Última actualización pedidos: {ultima_actualizacion_pedidos}."
        )

    with col_boton:
        st.write("")
        st.button(
            "⬅️ Volver",
            on_click=volver_al_dashboard,
            use_container_width=True
        )

    st.divider()

    pedidos = cargar_pedidos_programados()
    historico = historico_filtrado.copy()

    if "score_criticidad" not in historico.columns:
        historico = calcular_score_criticidad(historico)

    if "prioridad" not in historico.columns:
        historico["prioridad"] = historico["score_criticidad"].apply(clasificar_prioridad)

    clientes_filtrados = historico["cliente"].astype(str).unique()

    pedidos = pedidos[
        pedidos["cliente"].astype(str).isin(clientes_filtrados)
    ].copy()

    hoy = datetime.now(ZoneInfo("America/La_Paz")).date()

    buffer_clientes, detalle_buffer = construir_comunicar_buffer(
        pedidos,
        historico,
        hoy
    )

    opciones = []

    for n in range(1, 8):
        fecha = hoy + timedelta(days=n)

        if hoy.weekday() == 5 and n == 1:
            etiqueta = f"N+{n} - {fecha.strftime('%d/%m/%Y')} - Domingo sin atención"
        else:
            etiqueta = f"N+{n} - {fecha.strftime('%d/%m/%Y')}"

        opciones.append(
            {
                "n": n,
                "fecha": fecha,
                "etiqueta": etiqueta
            }
        )

    default_index = 1 if hoy.weekday() == 5 else 0

    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        opcion_sel = st.selectbox(
            "Fecha de entrega a evaluar",
            options=opciones,
            index=default_index,
            format_func=lambda x: x["etiqueta"]
        )

    fecha_objetivo = opcion_sel["fecha"]

    with col_f2:
        st.metric("Bloque visual", "10 clientes")

    pedidos_filtrados = pedidos.copy()

    base_preventiva, detalle_pedidos = construir_base_pedidos_preventiva(
        pedidos_filtrados,
        historico,
        fecha_objetivo
    )

    st.caption(f"Fecha evaluada: **{fecha_objetivo.strftime('%d/%m/%Y')}**")

    if fecha_objetivo.weekday() == 6:
        st.warning(
            "La fecha seleccionada cae domingo. Según la regla operativa, si hoy es sábado se recomienda usar N+2."
        )

    if base_preventiva.empty:
        st.info("No hay pedidos programados para la fecha seleccionada.")
    else:
        total_clientes = base_preventiva["cliente"].nunique()
        total_pedidos = base_preventiva["pedidos_programados"].sum()
        total_hl = base_preventiva["hl_programados"].sum()

        m1, m2, m3 = st.columns(3)

        m1.metric("Clientes con pedido", f"{total_clientes:,.0f}")
        m2.metric("Pedidos programados", f"{total_pedidos:,.0f}")
        m3.metric("HL programados", f"{total_hl:,.1f}")

        st.markdown("### 🚨 Top clientes a llamar preventivamente")

        ranking_preventivo = base_preventiva.reset_index(drop=True).copy()

        ya_atendi_llamadas = st.checkbox(
            "✅ Ya atendí estos 10 clientes de llamadas, mostrar los siguientes 10",
            key="ya_atendi_llamadas"
        )

        if ya_atendi_llamadas:
            max_saltar_llamadas = max(len(ranking_preventivo) - 1, 0)

            if max_saltar_llamadas >= 10:
                clientes_a_saltar_llamadas = st.number_input(
                    "Cantidad de clientes de llamadas ya atendidos",
                    min_value=10,
                    max_value=max_saltar_llamadas,
                    value=10,
                    step=10,
                    key="clientes_a_saltar_llamadas"
                )
            else:
                clientes_a_saltar_llamadas = 0
                st.info("No hay suficientes clientes de llamadas para mostrar el siguiente bloque.")
        else:
            clientes_a_saltar_llamadas = 0

        top_preventivo = ranking_preventivo.iloc[
            clientes_a_saltar_llamadas:clientes_a_saltar_llamadas + 10
        ].copy()

        if top_preventivo.empty:
            st.info("No hay clientes para mostrar en este bloque.")
        else:
            st.caption(
                f"Mostrando clientes de llamadas del puesto "
                f"{clientes_a_saltar_llamadas + 1} al "
                f"{clientes_a_saltar_llamadas + len(top_preventivo)} "
                f"de {len(ranking_preventivo)}."
            )

            cols_tabla_top = [
                "prioridad_llamada",
                "score_llamada_preventiva",
                "probabilidad_rechazo_pct",
                "cliente",
                "cliente_nombre",
                "dps",
                "pedidos_programados",
                "lista_pedidos",
                "hl_programados",
                "entregas_totales",
                "entregas_rech",
                "hl_rechazados",
                "motivo_rechazo_principal",
                "ventana_horaria_recepcion",
                "accion_preventiva"
            ]
            
            cols_tabla_top = [
                c for c in cols_tabla_top
                if c in top_preventivo.columns
            ]
            
            tabla_top = top_preventivo[cols_tabla_top].copy()

            mostrar_tabla_gestion(
                data=tabla_top,
                origen="Top clientes a llamar preventivamente",
                file_key="llamadas",
                key_base=f"top10_llamadas_{fecha_objetivo}_{clientes_a_saltar_llamadas}",
                column_config_extra={
                    "score_llamada_preventiva": st.column_config.NumberColumn(
                        "Score llamada",
                        format="%.1f"
                    ),
                    "probabilidad_rechazo_pct": st.column_config.NumberColumn(
                        "Prob. rechazo",
                        format="%.1f%%"
                    ),
                    "hl_programados": st.column_config.NumberColumn(
                        "HL programados",
                        format="%.2f"
                    ),
                    "hl_rechazados": st.column_config.NumberColumn(
                        "HL rechazados hist.",
                        format="%.2f"
                    ),
                    "ventana_horaria_recepcion": st.column_config.TextColumn(
                        "Ventana recomendada"
                    )
                },
                fecha_referencia=fecha_objetivo.strftime("%Y-%m-%d"),
                detalle_pedidos=detalle_pedidos
            )

            st.markdown("### 📱 Vista móvil de llamadas")

            for _, row in top_preventivo.iterrows():
                with st.container(border=True):
                    st.markdown(f"""
### {row['prioridad_llamada']} | {row['cliente']} - {row['cliente_nombre']}

**Score llamada:** {row['score_llamada_preventiva']:.1f}  
**Probabilidad rechazo:** {row['probabilidad_rechazo_pct']:.1f}%  
**DPS:** {row['dps']}  
**Pedidos:** {row['pedidos_programados']}  
**Nros pedido:** {row['lista_pedidos']}  
**HL programados:** {row['hl_programados']:.2f}  
**Histórico:** {int(row['entregas_rech'])} rechazos de {int(row['entregas_totales'])} entregas  
**HL rechazados histórico:** {row['hl_rechazados']:.2f}  
**Motivo principal:** {row['motivo_rechazo_principal']}  
**Ventana recepción:** {row['ventana_horaria_recepcion']}  
**Ventana local cerrado:** {row['ventana_local_cerrado']}  

👉 **Acción:** {row['accion_preventiva']}  

**Zona:** {row.get('zona_desc', 'SIN DATO')}  
**Dirección:** {row.get('domicilio', 'SIN DATO')}
                    """)

        st.markdown("### 📋 Lista completa preventiva")

        prioridad_sel = st.multiselect(
            "Filtrar prioridad llamada",
            options=base_preventiva["prioridad_llamada"].dropna().unique(),
            default=base_preventiva["prioridad_llamada"].dropna().unique()
        )

        base_filtrada = base_preventiva[
            base_preventiva["prioridad_llamada"].isin(prioridad_sel)
        ].copy()

        st.dataframe(
            base_filtrada[
                [
                    "prioridad_llamada",
                    "score_llamada_preventiva",
                    "probabilidad_rechazo_pct",
                    "cliente",
                    "cliente_nombre",
                    "dps",
                    "pedidos_programados",
                    "lista_pedidos",
                    "hl_programados",
                    "bultos_programados",
                    "importe_programado",
                    "entregas_totales",
                    "entregas_rech",
                    "hl_rechazados",
                    "motivo_rechazo_principal",
                    "accion_preventiva",
                    "zona_desc",
                    "domicilio"
                ]
            ],
            use_container_width=True,
            height=480,
            hide_index=True
        )

        csv_preventivo = base_filtrada.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "📥 Descargar lista preventiva CSV",
            csv_preventivo,
            f"pedidos_preventivos_{fecha_objetivo}.csv",
            "text/csv"
        )

        st.markdown("### 🧾 Detalle de pedidos de la fecha seleccionada")

        detalle_ordenado = detalle_pedidos.copy()

        orden_cols = [
            c for c in ["cliente", "cliente_nombre", "nro", "producto_nombre"]
            if c in detalle_ordenado.columns
        ]

        detalle_ordenado = detalle_ordenado.sort_values(orden_cols)

        st.dataframe(
            detalle_ordenado[
                [
                    "fecha_entrega",
                    "cliente",
                    "cliente_nombre",
                    "dps",
                    "nro",
                    "sts",
                    "producto",
                    "producto_nombre",
                    "bultos",
                    "hl",
                    "importe_total",
                    "zona_desc",
                    "domicilio"
                ]
            ],
            use_container_width=True,
            height=420,
            hide_index=True
        )

    # =========================================================
    # COMUNICAR BUFFER AL FINAL
    # =========================================================

    st.markdown("### 📣 Comunicar buffer")

    if buffer_clientes.empty:
        st.success("No hay pedidos vencidos pendientes en estado LIB o RET.")
    else:
        total_clientes_buffer = buffer_clientes["cliente"].nunique()
        total_pedidos_buffer = buffer_clientes["pedidos_buffer"].sum()
        total_hl_buffer = buffer_clientes["hl_buffer"].sum()
        max_dias_buffer = buffer_clientes["dias_atraso_max"].max()

        b1, b2, b3, b4 = st.columns(4)

        b1.metric("Clientes en buffer", f"{total_clientes_buffer:,.0f}")
        b2.metric("Pedidos en buffer", f"{total_pedidos_buffer:,.0f}")
        b3.metric("HL en buffer", f"{total_hl_buffer:,.1f}")
        b4.metric("Mayor atraso", f"{int(max_dias_buffer)} días")

        st.caption(
            "Clientes con fecha de entrega anterior a hoy y pedidos aún en estado LIB o RET."
        )

        ranking_buffer = buffer_clientes.reset_index(drop=True).copy()

        ya_atendi_buffer = st.checkbox(
            "✅ Ya atendí estos 10 clientes de buffer, mostrar los siguientes 10",
            key="ya_atendi_buffer"
        )

        if ya_atendi_buffer:
            max_saltar_buffer = max(len(ranking_buffer) - 1, 0)

            if max_saltar_buffer >= 10:
                clientes_a_saltar_buffer = st.number_input(
                    "Cantidad de clientes de buffer ya atendidos",
                    min_value=10,
                    max_value=max_saltar_buffer,
                    value=10,
                    step=10,
                    key="clientes_a_saltar_buffer"
                )
            else:
                clientes_a_saltar_buffer = 0
                st.info("No hay suficientes clientes de buffer para mostrar el siguiente bloque.")
        else:
            clientes_a_saltar_buffer = 0

        top_buffer = ranking_buffer.iloc[
            clientes_a_saltar_buffer:clientes_a_saltar_buffer + 10
        ].copy()

        st.caption(
            f"Mostrando clientes de buffer del puesto "
            f"{clientes_a_saltar_buffer + 1} al "
            f"{clientes_a_saltar_buffer + len(top_buffer)} "
            f"de {len(ranking_buffer)}."
        )

        tabla_buffer = top_buffer[
            [
                "prioridad_buffer",
                "score_comunicar_buffer",
                "cliente",
                "cliente_nombre",
                "dps",
                "fecha_entrega_mas_antigua",
                "fecha_entrega_mas_reciente",
                "dias_atraso_max",
                "pedidos_buffer",
                "lista_pedidos",
                "hl_buffer",
                "estados",
                "motivo_rechazo_principal",
                "accion_buffer"
            ]
        ].copy()

        mostrar_tabla_gestion(
            data=tabla_buffer,
            origen="Comunicar buffer",
            file_key="buffer",
            key_base=f"top10_buffer_{clientes_a_saltar_buffer}",
            column_config_extra={
                "score_comunicar_buffer": st.column_config.NumberColumn(
                    "Score buffer",
                    format="%.1f"
                ),
                "hl_buffer": st.column_config.NumberColumn(
                    "HL buffer",
                    format="%.2f"
                )
            }
        )

        with st.expander("📱 Vista móvil comunicar buffer", expanded=False):
            for _, row in top_buffer.iterrows():
                with st.container(border=True):
                    st.markdown(f"""
### {row['prioridad_buffer']} | {row['cliente']} - {row['cliente_nombre']}

**Score buffer:** {row['score_comunicar_buffer']:.1f}  
**DPS:** {row['dps']}  
**Pedidos pendientes:** {row['pedidos_buffer']}  
**Nros pedido:** {row['lista_pedidos']}  
**Estados:** {row['estados']}  
**Fecha más antigua:** {row['fecha_entrega_mas_antigua']}  
**Fecha más reciente:** {row['fecha_entrega_mas_reciente']}  
**Días de atraso:** {int(row['dias_atraso_max'])}  
**HL en buffer:** {row['hl_buffer']:.2f}  
**Motivo histórico principal:** {row['motivo_rechazo_principal']}  

👉 **Acción:** {row['accion_buffer']}  

**Zona:** {row.get('zona_desc', 'SIN DATO')}  
**Dirección:** {row.get('domicilio', 'SIN DATO')}
                    """)

        with st.expander("🧾 Detalle completo buffer", expanded=False):
            st.dataframe(
                detalle_buffer[
                    [
                        "fecha_entrega",
                        "dias_atraso",
                        "cliente",
                        "cliente_nombre",
                        "dps",
                        "nro",
                        "sts",
                        "producto",
                        "producto_nombre",
                        "bultos",
                        "hl",
                        "importe_total",
                        "zona_desc",
                        "domicilio"
                    ]
                ],
                use_container_width=True,
                height=420,
                hide_index=True
            )

            csv_buffer = buffer_clientes.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "📥 Descargar comunicar buffer CSV",
                csv_buffer,
                "comunicar_buffer.csv",
                "text/csv"
            )
# =========================================================
# HEADER CON BOTÓN INFORMACIÓN
# =========================================================

header_left, header_dashboard, header_pedidos, header_info = st.columns([4, 1.1, 1.4, 1])

with header_left:
    if st.session_state["vista_actual"] == "dashboard":
        st.title("🔥 PROYECTO FENIX")
    elif st.session_state["vista_actual"] == "pedidos_manana":
        st.title("📞 Pedidos para llamar")
    elif st.session_state["vista_actual"] == "informacion":
        st.title("📘 Información")

with header_dashboard:
    st.write("")
    st.button(
        "🏠 Dashboard",
        on_click=volver_al_dashboard,
        use_container_width=True
    )

with header_pedidos:
    st.write("")
    st.button(
        "📞 Pedidos",
        on_click=ir_a_pedidos_manana,
        use_container_width=True
    )

with header_info:
    st.write("")
    st.button(
        "ℹ️ Información",
        on_click=ir_a_informacion,
        use_container_width=True
    )

if st.session_state["vista_actual"] == "informacion":
    mostrar_glosario()
    st.stop()

ultima_actualizacion = get_last_update()

st.caption(
    f"Herramienta para detectar clientes críticos, recuperar HL y reducir rechazos con foco operativo. "
    f"Última fecha de actualización: {ultima_actualizacion}."
)

# =========================================================
# SIDEBAR FILTROS
# =========================================================

st.sidebar.title("🔎 Filtros")

st.sidebar.markdown("### 👤 Gestión")

st.sidebar.text_input(
    "Usuario que gestiona",
    placeholder="Ej: Pablo / Equipo DPS 7",
    key="usuario_gestion"
)

dps_sel = st.sidebar.multiselect(
    "DPS",
    sorted(df["dps"].unique())
)

cliente_label_map = {
    row["cliente"]: f"{row['cliente']} - {row['cliente_nombre']}"
    for _, row in df[["cliente", "cliente_nombre"]].drop_duplicates().iterrows()
}

cliente_filtro = st.sidebar.multiselect(
    "Cliente",
    sorted(df["cliente"].unique()),
    format_func=lambda x: cliente_label_map.get(x, x)
)

motivo_sel = st.sidebar.multiselect(
    "Motivo rechazo",
    sorted(df["motivo_rechazo_principal"].unique())
)

madurez_sel = st.sidebar.multiselect(
    "Madurez",
    sorted(df["madurez_cliente"].unique())
)

df_filtrado = df.copy()

if dps_sel:
    df_filtrado = df_filtrado[df_filtrado["dps"].isin(dps_sel)]

if cliente_filtro:
    df_filtrado = df_filtrado[df_filtrado["cliente"].isin(cliente_filtro)]

if motivo_sel:
    df_filtrado = df_filtrado[df_filtrado["motivo_rechazo_principal"].isin(motivo_sel)]

if madurez_sel:
    df_filtrado = df_filtrado[df_filtrado["madurez_cliente"].isin(madurez_sel)]

if df_filtrado.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

df_filtrado = calcular_score_criticidad(df_filtrado)
df_filtrado["prioridad"] = df_filtrado["score_criticidad"].apply(clasificar_prioridad)

prioridad_sel = st.sidebar.multiselect(
    "Prioridad",
    sorted(df_filtrado["prioridad"].unique())
)

if prioridad_sel:
    df_filtrado = df_filtrado[df_filtrado["prioridad"].isin(prioridad_sel)]

if df_filtrado.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# =========================================================
# VISTA PEDIDOS PARA LLAMAR
# Se ejecuta después de aplicar los mismos filtros del dashboard
# =========================================================

if st.session_state["vista_actual"] == "pedidos_manana":
    mostrar_pedidos_manana(df_filtrado)
    st.stop()

# =========================================================
# RESUMEN EJECUTIVO ORDENADO
# =========================================================

st.subheader("📊 Resumen Ejecutivo")

clientes_compradores = df_filtrado["cliente"].nunique()

clientes_rechazadores = df_filtrado.loc[
    df_filtrado["entregas_rech"] > 0,
    "cliente"
].nunique()

clientes_suspendidos = df_filtrado.loc[
    df_filtrado["entregas_sus"] > 0,
    "cliente"
].nunique()

entregas_totales = df_filtrado["entregas_totales"].sum()
entregas_rech = df_filtrado["entregas_rech"].sum()
entregas_sus = df_filtrado["entregas_sus"].sum()
entregas_ok = df_filtrado["entregas_ok"].sum()

hl_comprados = df_filtrado["hl_comprados"].sum()
hl_rechazados = df_filtrado["hl_rechazados"].sum()

pct_rechazo_total = entregas_rech / max(entregas_totales, 1)
pct_sus_total = entregas_sus / max(entregas_totales, 1)
pct_ok_total = entregas_ok / max(entregas_totales, 1)
pct_hl_rech_total = hl_rechazados / max(hl_comprados, 1)

freq_prom = df_filtrado["frecuencia_semanal"].mean()

c1, c2, c3 = st.columns(3)

c1.metric(
    "Clientes compradores",
    f"{clientes_compradores:,}"
)

c2.metric(
    "Clientes rechazadores",
    f"{clientes_rechazadores:,}"
)

c3.metric(
    "Clientes suspendidos",
    f"{clientes_suspendidos:,}"
)

e1, e2, e3, e4 = st.columns(4)

e1.metric(
    "Entregas totales",
    f"{int(entregas_totales):,}"
)

e2.metric(
    "Rechazos",
    f"{int(entregas_rech):,}",
    f"{pct_rechazo_total:.1%}"
)

e3.metric(
    "Suspensiones",
    f"{int(entregas_sus):,}",
    f"{pct_sus_total:.1%}"
)

e4.metric(
    "Entregas OK",
    f"{int(entregas_ok):,}",
    f"{pct_ok_total:.1%}"
)

h1, h2, h3 = st.columns(3)

h1.metric(
    "HL comprados",
    f"{hl_comprados:,.1f}"
)

h2.metric(
    "HL rechazados",
    f"{hl_rechazados:,.1f}",
    f"{pct_hl_rech_total:.1%}"
)

h3.metric(
    "Frecuencia promedio",
    f"{freq_prom:.2f}"
)

# =========================================================
# TOP 10 CLIENTES A INTERVENIR CON AVANCE
# =========================================================

st.subheader("🎯 Top 10 Clientes a Intervenir")

df_rech = df_filtrado[
    (df_filtrado["entregas_rech"] > 0) |
    (df_filtrado["hl_rechazados"] > 0)
].copy()

if df_rech.empty:
    st.info("No hay clientes con rechazos en el filtro actual.")
else:
    ranking_clientes = (
        df_rech
        .sort_values("score_criticidad", ascending=False)
        .reset_index(drop=True)
        .copy()
    )

    st.markdown("### 🔁 Gestión de avance operativo")

    ya_atendi_top10 = st.checkbox(
        "✅ Ya atendí estos 10 clientes, mostrar los siguientes 10"
    )

    if ya_atendi_top10:
        max_saltar = max(len(ranking_clientes) - 1, 0)

        if max_saltar >= 10:
            clientes_a_saltar = st.number_input(
                "Cantidad de clientes ya atendidos",
                min_value=10,
                max_value=max_saltar,
                value=10,
                step=10
            )
        else:
            clientes_a_saltar = 0
            st.info("No hay suficientes clientes para mostrar un siguiente bloque de 10.")
    else:
        clientes_a_saltar = 0

    top10 = ranking_clientes.iloc[
        clientes_a_saltar:clientes_a_saltar + 10
    ].copy()

    if top10.empty:
        st.info("No hay más clientes críticos después de los ya atendidos.")
    else:
        posicion_inicio = clientes_a_saltar + 1
        posicion_fin = clientes_a_saltar + len(top10)

        st.caption(
            f"Mostrando clientes del puesto {posicion_inicio} al {posicion_fin} "
            f"de {len(ranking_clientes)} clientes con rechazo."
        )

        hl_top10 = top10["hl_rechazados"].sum()
        rechazos_top10 = top10["entregas_rech"].sum()
        participacion_hl_top10 = hl_top10 / max(df_rech["hl_rechazados"].sum(), 1)
        participacion_rech_top10 = rechazos_top10 / max(df_rech["entregas_rech"].sum(), 1)

        t1, t2, t3, t4 = st.columns(4)

        t1.metric("HL recuperable bloque", f"{hl_top10:,.1f}")
        t2.metric("Rechazos bloque", f"{int(rechazos_top10):,}")
        t3.metric("% HL rechazo filtro", f"{participacion_hl_top10:.1%}")
        t4.metric("% rechazos filtro", f"{participacion_rech_top10:.1%}")

        top_cols = [
            "cliente",
            "cliente_nombre",
            "dps",
            "prioridad",
            "score_criticidad",
            "entregas_rech",
            "hl_rechazados",
            "pct_rechazo",
            "pct_hl_rechazado",
            "participacion_rechazos",
            "participacion_hl_rechazado",
            "frecuencia_semanal",
            "motivo_rechazo_principal",
            "tipo_gestion",
            "accion_recomendada"
        ]

        top_vista = top10[top_cols].copy()

        top_vista["pct_rechazo"] = top_vista["pct_rechazo"] * 100
        top_vista["pct_hl_rechazado"] = top_vista["pct_hl_rechazado"] * 100
        top_vista["participacion_rechazos"] = top_vista["participacion_rechazos"] * 100
        top_vista["participacion_hl_rechazado"] = top_vista["participacion_hl_rechazado"] * 100

        mostrar_tabla_gestion(
            data=top_vista,
            origen="Top 10 Dashboard",
            file_key="dashboard",
            key_base=f"top10_dashboard_{clientes_a_saltar}",
            column_config_extra={
                "score_criticidad": st.column_config.NumberColumn(
                    "Score",
                    format="%.1f"
                ),
                "hl_rechazados": st.column_config.NumberColumn(
                    "HL rechazados",
                    format="%.2f"
                ),
                "pct_rechazo": st.column_config.NumberColumn(
                    "% rechazo",
                    format="%.1f%%"
                ),
                "pct_hl_rechazado": st.column_config.NumberColumn(
                    "% HL rechazado",
                    format="%.1f%%"
                ),
                "participacion_rechazos": st.column_config.NumberColumn(
                    "% rechazos filtro",
                    format="%.1f%%"
                ),
                "participacion_hl_rechazado": st.column_config.NumberColumn(
                    "% HL rechazo filtro",
                    format="%.1f%%"
                ),
                "frecuencia_semanal": st.column_config.NumberColumn(
                    "Frecuencia semanal",
                    format="%.2f"
                ),
            }
        )

        st.subheader("🧠 Plan de Acción para Clientes Priorizados")

        for _, row in top10.iterrows():
            st.markdown(
                f"""
                **{row['prioridad']} | {row['cliente']} - {row['cliente_nombre']} | DPS {row['dps']}**  
                Score: **{row['score_criticidad']:.1f}** | Rechazos: **{int(row['entregas_rech'])}** | HL rechazados: **{row['hl_rechazados']:.2f}**  
                👉 {row['accion_recomendada']}
                """
            )

        st.subheader("🗺️ Ubicación Clientes Priorizados")
        mostrar_mapa_clientes(top10, "Mapa blanco del bloque priorizado")

# =========================================================
# ANÁLISIS VISUAL SOLO RECHAZOS
# =========================================================

st.subheader("📈 Análisis Visual de Rechazos")

df_rech = df_filtrado[
    (df_filtrado["entregas_rech"] > 0) |
    (df_filtrado["hl_rechazados"] > 0)
].copy()

if df_rech.empty:
    st.info("No hay datos de rechazo para graficar.")
else:
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("#### Top 20 HL Rechazados")
        pareto_hl = (
            df_rech
            .sort_values("hl_rechazados", ascending=False)
            .head(20)
            .copy()
        )
        pareto_hl["cliente_label"] = (
            pareto_hl["cliente"] + " - " + pareto_hl["cliente_nombre"]
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(pareto_hl["cliente_label"], pareto_hl["hl_rechazados"])
        ax.invert_yaxis()
        ax.set_xlabel("HL Rechazados")
        ax.set_ylabel("Cliente")
        st.pyplot(fig)

    with g2:
        st.markdown("#### Top 20 Cantidad de Rechazos")
        pareto_rech = (
            df_rech
            .sort_values("entregas_rech", ascending=False)
            .head(20)
            .copy()
        )
        pareto_rech["cliente_label"] = (
            pareto_rech["cliente"] + " - " + pareto_rech["cliente_nombre"]
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(pareto_rech["cliente_label"], pareto_rech["entregas_rech"])
        ax.invert_yaxis()
        ax.set_xlabel("Cantidad de rechazos")
        ax.set_ylabel("Cliente")
        st.pyplot(fig)

    g3, g4 = st.columns(2)

    with g3:
        st.markdown("#### Rechazos por Motivo")
        motivos = (
            df_rech
            .groupby("motivo_rechazo_principal", as_index=False)
            .agg(
                rechazos=("entregas_rech", "sum"),
                hl_rechazados=("hl_rechazados", "sum"),
                clientes=("cliente", "nunique")
            )
            .sort_values("rechazos", ascending=False)
            .head(10)
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(motivos["motivo_rechazo_principal"], motivos["rechazos"])
        ax.invert_yaxis()
        ax.set_xlabel("Cantidad de rechazos")
        ax.set_ylabel("Motivo")
        st.pyplot(fig)

    with g4:
        st.markdown("#### HL Rechazados por Motivo")
        motivos_hl = motivos.sort_values("hl_rechazados", ascending=False)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(motivos_hl["motivo_rechazo_principal"], motivos_hl["hl_rechazados"])
        ax.invert_yaxis()
        ax.set_xlabel("HL rechazados")
        ax.set_ylabel("Motivo")
        st.pyplot(fig)

    g5, g6 = st.columns(2)

    with g5:
        st.markdown("#### Rechazos por DPS")
        dps_rech = (
            df_rech
            .groupby("dps", as_index=False)
            .agg(
                rechazos=("entregas_rech", "sum"),
                hl_rechazados=("hl_rechazados", "sum")
            )
            .sort_values("rechazos", ascending=False)
        )

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dps_rech["dps"], dps_rech["rechazos"])
        ax.set_xlabel("DPS")
        ax.set_ylabel("Cantidad de rechazos")
        st.pyplot(fig)

    with g6:
        st.markdown("#### Cantidad de Rechazos vs HL Rechazados")
        fig, ax = plt.subplots(figsize=(10, 5))
        size = df_rech["score_criticidad"].clip(lower=5) * 5

        ax.scatter(
            df_rech["entregas_rech"],
            df_rech["hl_rechazados"],
            s=size,
            alpha=0.6
        )

        ax.set_xlabel("Cantidad de rechazos")
        ax.set_ylabel("HL rechazados")
        st.pyplot(fig)

# =========================================================
# FICHA CLIENTE MULTI-SELECCIÓN
# =========================================================

st.subheader("🧾 Ficha Cliente")

clientes_codigos = sorted(df_filtrado["cliente"].unique())

default_clientes = []
if "top10" in locals() and not top10.empty:
    default_clientes = top10["cliente"].head(1).tolist()

cliente_sel = st.multiselect(
    "Selecciona código(s) de cliente",
    clientes_codigos,
    default=default_clientes,
    format_func=lambda x: cliente_label_map.get(x, x)
)

if cliente_sel:
    fichas_df = (
        df_filtrado[df_filtrado["cliente"].isin(cliente_sel)]
        .sort_values("score_criticidad", ascending=False)
        .copy()
    )

    mostrar_mapa_clientes(fichas_df, "Mapa blanco clientes seleccionados")

    html_fichas = generar_html_fichas(fichas_df)

    st.download_button(
        "📄 Descargar fichas seleccionadas HTML",
        html_fichas.encode("utf-8"),
        "fichas_clientes_seleccionados.html",
        "text/html"
    )

    for _, c in fichas_df.iterrows():
        with st.expander(f"{c['cliente']} - {c['cliente_nombre']}", expanded=True):

            f1, f2, f3, f4, f5 = st.columns(5)

            f1.metric("Prioridad", c["prioridad"])
            f2.metric("Score", f"{c['score_criticidad']:.1f}")
            f3.metric("Rechazos", int(c["entregas_rech"]))
            f4.metric("HL Rechazados", f"{c['hl_rechazados']:.2f}")
            f5.metric("% Rechazo", f"{c['pct_rechazo']:.1%}")

            primera_fecha = (
                c["primera_fecha_entrega"].date()
                if pd.notnull(c["primera_fecha_entrega"])
                else "SIN DATO"
            )

            st.markdown(f"""
            ### 📌 Datos Generales

            **Código cliente:** {c['cliente']}  
            **Nombre:** {c['cliente_nombre']}  
            **DPS:** {c['dps']}  
            **Madurez:** {c['madurez_cliente']}  
            **Primera fecha entrega:** {primera_fecha}

            ---

            ### 📦 Volumen

            - **HL comprados:** {c['hl_comprados']:.2f}
            - **HL rechazados:** {c['hl_rechazados']:.2f}
            - **HL entregados estimados:** {c['hl_entregados_estimados']:.2f}
            - **% HL rechazado:** {c['pct_hl_rechazado']:.1%}

            ---

            ### 🚚 Operación

            - **Entregas totales:** {int(c['entregas_totales'])}
            - **Entregas rechazadas:** {int(c['entregas_rech'])}
            - **Entregas suspendidas:** {int(c['entregas_sus'])}
            - **Entregas OK:** {int(c['entregas_ok'])}
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

            - **Ventana horaria recepción:** {c['ventana_horaria_recepcion']}
            - **Ventana de rechazo por local cerrado:** {c['ventana_local_cerrado']}
            - **Día entrega:** {c['dia_entrega']}
            - **Días flex:** {c['dias_flex']}

            ---

            ### ✅ Acción Recomendada

            {c['accion_recomendada']}
            """)

            html_individual = generar_html_fichas(pd.DataFrame([c]))

            st.download_button(
                "📄 Descargar HTML de este cliente",
                html_individual.encode("utf-8"),
                f"ficha_cliente_{c['cliente']}.html",
                "text/html",
                key=f"html_{c['cliente']}"
            )
else:
    st.info("Selecciona uno o más códigos de cliente para ver la ficha.")

# =========================================================
# TABLA COMPLETA AL FINAL DEL DASHBOARD
# =========================================================

st.subheader("📋 Tabla Completa Filtrada")

tabla_cols = [
    "cliente",
    "cliente_nombre",
    "dps",
    "prioridad",
    "score_criticidad",
    "entregas_totales",
    "entregas_rech",
    "entregas_sus",
    "entregas_ok",
    "hl_comprados",
    "hl_rechazados",
    "pct_rechazo",
    "pct_suspension",
    "pct_hl_rechazado",
    "frecuencia_semanal",
    "madurez_cliente",
    "motivo_rechazo_principal",
    "resumen_motivos_rechazo",
    "ventana_horaria_recepcion",
    "ventana_local_cerrado",
    "dia_entrega",
    "dias_flex",
    "tipo_gestion",
    "accion_recomendada",
    "x",
    "y"
]

tabla_cols = [c for c in tabla_cols if c in df_filtrado.columns]

tabla_vista = (
    df_filtrado[tabla_cols]
    .sort_values("score_criticidad", ascending=False)
    .copy()
)

tabla_vista["pct_rechazo"] = tabla_vista["pct_rechazo"] * 100
tabla_vista["pct_suspension"] = tabla_vista["pct_suspension"] * 100
tabla_vista["pct_hl_rechazado"] = tabla_vista["pct_hl_rechazado"] * 100

st.dataframe(
    tabla_vista,
    use_container_width=True,
    height=520,
    column_config={
        "score_criticidad": st.column_config.NumberColumn(
            "Score criticidad",
            format="%.1f"
        ),
        "hl_comprados": st.column_config.NumberColumn(
            "HL comprados",
            format="%.2f"
        ),
        "hl_rechazados": st.column_config.NumberColumn(
            "HL rechazados",
            format="%.2f"
        ),
        "pct_rechazo": st.column_config.NumberColumn(
            "% rechazo",
            format="%.1f%%"
        ),
        "pct_suspension": st.column_config.NumberColumn(
            "% suspensión",
            format="%.1f%%"
        ),
        "pct_hl_rechazado": st.column_config.NumberColumn(
            "% HL rechazado",
            format="%.1f%%"
        ),
        "frecuencia_semanal": st.column_config.NumberColumn(
            "Frecuencia semanal",
            format="%.2f"
        ),
        "ventana_horaria_recepcion": st.column_config.TextColumn(
            "Ventana horaria de recepción"
        ),
        "ventana_local_cerrado": st.column_config.TextColumn(
            "Ventana rechazo local cerrado"
        ),
    }
)

csv = tabla_vista.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "📥 Descargar tabla filtrada CSV",
    csv,
    "tabla_clientes_filtrada.csv",
    "text/csv"
)
    
