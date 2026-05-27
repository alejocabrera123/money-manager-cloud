import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_auth():
    """Devuelve cliente Supabase con token del usuario autenticado."""
    client = init_supabase()
    if "access_token" in st.session_state and st.session_state.access_token:
        client.postgrest.auth(st.session_state.access_token)
    return client

def login_page():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "access_token" not in st.session_state:
        st.session_state.access_token = None

    if st.session_state.user:
        return True

    st.title("💰 Money Magnet")
    st.subheader("Iniciar sesión")

    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar", type="primary"):
        try:
            supabase = init_supabase()
            response = supabase.auth.sign_in_with_password(
                credentials={"email": email, "password": password}
            )
            st.session_state.user = response.user
            st.session_state.access_token = response.session.access_token
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

    return False

def get_user_id():
    return st.session_state.user.id

def procesar_xlsx(archivo):
    df = pd.read_excel(archivo)
    columnas_esperadas = [
        "Según un período", "Cuentas", "Categoría",
        "Subcategorías", "Nota", "EUR", "Ingreso/Gasto", "Descripción"
    ]
    columnas_faltantes = [c for c in columnas_esperadas if c not in df.columns]
    if columnas_faltantes:
        raise ValueError(f"Columnas faltantes en el archivo: {columnas_faltantes}")
    df = df[df["Cuentas"] == "Euros"].copy()
    df = df.rename(columns={
        "Según un período": "fecha_gasto",
        "Cuentas": "cuenta",
        "Categoría": "categoria_consumo",
        "Subcategorías": "sub_categoria",
        "Nota": "consumo",
        "EUR": "monto",
        "Ingreso/Gasto": "tipo",
        "Descripción": "descripcion"
    })
    df = df[["fecha_gasto", "cuenta", "categoria_consumo",
             "sub_categoria", "consumo", "monto", "tipo", "descripcion"]]
    df["tipo"] = df["tipo"].replace("Gastos", "Gasto")
    df["fecha_gasto"] = pd.to_datetime(df["fecha_gasto"]).dt.date
    # FIX 6: fillna solo en columnas texto, no en todo el DataFrame
    df["sub_categoria"] = df["sub_categoria"].fillna("")
    df["consumo"] = df["consumo"].fillna("")
    df["descripcion"] = df["descripcion"].fillna("")
    return df

def sincronizar(df, supabase, user_id):
    supabase.table("gastos").delete().eq("user_id", user_id).execute()
    registros = df.to_dict(orient="records")
    registros_str = []
    for r in registros:
        r["fecha_gasto"] = str(r["fecha_gasto"])
        r["monto"] = float(r["monto"])
        r["user_id"] = user_id
        registros_str.append(r)
    for i in range(0, len(registros_str), 500):
        lote = registros_str[i:i + 500]
        supabase.table("gastos").insert(lote).execute()
    return len(registros_str)

# ─── FIX 1+2: bug paginación corregido (eliminado if len < page_size) ────────
@st.cache_data(ttl=300)
def get_todos_gastos(_supabase, user_id):
    todos = []
    page_size = 1000
    offset = 0
    while True:
        result = _supabase.table("gastos")\
            .select("fecha_gasto, categoria_consumo, consumo, monto, tipo")\
            .eq("user_id", user_id)\
            .range(offset, offset + page_size - 1)\
            .execute()
        if not result.data:
            break
        todos.extend(result.data)
        offset += page_size  # ← solo avanza; el break lo controla "if not result.data"
    if not todos:
        return pd.DataFrame()
    df = pd.DataFrame(todos)
    df["fecha_gasto"] = pd.to_datetime(df["fecha_gasto"])
    df["importe"] = df.apply(
        lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"], axis=1
    )
    df["anio"] = df["fecha_gasto"].dt.year
    df["mes"] = df["fecha_gasto"].dt.month
    df["mes_anio"] = df["fecha_gasto"].dt.to_period("M")
    return df

def get_gastos_mes(supabase, year, month, user_id):
    inicio = date(year, month, 1)
    fin = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    result = supabase.table("gastos")\
        .select("categoria_consumo, monto, tipo")\
        .eq("user_id", user_id)\
        .gte("fecha_gasto", str(inicio))\
        .lt("fecha_gasto", str(fin))\
        .execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()

def get_presupuestos_mes(supabase, year, month, user_id):
    inicio = date(year, month, 1)
    result = supabase.table("presupuestos")\
        .select("categoria_consumo, monto")\
        .eq("user_id", user_id)\
        .eq("fecha", str(inicio))\
        .execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()

# ─── FIX 1+2: bug paginación corregido + cache añadido ───────────────────────
# Nota: parámetro renombrado a _supabase (prefijo _) para que st.cache_data
# no intente serializarlo — igual que en get_todos_gastos
@st.cache_data(ttl=300)
def get_balance_app(_supabase, user_id):
    todos = []
    offset = 0
    while True:
        result = _supabase.table("gastos")\
            .select("monto, tipo")\
            .eq("user_id", user_id)\
            .range(offset, offset + 999)\
            .execute()
        if not result.data:
            break
        todos.extend(result.data)
        offset += 1000  # ← solo avanza; el break lo controla "if not result.data"
    if not todos:
        return 0
    df = pd.DataFrame(todos)
    df["importe"] = df.apply(
        lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"], axis=1
    )
    return df["importe"].sum()

# ─── FIX 2: cache añadido ─────────────────────────────────────────────────────
# Nota: parámetro renombrado a _supabase por el mismo motivo
@st.cache_data(ttl=300)
def get_saldos_actuales(_supabase, user_id):
    result = _supabase.table("saldos_bancarios")\
        .select("banco, monto, fecha_registro")\
        .eq("user_id", user_id)\
        .order("fecha_registro", desc=True)\
        .execute()
    if not result.data:
        return pd.DataFrame(), None
    df = pd.DataFrame(result.data)
    ultima_fecha = df["fecha_registro"].max()
    df_actual = df[df["fecha_registro"] == ultima_fecha][["banco", "monto"]].copy()
    return df_actual, ultima_fecha

def guardar_saldos(supabase, saldos_dict, user_id):
    hoy = str(date.today())
    registros = [
        {"banco": banco, "monto": float(monto), "fecha_registro": hoy, "user_id": user_id}
        for banco, monto in saldos_dict.items()
        if banco.strip()
    ]
    if registros:
        supabase.table("saldos_bancarios").insert(registros).execute()

def widget_saldos_inline(supabase, user_id):
    df_saldos, ultima_fecha = get_saldos_actuales(supabase, user_id)

    st.divider()
    st.subheader("💳 ¿Actualizás tus saldos bancarios?")
    if ultima_fecha:
        st.caption(f"Últimos saldos registrados: {ultima_fecha}")

    if "saldos_temp" not in st.session_state:
        if not df_saldos.empty:
            st.session_state.saldos_temp = dict(
                zip(df_saldos["banco"], df_saldos["monto"])
            )
        else:
            st.session_state.saldos_temp = {}

    bancos = list(st.session_state.saldos_temp.keys())
    for banco in bancos:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.text(banco)
        with col2:
            nuevo_monto = st.number_input(
                f"€ {banco}",
                value=float(st.session_state.saldos_temp[banco]),
                step=0.01,
                label_visibility="collapsed",
                key=f"inline_{banco}"
            )
            st.session_state.saldos_temp[banco] = nuevo_monto

    col_no, col_si = st.columns([1, 1])
    with col_no:
        if st.button("Ahora no", key="sync_no"):
            st.session_state.mostrar_saldos_post_sync = False
            st.rerun()
    with col_si:
        if st.button("💾 Guardar saldos", type="primary", key="sync_si"):
            guardar_saldos(supabase, st.session_state.saldos_temp, user_id)
            # FIX 3: invalidación quirúrgica — solo saldos
            get_saldos_actuales.clear()
            st.session_state.mostrar_saldos_post_sync = False
            st.session_state.pop("saldos_temp", None)
            st.success("✅ Saldos guardados correctamente")
            st.rerun()

CATEGORIAS_OTROS = [
    "Education", "Other", "Impuesto Bancario", "Clothing",
    "Gifts", "Technology", "Payment", "Medical", "Tramites",
    "Visa", "Hacienda"
]

def pagina_dashboard(supabase, user_id):
    st.title("💰 Money Magnet")

    hoy = date.today()
    if "mes_offset" not in st.session_state:
        st.session_state.mes_offset = 0

    mes_actual = hoy + relativedelta(months=st.session_state.mes_offset)
    year, month = mes_actual.year, mes_actual.month
    nombre_mes = mes_actual.strftime("%B %Y").capitalize()

    col_izq, col_centro, col_der, col_hoy = st.columns([1, 2, 1, 1])
    with col_izq:
        if st.button("◀ Mes anterior"):
            st.session_state.mes_offset -= 1
            st.rerun()
    with col_centro:
        st.markdown(f"<h3 style='text-align:center'>📅 {nombre_mes}</h3>",
                    unsafe_allow_html=True)
    with col_der:
        if st.button("Mes siguiente ▶"):
            st.session_state.mes_offset += 1
            st.rerun()
    with col_hoy:
        if st.session_state.mes_offset != 0:
            if st.button("🏠 Hoy"):
                st.session_state.mes_offset = 0
                st.rerun()

    with st.spinner("Cargando datos..."):
        df_gastos = get_gastos_mes(supabase, year, month, user_id)
        df_presupuestos = get_presupuestos_mes(supabase, year, month, user_id)

    if df_gastos.empty and df_presupuestos.empty:
        st.warning("No hay datos para este mes.")
        return

    if not df_gastos.empty:
        df_gastos["importe"] = df_gastos.apply(
            lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"], axis=1
        )
        total_ingresos = df_gastos[df_gastos["tipo"] == "Ingreso"]["monto"].sum()
        total_gastado = df_gastos[df_gastos["tipo"] == "Gasto"]["monto"].sum()
        balance = total_ingresos - total_gastado
    else:
        total_ingresos = total_gastado = balance = 0

    presupuesto_total = df_presupuestos["monto"].sum() if not df_presupuestos.empty else 0

    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💸 Total Gastado", f"€{total_gastado:,.2f}")
    k2.metric("💰 Total Ingresos", f"€{total_ingresos:,.2f}")
    k3.metric("⚖️ Balance", f"€{balance:,.2f}")
    k4.metric("🎯 Presupuesto Neto", f"€{presupuesto_total:,.2f}")

    st.divider()
    st.subheader("📊 Detalle por Categoría")
    ocultar_cero = st.toggle("Ocultar categorías sin presupuesto (€0)", value=False)

    if not df_gastos.empty:
        real_cat = df_gastos.groupby("categoria_consumo")["importe"].sum().reset_index()
        real_cat.columns = ["categoria_consumo", "real"]
    else:
        real_cat = pd.DataFrame(columns=["categoria_consumo", "real"])

    if not df_presupuestos.empty:
        df_tabla = pd.merge(df_presupuestos, real_cat, on="categoria_consumo", how="left")
        df_tabla["real"] = df_tabla["real"].fillna(0)
    else:
        df_tabla = real_cat.copy()
        df_tabla["monto"] = 0

    df_tabla.columns = ["Categoría", "Presupuesto", "Real"]
    df_tabla["Diferencia"] = df_tabla["Real"] - df_tabla["Presupuesto"]

    def semaforo(row):
        if row["Real"] == 0 and row["Presupuesto"] != 0:
            return "🟡"
        elif row["Presupuesto"] < 0 and row["Real"] < row["Presupuesto"]:
            return "🔴"
        elif row["Presupuesto"] > 0 and row["Real"] < row["Presupuesto"]:
            return "🔴"
        else:
            return "🟢"

    df_tabla["Estado"] = df_tabla.apply(semaforo, axis=1)

    # ── Separar "Otros" del resto ─────────────────────────────────────────────
    mask_otros = df_tabla["Categoría"].isin(CATEGORIAS_OTROS)
    df_principales = df_tabla[~mask_otros].copy()
    df_otros = df_tabla[mask_otros].copy()

    if ocultar_cero:
        df_principales = df_principales[df_principales["Presupuesto"] != 0]

    df_principales = df_principales.reindex(
        df_principales["Real"].abs().sort_values(ascending=False).index
    )

    # Fila agrupada "Otras Categorías"
    if not df_otros.empty:
        fila_otros = pd.DataFrame([{
            "Categoría": "Otras Categorías ℹ️",
            "Presupuesto": df_otros["Presupuesto"].sum(),
            "Real": df_otros["Real"].sum(),
            "Diferencia": df_otros["Diferencia"].sum(),
            "Estado": "—"
        }])
        df_final = pd.concat([df_principales, fila_otros], ignore_index=True)
    else:
        df_final = df_principales

    df_mostrar = df_final.copy()
    df_mostrar["Presupuesto"] = df_mostrar["Presupuesto"].apply(lambda x: f"€{x:,.2f}")
    df_mostrar["Real"] = df_mostrar["Real"].apply(lambda x: f"€{x:,.2f}")
    df_mostrar["Diferencia"] = df_mostrar["Diferencia"].apply(lambda x: f"€{x:,.2f}")
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    if not df_otros.empty:
        cats_lista = ", ".join(sorted(df_otros["Categoría"].tolist()))
        st.caption(f"ℹ️ Otras Categorías incluye: {cats_lista}")

def pagina_bancos(supabase, user_id):
    st.title("💳 Saldos Bancarios")

    balance_app = get_balance_app(supabase, user_id)
    df_saldos, ultima_fecha = get_saldos_actuales(supabase, user_id)

    if "saldos_edit" not in st.session_state:
        if not df_saldos.empty:
            st.session_state.saldos_edit = dict(
                zip(df_saldos["banco"], df_saldos["monto"])
            )
        else:
            st.session_state.saldos_edit = {}

    if ultima_fecha:
        st.caption(f"Últimos saldos guardados: {ultima_fecha}")

    st.divider()
    st.markdown(f"📱 **Balance Money Magnet:** €{balance_app:,.2f}")
    st.divider()

    bancos = list(st.session_state.saldos_edit.keys())
    for banco in bancos:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.text(banco)
        with col2:
            nuevo_monto = st.number_input(
                f"€",
                value=float(st.session_state.saldos_edit[banco]),
                step=0.01,
                label_visibility="collapsed",
                key=f"edit_{banco}"
            )
            st.session_state.saldos_edit[banco] = nuevo_monto
        with col3:
            if st.button("🗑️", key=f"del_{banco}", help=f"Eliminar {banco}"):
                del st.session_state.saldos_edit[banco]
                st.rerun()

    st.divider()

    with st.expander("➕ Agregar banco"):
        nuevo_banco = st.text_input("Nombre del banco", key="nuevo_banco_nombre")
        nuevo_monto_banco = st.number_input("Monto (€)", value=0.0, step=0.01,
                                             key="nuevo_banco_monto")
        if st.button("Añadir"):
            if nuevo_banco.strip():
                st.session_state.saldos_edit[nuevo_banco.strip()] = nuevo_monto_banco
                st.rerun()

    total_bancos = sum(st.session_state.saldos_edit.values())
    diferencia = balance_app - total_bancos

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("💰 Total bancos", f"€{total_bancos:,.2f}")
    col_t2.metric("📱 Balance app", f"€{balance_app:,.2f}")
    if abs(diferencia) <= 0.01:
        col_t3.metric("⚖️ Diferencia", "€0.00 ✅")
    else:
        col_t3.metric("⚖️ Diferencia", f"€{diferencia:,.2f} ⚠️")

    st.divider()
    if st.button("💾 Guardar saldos", type="primary"):
        guardar_saldos(supabase, st.session_state.saldos_edit, user_id)
        # FIX 3: invalidación quirúrgica — solo saldos
        get_saldos_actuales.clear()
        st.session_state.pop("saldos_edit", None)
        st.success("✅ Saldos guardados correctamente")
        st.rerun()

    st.divider()
    with st.expander("📋 Ver historial de saldos"):
        result = supabase.table("saldos_bancarios")\
            .select("banco, monto, fecha_registro")\
            .eq("user_id", user_id)\
            .order("fecha_registro", desc=True)\
            .execute()
        if result.data:
            df_hist = pd.DataFrame(result.data)
            fechas = sorted(df_hist["fecha_registro"].unique(), reverse=True)
            fecha_sel = st.selectbox("Fecha", fechas)
            df_fecha = df_hist[df_hist["fecha_registro"] == fecha_sel][["banco", "monto"]]
            df_fecha.columns = ["Banco", "Monto (€)"]
            df_fecha["Monto (€)"] = df_fecha["Monto (€)"].apply(lambda x: f"€{x:,.2f}")
            st.dataframe(df_fecha, use_container_width=True, hide_index=True)
        else:
            st.info("Sin historial disponible")

def pagina_historico(supabase, user_id):
    st.title("📈 Histórico")

    with st.spinner("Cargando datos históricos..."):
        df = get_todos_gastos(supabase, user_id)

    if df.empty:
        st.warning("No hay datos disponibles.")
        return

    anios_disponibles = sorted(df["anio"].unique(), reverse=True)

    st.subheader("📊 Ingresos vs Gastos por Mes")
    anio_sel = st.selectbox("Año", anios_disponibles, index=0, key="anio_barras")

    df_anio = df[df["anio"] == anio_sel].copy()
    meses_nombres = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                     7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}

    df_barras = df_anio.groupby(["mes", "tipo"])["monto"].sum().reset_index()
    df_barras["mes_nombre"] = df_barras["mes"].map(meses_nombres)
    df_barras = df_barras.sort_values("mes")

    fig_barras = px.bar(
        df_barras, x="mes_nombre", y="monto", color="tipo", barmode="group",
        color_discrete_map={"Ingreso": "#82c9a0", "Gasto": "#e8968a"},
        labels={"monto": "€", "mes_nombre": "Mes", "tipo": ""},
        title=f"Ingresos vs Gastos — {anio_sel}"
    )
    fig_barras.update_layout(legend_title_text="")
    st.plotly_chart(fig_barras, use_container_width=True)

    st.divider()
    st.subheader("📈 Balance")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        vista_balance = st.radio(
            "Vista",
            ["Cascada mensual", "Balance mensual", "Balance acumulado"],
            horizontal=True
        )
    anios_rango = sorted(df["anio"].unique())
    with col2:
        anio_desde = st.selectbox("Desde año", anios_rango, index=0, key="desde_anio")
    with col3:
        anio_hasta = st.selectbox("Hasta año", anios_rango,
                                   index=len(anios_rango)-1, key="hasta_anio")

    df_rango = df[(df["anio"] >= anio_desde) & (df["anio"] <= anio_hasta)].copy()
    df_bal = df_rango.groupby("mes_anio")["importe"].sum().reset_index()
    df_bal = df_bal.sort_values("mes_anio")
    df_bal["etiqueta"] = df_bal["mes_anio"].astype(str)
    df_bal["acumulado"] = df_bal["importe"].cumsum()

    if vista_balance == "Cascada mensual":
        fig = go.Figure(go.Waterfall(
            orientation="v", measure=["relative"] * len(df_bal),
            x=df_bal["etiqueta"], y=df_bal["importe"],
            connector={"line": {"color": "rgba(150,150,150,0.3)"}},
            increasing={"marker": {"color": "#82c9a0"}},
            decreasing={"marker": {"color": "#e8968a"}},
            hovertemplate="%{x}<br>Δ mes: €%{y:,.2f}<extra></extra>"
        ))
        fig.update_layout(title="Cascada de balance mensual",
                          xaxis_title="Mes", yaxis_title="€", showlegend=False)
    elif vista_balance == "Balance mensual":
        fig = go.Figure(go.Bar(
            x=df_bal["etiqueta"], y=df_bal["importe"],
            marker_color=["#82c9a0" if v >= 0 else "#e8968a" for v in df_bal["importe"]],
            hovertemplate="%{x}<br>Balance: €%{y:,.2f}<extra></extra>"
        ))
        fig.update_layout(title="Balance neto por mes",
                          xaxis_title="Mes", yaxis_title="€", showlegend=False)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    else:
        fig = go.Figure(go.Scatter(
            x=df_bal["etiqueta"], y=df_bal["acumulado"],
            mode="lines+markers",
            line=dict(color="#3498db", width=2.5), marker=dict(size=6),
            hovertemplate="%{x}<br>Acumulado: €%{y:,.2f}<extra></extra>"
        ))
        fig.update_layout(title="Balance acumulado",
                          xaxis_title="Mes", yaxis_title="€", showlegend=False)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    st.plotly_chart(fig, use_container_width=True)

def pagina_detalle(supabase, user_id):
    st.title("🔍 Detalle de Transacciones")

    with st.spinner("Cargando datos..."):
        df = get_todos_gastos(supabase, user_id)

    if df.empty:
        st.warning("No hay datos disponibles.")
        return

    anios_disponibles = sorted(df["anio"].unique(), reverse=True)
    anio_default_idx = (
        anios_disponibles.index(date.today().year)
        if date.today().year in anios_disponibles else 0
    )

    meses_nombres = {0:"Todos",1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",
                     5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",
                     9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

    col1, col2 = st.columns(2)
    with col1:
        anio_sel = st.selectbox("Año", anios_disponibles, index=anio_default_idx)
    with col2:
        mes_sel = st.selectbox("Mes", list(meses_nombres.values()))

    # Filtrado — categoría ya no hace falta, la tabla lo muestra todo
    df_filtrado = df[df["anio"] == anio_sel].copy()
    if mes_sel != "Todos":
        mes_num = [k for k, v in meses_nombres.items() if v == mes_sel][0]
        df_filtrado = df_filtrado[df_filtrado["mes"] == mes_num]

    col_r1, col_r2 = st.columns(2)
    col_r1.metric("📋 Registros", f"{len(df_filtrado):,}")
    col_r2.metric("💰 Balance filtrado", f"€{df_filtrado['importe'].sum():,.2f}")

    st.divider()

    # ── Pivot: filas = categoría, columnas = meses con datos ─────────────────
    meses_col = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                 7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    meses_presentes = sorted(df_filtrado["mes"].unique())

    pivot = df_filtrado.groupby(["categoria_consumo", "mes"])["importe"].sum().unstack(level="mes")
    pivot.columns = [meses_col[m] for m in pivot.columns]
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total")  # gastos mayores arriba (más negativos primero)

    # Formatear: 0 y NaN → vacío, resto → €X,XX
    def fmt(x):
        if pd.isna(x) or x == 0:
            return ""
        return f"€{x:,.2f}"

    pivot_fmt = pivot.applymap(fmt)
    pivot_fmt.index.name = "Categoría"
    pivot_fmt = pivot_fmt.reset_index()

    altura = (len(pivot_fmt) + 1) * 35 + 10
    st.dataframe(pivot_fmt, use_container_width=True, hide_index=True, height=altura)

def pagina_sync(supabase, user_id):
    st.title("💰 Money Magnet")
    st.caption("Gestión de finanzas personales")
    st.divider()
    st.subheader("📤 Sincronizar Datos")
    st.write("Subí el archivo exportado desde Money Manager para actualizar tus datos.")

    archivo = st.file_uploader(
        "Seleccioná tu archivo xlsx",
        type=["xlsx"],
        help="Exportá desde Money Manager: Ajustes → Respaldo → Exportar"
    )

    if archivo:
        try:
            df = procesar_xlsx(archivo)
            st.success(
                f"✅ Archivo cargado: **{len(df)} registros** de cuenta Euros detectados")
            st.dataframe(
                df[["fecha_gasto", "categoria_consumo", "monto", "tipo"]].head(10),
                use_container_width=True
            )
            st.caption(f"Mostrando 10 de {len(df)} registros")
            st.divider()
            if st.button("🔄 Sincronizar con Supabase", type="primary"):
                with st.spinner("Sincronizando..."):
                    total = sincronizar(df, supabase, user_id)
                    balance = df.apply(
                        lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"],
                        axis=1
                    ).sum()
                # FIX 3: invalidación quirúrgica — solo lo que cambió, no cache global
                get_todos_gastos.clear()
                get_balance_app.clear()
                st.session_state.mostrar_saldos_post_sync = True
                st.session_state.pop("saldos_temp", None)
                st.success(f"""
                ✅ **Sincronización completada**
                - 📊 **{total:,} registros** subidos a Supabase
                - 💰 **Balance actual: €{balance:,.2f}**
                - 🕐 **{datetime.now().strftime('%d/%m/%Y %H:%M')}**
                """)

        except ValueError as e:
            st.error(f"❌ Error en el archivo: {e}")
        except Exception as e:
            st.error(f"❌ Error al sincronizar: {e}")

    if st.session_state.get("mostrar_saldos_post_sync", False):
        widget_saldos_inline(supabase, user_id)

def pagina_proyeccion(supabase, user_id):
    anio = date.today().year
    fecha_inicio = f"{anio}-01-01"
    fecha_fin = f"{anio}-12-31"

    st.title(f"🔮 Proyección Anual {anio}")

    with st.spinner("Calculando proyección..."):
        
        todos_hist = []
        offset = 0
        while True:
            result = supabase.table("gastos")\
                .select("monto, tipo, fecha_gasto")\
                .eq("user_id", user_id)\
                .lt("fecha_gasto", fecha_inicio)\
                .range(offset, offset + 999)\
                .execute()
            if not result.data:
                break
            todos_hist.extend(result.data)
            offset += 1000

        saldo_inicial = 0
        if todos_hist:
            df_hist = pd.DataFrame(todos_hist)
            saldo_inicial = df_hist.apply(
                lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"], axis=1
            ).sum()

        result_real = supabase.table("gastos")\
            .select("fecha_gasto, monto, tipo")\
            .eq("user_id", user_id)\
            .gte("fecha_gasto", fecha_inicio)\
            .lte("fecha_gasto", fecha_fin)\
            .execute()

        result_presup = supabase.table("presupuestos")\
            .select("fecha, monto")\
            .eq("user_id", user_id)\
            .gte("fecha", fecha_inicio)\
            .lte("fecha", fecha_fin)\
            .execute()

    meses = list(range(1, 13))
    meses_nombres = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                     7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}

    balance_real_mes = {m: None for m in meses}
    if result_real.data:
        df_real = pd.DataFrame(result_real.data)
        df_real["fecha_gasto"] = pd.to_datetime(df_real["fecha_gasto"])
        df_real["mes"] = df_real["fecha_gasto"].dt.month
        df_real["importe"] = df_real.apply(
            lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"], axis=1
        )
        for mes, grupo in df_real.groupby("mes"):
            balance_real_mes[mes] = grupo["importe"].sum()

    balance_presup_mes = {m: 0 for m in meses}
    if result_presup.data:
        df_presup = pd.DataFrame(result_presup.data)
        df_presup["fecha"] = pd.to_datetime(df_presup["fecha"])
        df_presup["mes"] = df_presup["fecha"].dt.month
        for mes, grupo in df_presup.groupby("mes"):
            balance_presup_mes[mes] = grupo["monto"].sum()

    filas = []
    saldo_real = saldo_inicial
    saldo_teorico = saldo_inicial
    mes_actual = date.today().month

    for mes in meses:
        es_real = balance_real_mes[mes] is not None
        balance_r = balance_real_mes[mes] if es_real else None
        balance_p = balance_presup_mes[mes]

        if es_real:
            saldo_real += balance_r
            saldo_real_final = saldo_real
        else:
            saldo_real_final = None

        saldo_teorico += balance_p
        saldo_teorico_final = saldo_teorico

        filas.append({
            "Mes": meses_nombres[mes],
            "Balance Real": balance_r,
            "Saldo Real": saldo_real_final,
            "Presupuesto": balance_p,
            "Saldo Teórico": saldo_teorico_final,
            "es_real": es_real,
            "mes_num": mes
        })

    df_tabla = pd.DataFrame(filas)

    saldo_actual = df_tabla[df_tabla["Saldo Real"].notna()]["Saldo Real"].iloc[-1]
    saldo_dic = df_tabla[df_tabla["mes_num"] == 12]["Saldo Teórico"].iloc[0]
    diferencia = saldo_dic - saldo_actual

    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Saldo actual", f"€{saldo_actual:,.2f}")
    k2.metric("🔮 Proyección diciembre", f"€{saldo_dic:,.2f}")
    k3.metric("📈 Diferencia", f"€{diferencia:,.2f}")

    st.divider()

    fig = go.Figure()

    df_real_plot = df_tabla[df_tabla["Saldo Real"].notna()]
    fig.add_trace(go.Scatter(
        x=df_real_plot["Mes"],
        y=df_real_plot["Saldo Real"],
        mode="lines+markers",
        name="Saldo Real",
        line=dict(color="#3498db", width=2.5),
        marker=dict(size=8),
        hovertemplate="%{x}<br>Saldo Real: €%{y:,.2f}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=df_tabla["Mes"],
        y=df_tabla["Saldo Teórico"],
        mode="lines+markers",
        name="Saldo Teórico",
        line=dict(color="#95a5a6", width=2, dash="dot"),
        marker=dict(size=6),
        hovertemplate="%{x}<br>Saldo Teórico: €%{y:,.2f}<extra></extra>"
    ))

    mes_corte = meses_nombres[mes_actual]
    fig.add_shape(
        type="line",
        x0=mes_corte, x1=mes_corte,
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="orange", width=2, dash="dash")
    )
    fig.add_annotation(
        x=mes_corte, y=1,
        xref="x", yref="paper",
        text="▲ Hoy",
        showarrow=False,
        font=dict(color="orange", size=12),
        yanchor="bottom"
    )

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.3)

    fig.update_layout(
        title=f"Proyección de Saldo {anio}",
        xaxis_title="Mes",
        yaxis_title="€",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Detalle mes a mes")

    df_mostrar = df_tabla.copy()
    df_mostrar["Balance Real"] = df_mostrar["Balance Real"].apply(
        lambda x: f"€{x:,.2f}" if x is not None else "—"
    )
    df_mostrar["Saldo Real"] = df_mostrar["Saldo Real"].apply(
        lambda x: f"€{x:,.2f}" if x is not None else "—"
    )
    df_mostrar["Presupuesto"] = df_mostrar["Presupuesto"].apply(
        lambda x: f"€{x:,.2f}"
    )
    df_mostrar["Saldo Teórico"] = df_mostrar["Saldo Teórico"].apply(
        lambda x: f"€{x:,.2f}"
    )
    df_mostrar[""] = df_mostrar["es_real"].apply(
        lambda x: "✅ Real" if x else "🔮 Proyectado"
    )

    st.dataframe(
        df_mostrar[["Mes", "Balance Real", "Saldo Real",
                    "Presupuesto", "Saldo Teórico", ""]],
        use_container_width=True,
        hide_index=True
    )

def main():
    if not login_page():
        return

    user_id = get_user_id()
    supabase = get_supabase_auth()

    st.sidebar.title("📱 Navegación")

    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state.user = None
        st.session_state.access_token = None
        st.rerun()

    pagina = st.sidebar.radio(
        "Ir a:",
        ["📊 Dashboard", "📈 Histórico", "🔍 Detalle",
         "💳 Bancos", "🔮 Proyección", "📤 Sincronizar"],
        index=0
    )

    st.sidebar.divider()
    balance_app = get_balance_app(supabase, user_id)
    df_saldos, ultima_fecha = get_saldos_actuales(supabase, user_id)

    if df_saldos.empty:
        st.sidebar.info("💳 Sin saldos registrados")
    else:
        total_bancos = df_saldos["monto"].sum()
        diferencia = abs(balance_app - total_bancos)
        if diferencia <= 0.01:
            st.sidebar.success(f"✅ Data cuadrada\n\n€{total_bancos:,.2f}")
        else:
            st.sidebar.warning(f"⚠️ Revisar saldos\n\nDif: €{diferencia:,.2f}")

    if pagina == "📊 Dashboard":
        pagina_dashboard(supabase, user_id)
    elif pagina == "📈 Histórico":
        pagina_historico(supabase, user_id)
    elif pagina == "🔍 Detalle":
        pagina_detalle(supabase, user_id)
    elif pagina == "💳 Bancos":
        pagina_bancos(supabase, user_id)
    elif pagina == "🔮 Proyección":
        pagina_proyeccion(supabase, user_id)
    elif pagina == "📤 Sincronizar":
        pagina_sync(supabase, user_id)

if __name__ == "__main__":
    main()