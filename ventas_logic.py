import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from database import get_connection
from exchange_provider import ExchangeProvider

exchange = ExchangeProvider()

# ========== FUNCIONES AUXILIARES ==========

def verificar_stock_multiples(productos):
    """Verifica stock para múltiples productos"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            cursor.execute("SELECT cantidad FROM inventario WHERE id_producto = %s", (id_producto,))
            resultado = cursor.fetchone()
            if not resultado or resultado[0] < cantidad:
                conn.close()
                return False, f"Stock insuficiente para producto ID {id_producto}"
        conn.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def actualizar_inventario_multiples(productos, es_venta=True):
    """Actualiza inventario después de una venta o cancelación"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            if es_venta:
                cursor.execute("UPDATE inventario SET cantidad = cantidad - %s WHERE id_producto = %s", 
                             (cantidad, id_producto))
            else:
                cursor.execute("UPDATE inventario SET cantidad = cantidad + %s, devolucion = devolucion + %s WHERE id_producto = %s", 
                             (cantidad, cantidad, id_producto))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error actualizando inventario: {e}")
        return False


# ========== FUNCIONES PRINCIPALES ==========

def registrar_venta(id_cliente, productos, es_credito=False, fecha_manual=None):
    """Registra una nueva venta"""
    try:
        stock_ok, mensaje = verificar_stock_multiples(productos)
        if not stock_ok:
            return {"success": False, "error": mensaje}
        
        tasas = exchange.get_all_rates(force_update=True)
        tasa_bs = tasas.get("bcv_usd", 0)
        if tasa_bs == 0:
            return {"success": False, "error": "No se pudo obtener la tasa BCV"}
        
        conn = get_connection()
        cursor = conn.cursor()
        
        total_venta = 0
        detalles = []
        
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            precio_usd = item.get('precio_usd', 0)
            
            if precio_usd == 0:
                cursor.execute("""
                    SELECT p.descripcion, i.costo 
                    FROM productos p 
                    JOIN inventario i ON p.id = i.id_producto 
                    WHERE p.id = %s
                """, (id_producto,))
                producto = cursor.fetchone()
                if not producto:
                    conn.close()
                    return {"success": False, "error": f"Producto ID {id_producto} no encontrado"}
                descripcion, costo_dolar = producto
                precio_usd = costo_dolar
            else:
                cursor.execute("SELECT descripcion FROM productos WHERE id = %s", (id_producto,))
                producto = cursor.fetchone()
                descripcion = producto[0] if producto else f"Producto {id_producto}"
            
            precio_unitario_bs = precio_usd * tasa_bs
            subtotal = precio_unitario_bs * cantidad
            total_venta += subtotal
            
            detalles.append({
                'id_producto': id_producto, 
                'cantidad': cantidad, 
                'descripcion': descripcion,
                'precio_unitario': precio_unitario_bs, 
                'subtotal': subtotal, 
                'costo_dolar': precio_usd
            })
        
        pagado = True if not es_credito else False
        credito = True if es_credito else False
        
        if fecha_manual:
            fecha_venta = fecha_manual
        else:
            fecha_venta = datetime.now()
        
        # Si es venta al contado, también se establece fecha_pago
        if not es_credito:
            cursor.execute("""
                INSERT INTO ventas (id_cliente, total, tasa, credito, pagado, fecha_venta, fecha_pago, saldo_pendiente) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (id_cliente, total_venta, tasa_bs, credito, pagado, fecha_venta, fecha_venta, 0))
        else:
            cursor.execute("""
                INSERT INTO ventas (id_cliente, total, tasa, credito, pagado, fecha_venta, saldo_pendiente) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (id_cliente, total_venta, tasa_bs, credito, pagado, fecha_venta, total_venta))
        
        id_venta = cursor.fetchone()[0]
        
        for detalle in detalles:
            cursor.execute("""
                INSERT INTO detalles_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal) 
                VALUES (%s, %s, %s, %s, %s)
            """, (id_venta, detalle['id_producto'], detalle['cantidad'], detalle['precio_unitario'], detalle['subtotal']))
        
        conn.commit()
        productos_para_inventario = [{'id_producto': d['id_producto'], 'cantidad': d['cantidad']} for d in detalles]
        actualizar_inventario_multiples(productos_para_inventario, es_venta=True)
        
        # Obtener nombre del cliente
        cursor.execute("SELECT nombre FROM clientes WHERE id = %s", (id_cliente,))
        cliente_nombre = cursor.fetchone()[0] if cursor.rowcount > 0 else "Cliente"
        
        conn.close()
        
        resumen_productos = [f"{d['descripcion']} x{d['cantidad']}" for d in detalles]
        return {
            "success": True, 
            "id_venta": id_venta, 
            "total": total_venta, 
            "total_bs": total_venta,
            "tasa_usada": tasa_bs, 
            "tipo": "crédito" if es_credito else "contado", 
            "productos": resumen_productos, 
            "detalles": detalles,
            "cliente_nombre": cliente_nombre
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancelar_venta(id_venta):
    """Cancela una venta y restaura el inventario"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_producto, cantidad FROM detalles_venta WHERE id_venta = %s", (id_venta,))
        productos = cursor.fetchall()
        if not productos:
            conn.close()
            return {"error": "Venta no encontrada"}
        cursor.execute("UPDATE ventas SET cancelada = TRUE WHERE id = %s", (id_venta,))
        for id_producto, cantidad in productos:
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s, devolucion = devolucion + %s WHERE id_producto = %s", 
                         (cantidad, cantidad, id_producto))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== CRÉDITOS ==========

def obtener_creditos_agrupados():
    """Obtiene todos los créditos pendientes agrupados por cliente"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        tasas = exchange.get_all_rates(force_update=False)
        tasa_actual = tasas.get("bcv_usd", 55.0)
        
        cursor.execute('''
            SELECT v.id, v.id_cliente, v.fecha_venta, v.total, v.tasa, v.saldo_pendiente,
                   c.nombre as cliente_nombre, c.telefono as cliente_telefono,
                   COALESCE(v.pagado, false) as pagado
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.credito = TRUE 
            AND v.cancelada = FALSE
            ORDER BY c.nombre, v.fecha_venta
        ''')
        
        ventas = cursor.fetchall()
        clientes_creditos = {}
        
        for venta in ventas:
            cliente_id = venta['id_cliente']
            id_venta = venta['id']
            total_venta = float(venta['total'])
            tasa_venta = float(venta['tasa']) if venta['tasa'] else 55.0
            saldo_db = float(venta['saldo_pendiente']) if venta['saldo_pendiente'] else total_venta
            
            if venta['pagado'] or saldo_db <= 0:
                continue
            
            total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
            total_actualizado = total_usd * tasa_actual
            
            # Obtener pagos acumulados
            cursor_pagos = conn.cursor()
            cursor_pagos.execute("""
                SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                FROM pagos_credito
                WHERE id_venta = %s
            """, (id_venta,))
            total_pagado = float(cursor_pagos.fetchone()[0] or 0)
            cursor_pagos.close()
            
            saldo_pendiente = total_actualizado - total_pagado
            
            if saldo_pendiente <= 0.01:
                continue
            
            if cliente_id not in clientes_creditos:
                clientes_creditos[cliente_id] = {
                    'cliente_id': cliente_id,
                    'cliente_nombre': venta['cliente_nombre'],
                    'cliente_telefono': venta['cliente_telefono'],
                    'deudas': []
                }
            
            cursor_prod = conn.cursor(cursor_factory=RealDictCursor)
            cursor_prod.execute('''
                SELECT p.descripcion, dv.cantidad
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = %s
            ''', (id_venta,))
            productos = cursor_prod.fetchall()
            cursor_prod.close()
            
            clientes_creditos[cliente_id]['deudas'].append({
                'id_venta': id_venta,
                'fecha_venta': venta['fecha_venta'].strftime('%d/%m/%Y') if venta['fecha_venta'] else '-',
                'total_original': total_venta,
                'tasa_venta': tasa_venta,
                'total_usd': total_usd,
                'total_actualizado': total_actualizado,
                'total_pagado': total_pagado,
                'saldo_pendiente': saldo_pendiente,
                'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos]
            })
        
        conn.close()
        
        resultado = []
        for cliente_data in clientes_creditos.values():
            deuda_total = sum(d['saldo_pendiente'] for d in cliente_data['deudas'])
            resultado.append({
                'cliente_id': cliente_data['cliente_id'],
                'cliente_nombre': cliente_data['cliente_nombre'],
                'cliente_telefono': cliente_data['cliente_telefono'],
                'deuda_total': deuda_total,
                'deudas': cliente_data['deudas']
            })
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error en obtener_creditos_agrupados: {e}")
        return []


def pagar_credito_con_tasa(id_venta, monto=0, observacion="", tasa_actual=None):
    """Registra un pago de crédito con tasa actualizada"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.total, v.tasa, v.pagado, v.saldo_pendiente, v.credito,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado_anterior,
                   c.nombre as cliente_nombre, c.telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.id = %s
        """, (id_venta,))
        
        venta = cursor.fetchone()
        if not venta:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        total_venta, tasa_venta, pagado_completo, saldo_db, es_credito, total_pagado_anterior, cliente_nombre, cliente_telefono = venta
        total_venta = float(total_venta)
        tasa_venta = float(tasa_venta) if tasa_venta else 55.0
        total_pagado_anterior = float(total_pagado_anterior) if total_pagado_anterior else 0
        
        if pagado_completo:
            conn.close()
            return {"success": False, "error": "Esta venta ya está pagada completamente"}
        
        if not es_credito:
            conn.close()
            return {"success": False, "error": "Esta venta no es a crédito"}
        
        if tasa_actual is None:
            tasas = exchange.get_all_rates(force_update=False)
            tasa_actual = tasas.get("bcv_usd", 55.0)
        
        if tasa_actual == 0:
            tasa_actual = 55.0
        
        # Calcular deuda actualizada
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_actual
        deuda_actual = total_actualizado - total_pagado_anterior
        
        if deuda_actual <= 0:
            conn.close()
            return {"success": False, "error": "No hay deuda pendiente"}
        
        if monto <= 0:
            monto_pagar = deuda_actual
            es_pago_total = True
        else:
            monto_pagar = min(monto, deuda_actual)
            es_pago_total = abs(monto_pagar - deuda_actual) <= 0.01
        
        if monto_pagar <= 0:
            conn.close()
            return {"success": False, "error": "Monto de pago inválido"}
        
        # Registrar pago
        cursor.execute("""
            INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion, fecha_pago)
            VALUES (%s, %s, %s, %s, %s)
        """, (id_venta, monto_pagar, tasa_actual, observacion or ("Pago completo" if es_pago_total else "Pago parcial"), datetime.now()))
        
        nuevo_total_pagado = total_pagado_anterior + monto_pagar
        nuevo_saldo = deuda_actual - monto_pagar
        
        if nuevo_saldo <= 0.01:
            cursor.execute("""
                UPDATE ventas 
                SET pagado = TRUE, 
                    pagado_parcial = FALSE, 
                    saldo_pendiente = 0, 
                    fecha_pago = CURRENT_TIMESTAMP, 
                    tasa_pago = %s
                WHERE id = %s
            """, (tasa_actual, id_venta))
            estado = "COMPLETADO"
            mensaje = f"Pago completado. Total pagado: Bs {nuevo_total_pagado:,.2f}"
        else:
            cursor.execute("""
                UPDATE ventas 
                SET saldo_pendiente = %s, 
                    pagado_parcial = TRUE, 
                    pagado = FALSE
                WHERE id = %s
            """, (nuevo_saldo, id_venta))
            estado = "PARCIAL"
            mensaje = f"Pago parcial registrado. Saldo pendiente: Bs {nuevo_saldo:,.2f}"
        
        # Obtener productos para el recibo
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario
            FROM detalles_venta dv
            JOIN productos p ON dv.id_producto = p.id
            WHERE dv.id_venta = %s
        """, (id_venta,))
        productos = cursor.fetchall()
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "estado": estado,
            "monto_pagado": monto_pagar,
            "total_pagado_acumulado": nuevo_total_pagado,
            "saldo_pendiente": max(0, nuevo_saldo),
            "tasa_aplicada": tasa_actual,
            "tasa_venta": tasa_venta,
            "total_venta": total_venta,
            "total_usd": total_usd,
            "total_actualizado": total_actualizado,
            "cliente_nombre": cliente_nombre,
            "cliente_telefono": cliente_telefono,
            "productos": [{"descripcion": p[0], "cantidad": p[1], "precio": p[2]} for p in productos],
            "mensaje": mensaje
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def pagar_credito(id_venta):
    """Paga completamente un crédito"""
    return pagar_credito_con_tasa(id_venta, 0, "Pago completo", None)


def pagar_credito_parcial(id_venta, monto_pagado, observacion=""):
    """Registra un pago parcial de crédito"""
    return pagar_credito_con_tasa(id_venta, monto_pagado, observacion, None)


def ventas_con_retraso():
    """Obtiene créditos con retraso"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v 
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.credito = TRUE AND v.pagado = FALSE AND v.cancelada = FALSE
        """)
        
        ventas_credito = []
        ahora = datetime.now()
        
        tasas = exchange.get_all_rates(force_update=False)
        tasa_actual = tasas.get("bcv_usd", 55.0)
        
        for row in cursor.fetchall():
            venta = dict(row)
            fecha_venta = venta['fecha_venta']
            horas_transcurridas = (ahora - fecha_venta).total_seconds() / 3600
            dias_retraso = max(0, (ahora - fecha_venta).days)
            
            total_venta = float(venta['total'])
            tasa_venta = float(venta['tasa']) if venta['tasa'] else 55.0
            total_pagado = float(venta.get('total_pagado', 0))
            
            total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
            total_actualizado = total_usd * tasa_actual
            saldo_pendiente = total_actualizado - total_pagado
            
            # Asegurar que saldo_pendiente no sea negativo
            if saldo_pendiente < 0:
                saldo_pendiente = 0
            
            cursor2 = conn.cursor(cursor_factory=RealDictCursor)
            cursor2.execute("""
                SELECT p.descripcion, dv.cantidad 
                FROM detalles_venta dv 
                JOIN productos p ON dv.id_producto = p.id 
                WHERE dv.id_venta = %s
            """, (venta['id'],))
            productos = cursor2.fetchall()
            cursor2.close()
            
            if productos:
                descripcion_productos = ", ".join([f"{p['descripcion']} x{p['cantidad']}" for p in productos])
            else:
                descripcion_productos = "Producto"
            
            # Calcular porcentaje pagado para el progress bar
            if total_actualizado > 0:
                porcentaje_pagado = (total_pagado / total_actualizado) * 100
                porcentaje_pagado = max(0, min(100, porcentaje_pagado))
            else:
                porcentaje_pagado = 0
            
            ventas_credito.append({
                'id_venta': venta['id'],
                'id_cliente': venta['id_cliente'],
                'cliente_nombre': venta['nombre'],
                'cliente_telefono': venta['telefono'],
                'total_venta': round(total_venta, 2),
                'tasa_venta': round(tasa_venta, 2),
                'total_usd': round(total_usd, 2),
                'tasa_actual': round(tasa_actual, 2),
                'total_actualizado': round(total_actualizado, 2),
                'total_pagado': round(total_pagado, 2),
                'saldo_pendiente': round(saldo_pendiente, 2),
                'porcentaje_pagado': round(porcentaje_pagado, 2),
                'fecha_venta': venta['fecha_venta'].isoformat() if hasattr(venta['fecha_venta'], 'isoformat') else str(venta['fecha_venta']),
                'horas_transcurridas': round(horas_transcurridas, 1),
                'dias_retraso': dias_retraso,
                'productos': descripcion_productos,
                'productos_lista': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos]
            })
        
        conn.close()
        return ventas_credito
        
    except Exception as e:
        print(f"Error en ventas_con_retraso: {e}")
        return []


def cancelar_creditos_global(cliente_id, tasa_actual=None):
    """Cancela TODAS las deudas de un cliente de una sola vez"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener información del cliente
        cursor.execute("SELECT nombre, telefono FROM clientes WHERE id = %s", (cliente_id,))
        cliente_info = cursor.fetchone()
        if not cliente_info:
            conn.close()
            return {"success": False, "error": "Cliente no encontrado"}
        
        cliente_nombre, cliente_telefono = cliente_info
        
        # Obtener todas las deudas del cliente
        cursor.execute("""
            SELECT v.id, v.total, v.tasa, v.saldo_pendiente,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as pagado_anterior,
                   v.credito, v.pagado, v.cancelada
            FROM ventas v
            WHERE v.id_cliente = %s 
            AND v.credito = TRUE 
            AND v.pagado = FALSE 
            AND v.cancelada = FALSE
        """, (cliente_id,))
        
        deudas = cursor.fetchall()
        
        if not deudas:
            conn.close()
            return {"success": False, "error": "No hay deudas pendientes para este cliente"}
        
        if tasa_actual is None:
            tasas = exchange.get_all_rates(force_update=False)
            tasa_actual = tasas.get("bcv_usd", 55.0)
        
        total_cancelado = 0
        deudas_canceladas = []
        ahora = datetime.now()
        
        for deuda in deudas:
            id_venta, total_venta, tasa_venta, saldo_db, pagado_anterior, credito, pagado, cancelada = deuda
            total_venta = float(total_venta)
            tasa_venta = float(tasa_venta) if tasa_venta else 55.0
            pagado_anterior = float(pagado_anterior) if pagado_anterior else 0
            
            # Calcular el monto a cancelar
            total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
            total_actualizado = total_usd * tasa_actual
            monto_cancelar = total_actualizado - pagado_anterior
            
            if monto_cancelar <= 0:
                continue
            
            # Obtener productos de la venta para el recibo
            cursor_prod = conn.cursor()
            cursor_prod.execute("""
                SELECT p.descripcion, dv.cantidad
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = %s
            """, (id_venta,))
            productos_venta = cursor_prod.fetchall()
            cursor_prod.close()
            
            # Registrar pago global
            cursor.execute("""
                INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion, fecha_pago)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_venta, monto_cancelar, tasa_actual, 
                  f"CANCELACIÓN GLOBAL - {ahora.strftime('%Y-%m-%d %H:%M:%S')}", 
                  ahora))
            
            # Actualizar venta como pagada
            cursor.execute("""
                UPDATE ventas
                SET pagado = TRUE, 
                    saldo_pendiente = 0, 
                    fecha_pago = %s, 
                    pagado_parcial = FALSE
                WHERE id = %s
            """, (ahora, id_venta))
            
            total_cancelado += monto_cancelar
            deudas_canceladas.append({
                'id_venta': id_venta, 
                'monto': monto_cancelar,
                'total_original': total_venta,
                'productos': [{'descripcion': p[0], 'cantidad': p[1]} for p in productos_venta],
                'fecha_venta': fecha_venta
            })
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "total_cancelado": total_cancelado,
            "deudas_canceladas": deudas_canceladas,
            "tasa_aplicada": tasa_actual,
            "cliente_nombre": cliente_nombre,
            "cliente_telefono": cliente_telefono,
            "cantidad_deudas": len(deudas_canceladas)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== REPORTES ==========

def reporte_ventas(periodo="semanal"):
    """Genera reporte de ventas por período"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if periodo == "semanal":
            cursor.execute("""
                SELECT 
                    TO_CHAR(MIN(fecha_venta), 'DD/MM/YYYY') || ' - ' || TO_CHAR(MAX(fecha_venta), 'DD/MM/YYYY') as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(total), 0) as total_bs,
                    COALESCE(SUM(CASE WHEN credito = FALSE THEN total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN credito = TRUE THEN total ELSE 0 END), 0) as total_credito
                FROM ventas 
                WHERE cancelada = FALSE
                GROUP BY EXTRACT(YEAR FROM fecha_venta), EXTRACT(WEEK FROM fecha_venta)
                ORDER BY MIN(fecha_venta) DESC
                LIMIT 10
            """)
        elif periodo == "mensual":
            cursor.execute("""
                SELECT 
                    TO_CHAR(fecha_venta, 'MM/YYYY') as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(total), 0) as total_bs,
                    COALESCE(SUM(CASE WHEN credito = FALSE THEN total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN credito = TRUE THEN total ELSE 0 END), 0) as total_credito
                FROM ventas 
                WHERE cancelada = FALSE
                GROUP BY TO_CHAR(fecha_venta, 'YYYY-MM'), TO_CHAR(fecha_venta, 'MM/YYYY')
                ORDER BY MIN(fecha_venta) DESC
                LIMIT 12
            """)
        elif periodo == "productos":
            cursor.execute("""
                SELECT 
                    p.descripcion as producto,
                    SUM(dv.cantidad) as unidades_vendidas,
                    COALESCE(SUM(dv.subtotal), 0) as total_bs
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                JOIN ventas v ON dv.id_venta = v.id
                WHERE v.cancelada = FALSE
                GROUP BY p.id, p.descripcion
                ORDER BY total_bs DESC
                LIMIT 20
            """)
        
        reportes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in reportes]
    except Exception as e:
        print(f"Error en reporte_ventas: {e}")
        return []


def reporte_produto():
    """Reporte de productos más vendidos"""
    return reporte_ventas("productos")


def reporte_por_rango(fecha_inicio, fecha_fin, tipo="dia", filtro_venta="todas"):
    """Genera reporte por rango de fechas"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        filtro_sql = ""
        params = [fecha_inicio, fecha_fin]
        
        if filtro_venta == "contado":
            filtro_sql = "AND v.credito = FALSE"
        elif filtro_venta == "credito_pendiente":
            filtro_sql = "AND v.credito = TRUE AND v.pagado = FALSE"
        elif filtro_venta == "credito_pagado":
            filtro_sql = "AND v.credito = TRUE AND v.pagado = TRUE"
        
        if tipo == "dia":
            cursor.execute(f"""
                SELECT 
                    DATE(v.fecha_venta) as fecha,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN v.credito = FALSE THEN v.total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = FALSE THEN v.total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = TRUE THEN v.total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(v.total), 0) as total_bs
                FROM ventas v
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY DATE(v.fecha_venta)
                ORDER BY fecha ASC
            """, params)
            
        elif tipo == "productos":
            cursor.execute(f"""
                SELECT 
                    p.descripcion as producto,
                    CAST(SUM(dv.cantidad) AS INTEGER) as unidades_vendidas,
                    COALESCE(SUM(CASE WHEN v.credito = FALSE THEN dv.subtotal ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = FALSE THEN dv.subtotal ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = TRUE THEN dv.subtotal ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(dv.subtotal), 0) as total_bs
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                JOIN ventas v ON dv.id_venta = v.id
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY p.id, p.descripcion
                ORDER BY unidades_vendidas DESC
            """, params)
            
        else:
            cursor.execute(f"""
                SELECT 
                    DATE_TRUNC('day', v.fecha_venta) as fecha,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(v.total), 0) as total_bs
                FROM ventas v
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY DATE_TRUNC('day', v.fecha_venta)
                ORDER BY fecha ASC
            """, params)
        
        resultados = cursor.fetchall()
        conn.close()
        
        if not resultados:
            return {
                'success': True,
                'data': [],
                'totales': {'contado': 0, 'credito_pendiente': 0, 'credito_cancelado': 0, 'general': 0}
            }
        
        data = []
        t_contado, t_pendiente, t_cancelado, t_general = 0, 0, 0, 0
        
        for row in resultados:
            if tipo == "productos":
                item = {
                    'producto': row['producto'],
                    'unidades_vendidas': int(row['unidades_vendidas']),
                    'total_contado': float(row['total_contado']),
                    'total_credito_pendiente': float(row['total_credito_pendiente']),
                    'total_credito_cancelado': float(row['total_credito_cancelado']),
                    'total_bs': float(row['total_bs'])
                }
            else:
                if tipo == "dia" and 'fecha' in row:
                    periodo = row['fecha'].strftime('%d/%m/%Y') if hasattr(row['fecha'], 'strftime') else str(row['fecha'])
                else:
                    periodo = row['fecha'].strftime('%d/%m/%Y') if hasattr(row['fecha'], 'strftime') else str(row['fecha'])
                
                item = {
                    'periodo': periodo,
                    'ventas': row['total_ventas'],
                    'contado': float(row.get('total_contado', 0)) if 'total_contado' in row else 0,
                    'credito_pendiente': float(row.get('total_credito_pendiente', 0)) if 'total_credito_pendiente' in row else 0,
                    'credito_cancelado': float(row.get('total_credito_cancelado', 0)) if 'total_credito_cancelado' in row else 0,
                    'total': float(row.get('total_bs', 0))
                }
            
            data.append(item)
            t_contado += float(row.get('total_contado', 0))
            t_pendiente += float(row.get('total_credito_pendiente', 0))
            t_cancelado += float(row.get('total_credito_cancelado', 0))
            t_general += float(row.get('total_bs', 0))
        
        return {
            'success': True,
            'data': data,
            'totales': {
                'contado': t_contado,
                'credito_pendiente': t_pendiente,
                'credito_cancelado': t_cancelado,
                'general': t_general
            }
        }
        
    except Exception as e:
        print(f"Error en reporte_por_rango: {e}")
        return {'success': False, 'error': str(e), 'data': []}


# ========== FUNCIONES ADICIONALES ==========

def obtener_historial_pagos(id_venta):
    """Obtiene el historial de pagos de un crédito"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM pagos_credito WHERE id_venta = %s ORDER BY fecha_pago DESC", (id_venta,))
        pagos = cursor.fetchall()
        conn.close()
        return [dict(row) for row in pagos]
    except Exception as e:
        print(f"Error en obtener_historial_pagos: {e}")
        return []


def obtener_tasa_actual():
    """Obtiene la tasa de cambio actual"""
    try:
        tasas = exchange.get_all_rates(force_update=False)
        return {"bcv_usd": tasas.get("bcv_usd", 55.0), "bcv_eur": tasas.get("bcv_eur", 57.75), "fecha": datetime.now().isoformat()}
    except Exception as e:
        print(f"Error en obtener_tasa_actual: {e}")
        return {"bcv_usd": 55.0, "bcv_eur": 57.75, "fecha": datetime.now().isoformat()}


def generar_nota_debito(id_venta):
    """Genera nota de débito para un crédito"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono, c.id as cliente_id,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v 
            JOIN clientes c ON v.id_cliente = c.id 
            WHERE v.id = %s
        """, (id_venta,))
        venta = cursor.fetchone()
        if not venta:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario, dv.subtotal 
            FROM detalles_venta dv 
            JOIN productos p ON dv.id_producto = p.id 
            WHERE dv.id_venta = %s
        """, (id_venta,))
        productos = cursor.fetchall()
        conn.close()
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 55.0)
        total_venta = float(venta['total'])
        tasa_venta = float(venta['tasa']) if venta['tasa'] else 55.0
        total_pagado = float(venta.get('total_pagado', 0))
        
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_actual
        saldo_pendiente = max(0, total_actualizado - total_pagado)
        
        return {"success": True, "nota_debito": {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cliente": venta['nombre'],
            "cliente_id": venta['cliente_id'],
            "telefono": venta['telefono'],
            "venta_id": id_venta,
            "fecha_venta_original": venta['fecha_venta'].isoformat() if hasattr(venta['fecha_venta'], 'isoformat') else str(venta['fecha_venta']),
            "productos": [{"descripcion": p['descripcion'], "cantidad": p['cantidad'], "precio": p['precio_unitario'], "subtotal": p['subtotal']} for p in productos],
            "total_original_bs": total_venta,
            "tasa_original": tasa_venta,
            "total_usd": total_usd,
            "tasa_actual": tasa_actual,
            "total_actualizado_bs": total_actualizado,
            "total_pagado": total_pagado,
            "saldo_pendiente_bs": saldo_pendiente,
            "mensaje": f"Nota de Débito por saldo pendiente de Bs {saldo_pendiente:,.2f}"
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtener_estado_credito(id_venta):
    """Obtiene el estado detallado de un crédito"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v 
            JOIN clientes c ON v.id_cliente = c.id 
            WHERE v.id = %s
        """, (id_venta,))
        credito = cursor.fetchone()
        if not credito:
            conn.close()
            return None
        
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario, dv.subtotal 
            FROM detalles_venta dv 
            JOIN productos p ON dv.id_producto = p.id 
            WHERE dv.id_venta = %s
        """, (id_venta,))
        productos = cursor.fetchall()
        conn.close()
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 55.0)
        total_venta = float(credito['total'])
        tasa_venta = float(credito['tasa']) if credito['tasa'] else 55.0
        total_pagado = float(credito.get('total_pagado', 0))
        
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_actual
        
        credito_dict = dict(credito)
        credito_dict['productos'] = [dict(p) for p in productos]
        credito_dict['tasa_actual'] = tasa_actual
        credito_dict['total_actualizado'] = total_actualizado
        credito_dict['total_usd'] = total_usd
        credito_dict['saldo_pendiente'] = max(0, total_actualizado - total_pagado)
        
        return credito_dict
    except Exception as e:
        print(f"Error en obtener_estado_credito: {e}")
        return None


def registrar_venta_simple(id_cliente, id_producto, cantidad, es_credito=False):
    """Registra una venta simple de un solo producto"""
    productos = [{"id_producto": id_producto, "cantidad": cantidad}]
    return registrar_venta(id_cliente, productos, es_credito)


# ========== FUNCIÓN PARA CALCULAR DEUDA DE CLIENTE ==========

def calcular_deuda_cliente(cliente_id):
    """Calcula la deuda total actualizada de un cliente"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener todas las deudas del cliente
        cursor.execute("""
            SELECT v.id, v.total, v.tasa, v.saldo_pendiente,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as pagado_anterior
            FROM ventas v
            WHERE v.id_cliente = %s 
            AND v.credito = TRUE 
            AND v.pagado = FALSE 
            AND v.cancelada = FALSE
        """, (cliente_id,))
        
        deudas = cursor.fetchall()
        
        if not deudas:
            conn.close()
            return 0
        
        # Obtener tasa actual
        tasas = exchange.get_all_rates(force_update=False)
        tasa_actual = tasas.get("bcv_usd", 55.0)
        
        deuda_total = 0
        
        for deuda in deudas:
            id_venta, total_venta, tasa_venta, saldo_db, pagado_anterior = deuda
            total_venta = float(total_venta)
            tasa_venta = float(tasa_venta) if tasa_venta else 55.0
            pagado_anterior = float(pagado_anterior) if pagado_anterior else 0
            
            # Calcular deuda actualizada
            total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
            total_actualizado = total_usd * tasa_actual
            deuda_actual = total_actualizado - pagado_anterior
            
            if deuda_actual > 0:
                deuda_total += deuda_actual
        
        conn.close()
        return deuda_total
        
    except Exception as e:
        print(f"Error calculando deuda del cliente: {e}")
        return 0
