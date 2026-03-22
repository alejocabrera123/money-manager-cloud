import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import os
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
APP_PASSWORD = os.getenv("APP_PASSWORD")

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("💰 Money Magnet")
        password = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            if password == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
        return False
    return True

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
    df = df.fillna("")
    return df

def sincronizar(df, supabase):
    supabase.table("gastos").delete().neq("id", 0).execute()
    registros = df.to_dict(orient="records")
    registros_str = []
    for r in registros:
        r["fecha_gasto"] = str(r["fecha_gasto"])
        r["monto"] = float(r["monto"])
        registros_str.append(r)
    for i in range(0, len(registros_str), 500):
        lote = registros_str[i:i + 500]
        supabase.table("gastos").insert(lote).execute()
    return len(registros_str)

def get_gastos_mes(supabase, year, month):
    inicio = date(year, month, 1)
    if month == 12:
        fin = date(year + 1, 1, 1)
    else:
        fin = date(year, month + 1, 1)
    result = supabase.table("gastos")\
        .select("categoria_consumo, monto, tipo")\
        .gte("fecha_gasto", str(inicio))\
        .lt("fecha_gasto", str(fin))\
        .execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()

def get_presupuestos_mes(supabase, year, month):
    inicio = date(year, month, 1)
    result = supabase.table("presupuestos")\
        .select("categoria_consumo, monto")\
        .eq("fecha", str(inicio))\
        .execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()

def pagina_dashboard(supabase):
    st.title("💰 Money Magnet")

    # Navegación de mes
    hoy = date.today()
    if "mes_offset" not in st.session_state:
        st.session_state.mes_offset = 0

    mes_actual = hoy + relativedelta(months=st.session_state.mes_offset)
    year, month = mes_actual.year, mes_actual.month
    nombre_mes = mes_actual.strftime("%B %Y").capitalize()

    col_izq, col_centro, col_der = st.columns([1, 2, 1])
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

    # Cargar datos
    with st.spinner("Cargando datos..."):
        df_gastos = get_gastos_mes(supabase, year, month)
        df_presupuestos = get_presupuestos_mes(supabase, year, month)

    if df_gastos.empty and df_presupuestos.empty:
        st.warning("No hay datos para este mes.")
        return

    # Calcular KPIs
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

    # Tarjetas KPI
    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💸 Total Gastado", f"€{total_gastado:,.2f}")
    k2.metric("💰 Total Ingresos", f"€{total_ingresos:,.2f}")
    k3.metric("⚖️ Balance", f"€{balance:,.2f}")
    k4.metric("🎯 Presupuesto Neto", f"€{presupuesto_total:,.2f}")

    # Tabla por categoría
    st.divider()
    st.subheader("📊 Detalle por Categoría")

    ocultar_cero = st.toggle("Ocultar categorías sin presupuesto (€0)", value=False)

    # Construir tabla combinada
    if not df_gastos.empty:
        real_cat = df_gastos.groupby("categoria_consumo")["importe"].sum().reset_index()
        real_cat.columns = ["categoria_consumo", "real"]
    else:
        real_cat = pd.DataFrame(columns=["categoria_consumo", "real"])

    if not df_presupuestos.empty:
        df_tabla = pd.merge(df_presupuestos, real_cat,
                            on="categoria_consumo", how="left")
        df_tabla["real"] = df_tabla["real"].fillna(0)
    else:
        df_tabla = real_cat.copy()
        df_tabla["monto"] = 0

    df_tabla.columns = ["Categoría", "Presupuesto", "Real"]
    df_tabla["Diferencia"] = df_tabla["Real"] - df_tabla["Presupuesto"]

    # Semáforo
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

    # Filtro categorías €0
    if ocultar_cero:
        df_tabla = df_tabla[df_tabla["Presupuesto"] != 0]

    # Ordenar por importe real descendente (mayor gasto arriba)
    df_tabla = df_tabla.reindex(
        df_tabla["Real"].abs().sort_values(ascending=False).index
    )

    # Formatear montos
    df_mostrar = df_tabla.copy()
    df_mostrar["Presupuesto"] = df_mostrar["Presupuesto"].apply(
        lambda x: f"€{x:,.2f}")
    df_mostrar["Real"] = df_mostrar["Real"].apply(lambda x: f"€{x:,.2f}")
    df_mostrar["Diferencia"] = df_mostrar["Diferencia"].apply(
        lambda x: f"€{x:,.2f}")

    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

def pagina_sync(supabase):
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
            st.success(f"✅ Archivo cargado: **{len(df)} registros** de cuenta Euros detectados")
            st.dataframe(
                df[["fecha_gasto", "categoria_consumo", "monto", "tipo"]].head(10),
                use_container_width=True
            )
            st.caption(f"Mostrando 10 de {len(df)} registros")
            st.divider()
            if st.button("🔄 Sincronizar con Supabase", type="primary"):
                with st.spinner("Sincronizando..."):
                    total = sincronizar(df, supabase)
                    balance = df.apply(
                        lambda r: r["monto"] if r["tipo"] == "Ingreso" else -r["monto"],
                        axis=1
                    ).sum()
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

def main():
    supabase = init_supabase()

    st.sidebar.title("📱 Navegación")
    pagina = st.sidebar.radio(
        "Ir a:",
        ["📊 Dashboard", "📤 Sincronizar"],
        index=0
    )

    if pagina == "📊 Dashboard":
        pagina_dashboard(supabase)
    elif pagina == "📤 Sincronizar":
        pagina_sync(supabase)

if __name__ == "__main__":
    if check_password():
        main()