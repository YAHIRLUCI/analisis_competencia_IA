import streamlit as st
import pandas as pd
import plotly.express as px

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

# 3. FUNCIÓN DE LIMPIEZA DE DATOS
@st.cache_data
def procesar_datos(archivo_cargado):
    df = pd.read_excel(archivo_cargado, header=None)

    df_limpio = df.iloc[:, [0, 5, 6, 7, 13]].copy()

    df_limpio.columns = [
        'ID_Pedido',
        'Cantidad',
        'Categoria',
        'Producto',
        'Cliente'
    ]

    df_limpio = df_limpio.dropna(subset=['Producto'])

    df_limpio['Cantidad'] = pd.to_numeric(
        df_limpio['Cantidad'],
        errors='coerce'
    ).fillna(0)

    def clasificar_origen(nombre_producto):
        nombre_str = str(nombre_producto).upper()

        # Ajusta estas palabras clave según tu competencia
        palabras_competencia = [
            'OTRO_MARCA',
            'COMPETIDOR_X'
        ]

        for palabra in palabras_competencia:
            if palabra in nombre_str:
                return 'Competencia'

        return 'Propio'

    df_limpio['Origen'] = df_limpio['Producto'].apply(
        clasificar_origen
    )

    return df_limpio


# 4. INTERFAZ DE USUARIO PRINCIPAL
st.title("📊 Panel de Inteligencia de Mercado")

st.markdown(
    "Sube tu archivo de ventas para analizar la distribución "
    "de productos propios frente a la competencia."
)


# PANEL LATERAL
with st.sidebar:

    st.header("⚙️ Configuración")

    archivo_subido = st.file_uploader(
        "Cargar reporte (Excel)",
        type=["xlsx", "xls"]
    )

    st.markdown("---")

    st.info(
        "💡 Asegúrate de que el archivo tenga la estructura estándar."
    )


# 5. COMPROBAR SI EXISTE UN ARCHIVO
if archivo_subido is not None:

    try:

        # Procesar archivo
        df = procesar_datos(archivo_subido)

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

            campo_busqueda = st.selectbox(
                "Buscar por:",
                [
                    "Cliente",
                    "Producto",
                    "Categoria",
                    "ID_Pedido"
                ]
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
            )

            cliente_seleccionado = st.selectbox(
                "Seleccionar Cliente (Óptica):",
                lista_clientes
            )

        with col_filtro2:

            origen_seleccionado = st.multiselect(
                "Filtrar por Origen:",
                options=df['Origen'].unique(),
                default=df['Origen'].unique()
            )


        # ---------------------------------------------------------
        # NUEVO: CAJA DE PROMPT
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

            st.info(
                f"📝 Indicación recibida: {prompt_usuario}"
            )


        # ---------------------------------------------------------
        # APLICAR FILTROS
        # ---------------------------------------------------------

        df_filtrado = df.copy()

        if cliente_seleccionado != "Todos":

            df_filtrado = df_filtrado[
                df_filtrado['Cliente'] == cliente_seleccionado
            ]

        if origen_seleccionado:

            df_filtrado = df_filtrado[
                df_filtrado['Origen'].isin(
                    origen_seleccionado
                )
            ]

        if texto_busqueda.strip():

            texto = texto_busqueda.strip().lower()

            df_filtrado = df_filtrado[
                df_filtrado[campo_busqueda]
                .astype(str)
                .str.lower()
                .str.contains(
                    texto,
                    na=False
                )
            ]


        # ---------------------------------------------------------
        # RESUMEN
        # ---------------------------------------------------------

        st.markdown("---")

        st.subheader(
            f"📈 Resumen para: {cliente_seleccionado}"
        )

        col_met1, col_met2, col_met3 = st.columns(3)

        total_productos = (
            df_filtrado['Cantidad'].sum()
        )

        total_propios = (
            df_filtrado[
                df_filtrado['Origen'] == 'Propio'
            ]['Cantidad'].sum()
        )

        total_competencia = (
            df_filtrado[
                df_filtrado['Origen'] == 'Competencia'
            ]['Cantidad'].sum()
        )

        col_met1.metric(
            label="Total Unidades",
            value=f"{total_productos:,.0f}"
        )

        col_met2.metric(
            label="Unidades Propias",
            value=f"{total_propios:,.0f}"
        )

        col_met3.metric(
            label="Unidades Competencia",
            value=f"{total_competencia:,.0f}"
        )


        # ---------------------------------------------------------
        # RESULTADOS
        # ---------------------------------------------------------

        st.markdown("---")

        st.subheader("📋 Resultados")

        if df_filtrado.empty:

            st.warning(
                "⚠️ No se encontraron resultados "
                "con los filtros seleccionados."
            )

        else:

            st.success(
                f"Se encontraron "
                f"**{len(df_filtrado)} registros**."
            )


        # ---------------------------------------------------------
        # GRÁFICA Y TABLA
        # ---------------------------------------------------------

        col_graf1, col_graf2 = st.columns([2, 1])

        with col_graf1:

            st.markdown(
                "#### Distribución de Productos"
            )

            resumen_prod = (
                df_filtrado
                .groupby(
                    ['Producto', 'Origen']
                )['Cantidad']
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

            st.plotly_chart(
                fig_bar,
                use_container_width=True
            )

        with col_graf2:

            st.markdown(
                "#### Detalle de Datos"
            )

            st.dataframe(
                df_filtrado[
                    [
                        'ID_Pedido',
                        'Producto',
                        'Categoria',
                        'Cliente',
                        'Origen',
                        'Cantidad'
                    ]
                ],

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
        "👈 Por favor, carga un archivo Excel en el menú "
        "lateral para comenzar el análisis."
    )