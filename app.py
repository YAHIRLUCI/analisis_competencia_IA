import streamlit as st
import pandas as pd
import re
import numpy as np
import requests

# Control de librerías para PDF y OCR
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import cv2
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError:
    cv2 = None
    pytesseract = None
    Image = None

# ============================================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Dashboard Ejecutivo | Productos Locales",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 2. ESTILOS CSS
# ============================================================
st.markdown("""
    <style>
    h1, h2, h3, h4 { color: #F8FAFC !important; font-weight: 700; }
    .stButton>button { background-color: #3B82F6; color: white; border-radius: 6px; border: none; transition: 0.3s; }
    .stButton>button:hover { background-color: #2563EB; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3); }
    div[data-testid="stMetricValue"] { font-size: 32px; font-weight: 800; color: #3B82F6; }
    div[data-testid="stMetricLabel"] { font-size: 13px; color: #94A3B8; font-weight: 600; text-transform: uppercase; }
    .producto-propio {
        background: linear-gradient(90deg, #1E293B 0%, #334155 100%);
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .producto-propio .nombre { font-size: 16px; font-weight: 700; color: #F8FAFC; }
    .producto-propio .detalle { font-size: 13px; color: #94A3B8; margin-top: 4px; }
    .producto-propio .cantidad { font-size: 20px; font-weight: 800; color: #3B82F6; float: right; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# 3. FUNCIONES
# ============================================================
def clasificar_origen(nombre_producto):
    nombre_str = str(nombre_producto).upper()
    palabras_competencia = ['OTRO_MARCA', 'COMPETIDOR_X', 'RIVAL', 'GENERICO', 'MARCA_X', 'COOPERVISION', 'ACUVUE', 'BIOFINITY', 'AIR OPTIX', 'DAILIES', 'CHEDRAUI', 'HUA XIN', 'FARMACIA']
    for palabra in palabras_competencia:
        if palabra in nombre_str:
            return 'Competencia'
    return 'Propio'

def corregir_errores_ocr(texto):
    reemplazos = {
        r'(?<=\d)O': '0',
        r'(?<=\d)l': '1',
        r'\bl(?=\d)': '1',
        r'[|]': 'I',
        r'[—–]': '-',
    }
    for patron, reemplazo in reemplazos.items():
        texto = re.sub(patron, reemplazo, texto)
    return texto

def extraer_productos_de_texto(texto):
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
        'PAGO', 'CREDITO', 'SALDO', 'ANTERIOR', 'DISPONIBLE', 'PRESENTA', 'EXIGE', 'GRACIAS',
        'AHORRANDO', 'CONTIGO', 'COMPROBANTE', 'ENTREGA', 'USO', 'INTERNO'
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

        match1 = re.search(r'^(\d+[\.,]\d{3})\s*(.+?)\s*(\d+[\.,]\d{2})\s*(\d+[\.,]\d{2})', linea_actual)
        if match1:
            cantidad = float(match1.group(1).replace(',', '.'))
            producto = match1.group(2).strip()
            precio_unit = float(match1.group(3).replace(',', '.'))
            total = float(match1.group(4).replace(',', '.'))
            match_encontrado = True

        if not match_encontrado:
            match2 = re.search(r'^(\d+)\s*(?:PZ|PZA|PIEZA)?\s+(.+?)\s+\$?(\d+[\.,]\d{2})$', linea_actual)
            if match2:
                cantidad = float(match2.group(1))
                producto = match2.group(2).strip()
                total = float(match2.group(3).replace(',', '.'))
                precio_unit = total / cantidad if cantidad > 0 else total
                match_encontrado = True

        if not match_encontrado:
            match3 = re.search(r'^(\d+)\s*[xX]?\s*(\d+[\.,]\d{2})\s+(.+?)\s+(\d+[\.,]\d{2})$', linea_actual)
            if match3:
                cantidad = float(match3.group(1))
                precio_unit = float(match3.group(2).replace(',', '.'))
                producto = match3.group(3).strip()
                total = float(match3.group(4).replace(',', '.'))
                match_encontrado = True

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

        if not match_encontrado:
            match5 = re.search(r'^(\d+[\.,]?\d*)\s+([A-Za-z].*?)\s+\$?(\d+[\.,]\d{2})$', linea_actual)
            if match5:
                cantidad = float(match5.group(1).replace(',', '.'))
                producto = match5.group(2).strip()
                total = float(match5.group(3).replace(',', '.'))
                precio_unit = total / cantidad if cantidad > 0 else 0
                match_encontrado = True

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

def leer_con_ocr_space(archivo_bytes, nombre_archivo, api_key):
    try:
        extension = nombre_archivo.lower().split('.')[-1]
        mime_types = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'pdf': 'application/pdf'}
        mime_type = mime_types.get(extension, 'application/octet-stream')
        files = {'file': (nombre_archivo, archivo_bytes, mime_type)}
        data = {'apikey': api_key, 'language': 'spa', 'isOverlayRequired': False, 'detectOrientation': True, 'scale': True, 'OCREngine': 2, 'isTable': True, 'filetype': extension.upper()}
        response = requests.post('https://api.ocr.space/parse/image', files=files, data=data, timeout=120)
        resultado = response.json()
        if resultado.get('IsErroredOnProcessing'):
            error_msg = resultado.get('ErrorMessage', ['Error desconocido'])
            if isinstance(error_msg, list): error_msg = ' | '.join(str(e) for e in error_msg)
            return None, f"Error OCR.space: {error_msg}"
        if resultado.get('ParsedResults'):
            texto = resultado['ParsedResults'][0].get('ParsedText', '')
            if texto.strip(): return texto, None
            return None, "OCR.space no detectó texto."
        return None, "Respuesta vacía de OCR.space."
    except Exception as e:
        return None, f"Error de conexión: {str(e)}"

def procesar_imagen_tesseract(archivo):
    if cv2 is None or pytesseract is None:
        return None, "Tesseract no está instalado."
    try:
        file_bytes = np.asarray(bytearray(archivo.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45: angle = -(90 + angle)
            else: angle = -angle
            (h, w) = binary.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        texto_ocr = pytesseract.image_to_string(binary, lang='spa', config='--oem 3 --psm 6')
        texto_ocr = corregir_errores_ocr(texto_ocr)
        return texto_ocr, None
    except Exception as e:
        return None, f"Error Tesseract: {str(e)}"

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
    df_limpio['Total'] = pd.to_numeric(df[col_precio], errors='coerce').fillna(0) if col_precio else 0.0
    df_limpio['Precio_Unitario'] = df_limpio['Total'] / df_limpio['Cantidad'].replace(0, 1)
    if col_origen:
        df_limpio['Origen'] = df[col_origen].astype(str).str.strip().str.capitalize()
    else:
        df_limpio['Origen'] = df_limpio['Producto'].apply(clasificar_origen)
    return df_limpio

# ============================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================
st.title("📊 Dashboard Ejecutivo | Productos Locales")
st.markdown("Análisis automatizado de tickets y reportes de ventas locales.")

st.warning("""
⚠️ **AVISO IMPORTANTE:** Esta herramienta está diseñada **únicamente para el análisis de productos locales**. 
Los datos aquí mostrados corresponden exclusivamente al mercado local y no deben ser utilizados para comparaciones 
con otros mercados o regiones.
""")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3094/3094939.png", width=50)
    st.header("Gestor de Archivos")
    st.markdown("### 🔑 OCR Inteligente")
    ocr_api_key = st.text_input("Clave de OCR.space:", type="password", value=st.session_state.get('ocr_api_key', ''))
    if ocr_api_key:
        st.session_state['ocr_api_key'] = ocr_api_key
    if not ocr_api_key:
        st.warning("⚠️ Sin clave, la lectura de fotos será básica.")
    st.markdown("---")
    archivo_subido = st.file_uploader("Sube tu archivo aquí", type=["xlsx", "xls", "csv", "pdf", "png", "jpg", "jpeg"])
    if archivo_subido:
        st.success("✅ Archivo cargado correctamente.")
    st.markdown("---")
    st.markdown("### 📱 ¿La foto no se lee?")
    st.info("1. Abre la foto en tu celular.\n2. Usa **Google Lens**.\n3. Pega el texto aquí abajo.")
    texto_manual = st.text_area("Pega aquí el texto del ticket:", height=150)
    boton_manual = st.button("🚀 Procesar Texto Manual")

# ============================================================
# 5. LÓGICA PRINCIPAL
# ============================================================
if archivo_subido is not None or (boton_manual and texto_manual):
    with st.spinner("Procesando datos..."):
        
        df = pd.DataFrame()
        mensaje_error = None
        
        if boton_manual and texto_manual:
            df = extraer_productos_de_texto(texto_manual)
                
        elif archivo_subido:
            nombre = archivo_subido.name.lower()
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
            elif nombre.endswith('.pdf'):
                if pdfplumber:
                    with pdfplumber.open(archivo_subido) as pdf:
                        texto_pdf = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
                    df = extraer_productos_de_texto(texto_pdf)
                else:
                    mensaje_error = "Falta instalar pdfplumber."
            elif nombre.endswith(('.png', '.jpg', '.jpeg')):
                texto_extraido = None
                if ocr_api_key:
                    archivo_subido.seek(0)
                    archivo_bytes = archivo_subido.read()
                    texto_extraido, error_ocr = leer_con_ocr_space(archivo_bytes, archivo_subido.name, ocr_api_key)
                    if error_ocr:
                        mensaje_error = error_ocr
                        texto_extraido = None
                if texto_extraido is None and not mensaje_error:
                    archivo_subido.seek(0)
                    texto_extraido, error_tess = procesar_imagen_tesseract(archivo_subido)
                    if error_tess: mensaje_error = error_tess
                if texto_extraido:
                    df = extraer_productos_de_texto(texto_extraido)
            else:
                mensaje_error = "Formato no compatible."

        if mensaje_error:
            st.error(f"❌ {mensaje_error}")

        if df is None or df.empty:
            st.warning("⚠️ No se pudieron detectar productos. Prueba con la caja de **Texto Manual**.")
            df = pd.DataFrame(columns=['ID_Pedido', 'Cantidad', 'Producto', 'Precio_Unitario', 'Total', 'Cliente', 'Origen'])

    # ============================================================
    # PASO 1: EDITOR (PRIMERO - antes de cualquier cálculo)
    # ============================================================
    st.markdown("### ✏️ Editor de Productos (Tiempo Real)")
    st.caption("Haz doble clic en cualquier celda para editar. Agrega filas con el botón '+'. Los cambios se reflejan automáticamente en las métricas de abajo.")
    
    df_editado = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="editor_principal"
    )

    st.markdown("---")

    # ============================================================
    # PASO 2: CÁLCULOS (usan df_editado, no df)
    # ============================================================
    total_uds = df_editado['Cantidad'].sum() if not df_editado.empty else 0
    total_gasto = df_editado['Total'].sum() if not df_editado.empty else 0
    total_prop = df_editado[df_editado['Origen']=='Propio']['Cantidad'].sum() if not df_editado.empty else 0
    total_comp = df_editado[df_editado['Origen']=='Competencia']['Cantidad'].sum() if not df_editado.empty else 0
    pct_prop = (total_prop/total_uds*100) if total_uds else 0
    pct_comp = (total_comp/total_uds*100) if total_uds else 0

    st.markdown("### 📋 Resumen del Escaneo")
    st.info(f"""
    **Resumen actual (después de tus ediciones):** 
    Se tienen **{total_uds:,.0f} unidades** en **{len(df_editado)} líneas de productos**. 
    El gasto total es de **${total_gasto:,.2f} MXN**.
    Propio: **{pct_prop:.1f}%** | Competencia: **{pct_comp:.1f}%**
    """)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Volumen Total", f"{total_uds:,.0f} uds")
    m2.metric("Gasto Total", f"${total_gasto:,.2f}")
    m3.metric("Market Share Propio", f"{total_prop:,.0f} uds", f"{pct_prop:.1f}%")
    m4.metric("Market Share Competencia", f"{total_comp:,.0f} uds", f"-{pct_comp:.1f}%", delta_color="inverse")

    st.markdown("---")

    # ============================================================
    # PASO 3: LISTA DE PRODUCTOS PROPIOS + COPILOT
    # ============================================================
    tab1, tab2 = st.tabs(["🏷️ Productos Propios", "🤖 Asistente Copilot"])

    with tab1:
        st.markdown("### 🏷️ Lista de Productos Propios")
        st.caption("Productos con Origen = Propio. Se actualizan en tiempo real al editar la tabla.")
        
        df_propios = df_editado[df_editado['Origen'] == 'Propio'].copy() if not df_editado.empty else pd.DataFrame()
        
        if df_propios.empty:
            st.info("No hay productos propios. Puedes cambiar el Origen en el editor de arriba.")
        else:
            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("Productos Propios", f"{len(df_propios)}")
            cp2.metric("Unidades Propias", f"{df_propios['Cantidad'].sum():,.0f} uds")
            cp3.metric("Valor Propio", f"${df_propios['Total'].sum():,.2f}")
            
            st.markdown("---")
            st.markdown("#### Detalle Visual")
            for _, row in df_propios.iterrows():
                st.markdown(f"""
                <div class="producto-propio">
                    <span class="cantidad">{row['Cantidad']:,.0f} uds</span>
                    <div class="nombre">{row['Producto']}</div>
                    <div class="detalle">
                        💰 ${row['Precio_Unitario']:,.2f} c/u &nbsp;|&nbsp; 
                        💵 Total: ${row['Total']:,.2f} &nbsp;|&nbsp; 
                        🆔 {row['ID_Pedido']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("#### Tabla Detallada")
            st.dataframe(df_propios, use_container_width=True, hide_index=True)
            csv = df_propios.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Productos Propios (CSV)", data=csv, file_name='productos_propios.csv', mime='text/csv')

    with tab2:
        st.markdown("### 💬 Copilot de Datos")
        if "mensajes" not in st.session_state:
            st.session_state.mensajes = [{"role": "assistant", "content": "¡Hola! Prueba:\n- 'resumen detallado'\n- 'lista todos los productos'\n- 'productos propios'\n- 'competencia'\n- 'gasto total'"}]

        for msg in st.session_state.mensajes:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Pregúntale a los datos..."):
            st.session_state.mensajes.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            txt = prompt.lower()
            
            if "resumen" in txt:
                resp = f"**📊 Resumen:**\n- Total: {total_uds:,.0f} uds\n- Gasto: ${total_gasto:,.2f}\n- Propio: {total_prop:,.0f} uds ({pct_prop:.1f}%)\n- Competencia: {total_comp:,.0f} uds ({pct_comp:.1f}%)"
            elif "propio" in txt or "marca" in txt:
                df_prop = df_editado[df_editado['Origen'] == 'Propio']
                resp = f"**🔵 Productos Propios ({total_prop:,.0f} uds):**\n\n" + "\n".join([f"- {r['Producto']}: {r['Cantidad']} uds | ${r['Total']:,.2f}" for _, r in df_prop.iterrows()])
            elif "competencia" in txt:
                df_comp = df_editado[df_editado['Origen'] == 'Competencia']
                resp = f"**🔴 Competencia ({total_comp:,.0f} uds):**\n\n" + "\n".join([f"- {r['Producto']}: {r['Cantidad']} uds" for _, r in df_comp.iterrows()]) if not df_comp.empty else "No hay competencia."
            elif "lista" in txt or "productos" in txt:
                resp = "**📋 Productos:**\n\n| Producto | Cantidad | Total | Origen |\n|---|---|---|---|\n"
                for _, row in df_editado.iterrows():
                    resp += f"| {row['Producto']} | {row['Cantidad']} | ${row['Total']:,.2f} | {row['Origen']} |\n"
            elif "gasto" in txt:
                resp = f"💰 **Gasto Total:** ${total_gasto:,.2f} MXN"
            else:
                encontrado = False
                for _, row in df_editado.iterrows():
                    if row['Producto'].lower() in txt:
                        resp = f"🔍 **{row['Producto']}** - Cantidad: {row['Cantidad']} uds, Total: ${row['Total']:,.2f}"
                        encontrado = True
                        break
                if not encontrado:
                    resp = f"No encontré '{prompt}'. Prueba 'resumen', 'propio', 'competencia' o 'gasto'."

            st.session_state.mensajes.append({"role": "assistant", "content": resp})
            st.chat_message("assistant").write(resp)

else:
    st.info("👋 Sube un archivo o pega el texto de un ticket en el panel lateral.")