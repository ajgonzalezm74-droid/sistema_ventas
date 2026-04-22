import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from database import get_connection
from exchange_provider import ExchangeProvider

exchange = ExchangeProvider()


def verificar_stock_multiples(productos):
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            if es_venta:
                cursor.execute("UPDATE inventario SET cantidad = cantidad - %s WHERE id_producto = %s", (cantidad, id_producto))
            else:
                cursor.execute("UPDATE inventario SET cantidad = cantidad + %s, devolucion = devolucion + %s WHERE id_producto = %s", (cantidad, cantidad, id_producto))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error actualizando inventario: {e}")
        return False


def registrar_venta(id_cliente, productos, es_credito=False, fecha_manual=None):
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
            precio_unitario_bs = costo_dolar * tasa_bs
            subtotal = precio_unitario_bs * cantidad
            total_venta += subtotal
            
            detalles.append({
                'id_producto': id_producto, 'cantidad': cantidad, 'descripcion': descripcion,
                'precio_unitario': precio_unitario_bs, 'subtotal': subtotal, 'costo_dolar': costo_dolar
            })
        
        pagado = True if not es_credito else False
        credito = True if es_credito else False
        
        if fecha_manual:
            fecha_venta = fecha_manual
        else:
            fecha_venta = datetime.now()
        
        cursor.execute("""
            INSERT INTO ventas (id_cliente, total, tasa, credito, pagado, fecha_venta, saldo_pendiente) 
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (id_cliente, total_venta, tasa_bs, credito, pagado, fecha_venta, total_venta if es_credito else 0))
        
        id_venta = cursor.fetchone()[0]
        
        for detalle in detalles:
            cursor.execute("""
                INSERT INTO detalles_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal) 
                VALUES (%s, %s, %s, %s, %s)
            """, (id_venta, detalle['id_producto'], detalle['cantidad'], detalle['precio_unitario'], detalle['subtotal']))
        
        conn.commit()
        productos_para_inventario = [{'id_producto': d['id_producto'], 'cantidad': d['cantidad']} for d in detalles]
        actualizar_inventario_multiples(productos_para_inventario, es_venta=True)
        conn.close()
        
        return {
            "success": True, "id_venta": id_venta, "total_bs": total_venta, "tasa_usada": tasa_bs,
            "tipo": "crédito" if es_credito else "contado", "detalles": detalles
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtener_creditos_agrupados():
    """Obtiene todos los créditos pendientes agrupados por cliente"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.credito = TRUE 
            AND v.pagado = FALSE 
            AND v.cancelada = FALSE
            ORDER BY c.nombre, v.fecha_venta
        ''')
        
        ventas = cursor.fetchall()
        
        clientes_creditos = {}
        for venta in ventas:
            cliente_id = venta['id_cliente']
            if cliente_id not in clientes_creditos:
                clientes_creditos[cliente_id] = {
                    'cliente_id': cliente_id,
                    'cliente_nombre': venta['cliente_nombre'],
                    'cliente_telefono': venta['cliente_telefono'],
                    'deudas': []
                }
            
            cursor2 = conn.cursor(cursor_factory=RealDictCursor)
            cursor2.execute('''
                SELECT dv.*, p.descripcion
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = %s
            ''', (venta['id'],))
            productos = cursor2.fetchall()
            cursor2.close()
            
            saldo_pendiente = venta['saldo_pendiente'] if venta['saldo_pendiente'] else venta['total']
            
            clientes_creditos[cliente_id]['deudas'].append({
                'id_venta': venta['id'],
                'fecha_venta': venta['fecha_venta'],
                'total': float(venta['total']),
                'tasa': float(venta['tasa']) if venta['tasa'] else 0,
                'saldo_pendiente': float(saldo_pendiente),
                'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos]
            })
        
        conn.close()
        return list(clientes_creditos.values())
    except Exception as e:
        print(f"Error en obtener_creditos_agrupados: {e}")
        return []


# El resto de funciones deben adaptarse de manera similar

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from database import get_connection
from exchange_provider import ExchangeProvider

exchange = ExchangeProvider()


def verificar_stock_multiples(productos):
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            if es_venta:
                cursor.execute("UPDATE inventario SET cantidad = cantidad - %s WHERE id_producto = %s", (cantidad, id_producto))
            else:
                cursor.execute("UPDATE inventario SET cantidad = cantidad + %s, devolucion = devolucion + %s WHERE id_producto = %s", (cantidad, cantidad, id_producto))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error actualizando inventario: {e}")
        return False


def registrar_venta(id_cliente, productos, es_credito=False, fecha_manual=None):
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
            precio_unitario_bs = costo_dolar * tasa_bs
            subtotal = precio_unitario_bs * cantidad
            total_venta += subtotal
            
            detalles.append({
                'id_producto': id_producto, 'cantidad': cantidad, 'descripcion': descripcion,
                'precio_unitario': precio_unitario_bs, 'subtotal': subtotal, 'costo_dolar': costo_dolar
            })
        
        pagado = True if not es_credito else False
        credito = True if es_credito else False
        
        if fecha_manual:
            fecha_venta = fecha_manual
        else:
            fecha_venta = datetime.now()
        
        cursor.execute("""
            INSERT INTO ventas (id_cliente, total, tasa, credito, pagado, fecha_venta, saldo_pendiente) 
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (id_cliente, total_venta, tasa_bs, credito, pagado, fecha_venta, total_venta if es_credito else 0))
        
        id_venta = cursor.fetchone()[0]
        
        for detalle in detalles:
            cursor.execute("""
                INSERT INTO detalles_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal) 
                VALUES (%s, %s, %s, %s, %s)
            """, (id_venta, detalle['id_producto'], detalle['cantidad'], detalle['precio_unitario'], detalle['subtotal']))
        
        conn.commit()
        productos_para_inventario = [{'id_producto': d['id_producto'], 'cantidad': d['cantidad']} for d in detalles]
        actualizar_inventario_multiples(productos_para_inventario, es_venta=True)
        conn.close()
        
        resumen_productos = [f"{d['descripcion']} x{d['cantidad']}" for d in detalles]
        return {
            "success": True, "id_venta": id_venta, "total_bs": total_venta, "tasa_usada": tasa_bs,
            "tipo": "crédito" if es_credito else "contado", "productos": resumen_productos, "detalles": detalles
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancelar_venta(id_venta):
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
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s, devolucion = devolucion + %s WHERE id_producto = %s", (cantidad, cantidad, id_producto))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtener_creditos_agrupados():
    """Obtiene todos los créditos pendientes agrupados por cliente"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.credito = TRUE 
            AND v.pagado = FALSE 
            AND v.cancelada = FALSE
            ORDER BY c.nombre, v.fecha_venta
        ''')
        
        ventas = cursor.fetchall()
        
        clientes_creditos = {}
        for venta in ventas:
            cliente_id = venta['id_cliente']
            if cliente_id not in clientes_creditos:
                clientes_creditos[cliente_id] = {
                    'cliente_id': cliente_id,
                    'cliente_nombre': venta['cliente_nombre'],
                    'cliente_telefono': venta['cliente_telefono'],
                    'deudas': []
                }
            
            cursor2 = conn.cursor(cursor_factory=RealDictCursor)
            cursor2.execute('''
                SELECT dv.*, p.descripcion
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = %s
            ''', (venta['id'],))
            productos = cursor2.fetchall()
            cursor2.close()
            
            saldo_pendiente = venta['saldo_pendiente'] if venta['saldo_pendiente'] else venta['total']
            
            clientes_creditos[cliente_id]['deudas'].append({
                'id_venta': venta['id'],
                'fecha_venta': venta['fecha_venta'],
                'total': float(venta['total']),
                'tasa': float(venta['tasa']) if venta['tasa'] else 0,
                'saldo_pendiente': float(saldo_pendiente),
                'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos]
            })
        
        conn.close()
        return list(clientes_creditos.values())
    except Exception as e:
        print(f"Error en obtener_creditos_agrupados: {e}")
        return []


def pagar_credito_con_tasa(id_venta, monto=0, observacion="", tasa_actual=None):
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
        
        if pagado_completo:
            conn.close()
            return {"success": False, "error": "Esta venta ya está pagada completamente"}
        
        if not es_credito:
            conn.close()
            return {"success": False, "error": "Esta venta no es a crédito"}
        
        if tasa_actual is None:
            tasas = exchange.get_all_rates(force_update=False)
            tasa_actual = tasas.get("bcv_usd", 0)
        
        if tasa_actual == 0:
            conn.close()
            return {"success": False, "error": "No se pudo obtener tasa actual"}
        
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_actual
        deuda_actual = total_actualizado - total_pagado_anterior
        
        if monto <= 0:
            monto_pagar = deuda_actual
            es_pago_total = True
        else:
            monto_pagar = min(monto, deuda_actual)
            es_pago_total = abs(monto_pagar - deuda_actual) <= 0.01
        
        if monto_pagar <= 0:
            conn.close()
            return {"success": False, "error": "No hay deuda pendiente"}
        
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


def ventas_con_retraso():
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
            
            total_usd = venta['total'] / venta['tasa'] if venta['tasa'] > 0 else 0
            total_actualizado = total_usd * tasa_actual
            total_pagado = venta.get('total_pagado', 0)
            saldo_pendiente = total_actualizado - total_pagado
            
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
            
            if saldo_pendiente <= 0.01:
                estado_texto = "✅ PAGADO"
                badge_class = "badge-success"
            elif total_pagado > 0:
                estado_texto = f"💰 PAGO PARCIAL (Pagado: Bs {total_pagado:,.2f})"
                badge_class = "badge-warning"
            elif horas_transcurridas < 24:
                estado_texto = "⏳ RECIÉN COMPRADO"
                badge_class = "badge-info"
            else:
                estado_texto = f"🔴 {dias_retraso} DÍA(S) DE RETRASO"
                badge_class = "badge-danger"
            
            ventas_credito.append({
                'id': venta['id'],
                'id_cliente': venta['id_cliente'],
                'nombre': venta['nombre'],
                'telefono': venta['telefono'],
                'total_original': round(venta['total'], 2),
                'tasa_venta': round(venta['tasa'], 2),
                'total_usd': round(total_usd, 2),
                'tasa_actual': round(tasa_actual, 2),
                'total_actualizado': round(total_actualizado, 2),
                'total_pagado': round(total_pagado, 2),
                'saldo_pendiente': round(max(0, saldo_pendiente), 2),
                'fecha_venta': venta['fecha_venta'].isoformat() if hasattr(venta['fecha_venta'], 'isoformat') else str(venta['fecha_venta']),
                'horas_transcurridas': round(horas_transcurridas, 1),
                'dias_retraso': dias_retraso,
                'productos': descripcion_productos,
                'estado_texto': estado_texto,
                'badge_class': badge_class
            })
        
        conn.close()
        return ventas_credito
        
    except Exception as e:
        print(f"Error en ventas_con_retraso: {e}")
        return []


def reporte_ventas(periodo="semanal"):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if periodo == "semanal":
            cursor.execute("""
                SELECT 
                    TO_CHAR(MIN(fecha_venta), 'DD/MM/YYYY') || ' - ' || TO_CHAR(MAX(fecha_venta), 'DD/MM/YYYY') as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(total), 0) as total_bs
                FROM ventas 
                WHERE cancelada = FALSE
                GROUP BY EXTRACT(YEAR FROM fecha_venta), EXTRACT(WEEK FROM fecha_venta)
                ORDER BY MIN(fecha_venta) DESC
            """)
        elif periodo == "mensual":
            cursor.execute("""
                SELECT 
                    TO_CHAR(fecha_venta, 'MM/YYYY') as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(total), 0) as total_bs
                FROM ventas 
                WHERE cancelada = FALSE
                GROUP BY TO_CHAR(fecha_venta, 'YYYY-MM')
                ORDER BY MIN(fecha_venta) DESC
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
                GROUP BY dv.id_producto
                ORDER BY total_bs DESC
            """)
        
        reportes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in reportes]
    except Exception as e:
        print(f"Error en reporte_ventas: {e}")
        return []


def reporte_produto():
    return reporte_ventas("productos")


def reporte_por_rango(fecha_inicio, fecha_fin, tipo="dia", filtro_venta="todas"):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        filtro_sql = ""
        if filtro_venta == "contado":
            filtro_sql = "AND pagado = TRUE AND credito = FALSE"
        elif filtro_venta == "credito_pendiente":
            filtro_sql = "AND credito = TRUE AND pagado = FALSE"
        elif filtro_venta == "credito_pagado":
            filtro_sql = "AND credito = TRUE AND pagado = TRUE"
        
        if tipo == "dia":
            cursor.execute(f"""
                SELECT 
                    DATE(v.fecha_venta) as fecha,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN v.pagado = TRUE AND v.credito = FALSE THEN v.total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = FALSE THEN v.total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = TRUE THEN v.total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(v.total), 0) as total_bs
                FROM ventas v
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY DATE(v.fecha_venta)
                ORDER BY fecha ASC
            """, (fecha_inicio, fecha_fin))
            
        elif tipo == "productos":
            cursor.execute(f"""
                SELECT 
                    p.descripcion as producto,
                    SUM(dv.cantidad) as unidades_vendidas,
                    COALESCE(SUM(CASE WHEN v.pagado = TRUE AND v.credito = FALSE THEN dv.subtotal ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = FALSE THEN dv.subtotal ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = TRUE THEN dv.subtotal ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(dv.subtotal), 0) as total_bs
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                JOIN ventas v ON dv.id_venta = v.id
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY dv.id_producto
                ORDER BY total_bs DESC
            """, (fecha_inicio, fecha_fin))
            
        elif tipo == "semana":
            cursor.execute(f"""
                SELECT 
                    DATE_TRUNC('week', v.fecha_venta) as semana,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN v.pagado = TRUE AND v.credito = FALSE THEN v.total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = FALSE THEN v.total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = TRUE THEN v.total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(v.total), 0) as total_bs
                FROM ventas v
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY DATE_TRUNC('week', v.fecha_venta)
                ORDER BY semana ASC
            """, (fecha_inicio, fecha_fin))
            
        elif tipo == "mes":
            cursor.execute(f"""
                SELECT 
                    DATE_TRUNC('month', v.fecha_venta) as mes,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN v.pagado = TRUE AND v.credito = FALSE THEN v.total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = FALSE THEN v.total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = TRUE AND v.pagado = TRUE THEN v.total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(v.total), 0) as total_bs
                FROM ventas v
                WHERE v.cancelada = FALSE AND DATE(v.fecha_venta) BETWEEN %s AND %s {filtro_sql}
                GROUP BY DATE_TRUNC('month', v.fecha_venta)
                ORDER BY mes ASC
            """, (fecha_inicio, fecha_fin))
        
        resultados = cursor.fetchall()
        conn.close()
        
        if not resultados:
            return {
                'success': True,
                'data': [],
                'totales': {'contado': 0, 'credito_pendiente': 0, 'credito_cancelado': 0, 'general': 0}
            }
        
        data = []
        total_contado = 0
        total_credito_pendiente = 0
        total_credito_cancelado = 0
        total_general = 0
        
        for row in resultados:
            if tipo == "productos":
                data.append({
                    'producto': row['producto'],
                    'unidades_vendidas': row['unidades_vendidas'],
                    'total_contado': float(row['total_contado']),
                    'total_credito_pendiente': float(row['total_credito_pendiente']),
                    'total_credito_cancelado': float(row['total_credito_cancelado']),
                    'total_bs': float(row['total_bs'])
                })
            else:
                if tipo == "dia":
                    periodo = row['fecha'].strftime('%d/%m/%Y')
                elif tipo == "semana":
                    periodo = row['semana'].strftime('%d/%m/%Y')
                elif tipo == "mes":
                    periodo = row['mes'].strftime('%B %Y')
                else:
                    periodo = str(row['fecha'])
                
                data.append({
                    'periodo': periodo,
                    'ventas': row['total_ventas'],
                    'contado': float(row['total_contado']),
                    'credito_pendiente': float(row['total_credito_pendiente']),
                    'credito_cancelado': float(row['total_credito_cancelado']),
                    'total': float(row['total_bs'])
                })
            
            total_contado += float(row['total_contado'])
            total_credito_pendiente += float(row['total_credito_pendiente'])
            total_credito_cancelado += float(row['total_credito_cancelado'])
            total_general += float(row['total_bs'])
        
        return {
            'success': True,
            'data': data,
            'totales': {
                'contado': total_contado,
                'credito_pendiente': total_credito_pendiente,
                'credito_cancelado': total_credito_cancelado,
                'general': total_general
            }
        }
        
    except Exception as e:
        print(f"Error en reporte_por_rango: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def obtener_historial_pagos(id_venta):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM pagos_credito WHERE id_venta = %s ORDER BY fecha_pago DESC", (id_venta,))
        pagos = cursor.fetchall()
        conn.close()
        return [dict(row) for row in pagos]
    except Exception as e:
        return []


def obtener_tasa_actual():
    try:
        tasas = exchange.get_all_rates(force_update=False)
        return {"bcv_usd": tasas.get("bcv_usd", 55.0), "bcv_eur": tasas.get("bcv_eur", 57.75), "fecha": datetime.now().isoformat()}
    except Exception as e:
        return {"bcv_usd": 55.0, "bcv_eur": 57.75, "fecha": datetime.now().isoformat()}


def generar_nota_debito(id_venta):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono, c.id as cliente_id,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v JOIN clientes c ON v.id_cliente = c.id WHERE v.id = %s
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
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 0)
        total_usd = venta['total'] / venta['tasa'] if venta['tasa'] > 0 else 0
        total_actualizado = total_usd * tasa_actual
        saldo_pendiente = total_actualizado - venta['total_pagado']
        
        return {"success": True, "nota_debito": {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cliente": venta['nombre'],
            "cliente_id": venta['cliente_id'],
            "telefono": venta['telefono'],
            "venta_id": id_venta,
            "fecha_venta_original": venta['fecha_venta'].isoformat() if hasattr(venta['fecha_venta'], 'isoformat') else str(venta['fecha_venta']),
            "productos": [{"descripcion": p['descripcion'], "cantidad": p['cantidad'], "precio": p['precio_unitario'], "subtotal": p['subtotal']} for p in productos],
            "total_original_bs": venta['total'],
            "tasa_original": venta['tasa'],
            "total_usd": total_usd,
            "tasa_actual": tasa_actual,
            "total_actualizado_bs": total_actualizado,
            "total_pagado": venta['total_pagado'],
            "saldo_pendiente_bs": max(0, saldo_pendiente),
            "mensaje": f"Nota de Débito por saldo pendiente de Bs {max(0, saldo_pendiente):,.2f}"
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtener_estado_credito(id_venta):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v JOIN clientes c ON v.id_cliente = c.id WHERE v.id = %s
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
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 0)
        total_usd = credito['total'] / credito['tasa'] if credito['tasa'] > 0 else 0
        total_actualizado = total_usd * tasa_actual
        total_pagado = credito.get('total_pagado', 0)
        
        credito_dict = dict(credito)
        credito_dict['productos'] = [dict(p) for p in productos]
        credito_dict['tasa_actual'] = tasa_actual
        credito_dict['total_actualizado'] = total_actualizado
        credito_dict['total_usd'] = total_usd
        credito_dict['saldo_pendiente'] = max(0, total_actualizado - total_pagado)
        
        return credito_dict
    except Exception as e:
        return None


def registrar_venta_simple(id_cliente, id_producto, cantidad, es_credito=False):
    productos = [{"id_producto": id_producto, "cantidad": cantidad}]
    return registrar_venta(id_cliente, productos, es_credito)


def pagar_credito(id_venta):
    return pagar_credito_con_tasa(id_venta, 0, "Pago completo", None)


def pagar_credito_parcial(id_venta, monto_pagado, observacion=""):
    return pagar_credito_con_tasa(id_venta, monto_pagado, observacion, None)


def cancelar_creditos_global(cliente_id, tasa_actual=None):
    return {"success": False, "error": "Función no implementada en esta versión"}