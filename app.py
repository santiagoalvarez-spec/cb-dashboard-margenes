import io
import json
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from email_db import (
    add_contact,
    delete_contact,
    get_contacts,
    get_email_log,
    init_db,
    toggle_contact,
)
from email_service import send_bulk_emails
from scheduler import is_job_active, next_run_time, remove_job, schedule_job

# ── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()

SMTP_CONFIG_FILE = Path("smtp_config.json")

st.set_page_config(page_title="Dashboard Márgenes de Servicios", layout="wide")
st.title("📊 Dashboard Márgenes de Servicios")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(col: str) -> str:
    """Normaliza nombres de columnas para que no fallen los acentos ni los espacios."""
    col = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode("ascii")
    col = col.strip().lower()
    col = col.replace("%", "porc").replace("$", "usd").replace(" ", "_")
    return col


def _load_smtp_config() -> dict:
    if SMTP_CONFIG_FILE.exists():
        return json.loads(SMTP_CONFIG_FILE.read_text())
    return {
        "host": "smtp.gmail.com",
        "port": "587",
        "user": "",
        "password": "",
        "from_email": "",
        "from_name": "Dashboard Márgenes",
        "use_ssl": False,
    }


def _save_smtp_config(cfg: dict):
    SMTP_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.read()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_dash, tab_email = st.tabs(["📊 Dashboard", "📧 Email Automático"])


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TAB 1 – DASHBOARD
# ╚══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    st.markdown(
        """
        Sube el archivo **Margen Productos.xlsx** (o cualquier Excel con columnas similares).<br>
        Si tus datos cambian frecuentemente, considera conectarlo a Google Sheets para ver todo en tiempo real.
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "📤 Carga tu archivo de Excel", type=["xlsx", "xls"]
    )

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
        col_servicio = next(
            (c for c in df.columns if "servicio" in c), df.columns[0]
        )
        col_venta = next(
            (
                c
                for c in df.columns
                if ("precio" in c and "venta" in c) or "venta" == c
            ),
            None,
        )
        col_utilidad_abs = next(
            (
                c
                for c in df.columns
                if ("utilidad" in c and "porc" not in c) or "ganancia" in c
            ),
            None,
        )
        col_utilidad_pct = next(
            (
                c
                for c in df.columns
                if ("utilidad" in c and "porc" in c)
                or "margen" in c
                or (
                    "%" in original_cols[df.columns.get_loc(c)] if c else False
                )
            ),
            None,
        )

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
        search = st.text_input("🔍 Busca un servicio", "")
        if search:
            filtered_df = df[
                df[col_servicio].str.contains(search, case=False, na=False)
            ]
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
            st.info(
                "Sin datos para graficar. Revisa el filtro o la columna de márgenes."
            )

        # Descarga
        excel_bytes = _df_to_excel_bytes(filtered_df)
        st.download_button(
            "📥 Descargar datos filtrados",
            data=excel_bytes,
            file_name="margenes_filtrados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Guardar df en session_state para usarlo en el tab de email
        st.session_state["last_df"] = filtered_df
    else:
        st.info("Para comenzar, sube tu archivo de Excel en el panel de la izquierda.")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TAB 2 – EMAIL AUTOMÁTICO
# ╚══════════════════════════════════════════════════════════════════════════════
with tab_email:

    # ── 1. Configuración SMTP ─────────────────────────────────────────────────
    with st.expander("⚙️ Configuración SMTP", expanded=False):
        cfg = _load_smtp_config()

        c1, c2 = st.columns(2)
        smtp_host = c1.text_input("Servidor SMTP", value=cfg["host"], key="smtp_host")
        smtp_port = c2.text_input("Puerto", value=cfg["port"], key="smtp_port")

        c3, c4 = st.columns(2)
        smtp_user = c3.text_input("Usuario / email de cuenta", value=cfg["user"], key="smtp_user")
        smtp_pass = c4.text_input("Contraseña / App Password", value=cfg["password"],
                                   type="password", key="smtp_pass")

        c5, c6 = st.columns(2)
        smtp_from = c5.text_input("Email remitente", value=cfg["from_email"], key="smtp_from")
        smtp_name = c6.text_input("Nombre remitente", value=cfg["from_name"], key="smtp_name")
        smtp_ssl = st.checkbox("Usar SSL directo (puerto 465)", value=cfg.get("use_ssl", False),
                               key="smtp_ssl")

        if st.button("💾 Guardar configuración SMTP"):
            new_cfg = {
                "host": smtp_host,
                "port": smtp_port,
                "user": smtp_user,
                "password": smtp_pass,
                "from_email": smtp_from,
                "from_name": smtp_name,
                "use_ssl": smtp_ssl,
            }
            _save_smtp_config(new_cfg)
            st.success("Configuración guardada.")

    st.markdown("---")

    # ── 2. Gestión de contactos ───────────────────────────────────────────────
    st.subheader("👥 Base de datos de contactos")

    with st.form("add_contact_form", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns(3)
        new_name    = fc1.text_input("Nombre *")
        new_email   = fc2.text_input("Email *")
        new_company = fc3.text_input("Empresa")
        submitted   = st.form_submit_button("➕ Agregar contacto")

    if submitted:
        if not new_name or not new_email:
            st.warning("Nombre y email son obligatorios.")
        elif "@" not in new_email:
            st.warning("Email no válido.")
        else:
            ok = add_contact(new_name, new_email, new_company)
            if ok:
                st.success(f"Contacto **{new_name}** agregado.")
            else:
                st.warning("Ese email ya existe en la base de datos.")

    # Mostrar tabla de contactos
    all_contacts = get_contacts(active_only=False)
    if all_contacts:
        st.markdown(f"**{len(all_contacts)} contactos registrados**")
        for row in all_contacts:
            cid, cname, cemail, ccompany, cactive, ccreated = row
            col_a, col_b, col_c, col_d, col_e = st.columns([3, 3, 2, 1, 1])
            col_a.write(f"**{cname}**")
            col_b.write(cemail)
            col_c.write(ccompany or "—")
            new_active = col_d.checkbox("Activo", value=bool(cactive), key=f"active_{cid}")
            if new_active != bool(cactive):
                toggle_contact(cid, new_active)
                st.rerun()
            if col_e.button("🗑️", key=f"del_{cid}", help="Eliminar contacto"):
                delete_contact(cid)
                st.rerun()
    else:
        st.info("No hay contactos. Agrega el primero usando el formulario de arriba.")

    st.markdown("---")

    # ── 3. Composición del email ──────────────────────────────────────────────
    st.subheader("✉️ Composición del email")

    email_subject = st.text_input(
        "Asunto",
        value="Reporte de Márgenes de Servicios",
        key="email_subject",
    )

    default_body = """\
<p>Hola {name},</p>

<p>Te enviamos el reporte actualizado de <strong>Márgenes de Servicios</strong>.</p>

<p>Encontrarás el detalle completo en el archivo adjunto.</p>

<p>Saludos,<br>Equipo Dashboard Márgenes</p>
"""
    email_body = st.text_area(
        "Cuerpo del email (HTML). Usa {name} y {company} como variables.",
        value=default_body,
        height=200,
        key="email_body",
    )

    attach_report = st.checkbox(
        "📎 Adjuntar reporte Excel (usa el archivo cargado en el Dashboard)",
        value=True,
        key="attach_report",
    )

    st.markdown("---")

    # ── 4. Envío manual ───────────────────────────────────────────────────────
    st.subheader("🚀 Envío manual")

    active_contacts = get_contacts(active_only=True)
    st.write(f"Se enviará a **{len(active_contacts)} contacto(s) activo(s)**.")

    if st.button("📤 Enviar ahora a todos los contactos", type="primary",
                 disabled=len(active_contacts) == 0):
        smtp_cfg = _load_smtp_config()
        if not smtp_cfg["user"] or not smtp_cfg["password"]:
            st.error("Configura el SMTP primero (usuario y contraseña vacíos).")
        else:
            attachment = st.session_state.get("last_df") if attach_report else None
            with st.spinner("Enviando emails…"):
                results = send_bulk_emails(
                    smtp_cfg,
                    active_contacts,
                    email_subject,
                    email_body,
                    attachment_df=attachment,
                )
            ok_count = sum(1 for r in results if r["success"])
            err_count = len(results) - ok_count
            if err_count == 0:
                st.success(f"✅ {ok_count} emails enviados correctamente.")
            else:
                st.warning(f"✅ {ok_count} enviados, ❌ {err_count} con error.")
                for r in results:
                    if not r["success"]:
                        st.error(f"{r['email']}: {r['error']}")

    st.markdown("---")

    # ── 5. Automatización programada ─────────────────────────────────────────
    st.subheader("🤖 Automatización programada")

    auto_col1, auto_col2 = st.columns(2)
    interval_hours = auto_col1.number_input(
        "Intervalo de envío (horas)", min_value=1, max_value=720, value=24, step=1
    )

    job_active = is_job_active("auto_email")
    status_label = "🟢 Activo" if job_active else "🔴 Detenido"
    auto_col2.metric("Estado del scheduler", status_label)
    if job_active:
        auto_col2.caption(f"Próximo envío: {next_run_time('auto_email')}")

    def _auto_send():
        """Función ejecutada automáticamente por el scheduler."""
        cfg_ = _load_smtp_config()
        if not cfg_["user"] or not cfg_["password"]:
            return
        contacts_ = get_contacts(active_only=True)
        if not contacts_:
            return
        send_bulk_emails(
            cfg_,
            contacts_,
            email_subject if "email_subject" in st.session_state else "Reporte de Márgenes",
            email_body if "email_body" in st.session_state else default_body,
            attachment_df=None,  # no hay df disponible en background
        )

    btn_c1, btn_c2 = st.columns(2)
    if btn_c1.button("▶️ Activar envío automático"):
        schedule_job(_auto_send, interval_hours=float(interval_hours))
        st.success(f"Scheduler activado: se enviará cada {interval_hours} hora(s).")
        st.rerun()

    if btn_c2.button("⏹️ Detener envío automático", disabled=not job_active):
        remove_job("auto_email")
        st.info("Scheduler detenido.")
        st.rerun()

    st.markdown("---")

    # ── 6. Historial de emails ────────────────────────────────────────────────
    st.subheader("📋 Historial de envíos")

    log_rows = get_email_log(limit=100)
    if log_rows:
        log_df = pd.DataFrame(
            log_rows,
            columns=["Email", "Asunto", "Estado", "Fecha/Hora", "Error"],
        )
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se ha enviado ningún email.")
