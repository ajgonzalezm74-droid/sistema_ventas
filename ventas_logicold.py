import sqlite3
from datetime import datetime
from database import DB_NAME
from exchange_provider import ExchangeProvider

exchange = ExchangeProvider()


def verificar_stock_multiples(productos):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            cursor.execute("SELECT cantidad FROM inventario WHERE id_producto = ?", (id_producto,))
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
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            if es_venta:
                cursor.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE id_producto = ?", (cantidad, id_producto))
            else:
                cursor.execute("UPDATE inventario SET cantidad = cantidad + ?, devolucion = devolucion + ? WHERE id_producto = ?", (cantidad, cantidad, id_producto))
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
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        total_venta = 0
        detalles = []
        
        for item in productos:
            id_producto = item['id_producto']
            cantidad = item['cantidad']
            cursor.execute("SELECT p.descripcion, i.costo FROM productos p JOIN inventario i ON p.id = i.id_producto WHERE p.id = ?", (id_producto,))
            producto = cursor.fetchone()
            if not producto:
                conn.close()
                return {"success": False, "error": f"Producto ID {id_producto} no encontrado"}
            
            descripcion, costo_dolar = producto
            precio_unitario_bs = costo_dolar * tasa_bs
            subtotal = precio_unitario_bs * cantidad
            total_venta += subtotal
            
            detalles.append({'id_producto': id_producto, 'cantidad': cantidad, 'descripcion': descripcion,
                           'precio_unitario': precio_unitario_bs, 'subtotal': subtotal, 'costo_dolar': costo_dolar})
        
        pagado = 1 if not es_credito else 0
        credito = 1 if es_credito else 0
        
        # Usar fecha manual o fecha actual
        if fecha_manual:
            fecha_venta = fecha_manual
        else:
            fecha_venta = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("INSERT INTO ventas (id_cliente, total, tasa, credito, pagado, fecha_venta) VALUES (?, ?, ?, ?, ?, ?)", 
                      (id_cliente, total_venta, tasa_bs, credito, pagado, fecha_venta))
        id_venta = cursor.lastrowid
        
        for detalle in detalles:
            cursor.execute("INSERT INTO detalles_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?, ?)",
                          (id_venta, detalle['id_producto'], detalle['cantidad'], detalle['precio_unitario'], detalle['subtotal']))
        
        conn.commit()
        productos_para_inventario = [{'id_producto': d['id_producto'], 'cantidad': d['cantidad']} for d in detalles]
        actualizar_inventario_multiples(productos_para_inventario, es_venta=True)
        conn.close()
        
        resumen_productos = [f"{d['descripcion']} x{d['cantidad']}" for d in detalles]
        return {"success": True, "id_venta": id_venta, "total_bs": total_venta, "tasa_usada": tasa_bs,
                "tipo": "crédito" if es_credito else "contado", "productos": resumen_productos, "detalles": detalles}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pagar_credito(id_venta):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT total, tasa, pagado FROM ventas WHERE id = ?", (id_venta,))
        resultado = cursor.fetchone()
        if not resultado:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        total_venta, tasa_venta, pagado = resultado
        if pagado == 1:
            conn.close()
            return {"success": False, "error": "Esta venta ya está pagada"}
        
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        tasas = exchange.get_all_rates(force_update=True)
        tasa_hoy = tasas.get("bcv_usd", 0)
        
        if tasa_hoy == 0:
            conn.close()
            return {"success": False, "error": "No se pudo obtener tasa actual"}
        
        total_pagar = total_usd * tasa_hoy
        
        cursor.execute("INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion) VALUES (?, ?, ?, ?)",
                      (id_venta, total_pagar, tasa_hoy, "Pago completo"))
        cursor.execute("UPDATE ventas SET pagado = 1, pagado_parcial = 0, saldo_pendiente = 0, fecha_pago = CURRENT_TIMESTAMP, tasa_pago = ? WHERE id = ?",
                      (tasa_hoy, id_venta))
        conn.commit()
        conn.close()
        
        return {"success": True, "total_pagado_bs": total_pagar, "tasa_venta": tasa_venta, "tasa_pago": tasa_hoy,
                "diferencia_tasa": total_pagar - total_venta, "mensaje": f"Pago completado. Total: Bs {total_pagar:,.2f}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pagar_credito_parcial(id_venta, monto_pagado, observacion=""):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.total, v.tasa, v.pagado, v.saldo_pendiente,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado_anterior
            FROM ventas v WHERE v.id = ? AND v.credito = 1
        """, (id_venta,))
        
        venta = cursor.fetchone()
        if not venta:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        total_venta, tasa_venta, pagado_completo, saldo_db, total_pagado_anterior = venta
        if pagado_completo == 1:
            conn.close()
            return {"success": False, "error": "Esta venta ya está pagada completamente"}
        
        tasas = exchange.get_all_rates(force_update=True)
        tasa_hoy = tasas.get("bcv_usd", 0)
        if tasa_hoy == 0:
            conn.close()
            return {"success": False, "error": "No se pudo obtener tasa actual"}
        
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_hoy
        deuda_actual = total_actualizado - total_pagado_anterior
        
        if monto_pagado > deuda_actual:
            conn.close()
            return {"success": False, "error": f"El pago excede la deuda actual (Bs {deuda_actual:.2f})"}
        
        cursor.execute("INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion) VALUES (?, ?, ?, ?)",
                      (id_venta, monto_pagado, tasa_hoy, observacion))
        
        nuevo_total_pagado = total_pagado_anterior + monto_pagado
        nuevo_saldo = deuda_actual - monto_pagado
        
        if nuevo_saldo <= 0.01:
            cursor.execute("UPDATE ventas SET pagado = 1, pagado_parcial = 0, saldo_pendiente = 0, fecha_pago = CURRENT_TIMESTAMP, tasa_pago = ? WHERE id = ?",
                          (tasa_hoy, id_venta))
            estado = "COMPLETADO"
            mensaje = f"Pago completado. Total pagado: Bs {nuevo_total_pagado:,.2f}"
        else:
            cursor.execute("UPDATE ventas SET saldo_pendiente = ?, pagado_parcial = 1, pagado = 0 WHERE id = ?",
                          (nuevo_saldo, id_venta))
            estado = "PARCIAL"
            mensaje = f"Pago parcial registrado. Saldo pendiente: Bs {nuevo_saldo:,.2f}"
        
        conn.commit()
        conn.close()
        return {"success": True, "estado": estado, "monto_pagado": monto_pagado,
                "total_pagado_acumulado": nuevo_total_pagado, "saldo_pendiente": max(0, nuevo_saldo),
                "tasa_aplicada": tasa_hoy, "mensaje": mensaje}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancelar_venta(id_venta):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id_producto, cantidad FROM detalles_venta WHERE id_venta = ?", (id_venta,))
        productos = cursor.fetchall()
        if not productos:
            conn.close()
            return {"error": "Venta no encontrada"}
        cursor.execute("UPDATE ventas SET cancelada = 1 WHERE id = ?", (id_venta,))
        for id_producto, cantidad in productos:
            cursor.execute("UPDATE inventario SET cantidad = cantidad + ?, devolucion = devolucion + ? WHERE id_producto = ?", (cantidad, cantidad, id_producto))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def ventas_con_retraso():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v 
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.credito = 1 AND v.pagado = 0 AND v.cancelada = 0
        """)
        
        ventas_credito = []
        ahora = datetime.now()
        
        # Obtener tasa actual
        tasas = exchange.get_all_rates(force_update=False)
        tasa_actual = tasas.get("bcv_usd", 55.0)
        
        for row in cursor.fetchall():
            venta = dict(row)
            
            try:
                fecha_venta = datetime.strptime(venta['fecha_venta'], '%Y-%m-%d %H:%M:%S')
            except:
                fecha_venta = ahora
            
            horas_transcurridas = (ahora - fecha_venta).total_seconds() / 3600
            dias_retraso = max(0, (ahora - fecha_venta).days)
            
            total_usd = venta['total'] / venta['tasa'] if venta['tasa'] > 0 else 0
            total_actualizado = total_usd * tasa_actual
            total_pagado = venta.get('total_pagado', 0)
            saldo_pendiente = total_actualizado - total_pagado
            
            # Obtener productos
            cursor2 = conn.cursor()
            cursor2.execute("""
                SELECT p.descripcion, dv.cantidad 
                FROM detalles_venta dv 
                JOIN productos p ON dv.id_producto = p.id 
                WHERE dv.id_venta = ?
            """, (venta['id'],))
            productos = cursor2.fetchall()
            cursor2.close()
            
            if productos:
                descripcion_productos = ", ".join([f"{p[0]} x{p[1]}" for p in productos])
            else:
                descripcion_productos = "Producto"
            
            # Estado
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
                'fecha_venta': venta['fecha_venta'],
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
    """Genera reporte de ventas semanal, mensual o por productos"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if periodo == "semanal":
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN MIN(fecha_venta) IS NOT NULL THEN 
                            strftime('%d/%m/%Y', MIN(fecha_venta)) || ' - ' || strftime('%d/%m/%Y', MAX(fecha_venta))
                        ELSE 'Fecha no disponible'
                    END as periodo,
                    COUNT(*) as total_ventas,
                    SUM(total) as total_bs
                FROM ventas 
                WHERE cancelada = 0
                GROUP BY strftime('%Y-%W', fecha_venta)
                ORDER BY MIN(fecha_venta) DESC
            ''')
            
        elif periodo == "mensual":
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN fecha_venta IS NOT NULL THEN strftime('%m/%Y', fecha_venta)
                        ELSE 'Fecha no registrada'
                    END as periodo,
                    COUNT(*) as total_ventas,
                    SUM(total) as total_bs
                FROM ventas 
                WHERE cancelada = 0
                GROUP BY 
                    CASE 
                        WHEN fecha_venta IS NOT NULL THEN strftime('%Y-%m', fecha_venta)
                        ELSE 'sin_fecha'
                    END
                ORDER BY MIN(fecha_venta) DESC
            ''')
            
        elif periodo == "productos":
            cursor.execute('''
                SELECT 
                    p.descripcion as producto,
                    SUM(dv.cantidad) as unidades_vendidas,
                    SUM(dv.subtotal) as total_bs
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                JOIN ventas v ON dv.id_venta = v.id
                WHERE v.cancelada = 0
                GROUP BY dv.id_producto
                ORDER BY total_bs DESC
            ''')
        
        reportes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return reportes
    except Exception as e:
        print(f"❌ Error en reporte_ventas: {e}")
        return []


def reporte_produto():
    return reporte_ventas("productos")


def obtener_historial_pagos(id_venta):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pagos_credito WHERE id_venta = ? ORDER BY fecha_pago DESC", (id_venta,))
        pagos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return pagos
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
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono, c.id as cliente_id,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v JOIN clientes c ON v.id_cliente = c.id WHERE v.id = ?
        """, (id_venta,))
        venta = cursor.fetchone()
        if not venta:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        cursor.execute("SELECT p.descripcion, dv.cantidad, dv.precio_unitario, dv.subtotal FROM detalles_venta dv JOIN productos p ON dv.id_producto = p.id WHERE dv.id_venta = ?", (id_venta,))
        productos = cursor.fetchall()
        conn.close()
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 0)
        total_usd = venta[3] / venta[5] if venta[5] > 0 else 0
        total_actualizado = total_usd * tasa_actual
        saldo_pendiente = total_actualizado - venta[13]
        
        return {"success": True, "nota_debito": {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "cliente": venta[14],
            "cliente_id": venta[16], "telefono": venta[15], "venta_id": id_venta,
            "fecha_venta_original": venta[2], "productos": [{"descripcion": p[0], "cantidad": p[1], "precio": p[2], "subtotal": p[3]} for p in productos],
            "total_original_bs": venta[3], "tasa_original": venta[5], "total_usd": total_usd,
            "tasa_actual": tasa_actual, "total_actualizado_bs": total_actualizado,
            "total_pagado": venta[13], "saldo_pendiente_bs": max(0, saldo_pendiente),
            "mensaje": f"Nota de Débito por saldo pendiente de Bs {max(0, saldo_pendiente):,.2f}"
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtener_estado_credito(id_venta):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v JOIN clientes c ON v.id_cliente = c.id WHERE v.id = ?
        """, (id_venta,))
        credito = cursor.fetchone()
        if not credito:
            conn.close()
            return None
        credito = dict(credito)
        cursor.execute("SELECT p.descripcion, dv.cantidad, dv.precio_unitario, dv.subtotal FROM detalles_venta dv JOIN productos p ON dv.id_producto = p.id WHERE dv.id_venta = ?", (id_venta,))
        productos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 0)
        total_usd = credito['total'] / credito['tasa'] if credito['tasa'] > 0 else 0
        total_actualizado = total_usd * tasa_actual
        total_pagado = credito.get('total_pagado', 0)
        
        credito['productos'] = productos
        credito['tasa_actual'] = tasa_actual
        credito['total_actualizado'] = total_actualizado
        credito['total_usd'] = total_usd
        credito['saldo_pendiente'] = max(0, total_actualizado - total_pagado)
        return credito
    except Exception as e:
        return None


def registrar_venta_simple(id_cliente, id_producto, cantidad, es_credito=False):
    productos = [{"id_producto": id_producto, "cantidad": cantidad}]
    return registrar_venta(id_cliente, productos, es_credito)


def reporte_por_rango(fecha_inicio, fecha_fin, tipo="dia", filtro_venta="todas"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        filtro_sql = ""
        if filtro_venta == "contado":
            filtro_sql = "AND pagado = 1 AND credito = 0"
        elif filtro_venta == "credito_pendiente":
            filtro_sql = "AND credito = 1 AND pagado = 0"
        elif filtro_venta == "credito_pagado":
            filtro_sql = "AND credito = 1 AND pagado = 1"
        
        if tipo == "dia":
            cursor.execute(f"""
                SELECT 
                    strftime('%d/%m/%Y', fecha_venta) as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN (pagado = 1 AND credito = 0) OR (credito = 1 AND pagado = 1 AND date(fecha_pago) = date(fecha_venta)) THEN total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN credito = 1 AND pagado = 0 THEN total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN credito = 1 AND pagado = 1 AND date(fecha_pago) > date(fecha_venta) THEN total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(total), 0) as total_bs
                FROM ventas 
                WHERE cancelada = 0 AND date(fecha_venta) BETWEEN ? AND ? {filtro_sql}
                GROUP BY date(fecha_venta)
                ORDER BY fecha_venta ASC
            """, (fecha_inicio, fecha_fin))
            
        elif tipo == "semana":
            cursor.execute(f"""
                SELECT 
                    strftime('%d/%m/%Y', MIN(fecha_venta)) || ' - ' || strftime('%d/%m/%Y', MAX(fecha_venta)) as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN (pagado = 1 AND credito = 0) OR (credito = 1 AND pagado = 1 AND date(fecha_pago) = date(fecha_venta)) THEN total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN credito = 1 AND pagado = 0 THEN total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN credito = 1 AND pagado = 1 AND date(fecha_pago) > date(fecha_venta) THEN total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(total), 0) as total_bs
                FROM ventas 
                WHERE cancelada = 0 AND date(fecha_venta) BETWEEN ? AND ? {filtro_sql}
                GROUP BY strftime('%Y-%W', fecha_venta)
                ORDER BY MIN(fecha_venta) ASC
            """, (fecha_inicio, fecha_fin))
            
        elif tipo == "mes":
            cursor.execute(f"""
                SELECT 
                    strftime('%B %Y', fecha_venta) as periodo,
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(CASE WHEN (pagado = 1 AND credito = 0) OR (credito = 1 AND pagado = 1 AND date(fecha_pago) = date(fecha_venta)) THEN total ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN credito = 1 AND pagado = 0 THEN total ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN credito = 1 AND pagado = 1 AND date(fecha_pago) > date(fecha_venta) THEN total ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(total), 0) as total_bs
                FROM ventas 
                WHERE cancelada = 0 AND date(fecha_venta) BETWEEN ? AND ? {filtro_sql}
                GROUP BY strftime('%Y-%m', fecha_venta)
                ORDER BY MIN(fecha_venta) ASC
            """, (fecha_inicio, fecha_fin))
            
        elif tipo == "productos":
            cursor.execute(f"""
                SELECT 
                    p.descripcion as producto,
                    SUM(dv.cantidad) as unidades_vendidas,
                    COALESCE(SUM(CASE WHEN (v.pagado = 1 AND v.credito = 0) OR (v.credito = 1 AND v.pagado = 1 AND date(v.fecha_pago) = date(v.fecha_venta)) THEN dv.subtotal ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN v.credito = 1 AND v.pagado = 0 THEN dv.subtotal ELSE 0 END), 0) as total_credito_pendiente,
                    COALESCE(SUM(CASE WHEN v.credito = 1 AND v.pagado = 1 AND date(v.fecha_pago) > date(v.fecha_venta) THEN dv.subtotal ELSE 0 END), 0) as total_credito_cancelado,
                    COALESCE(SUM(dv.subtotal), 0) as total_bs
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                JOIN ventas v ON dv.id_venta = v.id
                WHERE v.cancelada = 0 AND date(v.fecha_venta) BETWEEN ? AND ? {filtro_sql}
                GROUP BY dv.id_producto
                ORDER BY unidades_vendidas DESC
            """, (fecha_inicio, fecha_fin))
        
        resultados = cursor.fetchall()
        conn.close()
        
        if not resultados:
            return {
                'success': True,
                'data': [],
                'totales': {'contado': 0, 'credito_pendiente': 0, 'credito_cancelado': 0, 'general': 0}
            }
        
        # Para productos, el formato es diferente
        if tipo == "productos":
            data = []
            for row in resultados:
                data.append({
                    'producto': row[0],
                    'unidades_vendidas': row[1],
                    'total_contado': row[2],
                    'total_credito_pendiente': row[3],
                    'total_credito_cancelado': row[4],
                    'total_bs': row[5]
                })
            
            return {
                'success': True,
                'data': data,
                'totales': {
                    'contado': sum(r['total_contado'] for r in data),
                    'credito_pendiente': sum(r['total_credito_pendiente'] for r in data),
                    'credito_cancelado': sum(r['total_credito_cancelado'] for r in data),
                    'general': sum(r['total_bs'] for r in data)
                }
            }
        
        # Para dia, semana, mes
        total_contado = sum(r[2] for r in resultados)
        total_credito_pendiente = sum(r[3] for r in resultados)
        total_credito_cancelado = sum(r[4] for r in resultados)
        total_general = sum(r[5] for r in resultados)
        
        return {
            'success': True,
            'data': [{'periodo': r[0], 'ventas': r[1], 'contado': r[2], 'credito_pendiente': r[3], 'credito_cancelado': r[4], 'total': r[5]} for r in resultados],
            'totales': {
                'contado': total_contado,
                'credito_pendiente': total_credito_pendiente,
                'credito_cancelado': total_credito_cancelado,
                'general': total_general
            }
        }
        
    except Exception as e:
        print(f"Error en reporte_por_rango: {e}")
        return {'success': False, 'error': str(e)}

# ========== NUEVAS FUNCIONES PARA CANCELACIÓN GLOBAL Y PAGO CON TASA ==========

def obtener_creditos_agrupados():
    """Obtiene todos los créditos pendientes agrupados por cliente"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.credito = 1 
            AND v.pagado = 0 
            AND v.cancelada = 0
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
            
            # Obtener productos de esta venta
            cursor.execute('''
                SELECT dv.*, p.descripcion
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = ?
            ''', (venta['id'],))
            productos = cursor.fetchall()
            
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


def cancelar_creditos_global(cliente_id, tasa_actual=None):
    """Cancela todas las deudas pendientes de un cliente de una sola vez"""
    try:
        if tasa_actual is None:
            tasas = exchange.get_all_rates(force_update=False)
            tasa_actual = tasas.get("bcv_usd", 0)
        
        if tasa_actual == 0:
            return {"success": False, "error": "No se pudo obtener tasa actual"}
        
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todas las deudas pendientes del cliente
        cursor.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.id_cliente = ? 
            AND v.credito = 1 
            AND v.pagado = 0 
            AND v.cancelada = 0
        ''', (cliente_id,))
        
        deudas = cursor.fetchall()
        
        if not deudas:
            conn.close()
            return {"success": False, "error": "No hay deudas pendientes para este cliente"}
        
        total_cancelado_bs = 0
        deudas_canceladas = []
        
        for deuda in deudas:
            total_usd = deuda['total'] / deuda['tasa'] if deuda['tasa'] > 0 else 0
            monto_cancelar = total_usd * tasa_actual
            
            # Insertar registro de pago
            cursor.execute('''
                INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion, fecha_pago)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                deuda['id'],
                monto_cancelar,
                tasa_actual,
                f'CANCELACIÓN GLOBAL - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                datetime.now()
            ))
            
            # Actualizar la venta como pagada
            cursor.execute('''
                UPDATE ventas 
                SET pagado = 1, 
                    saldo_pendiente = 0,
                    pagado_parcial = 0,
                    fecha_pago = ?
                WHERE id = ?
            ''', (datetime.now(), deuda['id']))
            
            total_cancelado_bs += monto_cancelar
            
            # Obtener productos para el recibo
            cursor.execute('''
                SELECT dv.*, p.descripcion
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = ?
            ''', (deuda['id'],))
            productos = cursor.fetchall()
            
            deudas_canceladas.append({
                'id_venta': deuda['id'],
                'fecha_venta': deuda['fecha_venta'],
                'total': float(deuda['total']),
                'tasa': float(deuda['tasa']) if deuda['tasa'] else 0,
                'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos]
            })
        
        conn.commit()
        
        datos_cliente = {
            'id': cliente_id,
            'nombre': deudas[0]['cliente_nombre'],
            'telefono': deudas[0]['telefono']
        }
        
        conn.close()
        
        return {
            "success": True,
            "cliente": datos_cliente,
            "deudas_canceladas": deudas_canceladas,
            "total_cancelado_bs": total_cancelado_bs,
            "tasa_aplicada": tasa_actual,
            "cantidad_creditos": len(deudas_canceladas)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def pagar_credito_con_tasa(id_venta, monto=0, observacion="", tasa_actual=None):
    """
    Paga un crédito individual con la tasa actual.
    Si monto = 0, paga el total actualizado.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.total, v.tasa, v.pagado, v.saldo_pendiente, v.credito,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado_anterior,
                   c.nombre as cliente_nombre, c.telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.id = ?
        """, (id_venta,))
        
        venta = cursor.fetchone()
        if not venta:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        total_venta, tasa_venta, pagado_completo, saldo_db, es_credito, total_pagado_anterior, cliente_nombre, cliente_telefono = venta
        
        if pagado_completo == 1:
            conn.close()
            return {"success": False, "error": "Esta venta ya está pagada completamente"}
        
        if es_credito == 0:
            conn.close()
            return {"success": False, "error": "Esta venta no es a crédito"}
        
        # Obtener tasa actual
        if tasa_actual is None:
            tasas = exchange.get_all_rates(force_update=False)
            tasa_actual = tasas.get("bcv_usd", 0)
        
        if tasa_actual == 0:
            conn.close()
            return {"success": False, "error": "No se pudo obtener tasa actual"}
        
        # Calcular valores
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_actual
        deuda_actual = total_actualizado - total_pagado_anterior
        
        # Determinar monto a pagar
        if monto <= 0:
            monto_pagar = deuda_actual
            es_pago_total = True
        else:
            monto_pagar = min(monto, deuda_actual)
            es_pago_total = abs(monto_pagar - deuda_actual) <= 0.01
        
        if monto_pagar <= 0:
            conn.close()
            return {"success": False, "error": "No hay deuda pendiente"}
        
        # Registrar pago
        cursor.execute("""
            INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion, fecha_pago)
            VALUES (?, ?, ?, ?, ?)
        """, (id_venta, monto_pagar, tasa_actual, observacion or ("Pago completo" if es_pago_total else "Pago parcial"), datetime.now()))
        
        nuevo_total_pagado = total_pagado_anterior + monto_pagar
        nuevo_saldo = deuda_actual - monto_pagar
        
        if nuevo_saldo <= 0.01:
            cursor.execute("""
                UPDATE ventas 
                SET pagado = 1, 
                    pagado_parcial = 0, 
                    saldo_pendiente = 0, 
                    fecha_pago = CURRENT_TIMESTAMP, 
                    tasa_pago = ?
                WHERE id = ?
            """, (tasa_actual, id_venta))
            estado = "COMPLETADO"
            mensaje = f"Pago completado. Total pagado: Bs {nuevo_total_pagado:,.2f}"
        else:
            cursor.execute("""
                UPDATE ventas 
                SET saldo_pendiente = ?, 
                    pagado_parcial = 1, 
                    pagado = 0
                WHERE id = ?
            """, (nuevo_saldo, id_venta))
            estado = "PARCIAL"
            mensaje = f"Pago parcial registrado. Saldo pendiente: Bs {nuevo_saldo:,.2f}"
        
        # Obtener productos para el recibo
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario
            FROM detalles_venta dv
            JOIN productos p ON dv.id_producto = p.id
            WHERE dv.id_venta = ?
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