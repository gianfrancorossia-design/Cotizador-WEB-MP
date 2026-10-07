import streamlit as st
import math

# Diccionario de densidades según tu Excel
DENSIDADES = {
    "POM": 1.42,
    "PA-6": 1.14,
    "POLIPROPILENO": 0.92,
    "HMW": 0.96,
    "OTRO": 1.14
}

st.subheader("📐 Cotización por Trozo / Corte a Medida")

tipo_formato = st.radio("Tipo de Formato", ["Barra (Redonda)", "Plancha (Corte Rectangular)"], horizontal=True)

col_m1, col_m2, col_m3 = st.columns(3)
material_sel = col_m1.selectbox("Material para Cálculo", list(DENSIDADES.keys()))
densidad = DENSIDADES[material_sel]
precio_base_usd_kilo = col_m2.number_input("Precio Base USD / Kilo", value=12.0)
valor_dolar = col_m3.number_input("Dólar ($ CLP)", value=961.61)
descuento_porcentaje = col_m1.number_input("Descuento Cliente (%)", value=0.0)

# Precio final por kilo en CLP neto
precio_kilo_clp = precio_base_usd_kilo * valor_dolar * (1 - descuento_porcentaje / 100.0)

if tipo_formato == "Barra (Redonda)":
    c1, c2 = st.columns(2)
    diametro_mm = c1.number_input("Diámetro de Barra (mm)", min_value=5.0, value=60.0)
    largo_corte_cm = c2.number_input("Largo del Trozo Requerido (cm)", min_value=1.0, value=20.0)

    # Fórmula exacta del Excel para Barra
    kg_metro = ((diametro_mm * 1.035) ** 2) * (math.pi / 4.0) * densidad * 1000.0 / 1000000.0
    valor_metro_neto = kg_metro * precio_kilo_clp
    valor_cm_lineal = (valor_metro_neto / 100.0) * 1.20  # Factor 1.2 por trozado
    
    subtotal_neto = valor_cm_lineal * largo_corte_cm
    
    st.info(f"📊 **Peso est. por metro:** {kg_metro:.3f} kg/m | **Precio por cm lineal:** ${valor_cm_lineal:,.1f} CLP")

else:  # Plancha
    c1, c2, c3 = st.columns(3)
    espesor_mm = c1.number_input("Espesor de Plancha (mm)", min_value=1.0, value=20.0)
    ancho_trozo_cm = c2.number_input("Ancho del Trozo (cm)", min_value=1.0, value=30.0)
    largo_trozo_cm = c3.number_input("Largo del Trozo (cm)", min_value=1.0, value=50.0)

    # Medidas de la plancha estándar de origen (1000mm x 3000mm)
    ancho_std_mm = 1000.0
    largo_std_mm = 3000.0
    
    kg_plancha_std = (espesor_mm * 1.035) * ancho_std_mm * largo_std_mm * densidad / 1000000.0
    superficie_std_cm2 = (ancho_std_mm / 10.0) * (largo_std_mm / 10.0)
    
    precio_plancha_neto = kg_plancha_std * precio_kilo_clp
    precio_cm2 = (precio_plancha_neto / superficie_std_cm2) * 1.20  # Factor 1.2 por trozado
    
    area_trozo_cm2 = ancho_trozo_cm * largo_trozo_cm
    subtotal_neto = precio_cm2 * area_trozo_cm2
    
    st.info(f"📊 **Área del trozo:** {area_trozo_cm2:,.0f} cm² | **Precio por cm²:** ${precio_cm2:,.2f} CLP")

iva = subtotal_neto * 0.19
total_con_iva = subtotal_neto + iva

st.markdown("---")
st.success(f"### 💰 Precio del Trozo: ${total_con_iva:,.0f} CLP IVA Incl. (Neto: ${subtotal_neto:,.0f} CLP)")
