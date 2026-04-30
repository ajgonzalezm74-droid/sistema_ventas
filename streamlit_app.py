import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
from PIL import Image
import traceback

# IMPORTAR TU DATABASE.PY EXISTENTE
from database import (
    get_connection, init_db, get_clients, get_productos, 
    add_client_validado, add_product, reponer_stock,
    buscar_cliente_por_nombre, buscar_cliente_por_telefono,
    buscar_productos_por_descripcion
)

# IMPORTAR TU VENTAS_LOGIC.PY EXISTENTE
from ventas_logic import (
    registrar_venta,
    ventas_con_retraso,
    obtener_tasa_actual,
    pagar_credito_con_tasa,
    pagar_credito_parcial,
    reporte_ventas,
    reporte_produto,
    reporte_por_rango,
    obtener_creditos_agrupados,
    cancelar_creditos_global
)

# IMPORTAR GENERADORES DE RECIBOS
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
        cursor.execute("SELECT COALESCE(SUM(saldo_pendiente), 0) FROM ventas WHERE credito = true AND pagado = false")
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
        
        # Buscar cliente existente
        buscar_cliente = st.text_input("Buscar cliente por nombre o teléfono")
        
        id_cliente = None
        cliente_seleccionado = None
        
        if buscar_cliente:
            # Buscar por teléfono primero
            cliente = buscar_cliente_por_telefono(buscar_cliente)
            if not cliente:
                # Buscar por nombre
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
        
        # Si no se encuentra, crear nuevo
        if not id_cliente and buscar_cliente:
            st.warning("Cliente no encontrado. Complete el formulario:")
            nombre_nuevo = st.text_input("Nombre del nuevo cliente*")
            telefono_nuevo = st.text_input("Teléfono")
            
            if st.button("Registrar Cliente y Continuar"):
                if nombre_nuevo:
                    resultado = add_client_validado(nombre_nuevo, telefono_nuevo, "")
                    if resultado['success']:
                        id_cliente = resultado['id']
                        st.success(f"Cliente {nombre_nuevo} registrado exitosamente")
                        st.rerun()
                    else:
                        st.error(resultado.get('error'))
                else:
                    st.error("El nombre es requerido")
    
    with col2:
        st.subheader("📦 Productos")
        
        # Buscar producto
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
        
        # Mostrar carrito
        if st.session_state.carrito:
            st.subheader("🛒 Carrito")
            
            df_carrito = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_carrito[['descripcion', 'cantidad', 'precio_usd']], use_container_width=True)
            
            total_usd = sum(item['cantidad'] * item['precio_usd'] for item in st.session_state.carrito)
            total_bs = total_usd * tasa_actual.get('bcv_usd', 55.0)
            
            st.metric("Total USD", f"${total_usd:,.2f}")
            st.metric("Total Bs", f"Bs {total_bs:,.2f}")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🗑️ Vaciar carrito"):
                    st.session_state.carrito = []
                    st.rerun()
    
    # Registrar venta
    if st.button("✅ Registrar Venta", type="primary", use_container_width=True):
        if not id_cliente:
            st.error("Debe seleccionar o crear un cliente")
        elif not st.session_state.carrito:
            st.error("Debe agregar productos al carrito")
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
            
            with st.spinner("Registrando venta..."):
                resultado = registrar_venta(id_cliente, productos_venta, credito)
            
            if resultado.get('success'):
                st.success(f"✅ Venta registrada exitosamente!")
                st.balloons()
                st.info(f"**Total:** Bs {resultado.get('total', 0):,.2f}")
                
                # Limpiar carrito
                st.session_state.carrito = []
                
                # Opción para ver recibo
                if st.button("📄 Ver Recibo"):
                    try:
                        datos_recibo = {
                            'cliente': resultado.get('cliente_nombre', 'Cliente'),
                            'telefono': '',
                            'fecha': datetime.now().strftime('%d/%m/%Y'),
                            'productos': productos_venta,
                            'total': resultado.get('total', 0),
                            'tasa': tasa_actual.get('bcv_usd', 55.0),
                            'tasa_actual': tasa_actual.get('bcv_usd', 55.0),
                            'tipo': 'CRÉDITO' if credito else 'CONTADO',
                            'saldo_pendiente': resultado.get('total', 0) if credito else 0
                        }
                        img_bytes = generar_recibo_profesional(datos_recibo)
                        st.image(img_bytes, caption="Recibo de venta")
                    except Exception as e:
                        st.warning(f"No se pudo generar el recibo: {e}")
            else:
                st.error(f"❌ Error: {resultado.get('error')}")

# ========== CLIENTES ==========
elif opcion == "👥 Clientes":
    st.header("👥 Gestión de Clientes")
    
    tab1, tab2, tab3 = st.tabs(["📋 Lista de Clientes", "➕ Nuevo Cliente", "🔍 Buscar Cliente"])
    
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
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre completo*")
            telefono = st.text_input("Teléfono")
        with col2:
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
    
    with tab3:
        busqueda = st.text_input("Buscar por nombre o teléfono")
        if busqueda:
            cliente = buscar_cliente_por_telefono(busqueda)
            if cliente:
                st.dataframe(pd.DataFrame([cliente]), use_container_width=True)
            else:
                clientes = buscar_cliente_por_nombre(busqueda)
                if clientes:
                    st.dataframe(pd.DataFrame(clientes), use_container_width=True)
                else:
                    st.warning("No se encontraron clientes")

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
                
                # Reponer stock
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
    
    # Crear pestañas para créditos individuales y cancelación global
    tab_creditos, tab_global = st.tabs(["📋 Créditos Individuales", "🌍 Cancelación Global por Cliente"])
    
    with tab_creditos:
        try:
            creditos = ventas_con_retraso()
            
            if creditos:
                st.subheader(f"📋 Créditos Pendientes ({len(creditos)})")
                
                for credito in creditos:
                    with st.expander(f"📄 Venta #{credito.get('id_venta')} - {credito.get('cliente_nombre', 'N/A')}"):
                        col1, col2, col3 = st.columns(3)
                        
                        total_venta = float(credito.get('total_venta', 0))
                        saldo_pendiente = float(credito.get('saldo_pendiente', 0))
                        total_pagado = float(credito.get('total_pagado', 0))
                        total_actualizado = float(credito.get('total_actualizado', total_venta))
                        
                        if saldo_pendiente < 0:
                            saldo_pendiente = 0
                        
                        if total_actualizado > 0:
                            porcentaje_pagado = (total_pagado / total_actualizado) * 100
                            porcentaje_pagado = max(0, min(100, porcentaje_pagado))
                        else:
                            porcentaje_pagado = 0
                        
                        progress_value = porcentaje_pagado / 100
                        progress_value = max(0, min(1, progress_value))
                        
                        with col1:
                            st.metric("Total Original", f"Bs {total_venta:,.2f}")
                            st.metric("Saldo Pendiente", f"Bs {saldo_pendiente:,.2f}")
                        
                        with col2:
                            fecha_venta = credito.get('fecha_venta', 'N/A')
                            if fecha_venta and len(fecha_venta) > 10:
                                fecha_venta = fecha_venta[:10]
                            st.metric("Fecha Venta", fecha_venta)
                            st.metric("Tasa", f"Bs {credito.get('tasa_venta', 0):,.2f}")
                        
                        with col3:
                            st.metric("Pagado", f"Bs {total_pagado:,.2f}")
                            if 0 <= progress_value <= 1:
                                st.progress(progress_value)
                                st.caption(f"{porcentaje_pagado:.1f}% pagado")
                        
                        if saldo_pendiente <= 0:
                            st.success("✅ Este crédito ya está completamente pagado")
                        else:
                            st.subheader("💰 Registrar Pago")
                            monto_pago = st.number_input(
                                f"Monto a pagar (Máximo: Bs {saldo_pendiente:,.2f})",
                                min_value=0.0,
                                max_value=float(saldo_pendiente),
                                step=100.0,
                                key=f"monto_{credito.get('id_venta')}"
                            )
                            observacion = st.text_input("Observación", key=f"obs_{credito.get('id_venta')}")
                            
                            if st.button(f"Registrar Pago", key=f"btn_{credito.get('id_venta')}"):
                                if monto_pago > 0:
                                    with st.spinner("Procesando pago..."):
                                        resultado = pagar_credito_con_tasa(
                                            credito.get('id_venta'),
                                            monto_pago,
                                            observacion or "Pago registrado",
                                            tasa_actual.get('bcv_usd', 55.0)
                                        )
                                    if resultado.get('success'):
                                        st.success(f"✅ {resultado.get('mensaje', 'Pago registrado')}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Error: {resultado.get('error')}")
                                else:
                                    st.warning("Ingrese un monto válido")
            else:
                st.info("🎉 No hay créditos pendientes")
        except Exception as e:
            st.error(f"Error cargando créditos: {e}")
            st.code(traceback.format_exc())
    
    with tab_global:
        st.subheader("🌍 Cancelar TODAS las deudas de un cliente")
        st.warning("⚠️ Esta acción cancelará TODOS los créditos pendientes del cliente seleccionado de una sola vez.")
        
        # Seleccionar cliente para cancelación global
        clientes = get_clients()
        if clientes:
            cliente_seleccionado = st.selectbox(
                "Seleccionar cliente",
                clientes,
                format_func=lambda x: f"{x['nombre']} - {x.get('telefono', 'Sin teléfono')} (Deuda: Bs {calcular_deuda_cliente(x['id']):,.2f})"
            )
            
            if cliente_seleccionado:
                cliente_id = cliente_seleccionado['id']
                deuda_total = calcular_deuda_cliente(cliente_id)
                
                if deuda_total > 0:
                    st.error(f"💰 Deuda total del cliente: **Bs {deuda_total:,.2f}**")
                    st.warning(f"Se cancelarán todas las deudas de **{cliente_seleccionado['nombre']}**")
                    
                    # Botón de confirmación
                    confirmar = st.checkbox("✅ Confirmo que deseo cancelar TODAS las deudas de este cliente")
                    
                    if st.button("🌍 Cancelar TODOS los Créditos", type="primary", disabled=not confirmar):
                        with st.spinner("Procesando cancelación global..."):
                            resultado = cancelar_creditos_global(cliente_id, tasa_actual.get('bcv_usd', 55.0))
                        
                        if resultado.get('success'):
                            st.success(f"✅ Cancelación global completada exitosamente!")
                            st.balloons()
                            st.info(f"**Total cancelado:** Bs {resultado.get('total_cancelado', 0):,.2f}")
                            st.info(f"**Deudas canceladas:** {len(resultado.get('deudas_canceladas', []))}")
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {resultado.get('error')}")
                else:
                    st.success(f"✅ El cliente {cliente_seleccionado['nombre']} no tiene deudas pendientes")
        else:
            st.info("No hay clientes registrados")

# ========== REPORTES ==========
elif opcion == "📊 Reportes":
    st.header("📊 Reportes y Estadísticas")
    
    tipo_reporte = st.selectbox(
        "Tipo de Reporte",
        ["📈 Ventas por período", "🏆 Productos más vendidos", "💳 Estado de créditos", "📋 Reporte general de ventas"]
    )
    
    if tipo_reporte == "📈 Ventas por período":
        st.subheader("Reporte de Ventas por Rango de Fechas")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
        with col2:
            fecha_fin = st.date_input("Fecha fin", datetime.now())
        
        tipo_agrupacion = st.selectbox(
            "Agrupar por",
            ["dia", "semana", "mes"]
        )
        
        filtro_venta = st.selectbox(
            "Tipo de venta",
            ["todas", "contado", "credito_pendiente", "credito_pagado"]
        )
        
        if st.button("Generar Reporte", type="primary"):
            with st.spinner("Generando reporte..."):
                resultado = reporte_por_rango(
                    fecha_inicio.strftime('%Y-%m-%d'),
                    fecha_fin.strftime('%Y-%m-%d'),
                    tipo_agrupacion,
                    filtro_venta
                )
            
            if resultado.get('success') and resultado.get('data'):
                df = pd.DataFrame(resultado['data'])
                st.dataframe(df, use_container_width=True)
                
                # Mostrar totales
                st.subheader("📊 Totales")
                totales = resultado.get('totales', {})
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Contado", f"Bs {totales.get('contado', 0):,.2f}")
                col2.metric("Total Crédito Pendiente", f"Bs {totales.get('credito_pendiente', 0):,.2f}")
                col3.metric("Total Crédito Cancelado", f"Bs {totales.get('credito_cancelado', 0):,.2f}")
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
            
            # Gráfico de barras
            st.subheader("📊 Gráfico de Ventas por Producto")
            st.bar_chart(df.set_index('producto')['unidades_vendidas'])
            
            # Total general
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
            total_original = sum(c.get('total_venta', 0) for c in creditos)
            
            col1, col2 = st.columns(2)
            col1.metric("Total Deuda Pendiente", f"Bs {total_deuda:,.2f}")
            col2.metric("Total Original Créditos", f"Bs {total_original:,.2f}")
            
            # Porcentaje recuperado
            if total_original > 0:
                porcentaje_recuperado = ((total_original - total_deuda) / total_original) * 100
                st.progress(porcentaje_recuperado / 100)
                st.caption(f"{porcentaje_recuperado:.1f}% recuperado")
        else:
            st.info("No hay créditos registrados")
    
    elif tipo_reporte == "📋 Reporte general de ventas":
        st.subheader("Reporte General de Ventas")
        
        periodo = st.selectbox(
            "Período",
            ["semanal", "mensual"]
        )
        
        with st.spinner("Generando reporte..."):
            reporte = reporte_ventas(periodo)
        
        if reporte:
            df = pd.DataFrame(reporte)
            st.dataframe(df, use_container_width=True)
            
            total_ventas = df['total_bs'].sum() if 'total_bs' in df.columns else 0
            st.metric("Total Ventas", f"Bs {total_ventas:,.2f}")
        else:
            st.info("No hay datos de ventas")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"© 2024 Sistema de Ventas\n{datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Función auxiliar para calcular deuda de un cliente
def calcular_deuda_cliente(cliente_id):
    """Calcula la deuda total de un cliente"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(saldo_pendiente), 0) 
            FROM ventas 
            WHERE id_cliente = %s AND credito = true AND pagado = false AND cancelada = false
        """, (cliente_id,))
        deuda = cursor.fetchone()[0] or 0
        conn.close()
        return deuda
    except:
        return 0
