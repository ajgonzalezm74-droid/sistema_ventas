import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import io
from PIL import Image

# Importar tu lógica existente
from database import init_db, get_clients, get_productos as get_products, add_client, add_product, reponer_stock, buscar_producto_por_descripcion, buscar_cliente_por_telefono, buscar_cliente_por_nombre, add_client_validado, get_connection
from generar_recibo import generar_recibo_imagen
from generar_recibo_profesional import generar_recibo_profesional
from ventas_logic import (
    registrar_venta,
    pagar_credito_parcial,
    ventas_con_retraso,
    reporte_ventas,
    reporte_produto,
    obtener_tasa_actual,
    obtener_historial_pagos,
    reporte_por_rango,
    obtener_creditos_agrupados,
    pagar_credito_con_tasa
)

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
    st.success("✅ Conectado a la base de datos")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")

# Título principal
st.title("💰 Sistema de Ventas Profesional")
st.markdown("---")

# Sidebar para navegación
st.sidebar.title("📋 Menú Principal")
opcion = st.sidebar.selectbox(
    "Seleccione una opción",
    ["🏠 Dashboard", "🛍️ Registrar Venta", "👥 Clientes", "📦 Productos", 
     "💳 Créditos", "📊 Reportes", "⚙️ Configuración"]
)

# Mostrar tasa actual en sidebar
tasa_actual = obtener_tasa_actual()
st.sidebar.info(f"💵 Tasa BCV: Bs {tasa_actual.get('bcv_usd', 55.0):.2f} / USD")

# ========== DASHBOARD ==========
if opcion == "🏠 Dashboard":
    st.header("📈 Dashboard de Ventas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Obtener datos para el dashboard
    try:
        conn = get_connection()
        
        # Total ventas hoy
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM ventas WHERE DATE(fecha_venta) = CURRENT_DATE")
        ventas_hoy = cursor.fetchone()[0] or 0
        
        # Total clientes
        cursor.execute("SELECT COUNT(*) FROM clientes")
        total_clientes = cursor.fetchone()[0]
        
        # Total productos
        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = true")
        total_productos = cursor.fetchone()[0]
        
        # Créditos pendientes
        cursor.execute("SELECT COALESCE(SUM(saldo_pendiente), 0) FROM ventas WHERE credito = true AND pagado = false")
        creditos_pendientes = cursor.fetchone()[0] or 0
        
        conn.close()
        
        col1.metric("💰 Ventas Hoy", f"Bs {ventas_hoy:,.2f}")
        col2.metric("👥 Clientes", total_clientes)
        col3.metric("📦 Productos", total_productos)
        col4.metric("💳 Créditos Pendientes", f"Bs {creditos_pendientes:,.2f}")
        
    except Exception as e:
        st.error(f"Error cargando dashboard: {e}")
    
    # Gráfico de ventas últimos 7 días
    st.subheader("📊 Ventas Últimos 7 Días")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE(fecha_venta) as fecha, SUM(total) as total
            FROM ventas
            WHERE fecha_venta >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(fecha_venta)
            ORDER BY fecha
        """)
        datos = cursor.fetchall()
        conn.close()
        
        if datos:
            df = pd.DataFrame(datos, columns=['fecha', 'total'])
            fig = px.line(df, x='fecha', y='total', title='Ventas Diarias')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de ventas en los últimos 7 días")
    except Exception as e:
        st.error(f"Error cargando gráfico: {e}")

# ========== REGISTRAR VENTA ==========
elif opcion == "🛍️ Registrar Venta":
    st.header("🛍️ Nueva Venta")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Buscar cliente
        st.subheader("👤 Cliente")
        buscar_cliente = st.text_input("Buscar cliente por nombre o teléfono")
        
        if buscar_cliente:
            cliente_encontrado = buscar_cliente_por_nombre(buscar_cliente) or buscar_cliente_por_telefono(buscar_cliente)
            if cliente_encontrado:
                st.success(f"Cliente seleccionado: {cliente_encontrado['nombre']}")
                id_cliente = cliente_encontrado['id']
            else:
                st.warning("Cliente no encontrado. Complete el formulario para crear uno nuevo:")
                nombre_nuevo = st.text_input("Nombre del nuevo cliente")
                telefono_nuevo = st.text_input("Teléfono")
                if st.button("Registrar Cliente") and nombre_nuevo:
                    resultado = add_client_validado(nombre_nuevo, telefono_nuevo, "")
                    if resultado['success']:
                        st.success("Cliente registrado exitosamente")
                        id_cliente = resultado.get('id')
                    else:
                        st.error(resultado.get('error'))
        else:
            id_cliente = None
    
    with col2:
        # Agregar productos
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
                    cantidad = st.number_input("Cantidad", min_value=1, step=1)
                    if st.button("➕ Agregar al carrito"):
                        st.session_state.carrito.append({
                            'id': producto_seleccionado['id'],
                            'descripcion': producto_seleccionado['descripcion'],
                            'cantidad': cantidad,
                            'precio_usd': producto_seleccionado.get('costo', 0)
                        })
                        st.success(f"Agregado: {producto_seleccionado['descripcion']} x{cantidad}")
        
        # Mostrar carrito
        if st.session_state.carrito:
            st.subheader("🛒 Carrito de compra")
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
            st.error("Debe seleccionar o crear un cliente")
        elif not st.session_state.carrito:
            st.error("Debe agregar productos al carrito")
        else:
            # Preparar productos para la venta
            productos_venta = [
                {
                    "id_producto": item['id'],
                    "cantidad": item['cantidad'],
                    "precio_usd": item['precio_usd']
                }
                for item in st.session_state.carrito
            ]
            
            credito = st.checkbox("Venta a crédito")
            
            resultado = registrar_venta(id_cliente, productos_venta, credito)
            
            if resultado.get('success'):
                st.success(f"✅ Venta registrada exitosamente. Total: Bs {resultado.get('total', 0):,.2f}")
                
                # Generar recibo
                if st.button("📄 Ver recibo"):
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
                    try:
                        img_bytes = generar_recibo_profesional(datos_recibo)
                        st.image(img_bytes, caption="Recibo de venta")
                    except:
                        st.warning("No se pudo generar el recibo")
                
                # Limpiar carrito
                st.session_state.carrito = []
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
                df_clientes = pd.DataFrame(clientes)
                st.dataframe(df_clientes, use_container_width=True)
                
                # Opción para editar (simplificada)
                cliente_id_editar = st.number_input("ID del cliente a editar", min_value=1, step=1)
                nuevo_nombre = st.text_input("Nuevo nombre")
                nuevo_telefono = st.text_input("Nuevo teléfono")
                if st.button("Actualizar Cliente"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE clientes SET nombre = %s, telefono = %s WHERE id = %s", 
                                 (nuevo_nombre, nuevo_telefono, cliente_id_editar))
                    conn.commit()
                    conn.close()
                    st.success("Cliente actualizado")
                    st.rerun()
            else:
                st.info("No hay clientes registrados")
        except Exception as e:
            st.error(f"Error cargando clientes: {e}")
    
    with tab2:
        nombre = st.text_input("Nombre completo*")
        telefono = st.text_input("Teléfono")
        direccion = st.text_area("Dirección")
        
        if st.button("Registrar Cliente", type="primary"):
            if nombre:
                resultado = add_client_validado(nombre, telefono, direccion)
                if resultado['success']:
                    st.success("✅ Cliente registrado exitosamente")
                else:
                    st.error(f"❌ Error: {resultado.get('error')}")
            else:
                st.error("El nombre es requerido")
    
    with tab3:
        busqueda = st.text_input("Buscar por nombre o teléfono")
        if busqueda:
            clientes_encontrados = buscar_cliente_por_nombre(busqueda) or buscar_cliente_por_telefono(busqueda)
            if clientes_encontrados:
                if isinstance(clientes_encontrados, dict):
                    clientes_encontrados = [clientes_encontrados]
                st.dataframe(pd.DataFrame(clientes_encontrados), use_container_width=True)
            else:
                st.warning("No se encontraron clientes")

# ========== PRODUCTOS ==========
elif opcion == "📦 Productos":
    st.header("📦 Gestión de Productos")
    
    tab1, tab2 = st.tabs(["📋 Lista de Productos", "➕ Nuevo Producto"])
    
    with tab1:
        try:
            productos = get_products()
            if productos:
                df_productos = pd.DataFrame(productos)
                st.dataframe(df_productos, use_container_width=True)
                
                # Reponer stock
                st.subheader("Reponer Stock")
                producto_id = st.number_input("ID del producto", min_value=1, step=1)
                cantidad = st.number_input("Cantidad a agregar", min_value=1, step=1)
                costo = st.number_input("Costo unitario (opcional)", min_value=0.0, step=0.01)
                
                if st.button("Reponer Stock"):
                    resultado = reponer_stock(producto_id, cantidad, costo if costo > 0 else None)
                    if resultado.get('success'):
                        st.success(resultado.get('message'))
                        st.rerun()
                    else:
                        st.error(resultado.get('error'))
            else:
                st.info("No hay productos registrados")
        except Exception as e:
            st.error(f"Error cargando productos: {e}")
    
    with tab2:
        descripcion = st.text_input("Descripción del producto*")
        costo = st.number_input("Costo unitario (Bs)", min_value=0.0, step=0.01)
        stock = st.number_input("Stock inicial", min_value=0, step=1)
        
        if st.button("Registrar Producto", type="primary"):
            if descripcion:
                resultado = add_product(descripcion, costo, stock)
                if resultado.get('success'):
                    st.success("✅ Producto registrado exitosamente")
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
            st.subheader("📋 Créditos Pendientes")
            
            for credito in creditos:
                with st.expander(f"Venta #{credito.get('id_venta')} - Cliente: {credito.get('cliente_nombre', 'N/A')}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Total Deuda", f"Bs {credito.get('total_venta', 0):,.2f}")
                        st.metric("Saldo Pendiente", f"Bs {credito.get('saldo_pendiente', 0):,.2f}", 
                                 delta=f"{credito.get('porcentaje_pagado', 0):.1f}% pagado")
                    
                    with col2:
                        st.metric("Fecha Venta", credito.get('fecha_venta', 'N/A')[:10])
                        st.metric("Tasa Aplicada", f"Bs {credito.get('tasa', 0):,.2f}")
                    
                    # Pago de crédito
                    monto_pago = st.number_input(f"Monto a pagar (Venta #{credito.get('id_venta')})", 
                                                min_value=0.0, step=100.0, key=f"pago_{credito.get('id_venta')}")
                    
                    if st.button(f"Registrar Pago", key=f"btn_{credito.get('id_venta')}"):
                        if monto_pago > 0:
                            resultado = pagar_credito_con_tasa(
                                credito.get('id_venta'), 
                                monto_pago, 
                                f"Pago registrado en Streamlit",
                                tasa_actual.get('bcv_usd', 55.0)
                            )
                            if resultado.get('success'):
                                st.success(f"✅ Pago registrado exitosamente. Nuevo saldo: Bs {resultado.get('saldo_pendiente', 0):,.2f}")
                                st.rerun()
                            else:
                                st.error(f"❌ Error: {resultado.get('error')}")
                        else:
                            st.warning("Ingrese un monto válido")
        else:
            st.info("No hay créditos pendientes")
    
    except Exception as e:
        st.error(f"Error cargando créditos: {e}")

# ========== REPORTES ==========
elif opcion == "📊 Reportes":
    st.header("📊 Reportes y Estadísticas")
    
    tipo_reporte = st.selectbox(
        "Tipo de Reporte",
        ["Ventas por período", "Productos más vendidos", "Estado de créditos"]
    )
    
    if tipo_reporte == "Ventas por período":
        fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
        fecha_fin = st.date_input("Fecha fin", datetime.now())
        
        if st.button("Generar Reporte"):
            try:
                resultado = reporte_por_rango(
                    fecha_inicio.strftime('%Y-%m-%d'),
                    fecha_fin.strftime('%Y-%m-%d'),
                    'dia',
                    'todas'
                )
                
                if resultado.get('success') and resultado.get('datos'):
                    df = pd.DataFrame(resultado['datos'])
                    st.dataframe(df, use_container_width=True)
                    
                    # Gráfico
                    fig = px.bar(df, x='fecha', y='total', title='Ventas por día')
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.metric("Total Ventas", f"Bs {resultado.get('total_general', 0):,.2f}")
                    st.metric("Total USD", f"${resultado.get('total_usd', 0):,.2f}")
                else:
                    st.info("No hay datos en el período seleccionado")
            except Exception as e:
                st.error(f"Error generando reporte: {e}")
    
    elif tipo_reporte == "Productos más vendidos":
        try:
            reporte = reporte_produto()
            if reporte:
                df = pd.DataFrame(reporte)
                st.dataframe(df, use_container_width=True)
                
                fig = px.bar(df.head(10), x='descripcion', y='cantidad_vendida', 
                            title='Top 10 Productos más vendidos')
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error cargando reporte: {e}")
    
    elif tipo_reporte == "Estado de créditos":
        creditos = ventas_con_retraso()
        if creditos:
            df = pd.DataFrame(creditos)
            st.dataframe(df, use_container_width=True)
            
            total_deuda = sum(c.get('saldo_pendiente', 0) for c in creditos)
            st.metric("Total Deuda en Créditos", f"Bs {total_deuda:,.2f}")
        else:
            st.info("No hay créditos registrados")

# ========== CONFIGURACIÓN ==========
elif opcion == "⚙️ Configuración":
    st.header("⚙️ Configuración del Sistema")
    
    st.subheader("Actualizar Tasa de Cambio")
    tasa_manual = st.number_input("Tasa USD a Bs", min_value=0.0, value=55.0, step=0.50)
    
    if st.button("Actualizar Tasa"):
        # Aquí implementarías la lógica para guardar la tasa
        # Por ahora solo mostramos un mensaje
        st.success(f"Tasa actualizada a Bs {tasa_manual:.2f} (simulado)")
    
    st.subheader("Respaldo de Base de Datos")
    if st.button("Exportar Datos (CSV)"):
        # Implementar exportación a CSV
        st.info("Función de exportación en desarrollo")
    
    st.subheader("Información del Sistema")
    st.write(f"Versión: 1.0.0")
    st.write(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Footer en sidebar
st.sidebar.markdown("---")
st.sidebar.caption(f"© 2024 Sistema de Ventas\nÚltima conexión: {datetime.now().strftime('%H:%M:%S')}")
