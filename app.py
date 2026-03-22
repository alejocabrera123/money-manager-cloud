import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import os
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
APP_PASSWORD = os.getenv("APP_PASSWORD")

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Control de acceso
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

# Procesar xlsx de Money Manager
def procesar_xlsx(archivo):
    df = pd.read_excel(archivo)

    # Validar columnas esperadas
    columnas_esperadas = [
        "Según un período", "Cuentas", "Categoría",
        "Subcategorías", "Nota", "EUR", "Ingreso/Gasto", "Descripción"
    ]
    columnas_faltantes = [c for c in columnas_esperadas if c not in df.columns]
    if columnas_faltantes:
        raise ValueError(f"Columnas faltantes en el archivo: {columnas_faltantes}")

    # Filtrar solo cuenta Euros (excluir Airbnb)
    df = df[df["Cuentas"] == "Euros"].copy()

    # Mapear columnas
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

    # Seleccionar solo las columnas necesarias
    df = df[["fecha_gasto", "cuenta", "categoria_consumo",
             "sub_categoria", "consumo", "monto", "tipo", "descripcion"]]

    # Corregir Gastos → Gasto
    df["tipo"] = df["tipo"].replace("Gastos", "Gasto")

    # Limpiar fecha (quedarse solo con la fecha, sin hora)
    df["fecha_gasto"] = pd.to_datetime(df["fecha_gasto"]).dt.date

    # Limpiar valores nulos
    df = df.fillna("")

    return df

# Sincronizar con Supabase
def sincronizar(df, supabase):
    # TRUNCATE
    supabase.table("gastos").delete().neq("id", 0).execute()

    # INSERT
    registros = df.to_dict(orient="records")
    registros_str = []
    for r in registros:
        r["fecha_gasto"] = str(r["fecha_gasto"])
        r["monto"] = float(r["monto"])
        registros_str.append(r)

    # Insertar en lotes de 500
    tamano_lote = 500
    for i in range(0, len(registros_str), tamano_lote):
        lote = registros_str[i:i + tamano_lote]
        supabase.table("gastos").insert(lote).execute()

    return len(registros_str)

# App principal
def main():
    supabase = init_supabase()

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

            # Preview de datos
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

if __name__ == "__main__":
    if check_password():
        main()