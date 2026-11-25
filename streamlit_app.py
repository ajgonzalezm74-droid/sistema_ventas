# ==============================================================================
# SISTEMA DE VENTAS PROFESIONAL - INTERFAZ PRINCIPAL (STREAMLIT)
# ==============================================================================
# Este archivo contiene toda la interfaz de usuario, la navegación y la lógica
# de presentación (frontend). Se conecta con database.py y ventas_logic.py.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import traceback
import urllib.parse
import re

# --- IMPORTACIÓN DE LÓGICA DE NEGOCIO Y BASE DE DATOS ---
from database import (
    get_connection, init_db, get_clients, get_productos, 
    add_client_validado, add_product, reponer_stock,
    buscar_cliente_por_nombre, buscar_cliente_por_telefono,
    buscar_productos_por_descripcion,
    # Funciones bancarias
    obtener_datos_bancarios, guardar_datos_bancarios, eliminar_banco 
)

from ventas_logic import (
    registrar_venta, pagar_credito, pagar_credito_parcial,
    cancelar_venta, ventas_con_retraso, reporte_ventas,
    reporte_produto, obtener_tasa_actual, reporte_por_rango
)

from generar_recibo_profesional import generar_recibo_profesional

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================
st.set_page_config(
    page_title="Sistema de Ventas",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar base de datos (crea tablas si no existen)
try:
    init_db()
    # st.success("✅ Conectado a la base de datos PostgreSQL") # Descomentar si se necesita ver
except Exception as e:
    st.error(f"❌ Error de conexión a la base de datos: {e}")
    st.stop()

# Título principal
st.title("💰 Sistema de Ventas Profesional")
st.markdown("---")

# ==============================================================================
# MENÚ LATERAL (SIDEBAR)
# ==============================================================================
st.sidebar.title("📋 Menú Principal")
opcion = st.sidebar.selectbox(
    "Seleccione una opción",
    ["🏠 Dashboard", "🛍️ Registrar Venta", "👥 Clientes", "📦 Productos", 
     "💳 Créditos", "📊 Reportes", "⚙️ Configuración Bancaria"]
)

# Mostrar tasa actual en sidebar
try:
    tasa_actual = obtener_tasa_actual(force_update=True) 
    st.sidebar.info(f"💵 Tasa BCV: Bs {tasa_actual.get('bcv_usd', 55.0):.2f} / USD")
except:
    st.sidebar.warning("No se pudo obtener la tasa actual")
    tasa_actual = {'bcv_usd': 55.0}

# ==============================================================================
# SECCIÓN 1: DASHBOARD
# ==============================================================================
if opcion == "🏠 Dashboard":
    st.header("📈 Dashboard de Ventas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ventas del día
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM ventas WHERE DATE(fecha_venta) = CURRENT_DATE AND cancelada = FALSE")
        ventas_hoy = cursor.fetchone()[0] or 0
        
        # Total Clientes
        clientes = get_clients()
        total_clientes = len(clientes)
        
        # Total Productos
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
        
        st.subheader("📊 Últimas Ventas")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id, v.fecha_venta, c.nombre as cliente, v.total, 
                   CASE WHEN v.credito = true THEN 'Crédito' ELSE 'Contado' END as tipo
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.cancelada = FALSE
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

# ==============================================================================
# SECCIÓN 2: REGISTRAR VENTA
# ==============================================================================
elif opcion == "🛍️ Registrar Venta":
    st.header("🛍️ Nueva Venta")
    
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []
    
    col1, col2 = st.columns([1, 1])
    
    # --- COLUMNA CLIENTE ---
    with col1:
        st.subheader("👤 Cliente")
        buscar_cliente = st.text_input("Buscar cliente por nombre o teléfono")
        
        id_cliente = None
        cliente_seleccionado = None
        
        if buscar_cliente:
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
        
        # Si el cliente no existe, permitir crearlo
        if not id_cliente and buscar_cliente:
            st.warning("Cliente no encontrado")
            nombre_nuevo = st.text_input("Nombre del nuevo cliente*")
            telefono_nuevo = st.text_input("Teléfono")
            
            if st.button("Registrar Cliente"):
                if nombre_nuevo:
                    resultado = add_client_validado(nombre_nuevo, telefono_nuevo, "")
                    if resultado['success']:
                        st.success(f"Cliente {nombre_nuevo} registrado. Ya puede buscarlo.")
                        st.rerun()
                    else:
                        st.error(resultado.get('error'))
                else:
                    st.error("El nombre es requerido")
    
    # --- COLUMNA PRODUCTOS ---
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
    
    # --- BOTÓN REGISTRAR VENTA ---
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

# ==============================================================================
# SECCIÓN 3: CLIENTES
# ==============================================================================
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

# ==============================================================================
# SECCIÓN 4: PRODUCTOS
# ==============================================================================
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

# ==============================================================================
# SECCIÓN 5: CRÉDITOS (INCLUYE QR DE PAGO MÓVIL)
# ==============================================================================
elif opcion == "💳 Créditos":
    st.header("💳 Gestión de Créditos")
    
    try:
        creditos = ventas_con_retraso()
        mis_bancos = obtener_datos_bancarios() # Lista de cuentas bancarias guardadas
        
        if creditos:
            # --- AGRUPACIÓN POR CLIENTE ---
            clientes_dict = {}
            for credito in creditos:
                # En ventas_logic.py el nombre del cliente viene en 'cliente_nombre'
                nombre_cliente = credito.get('cliente_nombre', 'Cliente Desconocido')
                if nombre_cliente not in clientes_dict:
                    clientes_dict[nombre_cliente] = []
                clientes_dict[nombre_cliente].append(credito)
            
            st.subheader(f"📋 Créditos Pendientes ({len(creditos)} ventas en total)")
            
            # --- ITERAR POR CADA CLIENTE ---
            for nombre_cliente, lista_creditos in clientes_dict.items():
                deuda_total_cliente = sum(float(c.get('saldo_pendiente') or 0) for c in lista_creditos)
                
                with st.expander(f"👤 {nombre_cliente} - Deuda Total: Bs {deuda_total_cliente:,.2f} ({len(lista_creditos)} ventas)"):
                    
                    for idx, credito in enumerate(lista_creditos):
                        credito_id = credito.get('id_venta')
                        if credito_id is None: continue
                        
                        st.markdown(f"### 📄 Venta #{credito_id}")
                        
                        # --- DATOS DE LA VENTA (Corregidos con ventas_logic) ---
                        col1, col2 = st.columns(2)
                        with col1:
                            # Usamos total_venta y tasa_venta que trae ventas_logic.py
                            st.metric("Total Original", f"Bs {float(credito.get('total_venta') or 0):,.2f}")
                            st.metric("Saldo Pendiente", f"Bs {float(credito.get('saldo_pendiente') or 0):,.2f}")
                            
                            fecha_venta = credito.get('fecha_venta', 'N/A')
                            if fecha_venta and len(str(fecha_venta)) > 10:
                                fecha_venta = str(fecha_venta)[:10]
                            st.metric("Fecha Venta", fecha_venta)
                        
                        with col2:
                            st.metric("Tasa Venta", f"Bs {float(credito.get('tasa_venta') or 0):,.2f}")
                            st.metric("Tasa Actual", f"Bs {float(credito.get('tasa_actual') or 0):,.2f}")
                            
                            dias = credito.get('dias_retraso') or 0
                            if dias > 0:
                                st.metric("Días de Retraso", f"🔴 {dias} días")
                            else:
                                st.metric("Estado", "🟢 Al día")
                        
                        st.markdown(f"**Productos:** {credito.get('productos', 'N/A')}")
                        
                        saldo = float(credito.get('saldo_pendiente') or 0)
                        
                        # --- SECCIÓN DE QR DINÁMICO (PAGO MÓVIL) ---
                        if saldo > 0 and mis_bancos:
                            st.markdown("---")
                            st.write("📱 **Generar QR para Pago Móvil**")
                            
                            # Selector de banco
                            opciones_bancos = {f"{b['banco']} ({b['codigo_banco']})": b for b in mis_bancos}
                            banco_elegido_nombre = st.selectbox(
                                "Selecciona a qué cuenta quieres que te paguen:", 
                                list(opciones_bancos.keys()),
                                key=f"banco_sel_{credito_id}_{idx}"
                            )
                            
                            banco_elegido = opciones_bancos[banco_elegido_nombre]
                            
                            # Formateo estricto para el estándar de Pago Móvil (Venezuela)
                            codigo_banco_limpio = re.sub(r'[^0-9]', '', str(banco_elegido['codigo_banco']))[:4]
                            cedula_limpia = re.sub(r'[^0-9]', '', str(banco_elegido['cedula_rif']))
                            telefono_limpio = re.sub(r'[^0-9]', '', str(banco_elegido['telefono']))
                            
                            # Quitar el 0 inicial del teléfono si lo tiene
                            if telefono_limpio.startswith('0'):
                                telefono_limpio = telefono_limpio[1:] 
                            
                            # El formato es: Banco, Cedula, Telefono, Monto, Concepto
                            texto_qr = f"{codigo_banco_limpio},{cedula_limpia},{telefono_limpio},{saldo:.2f},"
                            
                            texto_qr_encoded = urllib.parse.quote(texto_qr)
                            url_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={texto_qr_encoded}"
                            
                            col_qr, col_info = st.columns([1, 2])
                            with col_qr:
                                st.image(url_qr, caption="Escanear para pagar")
                            with col_info:
                                st.info(f"""
                                **Datos para el pago:**
                                * **Banco:** {banco_elegido['banco']} ({codigo_banco_limpio})
                                * **C.I/RIF:** {cedula_limpia}
                                * **Teléfono:** {telefono_limpio}
                                * **Monto a pagar:** Bs {saldo:,.2f}
                                """)
                        elif saldo > 0:
                            st.warning("⚠️ Configura tus cuentas bancarias en el menú lateral para generar el QR.")

                        # --- FORMULARIO DE PAGO ---
                        st.subheader("💰 Registrar Pago")
                        monto_pago = st.number_input(
                            "Monto a pagar", min_value=0.0, max_value=saldo if saldo > 0 else 0.0,
                            step=100.0, key=f"monto_{credito_id}_{idx}"
                        )
                        observacion = st.text_input("Observación", key=f"obs_{credito_id}_{idx}")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button(f"Pagar Parcial", key=f"parcial_{credito_id}_{idx}"):
                                if monto_pago > 0 and monto_pago <= saldo:
                                    resultado = pagar_credito_parcial(credito_id, monto_pago, observacion)
                                    if resultado.get('success'):
                                        st.success(f"✅ {resultado.get('mensaje', 'Pago registrado')}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Error: {resultado.get('error')}")
                                else:
                                    st.warning(f"Ingrese un monto válido (1 - {saldo:,.2f})")
                        
                        with col_btn2:
                            if st.button(f"Pagar Completo", key=f"completo_{credito_id}_{idx}"):
                                resultado = pagar_credito(credito_id)
                                if resultado.get('success'):
                                    st.success(f"✅ Crédito pagado completamente")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Error: {resultado.get('error')}")
                        st.markdown("---")
        else:
            st.info("🎉 No hay créditos pendientes")
    
    except Exception as e:
        st.error(f"Error cargando créditos: {e}")
        st.code(traceback.format_exc())

# ==============================================================================
# SECCIÓN 6: REPORTES
# ==============================================================================
elif opcion == "📊 Reportes":
    st.header("📊 Reportes y Estadísticas")
    
    tipo_reporte = st.radio(
        "Seleccione el tipo de reporte",
        ["📈 Ventas por período", "🏆 Productos más vendidos", "💳 Estado de créditos"],
        horizontal=True
    )
    
    if tipo_reporte == "📈 Ventas por período":
        st.subheader("Reporte de Ventas por Rango de Fechas")
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
        with col2:
            fecha_fin = st.date_input("Fecha fin", datetime.now())
        
        tipo = st.selectbox("Agrupar por", ["dia", "semana", "mes"])
        filtro_venta = st.selectbox("Tipo de venta", ["todas", "contado", "credito_pendiente", "credito_pagado"])
        
        if st.button("🔍 Generar Reporte", type="primary"):
            with st.spinner("Generando reporte..."):
                try:
                    resultado = reporte_por_rango(
                        fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'),
                        tipo, filtro_venta
                    )
                    if resultado.get('success') and resultado.get('data'):
                        df = pd.DataFrame(resultado['data'])
                        st.dataframe(df, use_container_width=True)
                        st.subheader("💰 Totales del Período")
                        totales = resultado.get('totales', {})
                        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                        col_t1.metric("Contado", f"Bs {totales.get('contado', 0):,.2f}")
                        col_t2.metric("Créd. Pendientes", f"Bs {totales.get('credito_pendiente', 0):,.2f}")
                        col_t3.metric("Créd. Cancelados", f"Bs {totales.get('credito_cancelado', 0):,.2f}")
                        col_t4.metric("TOTAL", f"Bs {totales.get('general', 0):,.2f}")
                    else:
                        st.warning("No hay datos en el período seleccionado")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    elif tipo_reporte == "🏆 Productos más vendidos":
        st.subheader("Top Productos Más Vendidos")
        if st.button("🔍 Ver Reporte", type="primary"):
            with st.spinner("Cargando datos..."):
                try:
                    reporte = reporte_produto()
                    if reporte and len(reporte) > 0:
                        df = pd.DataFrame(reporte)
                        st.dataframe(df, use_container_width=True)
                        total_unidades = df['unidades_vendidas'].sum() if 'unidades_vendidas' in df.columns else 0
                        total_bs = df['total_bs'].sum() if 'total_bs' in df.columns else 0
                        col1, col2 = st.columns(2)
                        col1.metric("Total Unidades Vendidas", f"{int(total_unidades):,}")
                        col2.metric("Total Ventas (Bs)", f"Bs {total_bs:,.2f}")
                        if 'producto' in df.columns and 'unidades_vendidas' in df.columns:
                            st.subheader("📊 Gráfico de Ventas por Producto")
                            st.bar_chart(df.set_index('producto')['unidades_vendidas'].head(10))
                    else:
                        st.info("No hay datos de productos vendidos")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    elif tipo_reporte == "💳 Estado de créditos":
        st.subheader("Estado de Créditos Pendientes")
        if st.button("🔍 Ver Reporte", type="primary"):
            with st.spinner("Cargando créditos..."):
                try:
                    creditos = ventas_con_retraso()
                    if creditos and len(creditos) > 0:
                        df = pd.DataFrame(creditos)
                        columnas_mostrar = ['id_venta', 'cliente_nombre', 'total_venta', 'saldo_pendiente', 'dias_retraso', 'porcentaje_pagado']
                        columnas_existentes = [col for col in columnas_mostrar if col in df.columns]
                        st.dataframe(df[columnas_existentes] if columnas_existentes else df, use_container_width=True)
                        total_deuda = df['saldo_pendiente'].sum() if 'saldo_pendiente' in df.columns else 0
                        st.metric("Total Deuda Pendiente", f"Bs {total_deuda:,.2f}")
                        if 'cliente_nombre' in df.columns and 'saldo_pendiente' in df.columns:
                            st.subheader("Resumen por Cliente")
                            resumen_cliente = df.groupby('cliente_nombre')['saldo_pendiente'].sum().sort_values(ascending=False).reset_index()
                            resumen_cliente.columns = ['Cliente', 'Deuda Total']
                            st.dataframe(resumen_cliente, use_container_width=True)
                    else:
                        st.info("🎉 No hay créditos pendientes")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ==============================================================================
# SECCIÓN 7: CONFIGURACIÓN BANCARIA (QR)
# ==============================================================================
elif opcion == "⚙️ Configuración Bancaria":
    st.header("⚙️ Mis Cuentas Bancarias")
    st.write("Agrega o edita tus cuentas para que tus clientes puedan pagarte automáticamente con un QR.")
    
    bancos_guardados = obtener_datos_bancarios()
    
    tab1, tab2 = st.tabs(["➕ Agregar Cuenta", "✏️ Editar / Eliminar Cuentas"])
    
    # --- PESTAÑA 1: AGREGAR CUENTA ---
    with tab1:
        with st.form("form_agregar_banco"):
            st.subheader("Nueva Cuenta")
            col1, col2 = st.columns(2)
            with col1:
                banco = st.text_input("Nombre del Banco (Ej: Banesco)")
                codigo_banco = st.text_input("Código del Banco (Ej: 0134)")
            with col2:
                cedula_rif = st.text_input("Cédula o RIF")
                telefono = st.text_input("Teléfono de Pago Móvil")
            
            titular = st.text_input("Nombre del Titular")
            
            if st.form_submit_button("💾 Guardar Cuenta", type="primary"):
                if banco and codigo_banco and cedula_rif and telefono:
                    if guardar_datos_bancarios(banco, codigo_banco, cedula_rif, telefono, titular):
                        st.success("✅ Cuenta guardada correctamente.")
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar la cuenta.")
                else:
                    st.warning("Por favor, llena los campos obligatorios.")
    
    # --- PESTAÑA 2: EDITAR / ELIMINAR CUENTA ---
    with tab2:
        if bancos_guardados:
            st.subheader("Administrar mis Cuentas")
            
            opciones = {f"{b['banco']} ({b['codigo_banco']})": b for b in bancos_guardados}
            cuenta_sel_nombre = st.selectbox("Selecciona la cuenta a modificar:", list(opciones.keys()))
            cuenta_sel = opciones[cuenta_sel_nombre]
            
            with st.form("form_editar_banco"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    e_banco = st.text_input("Banco", value=cuenta_sel['banco'])
                    e_codigo = st.text_input("Código", value=cuenta_sel['codigo_banco'])
                with col_e2:
                    e_cedula = st.text_input("Cédula/RIF", value=cuenta_sel['cedula_rif'])
                    e_telefono = st.text_input("Teléfono", value=cuenta_sel['telefono'])
                
                e_titular = st.text_input("Titular", value=cuenta_sel['titular'])
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.form_submit_button("✏️ Actualizar Cuenta", type="primary"):
                        if eliminar_banco(cuenta_sel['id']):
                            if guardar_datos_bancarios(e_banco, e_codigo, e_cedula, e_telefono, e_titular):
                                st.success("✅ Cuenta actualizada correctamente.")
                                st.rerun()
                            else:
                                st.error("❌ Error al actualizar la cuenta.")
                with col_b2:
                    if st.form_submit_button("🗑️ Inactivar (Eliminar) Cuenta"):
                        if eliminar_banco(cuenta_sel['id']):
                            st.success("✅ Cuenta eliminada correctamente.")
                            st.rerun()
                        else:
                            st.error("❌ Error al eliminar la cuenta.")
        else:
            st.info("No tienes cuentas guardadas aún. Agrega una en la pestaña anterior.")

# ==============================================================================
# FOOTER
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.caption(f"© 2026 Sistema de Ventas\n{datetime.now().strftime('%d/%m/%Y %H:%M')}")
