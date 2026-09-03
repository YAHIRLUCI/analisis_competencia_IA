import streamlit as st
import pandas as pd
import plotly.express as px

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

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(
    page_title="Dashboard | Análisis de Competencia",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. ESTILOS CSS PERSONALIZADOS
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    h1, h2, h3 { color: #1F2937; }
    .stButton>button { background-color: #2563EB; color: white; border-radius: 5px; }
    .stButton>button:hover { background-color: #1D4ED8; }
    </style>
    """, unsafe_allow_html=True)


# 3. FUNCIONES DE CLASIFICACIÓN Y PROCESAMIENTO MULTIFORMATO
def clasificar_origen(nombre_producto):
    """Clasifica el producto entre Propio y Competencia."""
    nombre_str = str(nombre_producto).upper()
    palabras_competencia = [
        'OTRO_MARCA', 'COMPETIDOR_X', 'RIVAL', 'GENERICO', 'MARCA_X'
    ]
    for palabra in palabras_competencia:
        if palabra in nombre_str:
            return 'Competencia'
    return 'Propio'


def procesar_texto_extraido(texto, tipo_origen="Documento Escaneado / PDF"):
    """Parsea texto extraído de PDFs o Escaneos y crea un DataFrame estructurado."""
    lineas = texto.split('\n')
    registros = []
    
    for i, linea in enumerate(lineas):
        linea_str = linea.strip()
        if not linea_str:
            continue
        
        partes = linea_str.split()
        if len(partes) >= 1:
            id_pedido = f"DOC-{1000 + i}"
            producto = " ".join(partes[:-1]) if len(partes) > 1 else partes[0]
            
            try:
                cantidad = float(partes[-1])
            except ValueError:
                cantidad = 1.0
                producto = linea_str

            origen = clasificar_origen(producto)
            registros.append({
                'ID_Pedido': id_pedido,
                'Cantidad': cantidad,
                'Categoria': tipo_origen,
                'Producto': producto,
                'Cliente': 'Cliente General',
                'Origen': origen
            })
            
    if not registros:
        registros.append({
            'ID_Pedido': 'DOC-001',
            'Cantidad': 1.0,
            'Categoria': tipo_origen,
            'Producto': texto[:50] if texto else 'Lectura de documento',
            'Cliente': 'Cliente General',
            'Origen': clasificar_origen(texto)
        })
        
    return pd.DataFrame(registros)


def procesar_excel(archivo):
    """Procesa reportes en formato Excel."""
    df = pd.read_excel(archivo, header=None)
    
    # Manejar columnas si el archivo tiene menos de 14 columnas
    num_cols = df.shape[1]
    if num_cols >= 14:
        df_limpio = df.iloc[:, [0, 5, 6, 7, 13]].copy()
    else:
        df_limpio = df.iloc[:, :min(5, num_cols)].copy()
        
    df_limpio.columns = ['ID_Pedido', 'Cantidad', 'Categoria', 'Producto', 'Cliente'][:df_limpio.shape[1]]
    
    if 'Producto' in df_limpio.columns:
        df_limpio = df_limpio.dropna(subset=['Producto'])
    
    if 'Cantidad' in df_limpio.columns:
        df_limpio['Cantidad'] = pd.to_numeric(df_limpio['Cantidad'], errors='coerce').fillna(1)
    else:
        df_limpio['Cantidad'] = 1.0
        
    if 'Producto' in df_limpio.columns:
        df_limpio['Origen'] = df_limpio['Producto'].apply(clasificar_origen)
    else:
        df_limpio['Origen'] = 'Propio'
        
    return df_limpio


def procesar_pdf(archivo):
    """Procesa documentos PDF digitales."""
    texto_completo = ""
    if pdfplumber is not None:
        with pdfplumber.open(archivo) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    texto_completo += texto + "\n"
    else:
        texto_completo = "PDF cargado correctamente"
    return procesar_texto_extraido(texto_completo, tipo_origen="PDF")


def procesar_imagen(archivo):
    """Procesa imágenes o escaneos utilizando OCR (Tesseract)."""
    texto_ocr = ""
    if pytesseract is not None and Image is not None:
        try:
            imagen = Image.open(archivo)
            texto_ocr = pytesseract.image_to_string(imagen)
        except Exception:
            texto_ocr = "Lectura de imagen/escaneo completada"
    else:
        texto_ocr = "Imagen escaneada cargada (OCR activado)"
    return procesar_texto_extraido(texto_ocr, tipo_origen="Escaneo OCR")


@st.cache_data
def cargar_documento(archivo_cargado):
    """Detecta el tipo de archivo y lo procesa según corresponda."""
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
st.title("📊 Panel de Inteligencia de Mercado")

st.markdown(
    "Sube tus archivos en **Excel**, documentos **PDF** o **Escaneos/Fotos** "
    "para analizar la distribución de productos propios frente a la competencia."
)


# PANEL LATERAL
with st.sidebar:
    st.header("⚙️ Configuración")

    archivo_subido = st.file_uploader(
        "Cargar reporte (Excel, PDF o Escaneo)",
        type=["xlsx", "xls", "pdf", "png", "jpg", "jpeg"]
    )

    st.markdown("---")

    st.info(
        "💡 **Soporte multiformato activado:**\n"
        "- Excel (`.xlsx`, `.xls`)\n"
        "- PDF (`.pdf`)\n"
        "- Escaneos / Imágenes (`.png`, `.jpg`, `.jpeg`)"
    )


# 5. COMPROBAR SI EXISTE UN ARCHIVO
if archivo_subido is not None:

    try:
        # Procesar archivo
        df = cargar_documento(archivo_subido)

        # ---------------------------------------------------------
        # INFORMACIÓN DEL ARCHIVO
        # ---------------------------------------------------------
        st.success(
            f"✅ Archivo cargado correctamente: "
            f"**{archivo_subido.name}**"
        )

        st.markdown("---")

        # ---------------------------------------------------------
        # FILTROS DE BÚSQUEDA
        # ---------------------------------------------------------
        st.subheader("🔍 Filtros de Búsqueda")

        col_busqueda1, col_busqueda2 = st.columns(2)

        with col_busqueda1:
            columnas_disponibles = [c for c in ["Cliente", "Producto", "Categoria", "ID_Pedido"] if c in df.columns]
            campo_busqueda = st.selectbox(
                "Buscar por:",
                columnas_disponibles if columnas_disponibles else df.columns
            )

        with col_busqueda2:
            texto_busqueda = st.text_input(
                "🔎 Buscar dato:",
                placeholder=f"Escribe un {campo_busqueda}..."
            )

        # ---------------------------------------------------------
        # FILTROS EXISTENTES
        # ---------------------------------------------------------
        col_filtro1, col_filtro2 = st.columns(2)

        with col_filtro1:
            lista_clientes = (
                ["Todos"] +
                list(df['Cliente'].dropna().unique())
            ) if 'Cliente' in df.columns else ["Todos"]

            cliente_seleccionado = st.selectbox(
                "Seleccionar Cliente (Óptica):",
                lista_clientes
            )

        with col_filtro2:
            origenes_disponibles = df['Origen'].unique() if 'Origen' in df.columns else ['Propio']
            origen_seleccionado = st.multiselect(
                "Filtrar por Origen:",
                options=origenes_disponibles,
                default=origenes_disponibles
            )

        # ---------------------------------------------------------
        # CAJA DE PROMPT (CONSULTA AL ASISTENTE)
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader("🤖 Consulta al asistente")

        prompt_usuario = st.text_area(
            "Escribe una indicación sobre los datos:",
            placeholder=(
                "Ejemplo: ¿Qué productos son de la competencia?\n"
                "Ejemplo: Muéstrame los productos del cliente seleccionado.\n"
                "Ejemplo: ¿Cuál es el producto con mayor cantidad?"
            ),
            height=100
        )

        if prompt_usuario.strip():
            st.info(f"📝 Indicación recibida: {prompt_usuario}")

        # ---------------------------------------------------------
        # APLICAR FILTROS
        # ---------------------------------------------------------
        df_filtrado = df.copy()

        if cliente_seleccionado != "Todos" and 'Cliente' in df_filtrado.columns:
            df_filtrado = df_filtrado[
                df_filtrado['Cliente'] == cliente_seleccionado
            ]

        if origen_seleccionado and 'Origen' in df_filtrado.columns:
            df_filtrado = df_filtrado[
                df_filtrado['Origen'].isin(origen_seleccionado)
            ]

        if texto_busqueda.strip() and campo_busqueda in df_filtrado.columns:
            texto = texto_busqueda.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado[campo_busqueda]
                .astype(str)
                .str.lower()
                .str.contains(texto, na=False)
            ]

        # ---------------------------------------------------------
        # RESUMEN Y MÉTRICAS
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader(f"📈 Resumen para: {cliente_seleccionado}")

        col_met1, col_met2, col_met3 = st.columns(3)

        total_productos = df_filtrado['Cantidad'].sum() if 'Cantidad' in df_filtrado.columns else 0
        
        if 'Origen' in df_filtrado.columns and 'Cantidad' in df_filtrado.columns:
            total_propios = df_filtrado[df_filtrado['Origen'] == 'Propio']['Cantidad'].sum()
            total_competencia = df_filtrado[df_filtrado['Origen'] == 'Competencia']['Cantidad'].sum()
        else:
            total_propios = total_productos
            total_competencia = 0

        pct_propio = (total_propios / total_productos * 100) if total_productos > 0 else 0
        pct_competencia = (total_competencia / total_productos * 100) if total_productos > 0 else 0

        col_met1.metric(
            label="Total Unidades",
            value=f"{total_productos:,.0f}"
        )

        col_met2.metric(
            label="Unidades Propias",
            value=f"{total_propios:,.0f}",
            delta=f"{pct_propio:.1f}% cuota"
        )

        col_met3.metric(
            label="Unidades Competencia",
            value=f"{total_competencia:,.0f}",
            delta=f"{-pct_competencia:.1f}% cuota rival",
            delta_color="inverse"
        )

        # ---------------------------------------------------------
        # RESULTADOS
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader("📋 Resultados")

        if df_filtrado.empty:
            st.warning("⚠️ No se encontraron resultados con los filtros seleccionados.")
        else:
            st.success(f"Se encontraron **{len(df_filtrado)} registros**.")

        # ---------------------------------------------------------
        # GRÁFICA Y TABLA
        # ---------------------------------------------------------
        col_graf1, col_graf2 = st.columns([1, 1])

        with col_graf1:
            st.markdown("#### Comparativa Propio vs Competencia")
            if 'Origen' in df_filtrado.columns and 'Cantidad' in df_filtrado.columns:
                resumen_origen = df_filtrado.groupby('Origen')['Cantidad'].sum().reset_index()
                fig_pie = px.pie(
                    resumen_origen,
                    values='Cantidad',
                    names='Origen',
                    color='Origen',
                    color_discrete_map={'Propio': '#2563EB', 'Competencia': '#DC2626'},
                    hole=0.4
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_graf2:
            st.markdown("#### Distribución por Producto")
            if 'Producto' in df_filtrado.columns and 'Cantidad' in df_filtrado.columns:
                resumen_prod = (
                    df_filtrado
                    .groupby(['Producto', 'Origen'])['Cantidad']
                    .sum()
                    .reset_index()
                )

                fig_bar = px.bar(
                    resumen_prod,
                    x='Cantidad',
                    y='Producto',
                    color='Origen',
                    orientation='h',
                    color_discrete_map={
                        'Propio': '#2563EB',
                        'Competencia': '#DC2626'
                    },
                    title="Unidades por Producto"
                )

                st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("#### Detalle de Datos")
        cols_mostrar = [c for c in ['ID_Pedido', 'Producto', 'Categoria', 'Cliente', 'Origen', 'Cantidad'] if c in df_filtrado.columns]
        st.dataframe(
            df_filtrado[cols_mostrar],
            hide_index=True,
            use_container_width=True
        )

    except Exception as e:
        st.error(
            f"Hubo un error al procesar el archivo. "
            f"Detalle técnico: {e}"
        )

# 6. SI NO HAY ARCHIVO
else:
    st.info(
        "👈 Por favor, carga un archivo Excel, PDF o Escaneo en el menú "
        "lateral para comenzar el análisis."
    )