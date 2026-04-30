import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
from PIL import Image
import traceback
import os
from supabase import create_client, Client

# Configuración de Supabase
def init_supabase():
    """Inicializa cliente de Supabase"""
    try:
        # Intentar obtener de secrets de Streamlit Cloud
        if hasattr(st, 'secrets') and 'supabase' in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
        else:
            # Para desarrollo local
            url = os.getenv("SUPABASE_URL", "tu_url_aqui")
            key = os.getenv("SUPABASE_KEY", "tu_key_aqui")
        
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error conectando a Supabase: {e}")
        return None

# Inicializar cliente
supabase = init_supabase()

# ========== FUNCIONES DE BASE DE DATOS ==========
def get_clients():
    """Obtener todos los clientes"""
    try:
        response = supabase.table('clientes').select('*').execute()
        return response.data
    except Exception as e:
        st.error(f"Error obteniendo clientes: {e}")
        return []

def get_products():
    """Obtener todos los productos"""
    try:
        response = supabase.table('productos').select('*, inventario(cantidad, costo)').execute()
        productos = []
        for p in response.data:
            producto = {
                'id': p['id'],
                'descripcion': p['descripcion'],
                'activo': p['activo'],
                'cantidad': p.get('inventario', [{}])[0].get('cantidad', 0) if p.get('inventario') else 0,
                'costo': p.get('inventario', [{}])[0].get('costo', 0) if p.get('inventario') else 0
            }
            productos.append(producto)
        return productos
    except Exception as e:
        st.error(f"Error obteniendo productos: {e}")
        return []

def add_client_validado(nombre, telefono, direccion):
    """Agregar cliente validado"""
    try:
        # Verificar si ya existe
        existing = supabase.table('clientes').select('*').eq('nombre', nombre).execute()
        if existing.data:
            return {'success': False, 'error': 'El cliente ya existe'}
        
        # Insertar nuevo cliente
        data = {
            'nombre': nombre,
            'telefono': telefono if telefono else None,
            'direccion': direccion if direccion else None
        }
        response = supabase.table('clientes').insert(data).execute()
        
        if response.data:
            return {'success': True, 'id': response.data[0]['id'], 'cliente': response.data[0]}
        return {'success': False, 'error': 'No se pudo crear el cliente'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def buscar_cliente_por_nombre(nombre):
    """Buscar cliente por nombre"""
    try:
        response = supabase.table('clientes').select('*').ilike('nombre', f'%{nombre}%').limit(10).execute()
        return response.data
    except Exception as e:
        st.error(f"Error buscando cliente: {e}")
        return []

def buscar_cliente_por_telefono(telefono):
    """Buscar cliente por teléfono"""
    try:
        response = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Error buscando cliente: {e}")
        return None

def buscar_producto_por_descripcion(descripcion):
    """Buscar producto por descripción"""
    try:
        response = supabase.table('productos').select('*, inventario(cantidad, costo)').ilike('descripcion', f'%{descripcion}%').limit(10).execute()
        
        productos = []
        for p in response.data:
            producto = {
                'id': p['id'],
                'descripcion': p['descripcion'],
                'cantidad': p.get('inventario', [{}])[0].get('cantidad', 0) if p.get('inventario') else 0,
                'costo': p.get('inventario', [{}])[0].get('costo', 0) if p.get('inventario') else 0
            }
            productos.append(producto)
        return productos
    except Exception as e:
        st.error(f"Error buscando producto: {e}")
        return []

def registrar_venta_supabase(id_cliente, productos, credito=False):
    """Registrar venta usando Supabase"""
    try:
        # Obtener tasa actual
        tasa_response = obtener_tasa_actual()
        tasa = tasa_response.get('bcv_usd', 55.0)
        
        # Calcular total
        total = 0
        detalles = []
        
        for prod in productos:
            precio_usd = prod.get('precio_usd', 0)
            cantidad = prod.get('cantidad', 0)
            subtotal_usd = precio_usd * cantidad
            subtotal_bs = subtotal_usd * tasa
            
            total += subtotal_bs
            
            detalles.append({
                'id_producto': prod['id_producto'],
                'cantidad': cantidad,
                'precio_unitario': precio_usd,
                'subtotal': subtotal_bs
            })
        
        # Insertar venta
        venta_data = {
            'id_cliente': id_cliente,
            'fecha_venta': datetime.now().isoformat(),
            'total': total,
            'tasa': tasa,
            'credito': credito,
            'pagado': False if credito else True,
            'cancelada': False,
            'saldo_pendiente': total if credito else 0
        }
        
        venta_response = supabase.table('ventas').insert(venta_data).execute()
        
        if not venta_response.data:
            return {'success': False, 'error': 'No se pudo crear la venta'}
        
        id_venta = venta_response.data[0]['id']
        
        # Insertar detalles
        for detalle in detalles:
            detalle['id_venta'] = id_venta
            supabase.table('detalles_venta').insert(detalle).execute()
            
            # Actualizar stock
            producto_actual = supabase.table('inventario').select('cantidad').eq('id_producto', detalle['id_producto']).execute()
            if producto_actual.data:
                nuevo_stock = producto_actual.data[0]['cantidad'] - detalle['cantidad']
                supabase.table('inventario').update({'cantidad': nuevo_stock}).eq('id_producto', detalle['id_producto']).execute()
        
        # Obtener nombre del cliente
        cliente_response = supabase.table('clientes').select('nombre').eq('id', id_cliente).execute()
        cliente_nombre = cliente_response.data[0]['nombre'] if cliente_response.data else 'Cliente'
        
        return {
            'success': True,
            'id_venta': id_venta,
            'total': total,
            'cliente_nombre': cliente_nombre,
            'tasa': tasa
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def obtener_tasa_actual():
    """Obtener tasa de cambio actual"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # Intentar obtener del BCV
        url = "http://www.bcv.org.ve/"
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar tasa USD (esto puede variar)
        dolar_element = soup.find('div', {'id': 'dolar'})
        if dolar_element:
            tasa = float(dolar_element.find('strong').text.replace(',', '.'))
            return {'bcv_usd': tasa, 'bcv_eur': tasa * 1.05}
    except:
        pass
    
    # Tasa por defecto
    return {'bcv_usd': 55.0, 'bcv_eur': 57.75}

def ventas_con_retraso():
    """Obtener créditos vencidos"""
    try:
        response = supabase.table('ventas').select('*, clientes(nombre, telefono)').eq('credito', True).eq('pagado', False).execute()
        
        creditos = []
        for v in response.data:
            saldo = v.get('saldo_pendiente', v.get('total', 0))
            if saldo > 0:
                creditos.append({
                    'id_venta': v['id'],
                    'cliente_nombre': v['clientes']['nombre'] if v.get('clientes') else 'N/A',
                    'cliente_telefono': v['clientes'].get('telefono') if v.get('clientes') else '',
                    'total_venta': v['total'],
                    'saldo_pendiente': saldo,
                    'fecha_venta': v['fecha_venta'][:10] if v.get('fecha_venta') else '',
                    'tasa': v.get('tasa', 0),
                    'porcentaje_pagado': ((v['total'] - saldo) / v['total'] * 100) if v['total'] > 0 else 0
                })
        return creditos
    except Exception as e:
        st.error(f"Error obteniendo créditos: {e}")
        return []

def pagar_credito_con_tasa(id_venta, monto, observacion, tasa_actual):
    """Registrar pago de crédito"""
    try:
        # Obtener venta actual
        venta = supabase.table('ventas').select('*').eq('id', id_venta).execute()
        if not venta.data:
            return {'success': False, 'error': 'Venta no encontrada'}
        
        venta_data = venta.data[0]
        saldo_actual = venta_data.get('saldo_pendiente', venta_data['total'])
        monto_pagado_anterior = venta_data['total'] - saldo_actual
        
        nuevo_saldo = saldo_actual - monto
        
        # Insertar pago
        pago_data = {
            'id_venta': id_venta,
            'monto_pagado': monto,
            'tasa_pago': tasa_actual,
            'observacion': observacion,
            'fecha_pago': datetime.now().isoformat()
        }
        supabase.table('pagos_credito').insert(pago_data).execute()
        
        # Actualizar venta
        update_data = {
            'saldo_pendiente': max(0, nuevo_saldo),
            'pagado': nuevo_saldo <= 0
        }
        supabase.table('ventas').update(update_data).eq('id', id_venta).execute()
        
        # Obtener datos del cliente
        cliente = supabase.table('clientes').select('nombre, telefono').eq('id', venta_data['id_cliente']).execute()
        
        return {
            'success': True,
            'mensaje': 'Pago registrado exitosamente',
            'saldo_pendiente': max(0, nuevo_saldo),
            'cliente_nombre': cliente.data[0]['nombre'] if cliente.data else 'Cliente',
            'cliente_telefono': cliente.data[0].get('telefono') if cliente.data else '',
            'total_venta': venta_data['total'],
            'tasa_venta': venta_data.get('tasa', 0),
            'tasa_aplicada': tasa_actual
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ========== INTERFAZ DE STREAMLIT ==========

st.set_page_config(
    page_title="Sistema de Ventas",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Sistema de Ventas Profesional")
st.markdown("---")

# Sidebar
st.sidebar.title("📋 Menú Principal")
opcion = st.sidebar.selectbox(
    "Seleccione una opción",
    ["🏠 Dashboard", "🛍️ Registrar Venta", "👥 Clientes", "📦 Productos", "💳 Créditos"]
)

# Tasa actual
tasa_actual = obtener_tasa_actual()
st.sidebar.info(f"💵 Tasa BCV: Bs {tasa_actual.get('bcv_usd', 55.0):.2f} / USD")

# Verificar conexión a Supabase
if supabase is None:
    st.error("❌ No se pudo conectar a Supabase. Verifica la configuración.")
    st.stop()

# ========== DASHBOARD ==========
if opcion == "🏠 Dashboard":
    st.header("📈 Dashboard")
    
    try:
        # Estadísticas
        col1, col2, col3 = st.columns(3)
        
        clientes = get_clients()
        productos = get_products()
        creditos = ventas_con_retraso()
        
        col1.metric("👥 Clientes", len(clientes))
        col2.metric("📦 Productos", len(productos))
        col3.metric("💳 Créditos Pendientes", len(creditos))
        
        if creditos:
            total_deuda = sum(c.get('saldo_pendiente', 0) for c in creditos)
            st.metric("💰 Total en Créditos", f"Bs {total_deuda:,.2f}")
        
        # Últimas ventas
        st.subheader("📊 Últimas Ventas")
        ventas = supabase.table('ventas').select('*, clientes(nombre)').order('fecha_venta', desc=True).limit(10).execute()
        if ventas.data:
            df = pd.DataFrame(ventas.data)
            df['fecha'] = pd.to_datetime(df['fecha_venta']).dt.strftime('%d/%m/%Y')
            df['cliente'] = df.apply(lambda x: x['clientes']['nombre'] if x.get('clientes') else 'N/A', axis=1)
            st.dataframe(df[['id', 'fecha', 'cliente', 'total', 'credito']], use_container_width=True)
    except Exception as e:
        st.error(f"Error cargando dashboard: {e}")

# ========== REGISTRAR VENTA ==========
elif opcion == "🛍️ Registrar Venta":
    st.header("🛍️ Nueva Venta")
    
    # Buscar cliente
    st.subheader("👤 Cliente")
    buscar_cliente = st.text_input("Buscar cliente por nombre")
    
    id_cliente = None
    if buscar_cliente:
        clientes = buscar_cliente_por_nombre(buscar_cliente)
        if clientes:
            cliente_seleccionado = st.selectbox(
                "Seleccionar cliente",
                clientes,
                format_func=lambda x: f"{x['nombre']} - {x.get('telefono', 'Sin teléfono')}"
            )
            if cliente_seleccionado:
                id_cliente = cliente_seleccionado['id']
                st.success(f"Cliente: {cliente_seleccionado['nombre']}")
        else:
            st.warning("Cliente no encontrado")
            nombre_nuevo = st.text_input("Nombre del nuevo cliente")
            telefono_nuevo = st.text_input("Teléfono")
            if st.button("Registrar Cliente") and nombre_nuevo:
                resultado = add_client_validado(nombre_nuevo, telefono_nuevo, "")
                if resultado['success']:
                    st.success("Cliente registrado")
                    id_cliente = resultado['id']
                else:
                    st.error(resultado.get('error'))
    
    # Carrito de compras
    st.subheader("📦 Productos")
    
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []
    
    # Buscar producto
    buscar_producto = st.text_input("Buscar producto")
    if buscar_producto:
        productos = buscar_producto_por_descripcion(buscar_producto)
        if productos:
            producto_seleccionado = st.selectbox(
                "Seleccionar producto",
                productos,
                format_func=lambda x: f"{x['descripcion']} - Stock: {x.get('cantidad', 0)}"
            )
            
            if producto_seleccionado:
                cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
                if st.button("➕ Agregar"):
                    st.session_state.carrito.append({
                        'id_producto': producto_seleccionado['id'],
                        'descripcion': producto_seleccionado['descripcion'],
                        'cantidad': cantidad,
                        'precio_usd': producto_seleccionado.get('costo', 0)
                    })
                    st.success("Producto agregado")
                    st.rerun()
    
    # Mostrar carrito
    if st.session_state.carrito:
        st.subheader("🛒 Carrito")
        df_carrito = pd.DataFrame(st.session_state.carrito)
        st.dataframe(df_carrito[['descripcion', 'cantidad', 'precio_usd']], use_container_width=True)
        
        total_usd = sum(item['cantidad'] * item['precio_usd'] for item in st.session_state.carrito)
        total_bs = total_usd * tasa_actual.get('bcv_usd', 55.0)
        
        st.metric("Total USD", f"${total_usd:,.2f}")
        st.metric("Total Bs", f"Bs {total_bs:,.2f}")
        
        if st.button("🗑️ Vaciar carrito"):
            st.session_state.carrito = []
            st.rerun()
    
    # Registrar venta
    if st.button("✅ Registrar Venta", type="primary"):
        if not id_cliente:
            st.error("Debe seleccionar un cliente")
        elif not st.session_state.carrito:
            st.error("Debe agregar productos")
        else:
            credito = st.checkbox("Venta a crédito")
            
            productos_venta = [
                {
                    'id_producto': item['id_producto'],
                    'cantidad': item['cantidad'],
                    'precio_usd': item['precio_usd']
                }
                for item in st.session_state.carrito
            ]
            
            resultado = registrar_venta_supabase(id_cliente, productos_venta, credito)
            
            if resultado['success']:
                st.success(f"✅ Venta registrada - Total: Bs {resultado['total']:,.2f}")
                st.session_state.carrito = []
                st.balloons()
            else:
                st.error(f"❌ Error: {resultado.get('error')}")

# ========== CLIENTES ==========
elif opcion == "👥 Clientes":
    st.header("👥 Clientes")
    
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Nuevo"])
    
    with tab1:
        clientes = get_clients()
        if clientes:
            df = pd.DataFrame(clientes)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay clientes registrados")
    
    with tab2:
        nombre = st.text_input("Nombre*")
        telefono = st.text_input("Teléfono")
        direccion = st.text_area("Dirección")
        
        if st.button("Registrar"):
            if nombre:
                resultado = add_client_validado(nombre, telefono, direccion)
                if resultado['success']:
                    st.success("Cliente registrado")
                    st.rerun()
                else:
                    st.error(resultado.get('error'))
            else:
                st.error("Nombre requerido")

# ========== PRODUCTOS ==========
elif opcion == "📦 Productos":
    st.header("📦 Productos")
    
    productos = get_products()
    if productos:
        df = pd.DataFrame(productos)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay productos registrados")

# ========== CRÉDITOS ==========
elif opcion == "💳 Créditos":
    st.header("💳 Créditos Pendientes")
    
    creditos = ventas_con_retraso()
    
    if creditos:
        for credito in creditos:
            with st.expander(f"Venta #{credito['id_venta']} - {credito['cliente_nombre']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total", f"Bs {credito['total_venta']:,.2f}")
                    st.metric("Saldo Pendiente", f"Bs {credito['saldo_pendiente']:,.2f}")
                
                with col2:
                    st.metric("Fecha", credito['fecha_venta'])
                    st.metric("Tasa", f"Bs {credito.get('tasa', 0):,.2f}")
                
                monto_pago = st.number_input("Monto a pagar", min_value=0.0, step=100.0, key=f"pago_{credito['id_venta']}")
                
                if st.button("Registrar Pago", key=f"btn_{credito['id_venta']}"):
                    if monto_pago > 0:
                        resultado = pagar_credito_con_tasa(
                            credito['id_venta'],
                            monto_pago,
                            "Pago desde Streamlit",
                            tasa_actual.get('bcv_usd', 55.0)
                        )
                        if resultado['success']:
                            st.success(f"✅ Pago registrado. Nuevo saldo: Bs {resultado['saldo_pendiente']:,.2f}")
                            st.rerun()
                        else:
                            st.error(f"Error: {resultado.get('error')}")
                    else:
                        st.warning("Ingrese un monto válido")
    else:
        st.info("No hay créditos pendientes")

st.sidebar.markdown("---")
st.sidebar.caption(f"Sistema de Ventas\n{datetime.now().strftime('%d/%m/%Y %H:%M')}")
