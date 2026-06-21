# 🧲 MONEY MAGNET — Documento Maestro de Contexto

> Última actualización: 19 de Junio 2026 | Sprints 1–10.3 completados | Sprint 11 en proceso

---

## 1. El proyecto en una frase

Web app personal de finanzas en Python/Streamlit que reemplaza MySQL local + Power BI, con Supabase como backend, accesible desde cualquier dispositivo a coste €0/mes.

---

## 2. Personas


| Rol                       | Persona                               | Notas                                  |
| ------------------------- | ------------------------------------- | -------------------------------------- |
| Product Owner + Developer | David Cabrera                         | Usuario principal                      |
| Usuario Secundario        | Alicia (proyecto "Hola Lluvia")       | Incorporación futura via Supabase Auth |
| Ubicación                 | España                                |                                        |
| Moneda                    | Euro (€)                              |                                        |
| Fuente de datos           | Money Manager (iOS) → exporta `.xlsx` |                                        |


---

## 3. Stack tecnológico e infraestructura


| Capa                      | Tecnología                | Notas                                                                    |
| ------------------------- | ------------------------- | ------------------------------------------------------------------------ |
| Frontend / App            | Streamlit Community Cloud | [https://money-magnet.streamlit.app](https://money-magnet.streamlit.app) |
| Backend / BD              | Supabase (PostgreSQL)     | Free tier, región West EU (Ireland)                                      |
| Auth                      | Supabase Auth             | ✅ Activo — email + contraseña, RLS habilitado                            |
| Lenguaje                  | Python 100%               | Sin JS, sin HTML/CSS propio                                              |
| Gráficos                  | Plotly                    | express + graph_objects                                                  |
| Control de versiones      | GitHub                    | repo `money-manager-cloud` (cuenta: alejocabrera123)                     |
| Automatización keep-alive | GitHub Actions            | ping cada 5 días, evita pausa de Supabase                                |
| Automatización futura     | Make + FastAPI en Render  | Sprint 10 — trigger email → sync automático                              |
| IDE                       | VSCode                    | Mac M5 + Dell Inspiron 15500 (Windows)                                   |


**Constraint inamovible: $0/mes. Cualquier decisión que implique coste se descarta.**

## 4. Esquema de base de datos (Supabase/PostgreSQL)

### `gastos` — tabla principal

```
id                SERIAL PRIMARY KEY
fecha_gasto       DATE NOT NULL
cuenta            VARCHAR(100)         -- siempre 'Euros' (Airbnb filtrado)
categoria_consumo VARCHAR(100)
sub_categoria     VARCHAR(100)
consumo           VARCHAR(200)         -- descripción del gasto (ej: "Mercadona")
monto             DECIMAL(10,2)        -- SIEMPRE positivo
tipo              VARCHAR(10)          -- 'Ingreso' o 'Gasto' (nunca 'Gastos')
descripcion       TEXT
updated_at        TIMESTAMP DEFAULT NOW()
user_id           UUID REFERENCES auth.users(id) -- ✅ Sprint Multi-usuario
```

### `presupuestos`

```
id                SERIAL PRIMARY KEY
categoria_consumo VARCHAR(100) NOT NULL
fecha             DATE NOT NULL        -- primer día del mes (ej: 2026-03-01)
monto             DECIMAL(10,2)        -- con signo: gastos negativos, ingresos positivos
updated_at        TIMESTAMP DEFAULT NOW()
UNIQUE(categoria_consumo, fecha)
user_id           UUID REFERENCES 
auth.users(id) -- ✅ Sprint Multi-usuario UNIQUE(categoria_consumo, fecha) 
```

### `saldos_bancarios`

```
id                SERIAL PRIMARY KEY 
banco             VARCHAR(100) NOT NULL 
monto             DECIMAL(10,2) NOT NULL 
fecha_registro    DATE NOT NULL DEFAULT CURRENT_DATE 
user_id           UUID REFERENCES 
auth.users(id) -- ✅ Sprint Multi-usuario 
```

Lógica: cada guardado inserta snapshot completo con fecha. No se borran registros anteriores (historial).

### `carteras` — contenedor de carteras ⚠️ NUEVA en Sprint 9.2

```
id                SERIAL PRIMARY KEY
user_id           UUID REFERENCES auth.users(id)
nombre            VARCHAR(100)        -- ej: "XTB Europa", "Interactive Brokers"
moneda            VARCHAR(5)          -- 'EUR', 'USD', etc.
created_at        TIMESTAMP DEFAULT NOW()
```

Lógica: cada usuario puede tener hasta 5 carteras. Al crear una nueva, se ofrece carga xlsx inicial o entrada manual desde cero.

### `cartera` — transacciones de inversión

```
id                SERIAL PRIMARY KEY 
user_id           UUID REFERENCES auth.users(id)
cartera_id        INTEGER REFERENCES carteras(id)  -- ⚠️ NUEVO Sprint 9.2
ticker            VARCHAR(20)
tipo              VARCHAR(10)         -- 'Compra' o 'Venta'
fecha_operacion   DATE
cantidad          DECIMAL(12,6)       -- fracciones posibles
precio_entrada    DECIMAL(12,4)
comision          DECIMAL(10,4) DEFAULT 0  -- ⚠️ NUEVO Sprint 9.2 — opcional, coste real = (cantidad × precio) + comision
precio_actual     DECIMAL(12,4)       -- sobreescrito por yfinance
estado            VARCHAR(10) DEFAULT 'activo'  -- ⚠️ NUEVO Sprint 9.2 — 'activo' | 'eliminado' (soft delete)
updated_at        TIMESTAMP DEFAULT NOW()
```

Estrategia nueva: **Supabase es la fuente de verdad desde Sprint 9.2**. xlsx upload queda como opción de carga inicial al crear una cartera nueva. Entrada manual es el flujo principal ongoing. Nunca se borra físicamente — soft delete con campo `estado`.

### `cartera_tickers` — catálogo de activos

```
id                SERIAL PRIMARY KEY 
user_id           UUID REFERENCES auth.users(id)
ticker            VARCHAR(20) 
nombre            VARCHAR(200) 
sector            VARCHAR(50) -- 'Technology', 'ETF', 'Gold', etc. 
moneda            VARCHAR(5) DEFAULT 'USD' 
updated_at        TIMESTAMP DEFAULT NOW() UNIQUE(ticker, user_id)
```

Estrategia sync: UPSERT — preserva sectores asignados manualmente.

### `cartera_efectivo` — Nueva tabla del Sprint 9.3

```
id                SERIAL PRIMARY KEY
user_id           UUID REFERENCES auth.users(id)
cartera_id        INTEGER REFERENCES carteras(id)
monto             DECIMAL(12,2) NOT NULL
fecha_registro    DATE NOT NULL DEFAULT CURRENT_DATE
```

Lógica: snapshot editable, igual que `saldos_bancarios`. Cada guardado inserta nuevo registro con fecha; no se borran anteriores. Se muestra en un expander dentro de cada pestaña de cartera y se suma a "Valor actual" en los KPIs.

### `presupuesto_mensual_total` — ⚠️ DESCARTADA

Tabla vacía, no se usa. Los totales se calculan dinámicamente con `SUM()` sobre `presupuestos`.

---

## 5. Estructura de archivos

```
money-manager-cloud/
├── .env                          # credenciales locales (NO en GitHub)
├── app.py                        # toda la app (único archivo Python)
├── requirements.txt
├── README.md
├── .vscode/ 
    └── settings.json # intérprete Python 3.9 para VSCode 
└── .github/
    └── workflows/
        └── keep-alive.yml        # ping a Supabase cada 5 días
```

**Proyecto es monolítico — todo en `app.py`.** No hay carpetas `pages/`, `utils/`, ni módulos separados.

### requirements.txt actual

```
streamlit
supabase
pandas
openpyxl
python-dotenv
python-dateutil
plotly
yfinance
```

---

## 6. Navegación y páginas (app.py)

Menú lateral con `st.sidebar.radio()`. Orden actual:


| Página         | Función                | Contenido                                                                                 |
| :------------- | :--------------------- | :---------------------------------------------------------------------------------------- |
| 📊 Dashboard   | `pagina_dashboard()`   | KPIs mes actual + gráficos históricos (barras, waterfall, mensual, acumulado)             |
| 📋 Presupuesto | `pagina_presupuesto()` | Tabla estilo Excel: categorías × 12 meses, 2 sub-filas, colores G/R, selector de año      |
| 🔍 Detalle     | `pagina_detalle()`     | Tabla filtrable (año/mes/categoría), todos los registros                                  |
| 💳 Bancos      | `pagina_bancos()`      | Saldos editables, cuadre vs balance app, historial                                        |
| 🔮 Proyección  | `pagina_proyeccion()`  | Gráfico real vs teórico 2026, tabla mes a mes                                             |
| 💼 Cartera     | `pagina_cartera()`     | Pestañas por cartera; KPIs, sector/ticker/historial, donuts; entrada manual de posiciones |
| 🤖 Prompt IA   | `pagina_prompt()`      | Genera prompt financiero copiable para LLMs externos (Sprint 10.1)                        |
| 📤 Sincronizar | `pagina_sync()`        | Upload xlsx, preview, TRUNCATE+INSERT                                                     |


**Sidebar también muestra:** indicador ✅/⚠️ de cuadre bancos vs app + botón 🚪 Cerrar sesión.

---

## 7. Variables de entorno

### `.env` (local)

```env
SUPABASE_URL = "https://mkqymfnsXXXXXXXXXXXX.supabase.co" SUPABASE_KEY=sb_publishable_XXXX 
```

⚠️ `APP_PASSWORD` eliminado tras Sprint Multi-usuario. 

### Streamlit Cloud Secrets (formato TOML obligatorio)

```toml
SUPABASE_URL = "https://mkqymfnsXXXXXXXXXXXX.supabase.co" 
SUPABASE_KEY = "sb_publishable_XXXX" 
```

**Nota crítica:** La URL debe ser exactamente `https://xxxx.supabase.co` — sin `/rest/v1/` ni nada al final. Streamlit Secrets requiere formato TOML con comillas y espacios alrededor del "="

---

## 8. Lógica de negocio — reglas inamovibles

**Sync de datos:**

- Estrategia gastos: `DELETE` por `user_id` + `INSERT` en lotes de 500. Money Manager exporta historial completo → limpiar y reinsertar es correcto.
- Tras Sprint Multi-usuario: el DELETE y el INSERT filtran siempre por `user_id` del usuario autenticado.
- Filtro Airbnb: `df[df["Cuentas"] == "Euros"]` — más robusto que excluir por nombre.
- Normalización: `"Gastos"` → `"Gasto"` (legacy del script original, se mantiene).
- `monto` es SIEMPRE positivo. El signo se calcula en Python: `importe = monto if tipo == "Ingreso" else -monto`.
- Estrategia presupuestos: UPSERT vía CSV upload. Si existe `(categoria_consumo, fecha, user_id)` → actualiza; si no → inserta. Nunca borra registros de otros meses.
- Formato CSV presupuestos: columnas `categoria_consumo`, `fecha` (YYYY-MM-01), `monto` (ingresos positivos, gastos negativos).

**Presupuesto:**

- Presupuesto = balance neto esperado (no gasto bruto). Puede ser negativo (gasto esperado) o positivo (ingreso esperado).
- La comparación semáforo es siempre `real vs presupuesto` en términos de balance neto.
- Carga de presupuestos vía CSV upload en `pagina_sync()` con UPSERT sobre `(categoria_consumo, fecha, user_id)`. 
- `CATEGORIAS_OTROS` — lista hardcodeada en `app.py` con categorías menores agrupadas en Dashboard.

**Proyección anual:**

- Saldo inicial 2026 = suma acumulada de todos los importes hasta 31/12/2025 (calculado automático desde Supabase).
- Meses pasados: datos reales. Meses futuros: suma de presupuestos del mes.
- Investment se trata como cualquier otra categoría (no hay inversión de signo).

**Paginación Supabase:**

- Límite por defecto: 1.000 registros. Todas las queries sobre `gastos` usan bucle con `.range(offset, offset+999)`.

**Cuadre bancario:**

- Tolerancia: diferencia ≤ €0.01 se considera cuadrado (evita falsos positivos por redondeo).

---

## 9. Funciones principales en app.py

```python
init_supabase()                                   # @st.cache_resource — cliente Supabase (anon, pre-auth)
get_supabase_auth()                               # cliente con token del usuario autenticado inyectado via postgrest.auth()
login_page()                                      # Supabase Auth — email + contraseña, guarda user y access_token en session_state
get_user_id()                                     # retorna st.session_state.user.id
procesar_xlsx(archivo)                            # lee .xlsx, filtra Euros, mapea columnas, normaliza
sincronizar(df, supabase, user_id)                # DELETE por user_id + INSERT en lotes de 500
get_todos_gastos(_supabase, user_id)              # @st.cache_data(ttl=300) — query paginada completa
get_gastos_mes(supabase, year, month, user_id)    # query por mes específico
get_presupuestos_mes(supabase, year, month, user_id)  # query presupuestos por mes
get_balance_app(_supabase, user_id)               # suma total de importes (paginado)
get_saldos_actuales(_supabase, user_id)           # último snapshot de saldos bancarios
guardar_saldos(supabase, saldos_dict, user_id)    # INSERT snapshot completo con fecha hoy
widget_saldos_inline(supabase, user_id)           # widget post-sync para actualizar saldos
pagina_dashboard(supabase, user_id)               # KPIs + tabla presupuesto vs real + Otras Categorías
pagina_historico(supabase, user_id)               # barras ingresos/gastos + waterfall/mensual/acumulado
pagina_detalle(supabase, user_id)                 # pivot table categoría × meses
pagina_bancos(supabase, user_id)                  # saldos editables + cuadre + historial
pagina_proyeccion(supabase, user_id)              # gráfico real vs teórico, año dinámico
pagina_sync(supabase, user_id)                    # upload xlsx gastos + upload CSV presupuestos
main()                                            # login_page() → get_user_id() + get_supabase_auth() → navegación
procesar_xlsx_cartera(archivo)                    # lee pestaña 'INV Esp', extrae transacciones y tickers
sincronizar_cartera(df_t, df_tk, supabase, user_id)  # upsert tickers + DELETE/INSERT cartera
get_cartera(_supabase, user_id)                   # @st.cache_data(ttl=300) — JOIN cartera + cartera_tickers
get_tickers_sin_sector(_supabase, user_id)        # @st.cache_data(ttl=300) — tickers con sector NULL
widget_asignar_sector(supabase, user_id)          # selector sector para tickers nuevos sin sector
pagina_cartera(supabase, user_id)                 # KPIs + tabs sector/ticker/historial
_vista_por_sector(df)                             # tabla + donut por sector
_vista_por_ticker(df)                             # tabla + donut por ticker, precio medio ponderado
_vista_historial(df)                              # tabla cronológica de todas las operaciones
get_efectivo_actual(_supabase, user_id, cartera_id)        # último snapshot de efectivo
guardar_efectivo(supabase, user_id, cartera_id, monto)     # INSERT nuevo snapshot
widget_efectivo(supabase, user_id, cartera_id, moneda_sym) # UI expander
get_presupuestos_anio(year, user_id)                  # suma presupuestos por categoría para el año completo
get_categorias_usuario(_supabase, user_id)            # @st.cache_data(ttl=300) — categorías únicas de presupuestos
obtener_tipo_cambio_usd_eur()                         # @st.cache_data(ttl=3600) — EUR por 1 USD vía yfinance
generar_tabla_anual(supabase, user_id, year)          # tabla Presupuesto Anual | Real YTD | % Alcance (maneja caso sin presupuesto)
generar_tabla_mensual_ingresos_gastos(supabase, user_id, year)  # tabla Ingresos/Gastos por mes (YTD)
generar_seccion_cartera(supabase, user_id)            # bloque markdown por cartera: efectivo, valor, sector, últimas 10 compras
generar_prompt_master(supabase, user_id, pais, perfil, generar_tabla_mensual_ingresos_gastos(supabase, user_id, year, categorias_inversion)  # tabla Ingresos/Gastos/Aportaciones/Tasa ahorro por mes (YTD)
generar_prompt_master(supabase, user_id, pais, perfil, categorias_inversion, deuda_importe, deuda_cuota, deuda_fecha_fin, contexto_estrategico)  # ensambla el prompt completo
pagina_prompt(supabase, user_id)                      # UI página 🤖 Prompt IA — 5 niveles MiFID, deudas condicional, contexto estratégico

```

---

## 10. Plan de sprints


| Sprint        | Nombre                                                                 | Estado       |
| :------------ | :--------------------------------------------------------------------- | :----------- |
| 1             | Base de datos en la nube                                               | ✅ Completado |
| 2             | Sincronización desde xlsx                                              | ✅ Completado |
| 3             | Dashboard Core                                                         | ✅ Completado |
| 4             | Dashboard Histórico y Detalle                                          | ✅ Completado |
| 5             | Saldos Bancarios                                                       | ✅ Completado |
| 6             | Proyección Anual                                                       | ✅ Completado |
| Multi-usuario | Auth + RLS + aislamiento de datos                                      | ✅ Completado |
| Ajuste        | Fix paginación, cache sidebar, invalidación quirúrgica                 | ✅ Completado |
| 7             | Pivot Detalle, CSV Presupuestos, Otras Categorías                      | ✅ Completado |
| 8             | Cartera v1 — upload xlsx Google Sheets + visualización                 | ✅ Completado |
| 9             | Cartera v2 — precio en tiempo real vía yfinance                        | ✅ Completado |
| 9.2           | Cartera v3 — multi-cartera + entrada manual de posiciones              | ✅ Completado |
| 9.3           | Efectivo en Bróker — saldo editable por cartera                        | ✅ Completado |
| 10.1          | Master Prompt Engine (MVP)                                             | ✅ Completado |
| 10.2          | Refinamiento Master Prompt (feedback 2 iteraciones)                    | ✅ Completado |
| 10.3          | Backlog mayor (deudas, patrimonio histórico, reorden)                  | ✅ Completado |
| 11            | Tabla presupuesto estilo Excel (versión Streamlit 80%)                 | ✅ Completado |
| 12            | Configurador de usuario (user_preferences + CATEGORIAS_OTROS dinámico) | 🔄 Diseñado  |
| 13            | Fixes de cartera (FIFO/LIFO + cartera_snapshots)                       | 🔄 Diseñado  |
| 14            | Capa de IA (alertas, proyección estadística, Gemini)                   | 🔄 Diseñado  |
| 15            | Email automation (Make + FastAPI + Render)                             | 🔄 Diseñado  |


---

## 11. Sprint activo y próximos sprints inmediatos
### Sprint 12 — Configurador de usuario
🔄 Diseñado — pendiente de arrancar
**Alcance:**
- `user_preferences`: tabla Supabase (una fila por usuario, UPSERT). 
  Campos: perfil_inversion, deuda_importe, deuda_cuota, deuda_fecha_fin, 
  contexto_estrategico, pais, cuenta_personal, categorias_inversion.
  Los inputs de pagina_prompt() se cargan desde esta tabla al entrar y se 
  guardan con botón "💾 Guardar preferencias".
- `CATEGORIAS_OTROS` dinámico: UI para que cada usuario gestione qué 
  categorías se agrupan en "Otras Categorías", en lugar de lista hardcodeada.
### Sprint 13 — Fixes de cartera
🔄 Diseñado — pendiente de arrancar
**Alcance:**
- FIFO/LIFO para cerrar posiciones con match de lote específico
- `cartera_snapshots`: tabla para historial de valor de cartera a lo largo 
  del tiempo (valor de mercado vs coste por fecha)

---

## 12. Pins activos / alertas


| Pin                               | Detalle                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ℹ️ keep-alive.yml                 | Hace ping HTTP simple a la URL pública de Supabase. Si Supabase exige query autenticada para evitar pausa, actualizar.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ℹ️ Cache TTL 300s                 | `get_todos_gastos`, `get_balance_app` y `get_saldos_actuales` cachean 5 minutos. Se invalidan quirúrgicamente tras sync y tras guardar saldos.                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ℹ️ CATEGORIAS_OTROS               | Lista hardcodeada en `app.py`. Mover a configurador de usuario en sprint futuro.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ℹ️ CSV presupuestos               | Creación de CSV requiere Terminal en Mac. Pendiente: generación de plantilla desde la app en sprint futuro (Configurador).                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ℹ️ yfinance                       | scraping de Yahoo Finance, sin garantía de disponibilidad. Fallback automático a precio del xlsx. Conversión multi-bolsa vía `PREFIJO_A_SUFIJO_YF` (Sprint 9.2): `LON:→.L`, `GER:→.DE`, `PAR:→.PA`, `AMS:→.AS`, `MIL:→.MI`, `MAD:→.MC`, `SIX:→.SW`, `TYO:→.T`, `HKG:→.HK`, `TOR:→.TO`. Casos legacy: `BRK.B→BRK-B`, ETFs Londres sin prefijo (`GLDV`, `CSPX`, `IGLN`) → `XXX.L`                                                                                                                                                                                                                          |
| 💡 Tabla presupuesto estilo Excel | Idea propuesta por David: tabla con categorías en filas (2 sub-filas Gasto/Presupuesto), meses en columnas, colores G/P automáticos — réplica de su Excel manual. Versión "80%" viable en Streamlit con pandas Styler (sin sticky headers/columns ni bandas de color por categoría). Nota: Candidata a Sprint 11. Nota: Para usuarios sin presupuesto (ej. Alicia): se omite la fila "Presupuesto" y la fila "Gasto" se muestra sin color condicional (mismo patrón que generar_tabla_anual()). Nota: La versión completa cuando pase a Vercel/Reflex (sticky, edición inline + autoguardado a Supabase) |


---

## 13. Decisiones técnicas fijas (no se cuestionan)

- `**monto` siempre positivo** — el signo se aplica en Python según `tipo`.
- **TRUNCATE + INSERT es la estrategia correcta para `gastos`** — Money Manager exporta historial completo siempre.
- **Cartera — Supabase es la fuente de verdad desde Sprint 9.2** — xlsx solo como carga inicial al crear cartera nueva. Entrada manual es el flujo ongoing.
- **Cartera — soft delete siempre** — nunca borrado físico. Campo `estado`: 'activo' | 'eliminado'.
- **Cartera — posiciones netas por ticker** — Por Sector y Por Ticker calculan `compras − ventas` (cantidad y valor). Cantidad neta = 0 → activo no aparece (posición cerrada). Historial siempre muestra todas las transacciones individuales sin netear.
- **Cartera — ticker como clave de match** — el ticker guardado debe ser idéntico (incluyendo prefijo de mercado, ej. `LON:IDUS`) entre todas las transacciones del mismo activo, o no se calculará correctamente la posición neta. El selector de Mercado en el formulario manual ayuda a mantener consistencia.
- **Cartera** — cálculo de `Invertido` usa coste medio de compra por ticker para las ventas (no precio de venta), evitando inflar el `invertido neto`.
- `**"Gastos"` → `"Gasto"`** — normalización legacy heredada, se mantiene.
- **Filtro de cuenta personal configurable por el usuario** — `procesar_xlsx()` recibe `nombre_cuenta` como parámetro; `pagina_sync()` detecta las cuentas disponibles en el xlsx y permite seleccionar cuál sincronizar (preselecciona "Euros" si existe). Reemplaza el filtro hardcodeado de Sprints 1-9.
- `**presupuesto_mensual_total` descartada** — totales se calculan dinámicamente.
- **Monolítico en `app.py`** — sin separación en módulos por ahora.
- **Sin frontend propio** — Streamlit gestiona todo el HTML/CSS.
- **Gestión de usuarios vía Supabase dashboard** — sin UI de administración en la app.

---

## 14. Comandos útiles

### Arrancar la app en local (DELL Inspirion)

```bash
streamlit run app.py
```

### Arrancar la app en local (Mac)

```bash
/Users/davidcabrera/Library/Python/3.9/bin/streamlit run app.py 
```

### Ver estructura de archivos (PowerShell) (DELL)

```powershell
Get-ChildItem -Recurse -Force | Where-Object { $_.FullName -notmatch '\.git' } | Select-Object FullName | Sort-Object FullName
```

### Ver estructura de archivos (PowerShell)(Mac)

```zsh
find . -not -path '*/.git*' | sort
```

### Instalar dependencias

```bash
pip install -r requirements.txt
```

### Instalar dependencias (Mac)

```bash
pip3 install -r requirements.txt 
```

### Subir cambios a GitHub (flujo estándar)

```bash
git add .
git commit -m "descripción del cambio"
git push origin main
```

### Si falla autenticación en git push (renovar token)

```bash
git remote set-url origin https://alejocabrera123:TU_TOKEN@github.com/alejocabrera123/money-manager-cloud.git git push origin main 
```

- Token: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Mac.M5 → Regenerate. Marcar solo scope `repo`.

### Ver estado del repo

```bash
git status
git log --oneline -5
```

### Deshacer último commit (sin perder cambios)

```bash
git reset --soft HEAD~1
```

---

## 15. Notas técnicas importantes

- **Supabase pausa proyectos gratuitos** sin actividad en 7 días → mitigado con GitHub Actions keep-alive.
- **Streamlit Community Cloud** entra en sleep por inactividad — se reactiva en segundos, aceptable para uso personal.
- `**st.session_state`** es el mecanismo para persistir estado entre reruns (mes_offset, saldos_edit, mostrar_saldos_post_sync, etc.).
- `**@st.cache_resource`** para el cliente Supabase (una sola instancia). `**@st.cache_data(ttl=300)**` para datos — se invalida manualmente con `st.cache_data.clear()` tras sync.
- **Plotly en requirements.txt es obligatorio** — Streamlit Cloud no lo incluye por defecto (bug detectado en Sprint 4).
- `**openpyxl`** es la dependencia que permite a pandas leer `.xlsx`.
- **Lotes de 500** en INSERT — Supabase puede rechazar inserts masivos en un solo request con 3000+ registros.
- **Colores de gráficos:** verde `#82c9a0`, rojo `#e8968a`, azul `#3498db`, gris `#95a5a6`.
- **Supabase Auth con Streamlit:** token persistido en `st.session_state.access_token`, inyectado en cada request via `client.postgrest.auth(token)`. 
- **SUPABASE_URL debe ser** `https://xxxx.supabase.co` — sin `/rest/v1/` al final. Error frecuente al configurar `.env` o Streamlit Secrets. 
- **Streamlit Secrets requiere formato TOML** — con comillas y espacios: `KEY = "value"`, no `KEY=value`. 
- **Python en Mac:** usar `pip3` en lugar de `pip`. Intérprete en `/Users/davidcabrera/Library/Python/3.9/bin/python3`. 
- **Paginación:** el bucle while solo usa `if not result.data: break`. Nunca añadir condición `if len < 1000: break` — causa bug silencioso con múltiplos exactos de 1000 registros.
- **Cache quirúrgico:** usar siempre `función.clear()` en lugar de `st.cache_data.clear()` global — el clear global afecta a todos los usuarios.
- **Funciones cacheadas con cliente Supabase:** el parámetro debe llamarse `_supabase` (con guión bajo) para que `@st.cache_data` no intente serializarlo.
- **Cartera — parseo xlsx Google Sheets:** las celdas con GOOGLEFINANCE son fórmulas no evaluadas al exportar a xlsx. Se extrae el nombre con regex `r'"([^"]+)"\s*\)$'` y el precio fallback con `r',\s*([\d.]+)\s*\)'`. El sector se cruza desde la tabla resumen por ticker (filas 13-27 de la pestaña INV Esp).
- **Cartera — colores G/P:** implementados con pandas Styler (`map`). Verde `#2ecc71`, rojo `#e74c3c`. Negrita en filas pendiente para Reflex.

---

## 16. Horizonte futuro (fuera del roadmap actual)


| Proyecto / Feature                                | Notas                                                                                                                                                                                                                                                                                                                        |
| :------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Gemma 4 como alternativa a Gemini**             | Apache 2.0, open-weight, disponible via Groq API (gratuito). Anotado en backlog de ideas para Sprint 11.                                                                                                                                                                                                                     |
| **Reflex**                                        | Alternativa a Streamlit si se necesita control CSS/Bootstrap. No viable en Streamlit.                                                                                                                                                                                                                                        |
| **Airbnb**                                        | Cuenta separada, datos excluidos actualmente. Sprint futuro dedicado.                                                                                                                                                                                                                                                        |
| **Cartera & Patrimonio — Net Worth**              | Sprint 9 completado (precio RT). Layout dos columnas con placeholder gráfico histórico. Vista Net Worth pendiente.                                                                                                                                                                                                           |
| **Registro de inversiones nativo**                | ✅ Completado — Sprint 9.2. Entrada manual de posiciones + multi-cartera. Ver changelog (sección 19).                                                                                                                                                                                                                         |
| **Configurador de usuario**                       | Ver sección 18.2. Sprint futuro dedicado.                                                                                                                                                                                                                                                                                    |
| **Gráfico histórico cartera**                     | Valor de mercado vs coste a lo largo del tiempo. Requiere tabla `cartera_snapshots` con snapshot diario al sincronizar. Por ticker y global.                                                                                                                                                                                 |
| **Importación cartera estándar**                  | Formato CSV estándar para que otros usuarios (ej: Alicia) puedan importar su cartera sin depender de la estructura del xlsx de David.                                                                                                                                                                                        |
| **Cerrar posición con match de lote (FIFO/LIFO)** | Pendiente desde Sprint 9.2. El cálculo actual de "Invertido" usa precio medio de compra por ticker (parche en 9.3), pero no rastrea qué lote específico se vendió. Sprint futuro si se necesita detalle por lote.                                                                                                            |
| **Tabla presupuesto editable (Vercel/Reflex)**    | Misma tabla estilo Excel pero con edición inline de presupuestos + autoguardado (botón "Guardar" o modal "¿guardar cambios?" al cambiar de página) → UPSERT a `presupuestos`. Reemplazaría el flujo CSV actual. Fusionar con Configurador de usuario (18.2) cuando se implemente.                                            |
| **user_preferences**                              | Tabla Supabase con una fila por usuario (UPSERT). Guarda perfil MiFID, deuda (importe/cuota/fecha fin), contexto estratégico, país, cuenta personal por defecto, categorías de inversión. Reemplaza los inputs no persistidos de pagina_prompt(). Sprint futuro — candidato a fusionarse con Configurador de usuario (18.2). |

---

### 17. Dudas

> Sin dudas por ahora 25 mayo. Capitulo vivo

---

## 18. Funcionalidades futuras (requieren migración o sprint dedicado)

### 18.1 Para cuando migremos a Reflex

Funcionalidades no viables en Streamlit nativo, pendientes para cuando se adopte Reflex:


| Funcionalidad               | Detalle                                                                          |
| --------------------------- | -------------------------------------------------------------------------------- |
| Pivot table jerárquica      | Filas colapsables tipo Excel (categoría → subcategoría → consumo) usando AG Grid |
| Header sticky en tablas     | El encabezado permanece visible al hacer scroll vertical en la página            |
| Colorear filas individuales | Ej: fila "Otras Categorías" en azul oscuro                                       |
| Tooltips en celdas          | Burbuja al pasar cursor sobre celdas de tabla con información adicional          |


### 18.2 Configurador de usuario (sprint futuro)

Panel de configuración personal dentro de la app. Ideas y características a discutir:

| Característica                    | Detalle                                                                                                                                                                       |
| :-------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gestión de Otras Categorías       | UI para seleccionar qué categorías se agrupan en "Otras Categorías" en el Dashboard, en lugar de lista hardcodeada                                                            |
| Generación de plantilla CSV       | Botón para descargar plantilla de presupuesto con las categorías reales del usuario, lista para rellenar e importar                                                           |
| Editor manual de presupuestos     | Alternativa al CSV: tabla editable directamente en la app por categoría y mes                                                                                                 |
| Preferencias de visualización     | Configurar colores, categorías a mostrar/ocultar, orden de páginas                                                                                                            |
| Cuenta personal por defecto       | Guardar la cuenta seleccionada (ej. "Euros", "Dinero") como preferencia del usuario para no tener que elegirla en cada sync                                                   |
| Tabla presupuesto editable inline | Ver horizonte futuro — reemplazo del CSV/editor manual cuando se migre a Reflex/Vercel                                                                                        |
| Tabla presupuesto editable inline | Ver horizonte futuro — reemplazo del CSV/editor manual cuando se migre a Reflex/Vercel                                                                                        |
| Preferencias Prompt IA            | Persistir en Supabase los inputs de pagina_prompt(): perfil MiFID, deuda, contexto estratégico, país. Tabla user_preferences — una fila por usuario, UPSERT en cada guardado. |

---

## 19. Changelog (desde ahora se guardara un historial)

### Sprint 9.2 — Cartera v3 (13 Jun 2026)

**Implementado:**

- **Multi-cartera**: tabla `carteras` (id, user_id, nombre, moneda, created_at). Hasta 5 carteras por usuario. Cada una en su propia pestaña (`st.tabs()`), con KPIs, sector/ticker/historial independientes.
- **Entrada manual de posiciones**: formulario (`st.form()`) con ticker, mercado (selector con prefijos), tipo (Compra/Venta), fecha, cantidad, precio, comisión opcional. INSERT directo a `cartera`, nunca TRUNCATE.
- **Soft delete**: campo `estado` ('activo'/'eliminado'). Botón 🗑️ en historial, toggle "Ver posiciones eliminadas" con botón ↩️ Restaurar.
- **Posiciones netas (Compra − Venta)**: `_vista_por_sector` y `_vista_por_ticker` calculan cantidad y valor netos por ticker. Si la cantidad neta llega a 0, el activo desaparece de los resúmenes (posición cerrada). El historial sigue mostrando todas las transacciones individuales.
- **Selector de mercado multi-bolsa**: diccionario `MERCADO_A_PREFIJO` (EE.UU., Londres, Alemania, Francia, Países Bajos, Italia, España, Suiza, Japón, Hong Kong, Canadá) → prefijo guardado en `ticker` (ej. `LON:IDUS`). `convertir_ticker_yfinance` usa `PREFIJO_A_SUFIJO_YF` para mapear cada prefijo al sufijo yfinance correspondiente (`.L`, `.DE`, `.PA`, etc.).
- **Nombre real vía yfinance**: al añadir una posición manual, se consulta `yf.Ticker(...).info["longName"]` para poblar `cartera_tickers.nombre` (en vez de dejar el ticker como nombre). Script de un solo uso `fix_nombres.py` corrido para normalizar nombres de tickers existentes.
- `**sincronizar_cartera()` adaptada**: ahora recibe `cartera_id` y borra/inserta solo dentro de esa cartera (`DELETE ... WHERE cartera_id = X`), sin afectar otras carteras del usuario.
- `**pagina_sync()`**: sección de carga inicial xlsx ahora pide seleccionar la cartera destino antes de subir.
- **Historial restaurado a tabla** (no lista de texto), con columnas: Fecha, Activo, Ticker, Tipo, Cantidad, Precio, Precio actual, Posición inicial, Posición actual, G/P.

**Bugs corregidos durante el sprint:**

- Tickers añadidos manualmente con prefijo distinto al del xlsx (ej. `DFNS` vs `LON:DFNS`) generaban duplicados — corregido unificando el ticker al formato existente.
- Nombres de `cartera_tickers` para tickers manuales mostraban el ticker en vez del nombre completo — corregido con yfinance lookup.

**Decisión pendiente / fuera de scope para 9.2:**

- "Cerrar posición" con match de lote específico (FIFO/LIFO) — el cálculo actual es agregado por ticker (compras − ventas), correcto para totales pero no rastrea qué lote específico se vendió. Sprint futuro si se necesita detalle por lote.

### Sprint 9.3 — Efectivo en Bróker (13 Jun 2026)

Implementado:

- Nueva tabla `cartera_efectivo` (id, user_id, cartera_id, monto, fecha_registro). Snapshot editable con la misma lógica que `saldos_bancarios` — cada guardado inserta un nuevo registro con fecha, nunca se sobrescribe ni se borra el historial.
- `get_efectivo_actual()`: devuelve el último snapshot (monto + fecha) para una cartera específica.
- `guardar_efectivo()`: INSERT de un nuevo snapshot con la fecha de hoy.
- `widget_efectivo()`: expander dentro de cada pestaña de cartera, muestra el efectivo disponible actual con fecha de última actualización, y permite registrar un nuevo monto con botón "💾 Guardar efectivo".
- Integración en KPIs: "Valor actual" ahora = valor de posiciones (RT) + efectivo disponible de esa cartera. El efectivo se muestra desglosado en el `help` del KPI.
- Migración del registro legacy "Cash" (`cartera` id=1, ticker="Cash", $14.25) → insertado como snapshot inicial en `cartera_efectivo` con su fecha original (2026-03-30), y soft-delete (`estado='eliminado'`) de la fila original en `cartera` para que deje de aparecer en Por Ticker/Por Sector/Historial.

Fix de cálculo — "Invertido":

- Bug identificado: el cálculo de `total_invertido` restaba las ventas usando el **precio de venta** como si fuera el coste de adquisición, inflando el invertido neto. Detectado al comparar contra XTB real: diferencia de $12.89 atribuible exactamente a las 3 ventas del periodo (META, DFNS, GLDV).
- Corrección: para cada ticker con ventas, se calcula el **precio medio de compra** (`Σ(precio_entrada × cantidad) / Σcantidad` sobre las compras de ese ticker) y se usa ese precio medio × cantidad vendida como el coste a restar de `total_invertido`. `total_actual` no cambia (correctamente usa el valor real de venta).
- Validado contra datos reales de XTB: Invertido $2,463.04 vs $2,463.07 XTB (diff 3¢), G/P $396.18 vs $396.17 XTB (diff 1¢) — diferencias atribuibles a redondeo normal.

Decisión pendiente / relacionada:

- El fix de "Invertido" es un parche puntual para el cálculo agregado por ticker. La solución completa (tracking de lotes FIFO/LIFO para "cerrar posición") sigue pendiente como en 9.2 — si se implementa, este cálculo de coste medio quedaría obsoleto/reemplazado.

### Fix: Selector de cuenta dinámico en sincronización de gastos (13 Jun 2026)

> después del Sprint 9.3:

- `procesar_xlsx()` ahora recibe `nombre_cuenta` como parámetro (antes hardcodeado a "Euros").
- `pagina_sync()` detecta automáticamente las cuentas disponibles en el xlsx subido (`df["Cuentas"].unique()`) y muestra un selector — preselecciona "Euros" si existe, sino la primera disponible.
- Validación añadida: si el xlsx tiene columnas duplicadas (visto en exports de Money Manager de otros usuarios), se muestra un warning informativo sin bloquear el flujo.
- **Motivo:** el export de Money Manager de Alicia usa "Dinero" como nombre de cuenta en lugar de "Euros" — el filtro hardcodeado bloqueaba su sincronización.
- Validado con datos reales: 42 registros de la cuenta "Dinero" de Alicia cargados correctamente.

### Sprint 10.1 — Master Prompt Engine (14 Jun 2026)

Nueva página "🤖 Prompt IA" que agrega automáticamente la situación financiera del usuario en un prompt copiable para LLMs externos.

**Estructura del prompt:** Contexto (país/perfil/categorías de inversión, inputs no persistidos) → Saldos → Año actual (Presupuesto Anual vs Real YTD con % Alcance, saldo inicial, balance YTD, progreso del año, evolución mensual Ingresos/Gastos) → Cartera (por cartera: efectivo, valor, sector, últimas 10 compras) → Instrucciones.

**Decisiones clave:**

- Vista anual con % Alcance reemplaza comparación mensual — resuelve falsa alarma por sueldo no registrado a mitad de mes
- Maneja usuarios sin presupuesto (tabla simplificada solo con reales YTD)
- "Categorías de inversión" como multiselect dinámico, sin hardcoding

**Validado:** 2 iteraciones de testing con Gemini, Claude y ChatGPT. Feedback consolidado → Sprint 10.2.

### Sprint 10.2 — Refinamiento Master Prompt Engine (20 Jun 2026)

**Implementado:**

- **Desvío vs calendario**: nueva columna en `generar_tabla_anual()` — `% Alcance − % año transcurrido`, formateada como `+25 pp` / `-12 pp`. Nota explicativa al pie con el % del año transcurrido del día actual.
- **Meses de cobertura**: línea automática en Sección 2 del prompt — `total_bancos / gasto_promedio_mensual` (usando meses YTD con datos, no 12 fijo).
- **Tabla mensual separada**: `generar_tabla_mensual_ingresos_gastos()` ahora recibe `categorias_inversion` y divide Gastos en dos columnas (`Gastos sin inversión` / `Aportaciones a inversión`). Sin categorías marcadas → tabla de 3 columnas sin cambio (compatibilidad Alicia).
- **Nota reembolsos**: línea genérica al pie de la tabla anual advirtiendo que valores positivos en categorías de gasto pueden ser reembolsos o devoluciones.
- **Cartera completa**: `generar_seccion_cartera()` reemplaza "Últimas 10 compras" por "Posiciones actuales" — tabla neta por ticker (todas las posiciones abiertas), ordenada por valor descendente. Columnas: Activo / Precio medio / Precio actual / Valor / % Cartera.
- **Tasa de ahorro mensual**: columna adicional en tabla mensual. Fórmula con inversión: `(Ingresos − Gastos − Aportaciones) / Ingresos`. Sin inversión: `(Ingresos − Gastos) / Ingresos`. Muestra `—` si Ingresos = 0.
- **Perfil MiFID 5 niveles**: selector ampliado de 3 a 5 opciones → Conservador / Moderado-conservador / Moderado / Moderado-agresivo / Agresivo.
- **Deudas condicional**: radio Sí/No en UI. Si Sí: tres campos (importe total, cuota mensual, fecha fin). Genera línea automática en Sección 2 con contexto para el LLM. Si No: nada en el prompt.
- **Contexto estratégico guiado**: `st.text_area` opcional (máx. 300 chars) con placeholder de ejemplo. Se inserta en Sección 1 del prompt. Permite al usuario explicar estrategia Core-Satellite, gastos estacionales, etc.

### Sprint 10.3 — Reorden prompt + mejoras tabla (20 Jun 2026)

**Implementado:**

- **Tasa de ahorro — mes en curso**: lógica condicional en `generar_tabla_mensual_ingresos_gastos()`. Mes actual → `⏳ Mes en curso`. Mes pasado sin ingresos → `— sin ingresos`. Resto → cálculo normal.
- **Otras Categorías siempre al final**: fix de ordenación en `generar_tabla_anual()` — el sort por `Real YTD` ahora excluye la fila agregada "Otras Categorías", que se concatena al final después del sort.
- **Reorden y fusión de secciones del prompt**: nueva Sección 2 "Patrimonio Neto Estimado" que consolida liquidez bancaria + valor de cada cartera (con conversión EUR al tipo de cambio actual) + patrimonio total estimado + meses de cobertura + deuda. Sección 3 pasa a ser "Flujo del Año". Sección 4 queda como "Cartera — Detalle" con KPIs + sectores + posiciones sin repetir el resumen patrimonial.

### Sprint 11 — Tabla presupuesto estilo Excel (20 Jun 2026)

**Implementado:**

- **Nueva página 📋 Presupuesto**: tabla categorías × 12 meses con 2 sub-filas por categoría (Gasto real / Presupuesto). Selector de año desde el principio.
- **Colores automáticos**: verde si gasto ≤ presupuesto, rojo si supera. Sin color para usuarios sin presupuesto (Alicia).
- **Alternancia gris/blanco** por grupos de categoría para legibilidad.
- **Columna Total anual** al final (suma de los 12 meses por sub-fila).
- **3 filas de totales al pie**: Presupuesto total / Total gastado / % Ejecución (verde ≤ 100%, rojo > 100%).
- **Otras Categorías** agregadas en fila única al final (misma lógica que `generar_tabla_anual()`).
- **Dashboard reorganizado**: absorbe los gráficos de Histórico (barras Ingresos/Gastos + Balance cascada/mensual/acumulado). KPIs del mes actual se mantienen arriba.
- **Página 📈 Histórico eliminada** — sus gráficos viven ahora en Dashboard.
- **Menú lateral actualizado**: 📈 Histórico → 📋 Presupuesto.

**Pendiente / conocido:**

- 3 filas en blanco encima de los totales al pie — comportamiento del MultiIndex en Streamlit, no crítico, diferido a migración Reflex.

