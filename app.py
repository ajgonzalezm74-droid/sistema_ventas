from flask import Flask, render_template, request, jsonify, send_file
from database import get_connection, get_clients, get_productos, add_client, add_product, reponer_stock
from ventas_logic import *
from datetime import datetime
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# ========== CONFIGURACIÓN ==========
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# ========== RUTAS PRINCIPALES ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tasa', methods=['GET'])
def api_tasa():
    return jsonify(obtener_tasa_actual())

@app.route('/health', methods=['GET'])
def health_check():
    # Responde rápido para consumir pocos recursos
    return ("OK", 200)

# ========== CLIENTES ==========
@app.route('/api/clientes', methods=['GET'])
def api_clientes():
    return jsonify(get_clients())

@app.route('/api/clientes', methods=['POST'])
def api_add_cliente():
    data = request.json
    return jsonify(add_client_validado(data.get('nombre'), data.get('telefono', ''), ''))

@app.route('/api/clientes/<int:id_cliente>', methods=['PUT'])
def api_actualizar_cliente(id_cliente):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clientes SET nombre=%s, telefono=%s WHERE id=%s", 
                   (data.get('nombre'), data.get('telefono'), id_cliente))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/clientes/buscar', methods=['GET'])
def api_buscar_cliente():
    nombre = request.args.get('nombre', '')
    telefono = request.args.get('telefono', '')
    if telefono:
        return jsonify(buscar_cliente_por_telefono(telefono))
    return jsonify(buscar_cliente_por_nombre(nombre))

# ========== PRODUCTOS ==========
@app.route('/api/productos', methods=['GET'])
def api_productos():
    return jsonify(get_productos())

@app.route('/api/productos', methods=['POST'])
def api_add_producto():
    data = request.json
    return jsonify(add_product(data.get('descripcion'), data.get('costo', 0), data.get('stock', 0)))

@app.route('/api/productos/reponer/<int:id_producto>', methods=['POST'])
def api_reponer_stock(id_producto):
    data = request.json
    return jsonify(reponer_stock(id_producto, data.get('cantidad'), data.get('costo')))

# ========== VENTAS ==========
@app.route('/api/ventas', methods=['POST'])
def api_registrar_venta():
    data = request.json
    return jsonify(registrar_venta(
        data.get('id_cliente'), data.get('productos'), 
        data.get('credito', False), data.get('fecha_venta')
    ))

# ========== CRÉDITOS ==========
@app.route('/api/creditos/agrupados', methods=['GET'])
def get_creditos_agrupados():
    return jsonify(obtener_creditos_agrupados())

@app.route('/api/creditos/retraso', methods=['GET'])
def api_creditos_retraso():
    return jsonify(ventas_con_retraso())

# ========== REPORTE HTML CRÉDITOS ==========
@app.route('/api/creditos/reporte_cliente_pdf/<int:cliente_id>', methods=['GET'])
def api_reporte_cliente_pdf(cliente_id):
    """Genera reporte de créditos en HTML - Versión corregida"""
    try:
        from datetime import datetime
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener cliente
        cursor.execute("SELECT id, nombre, telefono FROM clientes WHERE id=%s", (cliente_id,))
        cliente = cursor.fetchone()
        if not cliente:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        # Obtener tasa actual
        tasas = exchange.get_all_rates(force_update=False)
        tasa_actual = tasas.get("bcv_usd", 55.0)
        
        # Obtener créditos del cliente con pagos
        cursor.execute("""
            SELECT v.id, v.fecha_venta, v.total, v.tasa,
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta=v.id), 0) as total_pagado
            FROM ventas v
            WHERE v.id_cliente=%s AND v.credito=true AND v.pagado=false
        """, (cliente_id,))
        
        creditos = cursor.fetchall()
        conn.close()
        
        deudas = []
        total_global = 0
        
        for credito in creditos:
            total = float(credito['total'])
            tasa_venta = float(credito['tasa']) if credito['tasa'] else 55.0
            pagado = float(credito['total_pagado']) if credito['total_pagado'] else 0
            
            total_usd = total / tasa_venta if tasa_venta > 0 else 0
            total_hoy = total_usd * tasa_actual
            saldo = total_hoy - pagado
            
            if saldo <= 0.01:
                continue
                
            total_global += saldo
            fecha = credito['fecha_venta'].strftime('%d/%m/%Y') if credito['fecha_venta'] else '-'
            
            deudas.append({
                'id': credito['id'],
                'fecha': fecha,
                'total': total,
                'tasa_venta': tasa_venta,
                'total_usd': total_usd,
                'total_hoy': total_hoy,
                'pagado': pagado,
                'saldo': saldo
            })
        
        # Generar HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Créditos - {cliente['nombre']}</title>
        <style>
            body {{ font-family: Arial; margin:20px; background:#f0f2f5; }}
            .container {{ max-width:700px; margin:0 auto; background:white; border-radius:10px; }}
            .header {{ background:#1976D2; color:white; padding:20px; text-align:center; }}
            .info {{ background:#f8f9fa; padding:15px; border-bottom:1px solid #ddd; }}
            .deuda {{ border:1px solid #ddd; margin:15px; padding:10px; border-radius:5px; }}
            .saldo {{ color:red; font-weight:bold; }}
            .total {{ background:#2c3e50; color:white; padding:15px; text-align:right; }}
            button {{ padding:10px 20px; margin:10px; cursor:pointer; }}
        </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h1>📄 VENTAS PRO</h1><p>Estado de Cuenta</p></div>
                <div class="info">
                    <p><strong>Cliente:</strong> {cliente['nombre']}</p>
                    <p><strong>Teléfono:</strong> {cliente['telefono'] or 'No registrado'}</p>
                    <p><strong>Tasa BCV:</strong> Bs {tasa_actual:.2f}</p>
                </div>
        """
        
        if deudas:
            for d in deudas:
                html += f"""
                <div class="deuda">
                    <strong>📅 {d['fecha']}</strong>
                    <div style="float:right" class="saldo">Bs {d['saldo']:,.2f}</div>
                    <div>💰 Deuda original: Bs {d['total']:,.2f}</div>
                    <div>✅ Pagado: Bs {d['pagado']:,.2f}</div>
                    <div>💵 Total actualizado: Bs {d['total_hoy']:,.2f}</div>
                </div>
                """
        else:
            html += '<p style="text-align:center; padding:20px;">✅ No hay deudas pendientes</p>'
        
        html += f"""
                <div class="total">💰 TOTAL ADEUDADO: Bs {total_global:,.2f}</div>
                <div style="text-align:center; padding:20px;">
                    <button onclick="window.print()">🖨️ Imprimir</button>
                    <button onclick="window.close()">❌ Cerrar</button>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
# ========== RECIBO VENTA ==========
@app.route('/api/ventas/recibo/<int:id_venta>', methods=['GET'])
def api_generar_recibo(id_venta):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono FROM ventas v 
            JOIN clientes c ON v.id_cliente=c.id WHERE v.id=%s
        """, (id_venta,))
        venta = cursor.fetchone()
        if not venta:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario
            FROM detalles_venta dv JOIN productos p ON dv.id_producto=p.id
            WHERE dv.id_venta=%s
        """, (id_venta,))
        productos = cursor.fetchall()
        conn.close()
        
        tasa_actual = obtener_tasa_actual().get('bcv_usd', 55.0)
        datos_recibo = {
            'cliente': venta['nombre'], 'telefono': venta.get('telefono', ''),
            'fecha': venta['fecha_venta'].strftime('%d/%m/%Y') if venta['fecha_venta'] else '',
            'productos': [{'descripcion': p['descripcion'], 'cantidad': p['cantidad']} for p in productos],
            'total': float(venta['total']), 'tasa': float(venta['tasa'] or 0),
            'tasa_actual': tasa_actual, 'tipo': 'CRÉDITO' if venta['credito'] else 'CONTADO'
        }
        
        from generar_recibo_profesional import generar_recibo_profesional
        return send_file(generar_recibo_profesional(datos_recibo), mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== OTROS ENDPOINTS ==========
@app.route('/api/creditos/pagar', methods=['POST'])
def api_pagar_credito():
    data = request.json
    resultado = pagar_credito_con_tasa(data.get('id_venta'), data.get('monto',0), 
                                       data.get('observacion',''), data.get('tasa_actual',0))
    if resultado.get('success'):
        from generar_recibo_profesional import generar_recibo_profesional
        datos_recibo = {
            'cliente': resultado.get('cliente_nombre'), 'telefono': resultado.get('cliente_telefono',''),
            'fecha': datetime.now().strftime('%d/%m/%Y'), 'productos': resultado.get('productos',[]),
            'total': resultado.get('total_venta',0), 'tasa': resultado.get('tasa_venta',0),
            'tasa_actual': resultado.get('tasa_aplicada',0), 'tipo': 'CRÉDITO',
            'saldo_pendiente': resultado.get('saldo_pendiente',0)
        }
        return send_file(generar_recibo_profesional(datos_recibo), mimetype='image/png')
    return jsonify(resultado), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)