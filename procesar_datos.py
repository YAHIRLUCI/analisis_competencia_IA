import pandas as pd

def preparar_datos_powerbi(nombre_archivo_entrada='archivosyl.xlsx'):
    print("Iniciando procesamiento de datos para Power BI...")
    
    # 1. Cargar el archivo Excel con encabezados
    try:
        df = pd.read_excel(nombre_archivo_entrada)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{nombre_archivo_entrada}'. Asegúrate de que esté en esta carpeta.")
        return

    # Normalizar nombres de columnas (eliminar espacios accidentales)
    df.columns = [str(c).strip() for c in df.columns]

    # 2. Mapear dinámicamente las columnas según la estructura real del Excel
    col_pedido = 'Pedido' if 'Pedido' in df.columns else ('ID_Pedido' if 'ID_Pedido' in df.columns else df.columns[0])
    col_cantidad = 'Cantidad de producto' if 'Cantidad de producto' in df.columns else ('Cantidad' if 'Cantidad' in df.columns else None)
    col_categoria = 'Presentación' if 'Presentación' in df.columns else ('Ruta' if 'Ruta' in df.columns else None)
    col_producto = 'Nombre del producto' if 'Nombre del producto' in df.columns else ('Producto' if 'Producto' in df.columns else None)
    col_cliente = 'Óptica' if 'Óptica' in df.columns else ('Cliente' if 'Cliente' in df.columns else None)
    col_origen = 'Origen' if 'Origen' in df.columns else None

    # 3. Crear DataFrame estructurado y limpio
    df_limpio = pd.DataFrame()
    
    df_limpio['ID_Pedido'] = df[col_pedido]
    df_limpio['Cantidad'] = pd.to_numeric(df[col_cantidad], errors='coerce').fillna(1) if col_cantidad else 1
    df_limpio['Categoria'] = df[col_categoria] if col_categoria else "General"
    df_limpio['Producto'] = df[col_producto] if col_producto else "Sin especificación"
    df_limpio['Cliente'] = df[col_cliente] if col_cliente else "Cliente General"

    # 4. Clasificación de Competencia vs Propio
    if col_origen and col_origen in df.columns:
        # Si la columna Origen ya existe en el Excel, la mantenemos intacta
        df_limpio['Origen'] = df[col_origen].astype(str).str.strip().str.capitalize()
    else:
        # Si NO existe, aplicamos la regla de clasificación por palabras clave
        def clasificar_origen(nombre_producto):
            nombre_str = str(nombre_producto).upper()
            palabras_competencia = [
                'COOPERVISION', 'MYDAY', 'ACUVUE', 'OASYS', 'BIOFINITY', 'AIR OPTIX', 'DAILIES'
            ] 
            for palabra in palabras_competencia:
                if palabra in nombre_str:
                    return 'Competencia'
            return 'Propio'

        df_limpio['Origen'] = df_limpio['Producto'].apply(clasificar_origen)

    # 5. Limpieza final
    df_limpio = df_limpio.dropna(subset=['Producto'])

    # 6. Guardar el nuevo archivo optimizado
    nombre_salida = 'datos_limpios_competencia.xlsx'
    df_limpio.to_excel(nombre_salida, index=False)
    
    print(f"\n¡Éxito! Archivo guardado como: {nombre_salida}")
    print(f"Total de registros procesados: {len(df_limpio)}")
    print("\nDesglose de Origen procesado:")
    print(df_limpio['Origen'].value_counts())

# Ejecutar la función
if __name__ == "__main__":
    preparar_datos_powerbi()