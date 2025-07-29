import streamlit as st
import pandas as pd

st.set_page_config(page_title="Dashboard Márgenes de Servicios", layout="wide")

st.title("📊 Dashboard Márgenes de Servicios")

st.markdown("""
Sube el archivo **Margen Productos.xlsx** o cualquiera con el mismo formato.
Si los datos cambian con frecuencia, conecta este dashboard a Google Sheets para tener todo en tiempo real.
""")

uploaded_file = st.file_uploader("📤 Carga tu archivo de Excel", type=["xlsx", "xls"])  # noqa: E501

if uploaded_file:
    # Leemos la primera hoja del archivo
    df = pd.read_excel(uploaded_file)

    # Normalizamos los nombres de las columnas por si vienen con espacios o tildes diferentes
    df.columns = df.columns.str.strip()

    # KPI principales
    total_ventas = df["Precio de venta"].sum()
    total_utilidad = df["$ Utilidad"].sum()
    margen_promedio = df["% Uitilidad"].mean()

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Ventas totales", f"${total_ventas:,.0f}")
    kpi2.metric("Utilidad total", f"${total_utilidad:,.0f}")
    kpi3.metric("Margen promedio", f"{margen_promedio:.1%}")

    st.markdown("---")

    # Filtro de búsqueda por servicio
    search = st.text_input("🔍 Busca un servicio", "")
    if search:
        filtered_df = df[df["Nombre del servicio"].str.contains(search, case=False, na=False)]
    else:
        filtered_df = df

    st.subheader("Tabla completa 🗒️")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # Gráfico de margen por servicio
    if "% Uitilidad" in df.columns:
        chart_df = (
            filtered_df[["Nombre del servicio", "% Uitilidad"]]
            .set_index("Nombre del servicio")
            .sort_values("% Uitilidad", ascending=False)
        )
        st.subheader("Márgenes por servicio 📈")
        st.bar_chart(chart_df)

    # Descarga del archivo filtrado
    @st.cache_data
    def to_excel(df_):
        return df_.to_excel(index=False, engine="xlsxwriter")

    excel_data = to_excel(filtered_df)
    st.download_button("📥 Descargar datos filtrados", data=excel_data, file_name="margenes_filtrados.xlsx")
else:
    st.info("Para comenzar, sube tu archivo de Excel en el panel de la izquierda.")
