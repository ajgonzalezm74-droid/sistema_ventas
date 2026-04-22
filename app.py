from flask import Flask, render_template, request, jsonify, send_file, make_response
from database import init_db, get_clients, get_productos as get_products, add_client, add_product, reponer_stock, buscar_producto_por_descripcion, buscar_cliente_por_telefono, buscar_cliente_por_nombre, add_client_validado, get_connection
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
    obtener_estado_credito,
    reporte_por_rango,
    obtener_creditos_agrupados,
    cancelar_creditos_global,
    pagar_credito_con_tasa
)
from datetime import datetime
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

def formatear_telefono(telefono):
    """Formatea número de teléfono 00000000000 -> 0000-0000000"""
    if not telefono:
        return telefono
    telefono_limpio = ''.join(filter(str.isdigit, str(telefono)))
    if len(telefono_limpio) == 11:
        return f"{telefono_limpio[:4]}-{telefono_limpio[4:]}"
    elif len(telefono_limpio) == 10:
        return f"0{telefono_limpio[:3]}-{telefono_limpio[3:]}"
    return telefono


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# Inicializar base de datos
init_db()


# ========== RUTA PRINCIPAL ==========
@app.route('/')
def index():
    return render_template('index.html')


# ========== API: TEST DB ==========
@app.route('/api/test_db')
def test_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clientes")
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({'success': True, 'clientes': count, 'db': 'PostgreSQL'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
        if not data or not data.get('nombre'):
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        resultado = add_client_validado(data.get('nombre'), data.get('telefono', ''), data.get('direccion', ''))
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/clientes/<int:id_cliente>', methods=['PUT'])
def api_actualizar_cliente(id_cliente):
    try:
        data = request.json
        nombre = data.get('nombre')
        telefono = data.get('telefono')
        
        if not nombre:
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        
        if telefono:
            telefono = formatear_telefono(telefono)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE clientes SET nombre = %s, telefono = %s WHERE id = %s", (nombre, telefono, id_cliente))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'mensaje': 'Cliente actualizado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/clientes/buscar', methods=['GET'])
def api_buscar_cliente():
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
    try:
        data = request.json
        nombre = data.get('nombre')
        telefono = data.get('telefono')
        
        if not nombre:
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        
        resultado = add_client_validado(nombre, telefono, '')
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
        nombre = request.args.get('nombre', '')
        descripcion = request.args.get('descripcion', '')
        busqueda = nombre if nombre else descripcion
        
        if not busqueda:
            return jsonify([])
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT p.*, i.cantidad, i.costo
            FROM productos p
            LEFT JOIN inventario i ON p.id = i.id_producto
            WHERE p.descripcion LIKE %s AND p.activo = TRUE
            LIMIT 10
        """, (f'%{busqueda}%',))
        productos = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in productos])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/productos/actualizar/<int:id_producto>', methods=['PUT'])
def api_actualizar_producto(id_producto):
    try:
        data = request.json
        descripcion = data.get('descripcion')
        costo = float(data.get('costo', 0))
        stock = int(data.get('stock', 0))
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE productos SET descripcion = %s WHERE id = %s", (descripcion, id_producto))
        cursor.execute("UPDATE inventario SET costo = %s, cantidad = %s WHERE id_producto = %s", (costo, stock, id_producto))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'mensaje': 'Producto actualizado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== API: VENTAS ==========
@app.route('/api/ventas', methods=['POST'])
def api_registrar_venta():
    try:
        data = request.json
        id_cliente = int(data.get('id_cliente'))
        productos = data.get('productos')
        credito = data.get('credito', False)
        fecha_manual = data.get('fecha_venta', None)
        
        if not productos and data.get('id_producto'):
            productos = [{"id_producto": int(data.get('id_producto')), "cantidad": int(data.get('cantidad', 1))}]
        
        if not id_cliente or not productos:
            return jsonify({'success': False, 'error': 'Cliente y productos requeridos'}), 400
        
        resultado = registrar_venta(id_cliente, productos, credito, fecha_manual)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== API: CRÉDITOS ==========
@app.route('/api/creditos/agrupados', methods=['GET'])
def get_creditos_agrupados():
    try:
        creditos = obtener_creditos_agrupados()
        return jsonify(creditos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/creditos/retraso', methods=['GET'])
def api_creditos_retraso():
    try:
        return jsonify(ventas_con_retraso())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/creditos/pagar', methods=['POST'])
def api_pagar_credito():
    try:
        data = request.json
        id_venta = data.get('id_venta')
        monto = data.get('monto', 0)
        observacion = data.get('observacion', '')
        tasa_actual = data.get('tasa_actual', 0)
        resultado = pagar_credito_con_tasa(id_venta, monto, observacion, tasa_actual)
        
        if resultado.get('success'):
            datos_recibo = {
                'cliente': resultado.get('cliente_nombre', 'Cliente'),
                'telefono': resultado.get('cliente_telefono', ''),
                'fecha': datetime.now().strftime('%d/%m/%Y'),
                'productos': resultado.get('productos', []),
                'total': resultado.get('total_venta', 0),
                'tasa': resultado.get('tasa_venta', 0),
                'tasa_actual': resultado.get('tasa_aplicada', 0),
                'tipo': 'CRÉDITO',
                'saldo_pendiente': resultado.get('saldo_pendiente', 0)
            }
            img_bytes = generar_recibo_profesional(datos_recibo)
            return send_file(img_bytes, mimetype='image/png', as_attachment=False)
        else:
            return jsonify(resultado), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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


@app.route('/api/reportes/rango', methods=['POST'])
def api_reporte_rango():
    try:
        data = request.json
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        tipo = data.get('tipo', 'dia')
        filtro_venta = data.get('filtro_venta', 'todas')
        resultado = reporte_por_rango(fecha_inicio, fecha_fin, tipo, filtro_venta)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== API: RECIBOS ==========
@app.route('/api/ventas/recibo/<int:id_venta>', methods=['GET'])
def api_generar_recibo(id_venta):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT v.*, c.nombre, c.telefono FROM ventas v JOIN clientes c ON v.id_cliente = c.id WHERE v.id = %s", (id_venta,))
        datos = cursor.fetchone()
        if not datos:
            conn.close()
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        datos = dict(datos)
        cursor.execute("SELECT p.descripcion, dv.cantidad, dv.precio_unitario FROM detalles_venta dv JOIN productos p ON dv.id_producto = p.id WHERE dv.id_venta = %s", (id_venta,))
        productos = cursor.fetchall()
        conn.close()
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", datos.get('tasa', 0))
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
        return send_file(img_bytes, mimetype='image/png', as_attachment=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== INICIAR SERVIDOR ==========
#if __name__ == '__main__':
#    port = int(os.environ.get("PORT", 5000))
#    app.run(host='0.0.0.0', port=port, debug=False)
    
    
if __name__ == '__main__':
    # Reducir el uso de memoria
    port = int(os.environ.get("PORT", 5000))
   # Para producción en Render
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)