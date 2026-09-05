import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Control de librerías para PDF y OCR/Escaneos
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

# 1. CONFIGURACIÓN DE LA PÁGINA (Debe ser el primer comando)
st.set_page_config(
    page_title="Dashboard Ejecutivo | Análisis de Mercado",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. ESTILOS CSS PROFESIONALES Y MINIMALISTAS
st.markdown("""
    <style>
    /* Fondo principal y tipografía */
    .main { background-color: #F4F7FC; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    h1, h2, h3 { color: #0F172A; font-weight: 600; }
    
    /* Estilo de los botones */
    .stButton>button { 
        background-color: #1E3A8A; 
        color: white; 
        border-radius: 6px; 
        border: none;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    .stButton>button:hover { background-color: #1E40AF; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
    
    /* Estilo para las métricas */
    div[data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #1E3A8A; }
    div[data-testid="stMetricLabel"] { font-size: 14px; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Separadores */
    hr { margin-top: 1rem; margin-bottom: 1rem; border: 0; border-top: 1px solid #E2E8F0; }
    
    /* Ocultar menú de Streamlit para vista más limpia (opcional) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)


# 3. FUNCIONES DE CLASIFICACIÓN Y PROCESAMIENTO
def clasificar_origen(nombre_producto):
    nombre_str = str(nombre_producto).upper()
    palabras_competencia = [
        'OTRO_MARCA', 'COMPETIDOR_X', 'RIVAL', 'GENERICO', 'MARCA_X',
        'COOPERVISION', 'ACUVUE', 'BIOFINITY', 'AIR OPTIX', 'DAILIES'
    ]
    for palabra in palabras_competencia:
        if palabra in nombre_str:
            return 'Competencia'
    return 'Propio'

def procesar_texto_extraido(texto, tipo_origen="Documento Escaneado / PDF"):
    lineas = texto.split('\n')
    registros = []
    for i, linea in enumerate(lineas):
        linea_str = linea.strip()
        if not linea_str or len(linea_str) < 3:
            continue
        
        cantidad = 1.0
        producto = linea_str
        
        match_final = re.search(r'(.*?)\s+(\d+[\.,]?\d*)$', linea_str)
        match_inicio = re.search(r'^(\d+[\.,]?\d*)\s+(.*)', linea_str)

        if match_final:
            producto = match_final.group(1).strip()
            try:
                cantidad = float(match_final.group(2).replace(',', '.'))
            except ValueError:
                pass
        elif match_inicio:
            try:
                cantidad = float(match_inicio.group(1).replace(',', '.'))
            except ValueError:
                pass
            producto = match_inicio.group(2).strip()

        origen = clasificar_origen(producto)
        registros.append({
            'ID_Pedido': f"DOC-{1000 + i}",
            'Cantidad': cantidad,
            'Categoria': tipo_origen,
            'Producto': producto,
            'Cliente': 'Cliente General',
            'Origen': origen
        })
            
    if not registros:
        registros.append({
            'ID_Pedido': 'DOC-001', 'Cantidad': 1.0, 'Categoria': tipo_origen,
            'Producto': 'Lectura de documento', 'Cliente': 'Cliente General', 'Origen': 'Propio'
        })
    return pd.DataFrame(registros)

def procesar_excel(archivo):
    df = pd.read_excel(archivo)
    df.columns = [str(c).strip() for c in df.columns]
    
    col_pedido = 'Pedido' if 'Pedido' in df.columns else df.columns[0]
    col_cantidad = 'Cantidad de producto' if 'Cantidad de producto' in df.columns else ('Cantidad' if 'Cantidad' in df.columns else None)
    col_producto = 'Nombre del producto' if 'Nombre del producto' in df.columns else ('Producto' if 'Producto' in df.columns else None)
    col_cliente = 'Óptica' if 'Óptica' in df.columns else ('Cliente' if 'Cliente' in df.columns else None)
    col_origen = 'Origen' if 'Origen' in df.columns else None
    col_categoria = 'Presentación' if 'Presentación' in df.columns else ('Ruta' if 'Ruta' in df.columns else None)

    df_limpio = pd.DataFrame()
    df_limpio['ID_Pedido'] = df[col_pedido] if col_pedido else df.index
    df_limpio['Producto'] = df[col_producto] if col_producto else "Sin especificación"
    df_limpio['Cantidad'] = pd.to_numeric(df[col_cantidad], errors='coerce').fillna(1) if col_cantidad else 1.0
    df_limpio['Cliente'] = df[col_cliente] if col_cliente else "Cliente General"
    df_limpio['Categoria'] = df[col_categoria] if col_categoria else "General"
    
    if col_origen and col_origen in df.columns:
        df_limpio['Origen'] = df[col_origen].astype(str).str.strip().str.capitalize()
    else:
        df_limpio['Origen'] = df_limpio['Producto'].apply(clasificar_origen)
    return df_limpio

def procesar_pdf(archivo):
    texto_completo = ""
    if pdfplumber is not None:
        with pdfplumber.open(archivo) as pdf:
            for pagina in pdf.pages:
                tablas = pagina.extract_tables()
                if tablas:
                    for tabla in tablas:
                        for fila in tabla:
                            fila_limpia = [str(c).strip() for c in fila if c]
                            if fila_limpia:
                                texto_completo += " ".join(fila_limpia) + "\n"
                else:
                    texto = pagina.extract_text()
                    if texto:
                        texto_completo += texto + "\n"
    else:
        texto_completo = "PDF cargado sin librería de extracción"
    return procesar_texto_extraido(texto_completo, tipo_origen="PDF")

def procesar_imagen(archivo):
    texto_ocr = ""
    if pytesseract is not None and Image is not None:
        try:
            imagen = Image.open(archivo)
            texto_ocr = pytesseract.image_to_string(imagen)
        except Exception:
            texto_ocr = "Lectura de imagen/escaneo completada sin éxito"
    else:
        texto_ocr = "Imagen escaneada cargada (OCR no disponible)"
    return procesar_texto_extraido(texto_ocr, tipo_origen="Escaneo OCR")

@st.cache_data
def cargar_documento(archivo_cargado):
    nombre = archivo_cargado.name.lower()
    if nombre.endswith(('.xlsx', '.xls')):
        return procesar_excel(archivo_cargado)
    elif nombre.endswith('.pdf'):
        return procesar_pdf(archivo_cargado)
    elif nombre.endswith(('.png', '.jpg', '.jpeg')):
        return procesar_imagen(archivo_cargado)
    else:
        raise ValueError("Formato de archivo no compatible.")


# 4. INTERFAZ DE USUARIO PRINCIPAL
st.title("📈 Dashboard Ejecutivo | Inteligencia de Mercado")
st.markdown("Plataforma de análisis comparativo de participación de mercado: **Propio vs Competencia**.")

# PANEL LATERAL PROFESIONAL
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3094/3094939.png", width=60) # Icono decorativo opcional
    st.header("Gestor de Archivos")
    
    archivo_subido = st.file_uploader(
        "Cargar origen de datos",
        type=["xlsx", "xls", "pdf", "png", "jpg", "jpeg"],
        help="Soporta Excel, PDF y fotografías de tickets."
    )

    st.markdown("---")
    st.caption("✔️ Excel (.xlsx, .xls)")
    st.caption("✔️ Documentos (.pdf)")
    st.caption("✔️ Fotografías/Tickets (.jpg, .png)")


# 5. LÓGICA PRINCIPAL SI HAY ARCHIVO
if archivo_subido is not None:
    try:
        df = cargar_documento(archivo_subido)

        # MENSAJES DE ESTADO
        if archivo_subido.name.lower().endswith(('.png', '.jpg', '.jpeg')):
            st.warning("⚠️ **VERIFICACIÓN REQUERIDA:** Se ha detectado la carga de una imagen (Ticket/Escaneo). Por favor, verifique en la pestaña 'Datos Detallados' que el motor OCR haya extraído las cantidades correctamente.")
        else:
            st.success(f"📄 Archivo procesado exitosamente: **{archivo_subido.name}**")

        # ---------------------------------------------------------
        # FILTROS AVANZADOS (OCULTOS EN UN EXPANDER PARA LIMPIEZA)
        # ---------------------------------------------------------
        with st.expander("⚙️ Filtros Avanzados de Información", expanded=False):
            col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
            
            with col_filtro1:
                lista_clientes = ["Todos"] + list(df['Cliente'].dropna().unique()) if 'Cliente' in df.columns else ["Todos"]
                cliente_seleccionado = st.selectbox("Óptica / Cliente:", lista_clientes)
                
            with col_filtro2:
                origenes_disponibles = list(df['Origen'].unique()) if 'Origen' in df.columns else ['Propio', 'Competencia']
                origen_seleccionado = st.multiselect("Origen del Producto:", options=origenes_disponibles, default=origenes_disponibles)
                
            with col_filtro3:
                texto_busqueda = st.text_input("🔎 Búsqueda rápida de producto:", placeholder="Ej. Acuvue...")

        # APLICAR FILTROS
        df_filtrado = df.copy()
        if cliente_seleccionado != "Todos" and 'Cliente' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Cliente'] == cliente_seleccionado]
        if origen_seleccionado and 'Origen' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Origen'].isin(origen_seleccionado)]
        if texto_busqueda.strip() and 'Producto' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Producto'].astype(str).str.lower().str.contains(texto_busqueda.strip().lower(), na=False)]

        # ---------------------------------------------------------
        # TARJETAS DE MÉTRICAS (KPIs)
        # ---------------------------------------------------------
        st.markdown("### 📊 Resumen Ejecutivo")
        col_met1, col_met2, col_met3 = st.columns(3)

        total_productos = df_filtrado['Cantidad'].sum() if 'Cantidad' in df_filtrado.columns else 0
        if 'Origen' in df_filtrado.columns and 'Cantidad' in df_filtrado.columns:
            total_propios = df_filtrado[df_filtrado['Origen'].str.lower() == 'propio']['Cantidad'].sum()
            total_competencia = df_filtrado[df_filtrado['Origen'].str.lower() == 'competencia']['Cantidad'].sum()
        else:
            total_propios = total_productos
            total_competencia = 0

        pct_propio = (total_propios / total_productos * 100) if total_productos > 0 else 0
        pct_competencia = (total_competencia / total_productos * 100) if total_productos > 0 else 0

        with col_met1:
            st.metric(label="Volumen Total (Unidades)", value=f"{total_productos:,.0f}")
        with col_met2:
            st.metric(label="Market Share (Propio)", value=f"{total_propios:,.0f}", delta=f"{pct_propio:.1f}%")
        with col_met3:
            st.metric(label="Market Share (Competencia)", value=f"{total_competencia:,.0f}", delta=f"{-pct_competencia:.1f}%", delta_color="inverse")

        st.markdown("<br>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # PESTAÑAS DE NAVEGACIÓN (TABS)
        # ---------------------------------------------------------
        tab_graficos, tab_datos, tab_asistente = st.tabs([
            "📊 Gráficos de Negocio", 
            "📋 Datos Detallados", 
            "🤖 Asistente de Análisis"
        ])

        # --- PESTAÑA 1: GRÁFICOS ---
        with tab_graficos:
            if df_filtrado.empty:
                st.info("No hay datos para graficar con los filtros actuales.")
            else:
                col_g1, col_g2 = st.columns(2)
                
                with col_g1:
                    resumen_origen = df_filtrado.groupby('Origen')['Cantidad'].sum().reset_index()
                    fig_pie = px.pie(
                        resumen_origen, values='Cantidad', names='Origen',
                        color='Origen', color_discrete_map={'Propio': '#1E3A8A', 'Competencia': '#EF4444'},
                        hole=0.5, title="Distribución de Participación"
                    )
                    # Estilo limpio para Plotly
                    fig_pie.update_layout(template="plotly_white", margin=dict(t=40, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col_g2:
                    resumen_prod = df_filtrado.groupby(['Producto', 'Origen'])['Cantidad'].sum().reset_index().sort_values(by='Cantidad', ascending=True).tail(10)
                    fig_bar = px.bar(
                        resumen_prod, x='Cantidad', y='Producto', color='Origen', orientation='h',
                        color_discrete_map={'Propio': '#1E3A8A', 'Competencia': '#EF4444'},
                        title="Top 10 Productos con Mayor Volumen"
                    )
                    fig_bar.update_layout(template="plotly_white", margin=dict(t=40, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_bar, use_container_width=True)

        # --- PESTAÑA 2: DATOS DETALLADOS ---
        with tab_datos:
            st.markdown("#### Matriz de Datos")
            cols_mostrar = [c for c in ['ID_Pedido', 'Producto', 'Categoria', 'Cliente', 'Origen', 'Cantidad'] if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols_mostrar], hide_index=True, use_container_width=True, height=400)

        # --- PESTAÑA 3: ASISTENTE ---
        with tab_asistente:
            st.markdown("#### 💬 Consultor Analítico")
            prompt_usuario = st.text_area(
                "Realice una consulta en lenguaje natural sobre la matriz de datos:",
                placeholder="Ej. Dame un resumen de la competencia. / ¿Cuál es el producto más vendido?",
                height=80
            )

            if prompt_usuario.strip():
                txt = prompt_usuario.strip().lower()
                st.markdown("##### 💡 Respuesta:")

                if "competencia" in txt or "rival" in txt:
                    df_comp = df_filtrado[df_filtrado['Origen'].str.lower() == 'competencia']
                    st.warning(f"Se identificaron **{len(df_comp)} registros** de la competencia ({df_comp['Cantidad'].sum():,.0f} unidades).")
                    st.dataframe(df_comp[['Producto', 'Cantidad']], hide_index=True)

                elif "propio" in txt or "propios" in txt or "nuestros" in txt:
                    df_prop = df_filtrado[df_filtrado['Origen'].str.lower() == 'propio']
                    st.success(f"Se encontraron **{len(df_prop)} registros propios** ({df_prop['Cantidad'].sum():,.0f} unidades).")
                    st.dataframe(df_prop[['Producto', 'Cantidad']], hide_index=True)

                elif any(word in txt for word in ["mas vendido", "mayor cantidad", "top", "máximo", "maximo"]):
                    top_prod = df_filtrado.groupby(['Producto', 'Origen'])['Cantidad'].sum().reset_index().sort_values(by='Cantidad', ascending=False)
                    lider = top_prod.iloc[0]
                    st.success(f"🏆 Producto líder: **{lider['Producto']}** ({lider['Origen']}) con **{lider['Cantidad']:,.0f} unidades**.")

                elif any(word in txt for word in ["resumen", "analisis", "general", "cuota"]):
                    st.info(f"**Análisis de cuota actual:**\n\n- **Volumen total:** {total_productos:,.0f} uds.\n- **Propio:** {pct_propio:.1f}% ({total_propios:,.0f} uds.)\n- **Competencia:** {pct_competencia:.1f}% ({total_competencia:,.0f} uds.)")
                
                else:
                    coincidencias = df_filtrado[df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(txt, na=False).any(), axis=1)]
                    if not coincidencias.empty:
                        st.dataframe(coincidencias, hide_index=True)
                    else:
                        st.info("No se encontraron coincidencias. Prueba con términos como 'competencia', 'top' o 'resumen'.")

    except Exception as e:
        st.error(f"Error técnico en el procesamiento del archivo: {e}")

else:
    # Pantalla de bienvenida limpia
    st.info("👋 Bienvenido al Dashboard. Por favor, **cargue un archivo desde el menú lateral** para iniciar el análisis.")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.markdown("📄 **Procesamiento PDF:**\nExtracción inteligente de tablas y formatos.")
    col2.markdown("📸 **Escáner OCR:**\nLectura automatizada de tickets fotográficos.")
    col3.markdown("🤖 **Asistente IA:**\nConsulta de datos mediante lenguaje natural.")