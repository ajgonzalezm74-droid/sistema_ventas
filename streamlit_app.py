import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import traceback

# IMPORTAR TODAS LAS FUNCIONES ORIGINALES
from database import (
    get_connection, init_db, get_clients, get_productos, 
    add_client_validado, add_product, reponer_stock,
    buscar_cliente_por_nombre, buscar_cliente_por_telefono,
    buscar_productos_por_descripcion
)

from ventas_logic import (
    registrar_venta,
    pagar_credito,
    pagar_credito_parcial,
    cancelar_venta,
    ventas_con_retraso,
    reporte_ventas,
    reporte_produto,
    obtener_tasa_actual,
    obtener_historial_pagos,
    generar_nota_debito,
    obtener_estado_credito,
    reporte_por_rango,
    obtener_creditos_agrupados,
    pagar_credito_con_tasa
)

from generar_recibo_profesional import generar_recibo_profesional

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Ventas",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar base de datos
try:
    init_db()
    st.success("✅ Conectado a la base de datos PostgreSQL")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# Título principal
st.title("💰 Sistema de Ventas Profesional")
st.markdown("---")

# Sidebar para navegación
st.sidebar.title("📋 Menú Principal")
opcion = st.sidebar.selectbox(
    "Seleccione una opción",
    ["🏠 Dashboard", "🛍️ Registrar Venta", "👥 Clientes", "📦 Productos", 
     "💳 Créditos", "📊 Reportes"]
)

# Mostrar tasa actual en sidebar
try:
    tasa_actual = obtener_tasa_actual()
    st.sidebar.info(f"💵 Tasa BCV: Bs {tasa_actual.get('bcv_usd', 55.0):.2f} / USD")
except:
    st.sidebar.warning("No se pudo obtener la tasa actual")
    tasa_actual = {'bcv_usd': 55.0}

# ========== DASHBOARD ==========
if opcion == "🏠 Dashboard":
    st.header("📈 Dashboard de Ventas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total ventas hoy
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM ventas WHERE DATE(fecha_venta) = CURRENT_DATE")
        ventas_hoy = cursor.fetchone()[0] or 0
        
        # Total clientes
        clientes = get_clients()
        total_clientes = len(clientes)
        
        # Total productos
        productos = get_productos()
        total_productos = len(productos)
        
        # Créditos pendientes
        cursor.execute("SELECT COALESCE(SUM(saldo_pendiente), 0) FROM ventas WHERE credito = true AND pagado = false AND cancelada = false")
        creditos_pendientes = cursor.fetchone()[0] or 0
        
        conn.close()
        
        col1.metric("💰 Ventas Hoy", f"Bs {ventas_hoy:,.2f}")
        col2.metric("👥 Clientes", total_clientes)
        col3.metric("📦 Productos", total_productos)
        col4.metric("💳 Créditos Pendientes", f"Bs {creditos_pendientes:,.2f}")
        
        # Últimas ventas
        st.subheader("📊 Últimas Ventas")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id, v.fecha_venta, c.nombre as cliente, v.total, 
                   CASE WHEN v.credito = true THEN 'Crédito' ELSE 'Contado' END as tipo
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            ORDER BY v.fecha_venta DESC
            LIMIT 10
        """)
        ultimas_ventas = cursor.fetchall()
        conn.close()
        
        if ultimas_ventas:
            df = pd.DataFrame(ultimas_ventas, columns=['ID', 'Fecha', 'Cliente', 'Total', 'Tipo'])
            df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay ventas registradas")
            
    except Exception as e:
        st.error(f"Error cargando dashboard: {e}")

# ========== REGISTRAR VENTA ==========
elif opcion == "🛍️ Registrar Venta":
    st.header("🛍️ Nueva Venta")
    
    # Inicializar carrito en sesión
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("👤 Cliente")
        
        buscar_cliente = st.text_input("Buscar cliente por nombre o teléfono")
        
        id_cliente = None
        cliente_seleccionado = None
        
        if buscar_cliente:
            # Buscar por teléfono primero
            cliente = buscar_cliente_por_telefono(buscar_cliente)
            if not cliente:
                clientes = buscar_cliente_por_nombre(buscar_cliente)
                if clientes:
                    cliente_seleccionado = st.selectbox(
                        "Seleccionar cliente",
                        clientes,
                        format_func=lambda x: f"{x['nombre']} - {x.get('telefono', 'Sin teléfono')}"
                    )
                    if cliente_seleccionado:
                        id_cliente = cliente_seleccionado['id']
            else:
                id_cliente = cliente['id']
                cliente_seleccionado = cliente
                st.success(f"Cliente encontrado: {cliente['nombre']}")
        
        if not id_cliente and buscar_cliente:
            st.warning("Cliente no encontrado")
            nombre_nuevo = st.text_input("Nombre del nuevo cliente*")
            telefono_nuevo = st.text_input("Teléfono")
            
            if st.button("Registrar Cliente"):
                if nombre_nuevo:
                    resultado = add_client_validado(nombre_nuevo, telefono_nuevo, "")
                    if resultado['success']:
                        id_cliente = resultado['id']
                        st.success(f"Cliente {nombre_nuevo} registrado")
                        st.rerun()
                    else:
                        st.error(resultado.get('error'))
                else:
                    st.error("El nombre es requerido")
    
    with col2:
        st.subheader("📦 Productos")
        
        buscar_producto = st.text_input("Buscar producto por descripción")
        
        if buscar_producto:
            productos = buscar_productos_por_descripcion(buscar_producto)
            if productos:
                producto_seleccionado = st.selectbox(
                    "Seleccionar producto",
                    productos,
                    format_func=lambda x: f"{x['descripcion']} - Stock: {x.get('cantidad', 0)}"
                )
                
                if producto_seleccionado:
                    cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
                    precio_usd = st.number_input("Precio USD", min_value=0.0, step=0.01, 
                                                 value=float(producto_seleccionado.get('costo', 0)))
                    
                    if st.button("➕ Agregar al carrito"):
                        st.session_state.carrito.append({
                            'id_producto': producto_seleccionado['id'],
                            'descripcion': producto_seleccionado['descripcion'],
                            'cantidad': cantidad,
                            'precio_usd': precio_usd
                        })
                        st.success(f"✅ Agregado: {producto_seleccionado['descripcion']} x{cantidad}")
                        st.rerun()
        
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
    credito = st.checkbox("Venta a crédito")
    
    if st.button("✅ Registrar Venta", type="primary", use_container_width=True):
        if not id_cliente:
            st.error("Debe seleccionar o crear un cliente")
        elif not st.session_state.carrito:
            st.error("Debe agregar productos al carrito")
        else:
            productos_venta = [
                {
                    'id_producto': item['id_producto'],
                    'cantidad': item['cantidad'],
                    'precio_usd': item['precio_usd']
                }
                for item in st.session_state.carrito
            ]
            
            with st.spinner("Registrando venta..."):
                resultado = registrar_venta(id_cliente, productos_venta, credito)
            
            if resultado.get('success'):
                st.success(f"✅ Venta registrada exitosamente!")
                st.balloons()
                st.info(f"**Total:** Bs {resultado.get('total_bs', 0):,.2f}")
                st.info(f"**Tipo:** {'Crédito' if credito else 'Contado'}")
                
                # Generar recibo
                try:
                    datos_recibo = {
                        'cliente': cliente_seleccionado['nombre'] if cliente_seleccionado else 'Cliente',
                        'telefono': cliente_seleccionado.get('telefono', '') if cliente_seleccionado else '',
                        'fecha': datetime.now().strftime('%d/%m/%Y'),
                        'productos': productos_venta,
                        'total': resultado.get('total_bs', 0),
                        'tasa': tasa_actual.get('bcv_usd', 55.0),
                        'tasa_actual': tasa_actual.get('bcv_usd', 55.0),
                        'tipo': 'CRÉDITO' if credito else 'CONTADO',
                        'saldo_pendiente': resultado.get('total_bs', 0) if credito else 0
                    }
                    img_bytes = generar_recibo_profesional(datos_recibo)
                    st.image(img_bytes, caption="Recibo de venta")
                except Exception as e:
                    st.warning(f"No se pudo generar el recibo: {e}")
                
                st.session_state.carrito = []
            else:
                st.error(f"❌ Error: {resultado.get('error')}")

# ========== CLIENTES ==========
elif opcion == "👥 Clientes":
    st.header("👥 Gestión de Clientes")
    
    tab1, tab2 = st.tabs(["📋 Lista de Clientes", "➕ Nuevo Cliente"])
    
    with tab1:
        try:
            clientes = get_clients()
            if clientes:
                df = pd.DataFrame(clientes)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No hay clientes registrados")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with tab2:
        nombre = st.text_input("Nombre completo*")
        telefono = st.text_input("Teléfono")
        direccion = st.text_area("Dirección")
        
        if st.button("Registrar Cliente", type="primary"):
            if nombre:
                resultado = add_client_validado(nombre, telefono, direccion)
                if resultado['success']:
                    st.success("✅ Cliente registrado exitosamente")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {resultado.get('error')}")
            else:
                st.error("El nombre es requerido")

# ========== PRODUCTOS ==========
elif opcion == "📦 Productos":
    st.header("📦 Gestión de Productos")
    
    tab1, tab2 = st.tabs(["📋 Lista de Productos", "➕ Nuevo Producto"])
    
    with tab1:
        try:
            productos = get_productos()
            if productos:
                df = pd.DataFrame(productos)
                st.dataframe(df, use_container_width=True)
                
                st.subheader("📦 Reponer Stock")
                producto_id = st.number_input("ID del producto", min_value=1, step=1)
                cantidad = st.number_input("Cantidad a agregar", min_value=1, step=1)
                costo = st.number_input("Costo unitario (opcional)", min_value=0.0, step=0.01)
                
                if st.button("Reponer Stock"):
                    resultado = reponer_stock(producto_id, cantidad, costo if costo > 0 else None)
                    if resultado.get('success'):
                        st.success("✅ Stock repuesto exitosamente")
                        st.rerun()
                    else:
                        st.error(f"Error: {resultado.get('error')}")
            else:
                st.info("No hay productos registrados")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with tab2:
        descripcion = st.text_input("Descripción del producto*")
        costo = st.number_input("Costo unitario (Bs)", min_value=0.0, step=0.01)
        stock = st.number_input("Stock inicial", min_value=0, step=1)
        
        if st.button("Registrar Producto", type="primary"):
            if descripcion:
                resultado = add_product(descripcion, costo, stock)
                if resultado.get('success'):
                    st.success("✅ Producto registrado exitosamente")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {resultado.get('error')}")
            else:
                st.error("La descripción es requerida")

# ========== CRÉDITOS ==========
elif opcion == "💳 Créditos":
    st.header("💳 Gestión de Créditos")
    
    try:
        creditos = ventas_con_retraso()
        
        if creditos:
            st.subheader(f"📋 Créditos Pendientes ({len(creditos)})")
            
            for credito in creditos:
                with st.expander(f"📄 Venta #{credito.get('id')} - {credito.get('nombre', 'N/A')}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Total Original", f"Bs {credito.get('total_original', 0):,.2f}")
                        st.metric("Saldo Pendiente", f"Bs {credito.get('saldo_pendiente', 0):,.2f}")
                        st.metric("Fecha Venta", credito.get('fecha_venta', 'N/A')[:10] if credito.get('fecha_venta') else 'N/A')
                    
                    with col2:
                        st.metric("Tasa Venta", f"Bs {credito.get('tasa_venta', 0):,.2f}")
                        st.metric("Tasa Actual", f"Bs {credito.get('tasa_actual', 0):,.2f}")
                        dias = credito.get('dias_retraso', 0)
                        if dias > 0:
                            st.metric("Días de Retraso", f"🔴 {dias} días")
                        else:
                            st.metric("Estado", "🟢 Al día")
                    
                    st.markdown(f"**Productos:** {credito.get('productos', 'N/A')}")
                    
                    st.subheader("💰 Registrar Pago")
                    
                    monto_pago = st.number_input(
                        "Monto a pagar",
                        min_value=0.0,
                        max_value=float(credito.get('saldo_pendiente', 0)) if credito.get('saldo_pendiente', 0) > 0 else 0.0,
                        step=100.0,
                        key=f"monto_{credito.get('id')}"
                    )
                    observacion = st.text_input("Observación", key=f"obs_{credito.get('id')}")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button(f"Pagar Parcial", key=f"parcial_{credito.get('id')}"):
                            if monto_pago > 0:
                                resultado = pagar_credito_parcial(credito.get('id'), monto_pago, observacion)
                                if resultado.get('success'):
                                    st.success(f"✅ {resultado.get('mensaje', 'Pago registrado')}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Error: {resultado.get('error')}")
                            else:
                                st.warning("Ingrese un monto válido")
                    
                    with col_btn2:
                        if st.button(f"Pagar Completo", key=f"completo_{credito.get('id')}"):
                            resultado = pagar_credito(credito.get('id'))
                            if resultado.get('success'):
                                st.success(f"✅ Crédito pagado completamente")
                                st.rerun()
                            else:
                                st.error(f"❌ Error: {resultado.get('error')}")
        else:
            st.info("🎉 No hay créditos pendientes")
    
    except Exception as e:
        st.error(f"Error cargando créditos: {e}")
        st.code(traceback.format_exc())

# ========== REPORTES ==========
elif opcion == "📊 Reportes":
    st.header("📊 Reportes")
    
    tipo_reporte = st.selectbox(
        "Tipo de Reporte",
        ["📈 Ventas por período", "🏆 Productos más vendidos", "💳 Estado de créditos", "📋 Reporte general de ventas"]
    )
    
    if tipo_reporte == "📈 Ventas por período":
        st.subheader("Reporte por Rango de Fechas")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
        with col2:
            fecha_fin = st.date_input("Fecha fin", datetime.now())
        
        tipo = st.selectbox("Agrupar por", ["dia", "semana", "mes"])
        filtro_venta = st.selectbox("Tipo de venta", ["todas", "contado", "credito_pendiente", "credito_pagado"])
        
        if st.button("Generar Reporte", type="primary"):
            with st.spinner("Generando reporte..."):
                resultado = reporte_por_rango(
                    fecha_inicio.strftime('%Y-%m-%d'),
                    fecha_fin.strftime('%Y-%m-%d'),
                    tipo,
                    filtro_venta
                )
            
            if resultado.get('success') and resultado.get('data'):
                df = pd.DataFrame(resultado['data'])
                st.dataframe(df, use_container_width=True)
                
                st.subheader("Totales")
                totales = resultado.get('totales', {})
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Contado", f"Bs {totales.get('contado', 0):,.2f}")
                col2.metric("Crédito Pendiente", f"Bs {totales.get('credito_pendiente', 0):,.2f}")
                col3.metric("Crédito Cancelado", f"Bs {totales.get('credito_cancelado', 0):,.2f}")
                col4.metric("Total General", f"Bs {totales.get('general', 0):,.2f}")
            else:
                st.warning("No hay datos en el período seleccionado")
    
    elif tipo_reporte == "🏆 Productos más vendidos":
        st.subheader("Top Productos Más Vendidos")
        
        with st.spinner("Cargando reporte..."):
            reporte = reporte_produto()
        
        if reporte:
            df = pd.DataFrame(reporte)
            st.dataframe(df, use_container_width=True)
            
            total_unidades = df['unidades_vendidas'].sum()
            total_bs = df['total_bs'].sum()
            st.metric("Total Unidades Vendidas", f"{total_unidades:,}")
            st.metric("Total Ventas (Bs)", f"Bs {total_bs:,.2f}")
        else:
            st.info("No hay datos de productos vendidos")
    
    elif tipo_reporte == "💳 Estado de créditos":
        st.subheader("Estado de Créditos")
        
        with st.spinner("Cargando créditos..."):
            creditos = ventas_con_retraso()
        
        if creditos:
            df = pd.DataFrame(creditos)
            st.dataframe(df, use_container_width=True)
            
            total_deuda = sum(c.get('saldo_pendiente', 0) for c in creditos)
            st.metric("Total Deuda Pendiente", f"Bs {total_deuda:,.2f}")
        else:
            st.info("No hay créditos registrados")
    
    elif tipo_reporte == "📋 Reporte general de ventas":
        st.subheader("Reporte General de Ventas")
        
        periodo = st.selectbox("Período", ["semanal", "mensual"])
        
        with st.spinner("Generando reporte..."):
            reporte = reporte_ventas(periodo)
        
        if reporte:
            df = pd.DataFrame(reporte)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay datos de ventas")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"© 2024 Sistema de Ventas\n{datetime.now().strftime('%d/%m/%Y %H:%M')}")
