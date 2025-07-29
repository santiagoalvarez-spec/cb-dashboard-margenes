import streamlit as st
import pandas as pd
import unicodedata

st.set_page_config(page_title="Dashboard Márgenes de Servicios", layout="wide")

st.title("📊 Dashboard Márgenes de Servicios")

st.markdown("""
Sube el archivo **Margen Productos.xlsx** (o cualquier Excel con columnas similares).<br>
Si tus datos cambian frecuentemente, considera conectarlo a Google Sheets para ver todo en tiempo real.
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📤 Carga tu archivo de Excel", type=["xlsx", "xls"])  # noqa: E501

def _clean(col: str) -> str:
    """Normaliza nombres de columnas para que no fallen los acentos ni los espacios."""
    col = unicodedata.normalize('NFKD', col).encode('ascii', 'ignore').decode('ascii')
    col = col.strip().lower()
    col = col.replace('%', 'porc').replace('$', 'usd').replace(' ', '_')
    return col

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as e:
        st.error(f"No pude leer el Excel: {e}")
        st.stop()

    # Normalizamos los nombres
    original_cols = df.columns.tolist()
    df.columns = [_clean(c) for c in df.columns]

    # Intentamos mapear las columnas claves por keywords
    col_servicio = next((c for c in df.columns if 'servicio' in c), df.columns[0])
    col_venta = next((c for c in df.columns if ('precio' in c and 'venta' in c) or 'venta' == c), None)
    col_utilidad_abs = next((c for c in df.columns if ('utilidad' in c and 'porc' not in c) or 'ganancia' in c), None)
    col_utilidad_pct = next((c for c in df.columns if ('utilidad' in c and 'porc' in c) or 'margen' in c or ('%' in original_cols[df.columns.get_loc(c)] if c else False)), None)

    # Validaciones mínimas
    if not all([col_venta, col_utilidad_abs, col_utilidad_pct]):
        st.warning(
            "No pude identificar todas las columnas necesarias. "
            "Revisa que tu Excel tenga precio de venta, utilidad $ y utilidad %/margen."
        )
        st.write("Nombres detectados:", df.columns.tolist())
        st.stop()

    total_ventas = df[col_venta].sum()
    total_utilidad = df[col_utilidad_abs].sum()
    margen_promedio = df[col_utilidad_pct].mean()

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Ventas totales", f"${total_ventas:,.0f}")
    kpi2.metric("Utilidad total", f"${total_utilidad:,.0f}")
    kpi3.metric("Margen promedio", f"{margen_promedio:.1%}")

    st.markdown("---")

    # Filtro de búsqueda
    search = st.text_input("🔍 Busca un servicio", "")
    if search:
        filtered_df = df[df[col_servicio].str.contains(search, case=False, na=False)]
    else:
        filtered_df = df

    st.subheader("Tabla completa 🗒️")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # Gráfico de margen
    st.subheader("Márgenes por servicio 📈")
    chart_df = (
        filtered_df[[col_servicio, col_utilidad_pct]]
        .dropna()
        .sort_values(col_utilidad_pct, ascending=False)
        .set_index(col_servicio)
    )
    if not chart_df.empty:
        st.bar_chart(chart_df)
    else:
        st.info("Sin datos para graficar. Revisa el filtro o la columna de márgenes.")

    # Descarga
    @st.cache_data
    def _to_excel(df_):
        return df_.to_excel(index=False, engine="xlsxwriter")

    excel_data = _to_excel(filtered_df)
    st.download_button(
        "📥 Descargar datos filtrados",
        data=excel_data,
        file_name="margenes_filtrados.xlsx",
    )
else:
    st.info("Para comenzar, sube tu archivo de Excel en el panel de la izquierda.")
