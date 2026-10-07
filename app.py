import os
import streamlit as st
import pandas as pd
import math
from supabase import create_client

st.set_page_config(page_title="Cotizador Avanzado", layout="wide")

# --- 1. INICIALIZAR SUPABASE ---
@st.cache_resource
def init_supabase():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_supabase()

# --- 2. ESTRUCTURA DE MATERIALES (Basado en Excel V3_6) ---
# Diccionario con las densidades y los sub-formatos específicos de cada material
ESTRUCTURA_MATERIALES = {
    "HMW": {
        "densidad": 0.96,
        "formatos": ["PLANCHA BCA/NEGRA", "PLANCHA COLOR", "PLANCHA Cu.", "BARRA BLANCA", "BARRA NEGRA"]
    },
    "PA-6": {
        "densidad": 1.14,
        "formatos": ["PLANCHA BCA.", "PLANCHA NEGRA", "BARRA BLANCA", "BARRA NEGRA"]
    },
    "POLIPROPILENO": {
        "densidad": 0.92,
        "formatos": ["PLANCHA", "BARRA"]
    },
    "POM": {
        "densidad": 1.42,
        "formatos": ["PLANCHA", "BARRA"]
    }
}

# --- 3. GESTIÓN DEL ESTADO (SESSION STATE) ---
if "cliente_actual" not in st.session_state:
    st.session_state.cliente_actual = None
if "cliente_en_bd" not in st.session_state:
    st.session_state.cliente_en_bd = False
if "carrito" not in st.session_state:
    st.session_state.carrito = []

# Funciones Auxiliares
def cliente_completo(cli):
    campos = ["rut", "atencion", "fono", "correo"]
    return all(cli.get(c) and str(cli.get(c)).strip() != "" for c in campos)

def cerrar_sesion_cliente():
    st.session_state.cliente_actual = None
    st.session_state.cliente_en_bd = False
    st.session_state.carrito = []
    st.rerun()

# --- 4. INTERFAZ DE USUARIO ---
st.title("⚙️ Sistema de Cotización y Gestión")

# =====================================================================
# PANTALLA A: BÚSQUEDA / SELECCIÓN DE CLIENTE
# =====================================================================
if st.session_state.cliente_actual is None:
    st.subheader("🔍 Buscar Cliente")
    busqueda = st.text_input("Ingresa RUT (ej: 12345678-9) o Nombre del Cliente")
    
    col1, col2 = st.columns([1, 4])
    if col1.button("Buscar en Base de Datos", type="primary"):
        if busqueda:
            # Busca por RUT o por el campo "atencion" (que reemplazó a razon_social en tu BD)
            res = supabase.table("clientes").select("*").or_(f"rut.eq.{busqueda},atencion.ilike.%{busqueda}%").execute()
            
            if res.data:
                if len(res.data) == 1:
                    st.session_state.cliente_actual = res.data[0]
                    st.session_state.cliente_en_bd = True
                    st.rerun()
                else:
                    st.warning("Se encontraron múltiples clientes. Sé más específico (usa el RUT).")
                    st.dataframe(res.data)
            else:
                st.info("Cliente no encontrado. Puedes ingresarlo a continuación.")
                es_rut = "-" in busqueda
                st.session_state.cliente_actual = {
                    "rut": busqueda if es_rut else "", 
                    "atencion": busqueda if not es_rut else ""
                }
                st.session_state.cliente_en_bd = False
                st.rerun()
        else:
            st.error("Ingresa un dato para buscar.")

# =====================================================================
# PANTALLA B: COMPLETAR DATOS DEL CLIENTE
# =====================================================================
elif not cliente_completo(st.session_state.cliente_actual):
    st.warning("⚠️ Los datos del cliente están incompletos o es un cliente nuevo. Por favor complétalos.")
    cli = st.session_state.cliente_actual
    
    with st.form("form_completar_cliente"):
        c1, c2 = st.columns(2)
        
        rut = c1.text_input("RUT (Sin puntos, con guión)", value=cli.get("rut", ""), disabled=st.session_state.cliente_en_bd)
        atencion = c2.text_input("Atención / Razón Social", value=cli.get("atencion", ""))
        fono = c1.text_input("Teléfono", value=cli.get("fono", ""))
        correo = c2.text_input("Correo Electrónico", value=cli.get("correo", ""))
        
        if st.form_submit_button("Guardar y Continuar"):
            if rut and atencion and fono and correo:
                datos_guardar = {
                    "rut": rut, "atencion": atencion, 
                    "fono": fono, "correo": correo
                }
                
                if st.session_state.cliente_en_bd:
                    res = supabase.table("clientes").update(datos_guardar).eq("rut", rut).execute()
                else:
                    res = supabase.table("clientes").insert(datos_guardar).execute()
                    st.session_state.cliente_en_bd = True
                
                st.session_state.cliente_actual = res.data[0]
                st.success("Cliente guardado correctamente.")
                st.rerun()
            else:
                st.error("Todos los campos son obligatorios.")
                
    if st.button("Cancelar / Volver"):
        cerrar_sesion_cliente()

# =====================================================================
# PANTALLA C: COTIZADOR Y CARRITO
# =====================================================================
else:
    cli = st.session_state.cliente_actual
    st.info(f"👤 **Cliente Activo:** {cli['atencion']} (RUT: {cli['rut']}) - {cli['correo']}")
    if st.button("Cambiar Cliente"):
        cerrar_sesion_cliente()
        
    st.markdown("---")
    
    st.subheader("🧮 Agregar Producto a la Cotización")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    
    # 1. Selección de Material
    material_sel = col_m1.selectbox("Material", list(ESTRUCTURA_MATERIALES.keys()))
    
    # 2. Selección de Formato dinámico (depende del material elegido, basado en el Excel)
    formatos_disponibles = ESTRUCTURA_MATERIALES[material_sel]["formatos"]
    formato_sel = col_m2.selectbox("Formato y Color", formatos_disponibles)
    
    tipo_venta = col_m3.radio("Tipo de Venta", ["Dimensionado (Trozo)", "Completo (Barra/Plancha entera)"])
    
    # Consultar si el cliente tiene un descuento usando su RUT para este material y formato específico
    res_desc = supabase.table("descuentos_cliente").select("*")\
        .eq("cliente_rut", cli["rut"]).eq("material", material_sel).eq("tipo_formato", formato_sel).execute()
    
    descuento_guardado = res_desc.data[0]["descuento_porcentaje"] if res_desc.data else 0.0
    desc_id_guardado = res_desc.data[0]["id"] if res_desc.data else None

    col_p1, col_p2, col_p3 = st.columns(3)
    precio_base_usd = col_p1.number_input("Precio Base USD / Kilo", value=12.0)
    dolar = col_p2.number_input("Dólar Observado ($ CLP)", value=961.61)
    descuento_aplicado = col_p3.number_input("Descuento a Aplicar (%)", value=float(descuento_guardado))
    
    densidad = ESTRUCTURA_MATERIALES[material_sel]["densidad"]
    precio_kilo_clp = precio_base_usd * dolar * (1 - descuento_aplicado / 100.0)
    
    factor_corte = 1.20 if tipo_venta == "Dimensionado (Trozo)" else 1.00
    
    subtotal_neto = 0
    descripcion_item = ""

    st.write("### 📐 Dimensiones")
    c1, c2, c3 = st.columns(3)
    
    # Determinar matemáticamente si el formato seleccionado es Barra o Plancha
    es_barra = "BARRA" in formato_sel.upper()
    
    if es_barra:
        diametro_mm = c1.number_input("Diámetro (mm)", min_value=5.0, value=60.0)
        largo_cm = c2.number_input("Largo Requerido (cm)", min_value=1.0, value=100.0 if tipo_venta == "Completo (Barra/Plancha entera)" else 20.0)
        
        kg_metro = ((diametro_mm * 1.035) ** 2) * (math.pi / 4.0) * densidad * 1000.0 / 1000000.0
        valor_cm_lineal = ((kg_metro * precio_kilo_clp) / 100.0) * factor_corte
        subtotal_neto = valor_cm_lineal * largo_cm
        descripcion_item = f"{material_sel} {formato_sel} Ø{diametro_mm}mm x {largo_cm}cm ({tipo_venta})"
        st.caption(f"Peso est. metro: {kg_metro:.2f} kg | Valor cm lineal: ${valor_cm_lineal:.1f}")

    else: # Es Plancha
        espesor_mm = c1.number_input("Espesor (mm)", min_value=1.0, value=20.0)
        ancho_cm = c2.number_input("Ancho Requerido (cm)", min_value=1.0, value=100.0 if tipo_venta == "Completo (Barra/Plancha entera)" else 30.0)
        largo_cm = c3.number_input("Largo Requerido (cm)", min_value=1.0, value=300.0 if tipo_venta == "Completo (Barra/Plancha entera)" else 50.0)
        
        kg_plancha_entera = (espesor_mm * 1.035) * 1000.0 * 3000.0 * densidad / 1000000.0
        precio_cm2 = ((kg_plancha_entera * precio_kilo_clp) / (100.0 * 300.0)) * factor_corte
        area_cm2 = ancho_cm * largo_cm
        subtotal_neto = precio_cm2 * area_cm2
        descripcion_item = f"{material_sel} {formato_sel} {espesor_mm}mm [{ancho_cm}cm x {largo_cm}cm] ({tipo_venta})"
        st.caption(f"Área cotizada: {area_cm2:,.0f} cm² | Valor cm²: ${precio_cm2:.2f}")

    if st.button("➕ Agregar al Carrito de Cotización", type="primary"):
        if descuento_aplicado != descuento_guardado:
            datos_desc = {
                "cliente_rut": cli["rut"], 
                "material": material_sel, 
                "tipo_formato": formato_sel, 
                "descuento_porcentaje": descuento_aplicado
            }
            if desc_id_guardado:
                supabase.table("descuentos_cliente").update(datos_desc).eq("id", desc_id_guardado).execute()
            else:
                supabase.table("descuentos_cliente").insert(datos_desc).execute()
            st.toast(f"✅ Descuento de {descuento_aplicado}% guardado para {material_sel} {formato_sel}")

        st.session_state.carrito.append({
            "Descripción": descripcion_item,
            "Cant.": 1,
            "Descuento": f"{descuento_aplicado}%",
            "Neto (CLP)": subtotal_neto,
            "IVA (CLP)": subtotal_neto * 0.19,
            "Total (CLP)": subtotal_neto * 1.19
        })
        st.rerun()

    # --- 5. CARRITO Y TOTALES ---
    st.markdown("---")
    st.subheader("🛒 Resumen de Cotización Actual")
    
    if len(st.session_state.carrito) > 0:
        df_carrito = pd.DataFrame(st.session_state.carrito)
        
        st.dataframe(
            df_carrito.style.format({"Neto (CLP)": "${:,.0f}", "IVA (CLP)": "${:,.0f}", "Total (CLP)": "${:,.0f}"}), 
            use_container_width=True
        )
        
        total_neto = sum(item["Neto (CLP)"] for item in st.session_state.carrito)
        total_iva = total_neto * 0.19
        total_final = total_neto + total_iva
        
        st.success(f"### Total Cotización: ${total_final:,.0f} CLP (Neto: ${total_neto:,.0f} + IVA)")
        
        if st.button("🗑️ Vaciar Carrito"):
            st.session_state.carrito = []
            st.rerun()
    else:
        st.write("El carrito está vacío.")
