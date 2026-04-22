import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from database import get_connection  # Usar la conexión centralizada
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
        fecha_venta = fecha_manual if fecha_manual else datetime.now()
        
        # En PostgreSQL usamos RETURNING id para obtener el ID generado
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

def pagar_credito(id_venta):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT total, tasa, pagado FROM ventas WHERE id = %s", (id_venta,))
        resultado = cursor.fetchone()
        
        if not resultado:
            conn.close()
            return {"success": False, "error": "Venta no encontrada"}
        
        total_venta, tasa_venta, pagado = resultado
        if pagado:
            conn.close()
            return {"success": False, "error": "Esta venta ya está pagada"}
        
        total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
        tasas = exchange.get_all_rates(force_update=True)
        tasa_hoy = tasas.get("bcv_usd", 0)
        
        if tasa_hoy == 0:
            conn.close()
            return {"success": False, "error": "No se pudo obtener tasa actual"}
        
        total_pagar = total_usd * tasa_hoy
        
        cursor.execute("INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion) VALUES (%s, %s, %s, %s)",
                      (id_venta, total_pagar, tasa_hoy, "Pago completo"))
        
        cursor.execute("""
            UPDATE ventas 
            SET pagado = TRUE, pagado_parcial = FALSE, saldo_pendiente = 0, 
                fecha_pago = CURRENT_TIMESTAMP, tasa_pago = %s 
            WHERE id = %s
        """, (tasa_hoy, id_venta))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "total_pagado_bs": total_pagar, "tasa_pago": tasa_hoy}
    except Exception as e:
        return {"success": False, "error": str(e)}
