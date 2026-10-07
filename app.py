import os
import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Cotizador de Plásticos", layout="wide")

@st.cache_resource
def init_supabase():
    # Intenta obtener credenciales desde las variables de Render u el archivo local secrets.toml
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        try:
            url = url or st.secrets["SUPABASE_URL"]
            key = key or st.secrets["SUPABASE_KEY"]
        except Exception:
            pass
            
    return create_client(url, key)

supabase = init_supabase()

st.title("⚙️ Sistema de Cotización y Gestión de Precios")

tabs = st.tabs(["🧮 Cotizar", "👥 Gestionar Clientes y Descuentos", "💵 Precios Base USD"])

# --- TAB 1: COTIZADOR AUTOMÁTICO ---
with tabs[0]:
    st.header("Calcular Cotización")
    
    col_c1, col_c2 = st.columns(2)
    
    res_cli = supabase.table("clientes").select("id, razon_social, rut").execute()
    if res_cli.data:
        dict_cli = {f"{c['razon_social']} ({c['rut']})": c['id'] for c in res_cli.data}
        cli_sel_name = col_c1.selectbox("Cliente", list(dict_cli.keys()))
        cli_id = dict_cli[cli_sel_name]
    else:
        st.warning("No hay clientes registrados en la base de datos.")
        cli_id = None
    
    res_fmt = supabase.table("formatos_material").select("*").execute()
    df_fmt = pd.DataFrame(res_fmt.data) if res_fmt.data else pd.DataFrame()
    
    if not df_fmt.empty:
        mat_sel = col_c2.selectbox("Material", df_fmt['material'].unique())
        fmts_disponibles = df_fmt[df_fmt['material'] == mat_sel]
        fmt_sel = col_c2.selectbox("Formato / Variante", fmts_disponibles['formato'].unique())
        
        fmt_obj = fmts_disponibles[fmts_disponibles['formato'] == fmt_sel].iloc[0]
        fmt_id = int(fmt_obj['id'])
        precio_base_usd = float(fmt_obj['precio_base_usd'])
        
        # Buscar Descuento Pactado
        descuento_aplicado = 0.0
        if cli_id:
            res_desc = supabase.table("descuentos_cliente") \
                .select("descuento_porcentaje") \
                .eq("cliente_id", cli_id) \
                .eq("formato_material_id", fmt_id) \
                .execute()
            if res_desc.data:
                descuento_aplicado = float(res_desc.data[0]['descuento_porcentaje'])
        
        st.info(f"💡 **Descuento asignado a este cliente para {mat_sel} - {fmt_sel}:** {descuento_aplicado}%")
        
        col_k1, col_k2, col_k3 = st.columns(3)
        kilos = col_k1.number_input("Kilos Requeridos", min_value=0.1, value=10.0)
        dolar = col_k2.number_input("Valor Dólar Observado ($)", value=961.61)
        desc_override = col_k3.number_input("Descuento Aplicado (%)", value=descuento_aplicado)

        precio_kilo_clp = precio_base_usd * dolar
        subtotal_neto = kilos * precio_kilo_clp * (1 - desc_override / 100.0)
        iva = subtotal_neto * 0.19
        total = subtotal_neto + iva

        st.markdown("---")
        st.success(f"### Total Cotización: ${total:,.0f} CLP (Neto: ${subtotal_neto:,.0f} + IVA)")

# --- TAB 2: GESTIONAR CLIENTES Y DESCUENTOS ---
with tabs[1]:
    st.header("Directorio de Clientes")
    if res_cli.data:
        df_c = pd.DataFrame(supabase.table("clientes").select("*").execute().data)
        st.dataframe(df_c, use_container_width=True)

# --- TAB 3: PRECIOS BASE ---
with tabs[2]:
    st.header("Precios Base USD por Formato")
    if not df_fmt.empty:
        df_edited = st.data_editor(df_fmt[['id', 'material', 'formato', 'precio_base_usd']], use_container_width=True)
        if st.button("Guardar Cambios en Precios Base"):
            for idx, row in df_edited.iterrows():
                supabase.table("formatos_material").update({'precio_base_usd': row['precio_base_usd']}).eq("id", row['id']).execute()
            st.success("Precios actualizados correctamente.")
