import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np

# Control de librerías para PDF y OCR
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import cv2
    import pytesseract
    from PIL import Image
    # ⚠️ RUTA DE TESSERACT EN TU COMPUTADORA (Ajusta si es necesario)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError:
    cv2 = None
    pytesseract = None
    Image = None

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(
    page_title="Dashboard Ejecutivo | Análisis de Mercado",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. ESTILOS CSS PROFESIONALES
st.markdown("""
    <style>
    h1, h2, h3, h4 { color: #F8FAFC !important; font-weight: 700; }
    .stButton>button { background-color: #3B82F6; color: white; border-radius: 6px; border: none; transition: 0.3s; }
    .stButton>button:hover { background-color: #2563EB; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3); }
    div[data-testid="stMetricValue"] { font-size: 32px; font-weight: 800; color: #3B82F6; }
    div[data-testid="stMetricLabel"] { font-size: 13px; color: #94A3B8; font-weight: 600; text-transform: uppercase; }
    .st-emotion-cache-1wivap2 { border-radius: 10px; border: 1px solid #334155; background: #1E293B; padding: 20px; }
    .stAlert { background-color: rgba(16, 185, 129, 0.1) !important; color: #10B981 !important; border: 1px solid rgba(16,185,129,0.2); }
    .stWarning { background-color: rgba(245, 158, 11, 0.1) !important; color: #F59E0B !important; border: 1px solid rgba(245,158,11,0.2); }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNCIONES DE PROCESAMIENTO

def clasificar_origen(nombre_producto):
    nombre_str = str(nombre_producto).upper()
    palabras_competencia = ['OTRO_MARCA', 'COMPETIDOR_X', 'RIVAL', 'GENERICO', 'MARCA_X', 'COOPERVISION', 'ACUVUE', 'BIOFINITY', 'AIR OPTIX', 'DAILIES', 'CHEDRAUI', 'HUA XIN', 'FARMACIA']
    for palabra in palabras_competencia:
        if palabra in nombre_str:
            return 'Competencia'
    return 'Propio'

def extraer_productos_de_texto(texto):
    """
    MOTOR DE EXTRACCIÓN LOCAL (Sin APIs)
    Entiende tickets de Preventa, Farmacia Guadalajara, HUA XIN, Chedraui, etc.
    """
    lineas = texto.split('\n')
    registros = []
    
    palabras_ignoradas = [
        'TOTAL', 'SUBTOTAL', 'FECHA', 'HORA', 'TEL', 'TELEFONO', 'RFC', 'IVA', 'GRACIAS', 
        'CAMBIO', 'EFECTIVO', 'TARJETA', 'TICKET', 'FACTURA', 'CLIENTE', 'DIRECCION', 
        'SUCURSAL', 'CAJERO', 'TERMINAL', 'AUTORIZACION', 'IMPORTE', 'PAGO', 'VENTA',
        'DESCUENTO', 'AHORRO', 'BONIFICACION', 'CUPON', 'WWW.', 'CALLE', 'COL.', 'C.P.',
        'FOLIO', 'REFERENCIA', 'SALDO', 'ATENDIDO', 'GARANTIA', 'EMPAQUE', 'MERCANCIA',
        'PZ', 'PZA', 'PIEZA', 'ARTICULO', 'ARTICULOS', 'SUC', 'MEX', 'AV.', 'NO.', 'REF',
        'CAJA', 'DESCRIPCION', 'PRECIO', 'VENTA', 'IMPORTE', 'ILEGIBLE', 'TOTALES', 'DEBIDO',
        'PAGO', 'CREDITO', 'SALDO', 'ANTERIOR', 'DISPONIBLE'
    ]
    
    i = 0
    while i < len(lineas):
        linea_actual = re.sub(r'[|\\[\]{}]', '', lineas[i]).strip()
        linea_actual = re.sub(r'\s+', ' ', linea_actual)
        
        if not linea_actual or len(linea_actual) < 3:
            i += 1
            continue
            
        if any(p in linea_actual.upper() for p in palabras_ignoradas):
            i += 1
            continue
            
        if re.match(r'^[\d\s\.,\-\$]+$', linea_actual):
            i += 1
            continue

        cantidad, producto, precio_unit, total = 1.0, "", 0.0, 0.0
        match_encontrado = False

        # --- PATRÓN 1: Formato Chedraui / Supermercados ---
        match1 = re.search(r'^(\d+[\.,]\d{3})\s*(.+?)\s*(\d+[\.,]\d{2})\s*(\d+[\.,]\d{2})', linea_actual)
        if match1:
            cantidad = float(match1.group(1).replace(',', '.'))
            producto = match1.group(2).strip()
            precio_unit = float(match1.group(3).replace(',', '.'))
            total = float(match1.group(4).replace(',', '.'))
            match_encontrado = True

        # --- PATRÓN 2: Formato Farmacia Guadalajara ---
        if not match_encontrado:
            match2 = re.search(r'^(\d+)\s*(?:PZ|PZA|PIEZA)?\s+(.+?)\s+\$?(\d+[\.,]\d{2})$', linea_actual)
            if match2:
                cantidad = float(match2.group(1))
                producto = match2.group(2).strip()
                total = float(match2.group(3).replace(',', '.'))
                precio_unit = total / cantidad if cantidad > 0 else total
                match_encontrado = True

        # --- PATRÓN 3: Formato HUA XIN (Cant x Precio Producto Total) ---
        if not match_encontrado:
            match3 = re.search(r'^(\d+)\s*[xX]?\s*(\d+[\.,]\d{2})\s+(.+?)\s+(\d+[\.,]\d{2})$', linea_actual)
            if match3:
                cantidad = float(match3.group(1))
                precio_unit = float(match3.group(2).replace(',', '.'))
                producto = match3.group(3).strip()
                total = float(match3.group(4).replace(',', '.'))
                match_encontrado = True

        # --- PATRÓN 4: Formato Preventa (3 líneas por producto) ---
        if not match_encontrado:
            if re.search(r'[A-Za-z]', linea_actual) and not re.search(r'\d{7}', linea_actual):
                if i + 1 < len(lineas):
                    linea_siguiente = re.sub(r'\s+', ' ', lineas[i+1]).strip()
                    match_clave = re.search(r'(\d{6,8})\s+(\d+)', linea_siguiente)
                    if match_clave:
                        cantidad_temp = float(match_clave.group(2))
                        linea_precios = ""
                        if i + 2 < len(lineas):
                            linea_precios = re.sub(r'\s+', ' ', lineas[i+2]).strip()
                        
                        match_precios = re.search(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', linea_precios)
                        if match_precios:
                            cantidad = cantidad_temp
                            producto = linea_actual
                            precio_unit = float(match_precios.group(1).replace(',', ''))
                            total = float(match_precios.group(3).replace(',', ''))
                            match_encontrado = True
                            i += 2

        if match_encontrado and len(producto) > 3:
            producto = re.sub(r'[*#]', '', producto)
            producto = re.sub(r'\s+', ' ', producto).strip()
            
            registros.append({
                'ID_Pedido': f"DOC-{1000 + i}",
                'Cantidad': cantidad,
                'Producto': producto,
                'Precio_Unitario': precio_unit,
                'Total': total,
                'Cliente': 'Cliente General',
                'Origen': clasificar_origen(producto)
            })
        i += 1
            
    if not registros:
        return pd.DataFrame(columns=['ID_Pedido', 'Cantidad', 'Producto', 'Precio_Unitario', 'Total', 'Cliente', 'Origen'])
    
    return pd.DataFrame(registros)

def procesar_excel(archivo):
    df = pd.read_excel(archivo)
    df.columns = [str(c).strip() for c in df.columns]
    
    col_pedido = next((c for c in df.columns if 'pedido' in c.lower()), df.columns[0])
    col_cantidad = next((c for c in df.columns if 'cantidad' in c.lower()), None)
    col_producto = next((c for c in df.columns if 'producto' in c.lower() or 'nombre' in c.lower()), None)
    col_cliente = next((c for c in df.columns if 'óptica' in c.lower() or 'cliente' in c.lower()), None)
    col_origen = next((c for c in df.columns if 'origen' in c.lower()), None)
    col_precio = next((c for c in df.columns if 'precio' in c.lower() or 'total' in c.lower()), None)
    
    df_limpio = pd.DataFrame()
    df_limpio['ID_Pedido'] = df[col_pedido]
    df_limpio['Producto'] = df[col_producto] if col_producto else "Sin especificación"
    df_limpio['Cantidad'] = pd.to_numeric(df[col_cantidad], errors='coerce').fillna(1) if col_cantidad else 1.0
    df_limpio['Cliente'] = df[col_cliente] if col_cliente else "Cliente General"
    df_limpio['Categoria'] = "General"
    df_limpio['Total'] = pd.to_numeric(df[col_precio], errors='coerce').fillna(0) if col_precio else 0.0
    df_limpio['Precio_Unitario'] = df_limpio['Total'] / df_limpio['Cantidad']
    
    if col_origen:
        df_limpio['Origen'] = df[col_origen].astype(str).str.strip().str.capitalize()
    else:
        df_limpio['Origen'] = df_limpio['Producto'].apply(clasificar_origen)
    return df_limpio

# 4. INTERFAZ PRINCIPAL
st.title("📊 Dashboard Ejecutivo | Inteligencia de Mercado")
st.markdown("Análisis automatizado de tickets, PDFs y reportes de ventas (100% Local).")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3094/3094939.png", width=50)
    st.header("Gestor de Archivos")
    
    # ¡AQUÍ ESTÁ LA CORRECCIÓN! Aceptamos PDF e Imágenes de nuevo
    archivo_subido = st.file_uploader("Sube tu archivo aquí", type=["xlsx", "xls", "csv", "pdf", "png", "jpg", "jpeg"])
    
    st.markdown("---")
    st.markdown("### 📱 ¿Tienes una foto del ticket?")
    st.info("""
    1. Abre la foto en tu celular.
    2. Usa **Google Lens** o la función **Copiar Texto**.
    3. Pega el texto aquí abajo.
    """)
    
    texto_manual = st.text_area("Pega aquí el texto del ticket:", height=150)
    boton_manual = st.button("🚀 Procesar Texto del Ticket")

# 5. LÓGICA PRINCIPAL
if archivo_subido is not None or (boton_manual and texto_manual):
    with st.spinner("Procesando datos..."):
        
        df = pd.DataFrame()
        
        # CASO 1: TEXTO MANUAL
        if boton_manual and texto_manual:
            df = extraer_productos_de_texto(texto_manual)
                
        # CASO 2: ARCHIVO SUBIDO
        elif archivo_subido:
            nombre = archivo_subido.name.lower()
            
            # 2.1 EXCEL / CSV
            if nombre.endswith(('.xlsx', '.xls')):
                df = procesar_excel(archivo_subido)
            elif nombre.endswith('.csv'):
                df = pd.read_csv(archivo_subido)
                df.columns = [str(c).strip() for c in df.columns]
                if 'Producto' not in df.columns and 'producto' in [c.lower() for c in df.columns]:
                    df = df.rename(columns={c: 'Producto' for c in df.columns if c.lower() == 'producto'})
                if 'Cantidad' not in df.columns and 'cantidad' in [c.lower() for c in df.columns]:
                    df = df.rename(columns={c: 'Cantidad' for c in df.columns if c.lower() == 'cantidad'})
                if 'Producto' in df.columns:
                    df['Origen'] = df['Producto'].apply(clasificar_origen)
                    if 'Total' not in df.columns: df['Total'] = 0.0
                    if 'Precio_Unitario' not in df.columns: df['Precio_Unitario'] = df['Total'] / df['Cantidad'].replace(0, 1)
                    if 'Cliente' not in df.columns: df['Cliente'] = 'Cliente General'
                    if 'ID_Pedido' not in df.columns: df['ID_Pedido'] = 'DOC-001'
            
            # 2.2 PDF (¡Restaurado!)
            elif nombre.endswith('.pdf'):
                if pdfplumber:
                    with pdfplumber.open(archivo_subido) as pdf:
                        texto_pdf = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
                    df = extraer_productos_de_texto(texto_pdf)
                else:
                    st.error("Falta instalar pdfplumber. Ejecuta: pip install pdfplumber")
                    
            # 2.3 IMAGEN (¡Restaurado!)
            elif nombre.endswith(('.png', '.jpg', '.jpeg')):
                if cv2 is not None and pytesseract is not None:
                    file_bytes = np.asarray(bytearray(archivo_subido.read()), dtype=np.uint8)
                    img = cv2.imdecode(file_bytes, 1)
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    texto_ocr = pytesseract.image_to_string(thresh, lang='spa', config='--psm 6')
                    df = extraer_productos_de_texto(texto_ocr)
                else:
                    st.error("Faltan las librerías de OCR (Tesseract/OpenCV). Revisa la instalación.")
            else:
                st.error("Formato no compatible.")

        if df is None or df.empty:
            st.warning("""
            ⚠️ **No se pudieron detectar productos claros en este documento.**
            Si subiste una imagen, intenta mejorar la foto o usa la caja de "Texto Manual" en el panel izquierdo.
            """)
            df = pd.DataFrame(columns=['ID_Pedido', 'Cantidad', 'Producto', 'Precio_Unitario', 'Total', 'Cliente', 'Origen'])

    # Filtros
    with st.expander("⚙️ Controles y Filtros Avanzados", expanded=False):
        c1, c2, c3 = st.columns(3)
        cliente_sel = c1.selectbox("Cliente / Óptica:", ["Todos"] + list(df['Cliente'].unique()) if not df.empty else ["Todos"])
        origen_sel = c2.multiselect("Origen:", df['Origen'].unique() if not df.empty else ["Propio"], default=df['Origen'].unique() if not df.empty else ["Propio"])
        buscar = c3.text_input("Buscar producto:")

    # Aplicar Filtros
    df_filtrado = df.copy()
    if not df_filtrado.empty:
        if cliente_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['Cliente'] == cliente_sel]
        if origen_sel: df_filtrado = df_filtrado[df_filtrado['Origen'].isin(origen_sel)]
        if buscar: df_filtrado = df_filtrado[df_filtrado['Producto'].str.contains(buscar, case=False, na=False)]

    # Variables de resumen
    total_uds = df_filtrado['Cantidad'].sum() if not df_filtrado.empty else 0
    total_gasto = df_filtrado['Total'].sum() if not df_filtrado.empty else 0
    total_prop = df_filtrado[df_filtrado['Origen']=='Propio']['Cantidad'].sum() if not df_filtrado.empty else 0
    total_comp = df_filtrado[df_filtrado['Origen']=='Competencia']['Cantidad'].sum() if not df_filtrado.empty else 0
    pct_prop = (total_prop/total_uds*100) if total_uds else 0
    pct_comp = (total_comp/total_uds*100) if total_uds else 0

    # Texto Explicativo del Resumen
    st.markdown("### 📋 Resumen del Escaneo")
    if not df_filtrado.empty:
        st.info(f"""
        **¿Qué estamos viendo?** 
        El sistema ha leído el documento y extrajo un total de **{total_uds:,.0f} unidades** en **{len(df_filtrado)} líneas de productos**. 
        El gasto total detectado es de **${total_gasto:,.2f} MXN**.
        De este total, **{pct_prop:.1f}%** pertenecen a tu marca (Propio) y el **{pct_comp:.1f}%** pertenece a la Competencia. 
        *Nota: Si el escáner cometió un error, puedes corregirlo manualmente en la pestaña "Editar Datos".*
        """)

    # KPIs
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Volumen Total", f"{total_uds:,.0f} uds")
    m2.metric("Gasto Total", f"${total_gasto:,.2f}")
    m3.metric("Market Share Propio", f"{total_prop:,.0f} uds", f"{pct_prop:.1f}%")
    m4.metric("Market Share Competencia", f"{total_comp:,.0f} uds", f"-{pct_comp:.1f}%", delta_color="inverse")

    st.markdown("---")

    # Pestañas
    tab1, tab2, tab3 = st.tabs(["📊 Gráficos", "✏️ Editar Datos", "🤖 Asistente Copilot"])

    with tab1:
        if not df_filtrado.empty:
            g1, g2 = st.columns(2)
            with g1:
                fig1 = px.pie(df_filtrado, values='Cantidad', names='Origen', hole=0.4, title="Participación de Mercado", color='Origen', color_discrete_map={'Propio': '#3B82F6', 'Competencia': '#F43F5E'})
                fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#F8FAFC'))
                st.plotly_chart(fig1, use_container_width=True)
            with g2:
                top = df_filtrado.groupby(['Producto', 'Origen'])['Cantidad'].sum().reset_index().nlargest(10, 'Cantidad')
                fig2 = px.bar(top, x='Cantidad', y='Producto', color='Origen', orientation='h', title="Top 10 Productos por Unidades", color_discrete_map={'Propio': '#3B82F6', 'Competencia': '#F43F5E'})
                fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#F8FAFC'))
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sube un archivo con datos válidos para ver los gráficos.")

    with tab2:
        st.markdown("### ✏️ Edición Interactiva de Datos")
        st.caption("¿El escáner cometió un error? Haz doble clic en cualquier celda para corregir.")
        
        df_editado = st.data_editor(
            df_filtrado, 
            use_container_width=True, 
            num_rows="dynamic", 
            hide_index=True
        )
        
        csv = df_editado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Datos Editados (CSV)", 
            data=csv, 
            file_name='reporte_corregido.csv', 
            mime='text/csv'
        )

    with tab3:
        st.markdown("### 💬 Copilot de Datos (Análisis Avanzado)")
        if "mensajes" not in st.session_state:
            st.session_state.mensajes = [{"role": "assistant", "content": "¡Hola! Soy tu asistente de datos. Prueba preguntando:\n- 'Dame un resumen detallado'\n- 'Lista todos los productos'\n- '¿Cuáles son los productos de la competencia?'\n- '¿Cuánto gasté en total?'"}]

        for msg in st.session_state.mensajes:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Pregúntale a los datos..."):
            st.session_state.mensajes.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            txt = prompt.lower()
            
            if "resumen" in txt or "detallado" in txt:
                top_prod = df_filtrado.groupby('Producto')['Cantidad'].sum().idxmax() if not df_filtrado.empty else "N/A"
                resp = f"""**📊 Resumen Detallado:**
- **Total Unidades:** {total_uds:,.0f} uds
- **Gasto Total:** ${total_gasto:,.2f} MXN
- **Total Líneas/Productos:** {len(df_filtrado)}
- **Producto Estrella:** {top_prod}
- **Tu Marca (Propio):** {total_prop:,.0f} uds ({pct_prop:.1f}%)
- **Competencia:** {total_comp:,.0f} uds ({pct_comp:.1f}%)"""

            elif "lista" in txt or "productos" in txt or "todo" in txt:
                if df_filtrado.empty:
                    resp = "No hay productos en la lista actual."
                else:
                    resp = "**📋 Listado de Productos Extraídos:**\n\n"
                    resp += "| Producto | Cantidad | Precio Unit. | Total | Origen |\n|---|---|---|---|---|\n"
                    for _, row in df_filtrado.iterrows():
                        resp += f"| {row['Producto']} | {row['Cantidad']} | ${row['Precio_Unitario']:,.2f} | ${row['Total']:,.2f} | {row['Origen']} |\n"

            elif "competencia" in txt:
                df_comp = df_filtrado[df_filtrado['Origen'] == 'Competencia']
                if df_comp.empty:
                    resp = "No se detectaron productos de la competencia en este documento."
                else:
                    resp = f"**🔴 Productos de la Competencia ({total_comp:,.0f} uds):**\n\n"
                    for _, row in df_comp.iterrows():
                        resp += f"- **{row['Producto']}**: {row['Cantidad']} uds | Total: ${row['Total']:,.2f}\n"

            elif "propio" in txt or "marca" in txt or "mía" in txt:
                df_prop = df_filtrado[df_filtrado['Origen'] == 'Propio']
                resp = f"**🔵 Tus Productos ({total_prop:,.0f} uds):**\n\n"
                for _, row in df_prop.iterrows():
                    resp += f"- **{row['Producto']}**: {row['Cantidad']} uds | Total: ${row['Total']:,.2f}\n"

            elif "gasto" in txt or "dinero" in txt or "total" in txt:
                resp = f"💰 **Análisis de Gasto:**\n\nEl gasto total detectado es de **${total_gasto:,.2f} MXN**.\n\n"
                if not df_filtrado.empty:
                    top_gasto = df_filtrado.groupby('Producto')['Total'].sum().nlargest(3)
                    resp += "**Top 3 productos que más gasto generaron:**\n"
                    for prod, monto in top_gasto.items():
                        resp += f"- {prod}: ${monto:,.2f}\n"

            elif "top" in txt or "mejor" in txt or "más" in txt:
                if df_filtrado.empty:
                    resp = "No hay productos para calcular el Top."
                else:
                    top = df_filtrado.groupby(['Producto', 'Origen'])['Cantidad'].sum().reset_index().nlargest(5, 'Cantidad')
                    resp = "**🏆 Top 5 Productos por Unidades:**\n\n"
                    for _, row in top.iterrows():
                        resp += f"- **{row['Producto']}** ({row['Origen']}): {row['Cantidad']} uds\n"

            else:
                encontrado = False
                for _, row in df_filtrado.iterrows():
                    if row['Producto'].lower() in txt:
                        resp = f"🔍 **Detalle del producto encontrado:**\n- **Producto:** {row['Producto']}\n- **Cantidad:** {row['Cantidad']} uds\n- **Precio Unitario:** ${row['Precio_Unitario']:,.2f}\n- **Total:** ${row['Total']:,.2f}\n- **Origen:** {row['Origen']}"
                        encontrado = True
                        break
                
                if not encontrado:
                    resp = f"No encontré una coincidencia exacta para '{prompt}'. Intenta usar palabras clave como 'resumen', 'lista', 'competencia', 'propio', 'gasto' o el nombre exacto de un producto."

            st.session_state.mensajes.append({"role": "assistant", "content": resp})
            st.chat_message("assistant").write(resp)

else:
    st.info("👋 Sube un archivo (Excel, PDF, Imagen) o pega el texto de un ticket en el panel lateral para comenzar.")