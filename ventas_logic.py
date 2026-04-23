from database import get_connection
from datetime import datetime
import requests

def obtener_tasa_actual():
    try:
        r = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=5)
        tasa = r.json().get('rates', {}).get('VES', 55.0)
        return {'bcv_usd': round(float(tasa), 2), 'bcv_eur': round(float(tasa)*1.05, 2)}
    except:
        return {'bcv_usd': 55.0, 'bcv_eur': 57.75}

def obtener_creditos_agrupados():
    """Obtiene todos los créditos pendientes agrupados por cliente - Versión corregida"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Primero, obtener las tasas actuales
        tasas = exchange.get_all_rates(force_update=False)
        tasa_actual = tasas.get("bcv_usd", 55.0)
        
        # Obtener todas las ventas a crédito no pagadas
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
            
            # Calcular el saldo REAL basado en pagos registrados
            cursor_pagos = conn.cursor(cursor_factory=RealDictCursor)
            cursor_pagos.execute('''
                SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                FROM pagos_credito
                WHERE id_venta = %s
            ''', (venta['id'],))
            resultado_pagos = cursor_pagos.fetchone()
            cursor_pagos.close()
            
            total_pagado = float(resultado_pagos['total_pagado']) if resultado_pagos else 0
            
            # Calcular el saldo REAL
            total_venta = float(venta['total'])
            tasa_venta = float(venta['tasa']) if venta['tasa'] else 55.0
            
            # Calcular el valor actualizado en USD
            total_usd = total_venta / tasa_venta if tasa_venta > 0 else 0
            total_actualizado = total_usd * tasa_actual
            
            # Saldo pendiente = valor actualizado - pagos realizados
            saldo_pendiente = total_actualizado - total_pagado
            
            # Solo mostrar si hay saldo pendiente
            if saldo_pendiente <= 0.01:
                continue
            
            if cliente_id not in clientes_creditos:
                clientes_creditos[cliente_id] = {
                    'cliente_id': cliente_id,
                    'cliente_nombre': venta['cliente_nombre'],
                    'cliente_telefono': venta['cliente_telefono'],
                    'deudas': []
                }
            
            # Obtener productos de la venta
            cursor_prod = conn.cursor(cursor_factory=RealDictCursor)
            cursor_prod.execute('''
                SELECT dv.*, p.descripcion
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = %s
            ''', (venta['id'],))
            productos = cursor_prod.fetchall()
            cursor_prod.close()
            
            clientes_creditos[cliente_id]['deudas'].append({
                'id_venta': venta['id'],
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
        
        # Convertir a lista y calcular deuda total por cliente
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
        print(f"Error en obtener_creditos_agrupados: {e}")
        import traceback
        traceback.print_exc()
        return []

def registrar_venta(id_cliente, productos, credito=False, fecha_manual=None):
    conn = get_connection()
    cursor = conn.cursor()
    tasa = obtener_tasa_actual()['bcv_usd']
    total_usd = sum(p.get('precio_usd',0)*p.get('cantidad',1) for p in productos)
    total_bs = total_usd * tasa
    fecha = fecha_manual or datetime.now()
    
    cursor.execute("INSERT INTO ventas (id_cliente,fecha_venta,total,tasa,credito) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                   (id_cliente, fecha, total_bs, tasa, credito))
    id_venta = cursor.fetchone()[0]
    for p in productos:
        cursor.execute("INSERT INTO detalles_venta (id_venta,id_producto,cantidad,precio_unitario,subtotal) VALUES (%s,%s,%s,%s,%s)",
                       (id_venta, p['id_producto'], p['cantidad'], p['precio_usd'], p['precio_usd']*p['cantidad']*tasa))
    conn.commit()
    conn.close()
    return {'success': True, 'id_venta': id_venta}

def pagar_credito_con_tasa(id_venta, monto_bs, observacion, tasa_actual):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total, COALESCE(monto_pagado,0), tasa, credito FROM ventas WHERE id=%s", (id_venta,))
    venta = cursor.fetchone()
    if not venta or not venta[3]:
        return {'success': False, 'error': 'No es un crédito válido'}
    total, pagado, tasa_venta = float(venta[0]), float(venta[1]), float(venta[2] or 55.0)
    nuevo_pagado = pagado + monto_bs
    saldo = total - nuevo_pagado
    cursor.execute("INSERT INTO pagos_credito (id_venta,monto_pagado,tasa_pago,observacion) VALUES (%s,%s,%s,%s)",
                   (id_venta, monto_bs, tasa_actual, observacion))
    cursor.execute("UPDATE ventas SET monto_pagado=%s, pagado=%s, saldo_pendiente=%s WHERE id=%s",
                   (nuevo_pagado, saldo<=0.01, max(0,saldo), id_venta))
    conn.commit()
    conn.close()
    return {'success': True, 'cliente_nombre': 'Cliente', 'total_venta': total, 'saldo_pendiente': max(0,saldo)}

def ventas_con_retraso():
    return []