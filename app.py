from flask import Flask, render_template, request, jsonify, send_file, make_response
from database import init_db, get_clients, get_productos as get_products, add_client, add_product, reponer_stock, buscar_producto_por_descripcion, buscar_cliente_por_telefono, buscar_cliente_por_nombre, add_client_validado
from generar_recibo import generar_recibo_imagen
from generar_recibo_cliente import generar_recibo_cliente
from generar_recibo_profesional import generar_recibo_profesional
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
    obtener_estado_credito
)
from datetime import datetime
import sqlite3
import io
import os

app = Flask(__name__)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

init_db()

# ========== RUTA PRINCIPAL ==========
@app.route('/')
def index():
    return render_template('index.html')

# ========== API: TASA ==========
@app.route('/api/tasa', methods=['GET'])
def api_tasa():
    try:
        return jsonify(obtener_tasa_actual())
    except Exception as e:
        return jsonify({'error': str(e), 'bcv_usd': 55.0, 'bcv_eur': 57.75}), 200

# ========== API: CLIENTES ==========
@app.route('/api/clientes', methods=['GET'])
def api_clientes():
    try:
        return jsonify(get_clients())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clientes', methods=['POST'])
def api_add_cliente():
    try:
        data = request.json
        if not data.get('nombre'):
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        id_cliente = add_client(data.get('nombre'), data.get('telefono', ''))
        return jsonify({'id': id_cliente, 'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/clientes/buscar', methods=['GET'])
def api_buscar_cliente():
    """Buscar cliente por nombre o teléfono"""
    try:
        nombre = request.args.get('nombre', '')
        telefono = request.args.get('telefono', '')
        
        if telefono:
            cliente = buscar_cliente_por_telefono(telefono)
            return jsonify(cliente if cliente else None)
        elif nombre:
            clientes = buscar_cliente_por_nombre(nombre)
            return jsonify(clientes)
        else:
            return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clientes/validar', methods=['POST'])
def api_validar_cliente():
    """Validar y agregar cliente (evita duplicados por teléfono)"""
    try:
        data = request.json
        nombre = data.get('nombre')
        telefono = data.get('telefono')
        
        if not nombre:
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        
        resultado = add_client_validado(nombre, telefono)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API: PRODUCTOS ==========
@app.route('/api/productos', methods=['GET'])
def api_productos():
    try:
        return jsonify(get_products())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos', methods=['POST'])
def api_add_producto():
    try:
        data = request.json
        if not data.get('descripcion'):
            return jsonify({'success': False, 'error': 'Descripción requerida'}), 400
        resultado = add_product(data.get('descripcion'), float(data.get('costo', 0)), int(data.get('stock', 0)))
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/productos/reponer/<int:id_producto>', methods=['POST'])
def api_reponer_stock(id_producto):
    try:
        data = request.json
        cantidad = int(data.get('cantidad', 0))
        if cantidad <= 0:
            return jsonify({'success': False, 'error': 'Cantidad debe ser mayor a 0'}), 400
        costo = float(data.get('costo')) if data.get('costo') else None
        resultado = reponer_stock(id_producto, cantidad, costo)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/productos/buscar', methods=['GET'])
def api_buscar_producto():
    try:
        descripcion = request.args.get('descripcion', '')
        producto = buscar_producto_por_descripcion(descripcion)
        return jsonify(producto if producto else None)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== API: VENTAS ==========
@app.route('/api/ventas', methods=['POST'])
def api_registrar_venta():
    try:
        data = request.json
        id_cliente = int(data.get('id_cliente'))
        productos = data.get('productos')
        credito = data.get('credito', False)
        
        if not productos and data.get('id_producto'):
            productos = [{"id_producto": int(data.get('id_producto')), "cantidad": int(data.get('cantidad', 1))}]
        
        if not id_cliente or not productos:
            return jsonify({'success': False, 'error': 'Cliente y productos requeridos'}), 400
        
        resultado = registrar_venta(id_cliente, productos, credito)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ventas/pagar/<int:id_venta>', methods=['POST'])
def api_pagar_credito(id_venta):
    try:
        resultado = pagar_credito(id_venta)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ventas/cancelar/<int:id_venta>', methods=['POST'])
def api_cancelar_venta(id_venta):
    try:
        resultado = cancelar_venta(id_venta)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ventas/actualizar-fecha/<int:id_venta>', methods=['POST'])
def api_actualizar_fecha_venta(id_venta):
    try:
        data = request.json
        fecha = data.get('fecha')
        tasa = float(data.get('tasa', 0))
        
        conn = sqlite3.connect('ventas.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(i.costo * dv.cantidad) 
            FROM detalles_venta dv
            JOIN inventario i ON dv.id_producto = i.id_producto
            WHERE dv.id_venta = ?
        """, (id_venta,))
        total_usd = cursor.fetchone()[0] or 0
        total_bs = total_usd * tasa
        
        cursor.execute("UPDATE ventas SET fecha_venta = ?, tasa = ?, total = ? WHERE id = ?", 
                      (fecha, tasa, total_bs, id_venta))
        cursor.execute("UPDATE detalles_venta SET precio_unitario = ?, subtotal = ? WHERE id_venta = ?", 
                      (total_bs, total_bs, id_venta))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API: CRÉDITOS ==========
@app.route('/api/creditos/pagar-parcial', methods=['POST'])
def api_pagar_credito_parcial():
    try:
        data = request.json
        resultado = pagar_credito_parcial(int(data.get('id_venta')), float(data.get('monto')), data.get('observacion', ''))
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/creditos/historial/<int:id_venta>', methods=['GET'])
def api_historial_pagos(id_venta):
    try:
        return jsonify(obtener_historial_pagos(id_venta))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/creditos/nota-debito/<int:id_venta>', methods=['GET'])
def api_generar_nota_debito(id_venta):
    try:
        return jsonify(generar_nota_debito(id_venta))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/creditos/estado/<int:id_venta>', methods=['GET'])
def api_estado_credito(id_venta):
    try:
        resultado = obtener_estado_credito(id_venta)
        return jsonify(resultado if resultado else {'error': 'No encontrado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/creditos/reporte', methods=['GET'])
def api_reporte_creditos():
    try:
        creditos = ventas_con_retraso()
        return jsonify({
            'success': True,
            'total_creditos': len(creditos),
            'total_deuda_pendiente': sum(c.get('saldo_pendiente', 0) for c in creditos),
            'creditos': creditos
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/creditos/retraso', methods=['GET'])
def api_creditos_retraso():
    try:
        return jsonify(ventas_con_retraso())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== API: REPORTES ==========
@app.route('/api/reportes/ventas', methods=['GET'])
def api_reporte_ventas():
    try:
        periodo = request.args.get('periodo', 'semanal')
        return jsonify(reporte_ventas(periodo))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/productos', methods=['GET'])
def api_reporte_productos():
    try:
        return jsonify(reporte_produto())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== API: RECIBOS ==========

@app.route('/api/ventas/recibo/<int:id_venta>', methods=['GET'])
def api_generar_recibo(id_venta):
    try:
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener datos de la venta
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.id = ?
        """, (id_venta,))
        
        datos = cursor.fetchone()
        if not datos:
            conn.close()
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        datos = dict(datos)
        
        # Obtener productos
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario
            FROM detalles_venta dv
            JOIN productos p ON dv.id_producto = p.id
            WHERE dv.id_venta = ?
        """, (id_venta,))
        
        productos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Obtener tasa actual
        tasa_actual = obtener_tasa_actual().get("bcv_usd", datos.get('tasa', 0))
        
        # Preparar datos para el recibo (con la misma información que ves en créditos)
        datos_recibo = {
            'cliente': datos.get('nombre', 'Cliente'),
            'fecha': datos.get('fecha_venta', '')[:10],
            'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos],
            'total': datos.get('total', 0),
            'tasa': datos.get('tasa', 0),
            'tasa_actual': tasa_actual,
            'tipo': 'CRÉDITO' if datos.get('credito') else 'CONTADO',
            'saldo_pendiente': datos.get('saldo_pendiente', 0)
        }
        
        img_bytes = generar_recibo_profesional(datos_recibo)
        
        return send_file(
            img_bytes,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"recibo_{id_venta}.png"
        )
        
    except Exception as e:
        print(f"Error generando recibo: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ventas/recibo/imprimir/<int:id_venta>', methods=['GET'])
def api_imprimir_recibo(id_venta):
    try:
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono
            FROM ventas v
            JOIN clientes c ON v.id_cliente = c.id
            WHERE v.id = ?
        """, (id_venta,))
        
        datos = cursor.fetchone()
        if not datos:
            conn.close()
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        datos = dict(datos)
        
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario
            FROM detalles_venta dv
            JOIN productos p ON dv.id_producto = p.id
            WHERE dv.id_venta = ?
        """, (id_venta,))
        
        productos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        datos_recibo = {
            'cliente': datos.get('nombre', 'Cliente'),
            'telefono': datos.get('telefono', ''),
            'fecha': datos.get('fecha_venta', '')[:10],
            'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad'], 'precio': p['precio_unitario']} for p in productos],
            'total': datos.get('total', 0),
            'tasa': datos.get('tasa', 0),
            'tipo': 'crédito' if datos.get('credito') else 'contado',
            'saldo_pendiente': datos.get('saldo_pendiente', 0),
            'id_venta': id_venta
        }
        
        img_bytes = generar_recibo_profesional(datos_recibo)
        response = make_response(send_file(img_bytes, mimetype='image/png'))
        response.headers['Content-Disposition'] = 'inline; filename=recibo.png'
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ventas/recibo/compartir/<int:id_venta>', methods=['GET'])
def api_compartir_recibo(id_venta):
    try:
        datos = obtener_estado_credito(id_venta)
        if not datos:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        productos = datos.get('productos', [])
        datos_recibo = {
            'cliente': datos.get('nombre', 'Cliente'),
            'telefono': datos.get('telefono', ''),
            'fecha': datos.get('fecha_venta', '')[:10],
            'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad'], 'precio': p['precio_unitario']} for p in productos],
            'total': datos.get('total_actualizado', datos.get('total', 0)),
            'tasa': datos.get('tasa_actual', datos.get('tasa', 0)),
            'tipo': 'crédito' if datos.get('credito') else 'contado',
            'saldo_pendiente': datos.get('saldo_pendiente', 0),
            'id_venta': id_venta
        }
        ruta_imagen, nombre_archivo = generar_recibo_imagen(datos_recibo)
        return jsonify({'success': True, 'url': f"/static/recibos/{nombre_archivo}", 'mensaje': 'Recibo generado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ventas/recibo/cliente/<int:id_cliente>', methods=['GET'])
def api_generar_recibo_cliente(id_cliente):
    """Genera recibo con todas las deudas del cliente"""
    try:
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener datos del cliente
        cursor.execute("SELECT nombre, telefono FROM clientes WHERE id = ?", (id_cliente,))
        cliente = cursor.fetchone()
        if not cliente:
            conn.close()
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        cliente = dict(cliente)
        
        # Obtener todas las ventas a crédito del cliente (no pagadas)
        cursor.execute("""
            SELECT v.*, 
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v
            WHERE v.id_cliente = ? AND v.credito = 1 AND v.pagado = 0 AND v.cancelada = 0
            ORDER BY v.fecha_venta ASC
        """, (id_cliente,))
        
        ventas = cursor.fetchall()
        
        if not ventas:
            conn.close()
            return jsonify({'error': 'Cliente no tiene deudas pendientes'}), 404
        
        # Obtener tasa actual
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 55.0)
        
        # Preparar datos para el recibo
        deudas = []
        for venta in ventas:
            venta = dict(venta)
            
            # Obtener productos de esta venta
            cursor.execute("""
                SELECT p.descripcion, dv.cantidad
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = ?
            """, (venta['id'],))
            productos = cursor.fetchall()
            
            # Calcular valores actualizados
            total_usd = venta['total'] / venta['tasa'] if venta['tasa'] > 0 else 0
            total_actualizado = total_usd * tasa_actual
            total_pagado = venta.get('total_pagado', 0)
            saldo_pendiente = total_actualizado - total_pagado
            
            deudas.append({
                'id': venta['id'],
                'fecha': venta['fecha_venta'][:10],
                'total_original': venta['total'],
                'tasa_venta': venta['tasa'],
                'total_usd': total_usd,
                'total_actualizado': total_actualizado,
                'saldo_pendiente': saldo_pendiente,
                'productos': [{'descripcion': p[0], 'cantidad': p[1]} for p in productos]
            })
        
        conn.close()
        
        # Preparar datos para el recibo
        datos_recibo = {
            'cliente': cliente['nombre'],
            'telefono': cliente['telefono'],
            'tasa_actual': tasa_actual,
            'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'deudas': deudas,
            'total_general': sum(d['saldo_pendiente'] for d in deudas)
        }
        
        img_bytes = generar_recibo_cliente(datos_recibo)
        
        return send_file(
            img_bytes,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"recibo_cliente_{id_cliente}.png"
        )
        
    except Exception as e:
        print(f"Error generando recibo: {e}")
        return jsonify({'error': str(e)}), 500


# ========== INICIAR SERVIDOR ==========
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)