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
    obtener_estado_credito,
    reporte_por_rango,
    obtener_creditos_agrupados,
    cancelar_creditos_global,
    pagar_credito_con_tasa
)
from datetime import datetime
import sqlite3
import io
import os

app = Flask(__name__)

def formatear_telefono(telefono):
    """Formatea número de teléfon 00000000000 -> 0000-0000000"""
    if not telefono:
        return telefono
    
    # Eliminar caracteres no numéricos
    telefono_limpio = ''.join(filter(str.isdigit, str(telefono)))
    
    # Formato para Venezuela: 0412-XXX-XXXX o 0412-XXXXXXX
    if len(telefono_limpio) == 11:  # 0412XXXXXXX
        return f"{telefono_limpio[:4]}-{telefono_limpio[4:]}"
    elif len(telefono_limpio) == 10:  # 412XXXXXXX
        return f"0{telefono_limpio[:3]}-{telefono_limpio[3:]}"
    else:
        return telefono  # Devolver como está si no cumple el formato
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

@app.route('/favicon.ico')
def favicon():
    return '', 204  # Retorna vacío sin error
# ========== FUNCIÓN PARA RECIBO DE CANCELACIÓN GLOBAL ==========
def generar_recibo_cancelacion_global(datos_cliente, lista_deudas, tasa_actual):
    """
    Genera un recibo profesional UNIFICADO para cancelación global de todas las deudas de un cliente
    """
    from PIL import Image, ImageDraw, ImageFont
    
    # Configuración
    ancho = 700
    alto = 500 + (len(lista_deudas) * 180)
    color_fondo = (255, 255, 255)
    color_primario = (25, 118, 210)
    color_exito = (76, 175, 80)
    color_texto = (51, 51, 51)
    color_gris = (117, 117, 117)
    
    img = Image.new('RGB', (ancho, alto), color_fondo)
    draw = ImageDraw.Draw(img)
    
    # Fuentes
    try:
        font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 24)
        font_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 18)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 14)
        font_pequeno = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 11)
    except:
        try:
            font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_pequeno = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except:
            font_titulo = font_subtitulo = font_normal = font_pequeno = ImageFont.load_default()
    
    y = 25
    
    # Encabezado
    draw.rectangle([0, 0, ancho, 100], fill=color_primario)
    draw.text((ancho//2 - 80, 30), "VENTAS PRO", font=font_titulo, fill=(255,255,255))
    draw.text((ancho//2 - 110, 65), "CANCELACIÓN TOTAL DE CRÉDITOS", font=font_subtitulo, fill=(255,255,255))
    
    y = 120
    
    # Datos del cliente
    draw.text((30, y), f"Cliente: {datos_cliente['nombre']}", font=font_subtitulo, fill=color_primario)
    y += 25
    draw.text((30, y), f"Teléfono: {datos_cliente.get('telefono', 'N/A')}", font=font_normal, fill=color_texto)
    y += 25
    draw.text((30, y), f"Fecha de cancelación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", font=font_pequeno, fill=color_gris)
    y += 40
    
    draw.line([30, y, ancho-30, y], fill=color_gris, width=1)
    y += 20
    
    # Lista de deudas canceladas
    draw.text((30, y), "CRÉDITOS CANCELADOS", font=font_subtitulo, fill=color_primario)
    y += 30
    
    total_general_bs = 0
    total_general_usd = 0
    
    for i, deuda in enumerate(lista_deudas):
        if i % 2 == 0:
            draw.rectangle([30, y-5, ancho-30, y+140], fill=(248, 248, 248))
        
        total_usd = deuda['total'] / deuda['tasa'] if deuda['tasa'] > 0 else 0
        total_actualizado = total_usd * tasa_actual
        
        total_general_usd += total_usd
        total_general_bs += total_actualizado
        
        fecha_venta = deuda.get('fecha_venta', '').split(' ')[0]
        draw.text((45, y), f"Venta del: {fecha_venta}", font=font_normal, fill=color_primario)
        y += 22
        
        productos = deuda.get('productos', [])
        prod_text = ", ".join([f"{p['descripcion']} x{p['cantidad']}" for p in productos[:2]])
        if len(productos) > 2:
            prod_text += f" +{len(productos)-2} mas"
        draw.text((45, y), prod_text, font=font_pequeno, fill=color_gris)
        y += 20
        
        draw.text((45, y), f"Deuda original: Bs {deuda['total']:,.2f}", font=font_normal, fill=color_texto)
        draw.text((280, y), f"Tasa venta: Bs {deuda['tasa']:,.2f}", font=font_normal, fill=color_texto)
        y += 18
        
        draw.text((45, y), f"Cancelado HOY: Bs {total_actualizado:,.2f}", font=font_normal, fill=color_exito)
        draw.text((280, y), f"(USD ${total_usd:,.2f} x Tasa Bs {tasa_actual:,.2f})", font=font_pequeno, fill=color_gris)
        y += 25
        
        draw.line([45, y, ancho-45, y], fill=color_gris, width=1)
        y += 15
    
    # Total general
    y += 10
    draw.rectangle([30, y-10, ancho-30, y+40], fill=color_exito)
    draw.text((ancho//2 - 130, y), f"TOTAL CANCELADO: Bs {total_general_bs:,.2f}", 
              font=font_subtitulo, fill=(255,255,255))
    y += 55
    draw.text((ancho//2 - 80, y), f"(Equivalente a USD ${total_general_usd:,.2f})", 
              font=font_pequeno, fill=color_gris)
    
    # Footer
    y = alto - 60
    draw.line([30, y, ancho-30, y], fill=color_gris, width=1)
    draw.text((ancho//2 - 120, y+15), "Todas las deudas han sido canceladas", font=font_pequeno, fill=color_exito)
    draw.text((ancho//2 - 100, y+32), "Gracias por confiar en nosotros!", font=font_pequeno, fill=color_gris)
    
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


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
        
        resultado = add_client_validado(nombre, telefono)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API: ACTUALIZAR CLIENTE ==========
@app.route('/api/clientes/<int:id_cliente>', methods=['PUT'])
def api_actualizar_cliente(id_cliente):
    try:
        data = request.json
        nombre = data.get('nombre')
        telefono = data.get('telefono')
        
        if not nombre:
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        
        # Formatear teléfono automáticamente
        if telefono:
            telefono = formatear_telefono(telefono)
        
        conn = sqlite3.connect('ventas.db')
        cursor = conn.cursor()
        
        cursor.execute("UPDATE clientes SET nombre = ?, telefono = ? WHERE id = ?", (nombre, telefono, id_cliente))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'mensaje': 'Cliente actualizado correctamente'})
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
        # Aceptar ambos parámetros: 'nombre' y 'descripcion'
        nombre = request.args.get('nombre', '')
        descripcion = request.args.get('descripcion', '')
        
        # Usar el que venga
        busqueda = nombre if nombre else descripcion
        
        if not busqueda:
            return jsonify([])
        
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Búsqueda por nombre parcial (insensible a mayúsculas)
        cursor.execute("""
            SELECT p.*, i.cantidad, i.costo 
            FROM productos p 
            LEFT JOIN inventario i ON p.id = i.id_producto 
            WHERE p.descripcion LIKE ? AND p.activo = 1
            LIMIT 10
        """, (f'%{busqueda}%',))
        
        productos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(productos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/actualizar/<int:id_producto>', methods=['PUT'])
def api_actualizar_producto(id_producto):
    """Actualizar producto existente"""
    try:
        data = request.json
        descripcion = data.get('descripcion')
        costo = float(data.get('costo', 0))
        stock = int(data.get('stock', 0))
        
        conn = sqlite3.connect('ventas.db')
        cursor = conn.cursor()
        
        # Actualizar producto
        cursor.execute("UPDATE productos SET descripcion = ? WHERE id = ?", (descripcion, id_producto))
        
        # Actualizar inventario
        cursor.execute("""
            UPDATE inventario 
            SET costo = ?, cantidad = ? 
            WHERE id_producto = ?
        """, (costo, stock, id_producto))
        
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
        fecha_manual = data.get('fecha_venta', None)  # Fecha opcional para ventas históricas
        
        if not productos and data.get('id_producto'):
            productos = [{"id_producto": int(data.get('id_producto')), "cantidad": int(data.get('cantidad', 1))}]
        
        if not id_cliente or not productos:
            return jsonify({'success': False, 'error': 'Cliente y productos requeridos'}), 400
        
        # Validar fecha si se proporcionó
        if fecha_manual:
            try:
                fecha_venta = datetime.strptime(fecha_manual, '%Y-%m-%d')
                hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if fecha_venta > hoy:
                    return jsonify({'success': False, 'error': 'No se puede registrar una venta con fecha adelantada'}), 400
            except:
                pass
        
        resultado = registrar_venta(id_cliente, productos, credito, fecha_manual)
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
    
@app.route('/api/ventas/actualizar-fecha-historica/<int:id_venta>', methods=['POST'])
def api_actualizar_fecha_historica(id_venta):
    try:
        data = request.json
        fecha = data.get('fecha')
        tasa = float(data.get('tasa', 0))
        productos = data.get('productos', [])
        
        conn = sqlite3.connect('ventas.db')
        cursor = conn.cursor()
        
        total_correcto = sum(p['subtotal'] for p in productos)
        
        cursor.execute("""
            UPDATE ventas 
            SET fecha_venta = ?, tasa = ?, total = ? 
            WHERE id = ?
        """, (fecha, tasa, total_correcto, id_venta))
        
        for prod in productos:
            precio_unitario = prod['subtotal'] / prod['cantidad']
            cursor.execute("""
                UPDATE detalles_venta 
                SET cantidad = ?, precio_unitario = ?, subtotal = ? 
                WHERE id_venta = ? AND id_producto = ?
            """, (prod['cantidad'], precio_unitario, prod['subtotal'], id_venta, prod['id_producto']))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Venta {id_venta} actualizada - Total: Bs {total_correcto:.2f}")
        return jsonify({'success': True, 'total': total_correcto})
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== API: CRÉDITOS AGRUPADOS POR CLIENTE ==========
@app.route('/api/creditos/agrupados', methods=['GET'])
def get_creditos_agrupados():
    """Retorna todos los créditos pendientes agrupados por cliente"""
    try:
        conn = sqlite3.connect('ventas.db')
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
        return jsonify(list(clientes_creditos.values()))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== API: CANCELACIÓN GLOBAL DE CRÉDITOS ==========
@app.route('/api/creditos/cancelar_global', methods=['POST'])
def cancelar_creditos_global():
    """Cancela TODAS las deudas de un cliente de una sola vez"""
    try:
        data = request.json
        cliente_id = data.get('cliente_id')
        tasa_actual = data.get('tasa_actual', 0)
        
        if not cliente_id:
            return jsonify({'error': 'Cliente no especificado'}), 400
        
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
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
            return jsonify({'error': 'No hay deudas pendientes para este cliente'}), 400
        
        total_cancelado_bs = 0
        deudas_canceladas = []
        
        for deuda in deudas:
            total_usd = deuda['total'] / deuda['tasa'] if deuda['tasa'] > 0 else 0
            monto_cancelar = total_usd * tasa_actual
            
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
            
            cursor.execute('''
                UPDATE ventas 
                SET pagado = 1, 
                    saldo_pendiente = 0,
                    pagado_parcial = 0,
                    fecha_pago = ?
                WHERE id = ?
            ''', (datetime.now(), deuda['id']))
            
            total_cancelado_bs += monto_cancelar
            
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
        
        recibo_img = generar_recibo_cancelacion_global(datos_cliente, deudas_canceladas, tasa_actual)
        
        conn.close()
        
        return send_file(
            recibo_img,
            mimetype='image/png',
            as_attachment=False,
            download_name=f"cancelacion_global_{datos_cliente['nombre'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
    except Exception as e:
        print(f"Error en cancelación global: {e}")
        return jsonify({'error': str(e)}), 500


# ========== API: PAGAR CRÉDITO CON TASA ACTUAL ==========
@app.route('/api/creditos/pagar', methods=['POST'])
def api_pagar_credito_con_tasa():
    """Registra pago de un crédito individual con la tasa actual"""
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
            
            return send_file(
                img_bytes,
                mimetype='image/png',
                as_attachment=False,
                download_name=f"recibo_pago_{id_venta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        print(f"Error en pago de crédito: {e}")
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


# ========== API: REPORTE GLOBAL POR CLIENTE ==========
@app.route('/api/creditos/reporte_cliente/<int:id_cliente>', methods=['GET'])
def api_reporte_creditos_cliente(id_cliente):
    """Genera reporte global de todas las deudas de un cliente"""
    try:
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT nombre, telefono FROM clientes WHERE id = ?", (id_cliente,))
        cliente = cursor.fetchone()
        if not cliente:
            conn.close()
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        cliente = dict(cliente)
        
        cursor.execute("""
            SELECT v.*, 
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v
            WHERE v.id_cliente = ? AND v.credito = 1 AND v.cancelada = 0
            ORDER BY v.fecha_venta ASC
        """, (id_cliente,))
        
        ventas = cursor.fetchall()
        
        if not ventas:
            conn.close()
            return jsonify({'error': 'Cliente no tiene créditos registrados'}), 404
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 55.0)
        
        deudas = []
        total_adeudado = 0
        total_pagado_acumulado = 0
        total_original_acumulado = 0
        
        for venta in ventas:
            venta = dict(venta)
            
            cursor.execute("""
                SELECT p.descripcion, dv.cantidad, dv.precio_unitario, dv.subtotal
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = ?
            """, (venta['id'],))
            productos = cursor.fetchall()
            
            total_usd = venta['total'] / venta['tasa'] if venta['tasa'] > 0 else 0
            total_actualizado = total_usd * tasa_actual
            total_pagado = venta.get('total_pagado', 0)
            saldo_pendiente = total_actualizado - total_pagado
            
            estado = "PAGADO" if venta['pagado'] == 1 else "PENDIENTE"
            if venta.get('pagado_parcial') == 1 and venta['pagado'] == 0:
                estado = "PAGO PARCIAL"
            
            deudas.append({
                'id_venta': venta['id'],
                'fecha_venta': venta['fecha_venta'],
                'total_original': round(venta['total'], 2),
                'tasa_venta': round(venta['tasa'], 2),
                'total_usd': round(total_usd, 2),
                'total_actualizado': round(total_actualizado, 2),
                'total_pagado': round(total_pagado, 2),
                'saldo_pendiente': round(max(0, saldo_pendiente), 2),
                'estado': estado,
                'productos': [{'descripcion': p[0], 'cantidad': p[1], 'precio': p[2], 'subtotal': p[3]} for p in productos]
            })
            
            total_adeudado += max(0, saldo_pendiente)
            total_pagado_acumulado += total_pagado
            total_original_acumulado += venta['total']
        
        conn.close()
        
        reporte = {
            'success': True,
            'cliente': {
                'id': id_cliente,
                'nombre': cliente['nombre'],
                'telefono': cliente['telefono']
            },
            'tasa_actual': tasa_actual,
            'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'deudas': deudas,
            'resumen': {
                'total_original_bs': round(total_original_acumulado, 2),
                'total_pagado_bs': round(total_pagado_acumulado, 2),
                'total_adeudado_bs': round(total_adeudado, 2),
                'total_adeudado_usd': round(total_adeudado / tasa_actual if tasa_actual > 0 else 0, 2),
                'cantidad_creditos': len(deudas),
                'creditos_pagados': sum(1 for d in deudas if d['estado'] == 'PAGADO'),
                'creditos_pendientes': sum(1 for d in deudas if d['estado'] == 'PENDIENTE'),
                'creditos_parciales': sum(1 for d in deudas if d['estado'] == 'PAGO PARCIAL')
            }
        }
        
        return jsonify(reporte)
        
    except Exception as e:
        print(f"Error generando reporte global de cliente: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== API: GENERAR PDF DEL REPORTE GLOBAL POR CLIENTE ==========
@app.route('/api/creditos/reporte_cliente_pdf/<int:id_cliente>', methods=['GET'])
def api_generar_pdf_reporte_cliente(id_cliente):
    """Genera un PNG con el reporte global de todas las deudas del cliente"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        conn = sqlite3.connect('ventas.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT nombre, telefono FROM clientes WHERE id = ?", (id_cliente,))
        cliente = cursor.fetchone()
        if not cliente:
            conn.close()
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        cliente = dict(cliente)
        
        cursor.execute("""
            SELECT v.*, 
                   COALESCE((SELECT SUM(monto_pagado) FROM pagos_credito WHERE id_venta = v.id), 0) as total_pagado
            FROM ventas v
            WHERE v.id_cliente = ? AND v.credito = 1 AND v.cancelada = 0
            ORDER BY v.fecha_venta ASC
        """, (id_cliente,))
        
        ventas = cursor.fetchall()
        
        if not ventas:
            conn.close()
            return jsonify({'error': 'Cliente no tiene creditos registrados'}), 404
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 55.0)
        
        ancho = 800
        alto = 500 + (len(ventas) * 150)
        color_fondo = (255, 255, 255)
        color_primario = (25, 118, 210)
        color_exito = (76, 175, 80)
        color_warning = (255, 152, 0)
        color_texto = (51, 51, 51)
        color_gris = (117, 117, 117)
        
        img = Image.new('RGB', (ancho, alto), color_fondo)
        draw = ImageDraw.Draw(img)
        
        font_titulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        
        y = 20
        
        draw.rectangle([0, 0, ancho, 80], fill=color_primario)
        draw.text((ancho//2 - 40, 30), "VENTAS PRO", font=font_titulo, fill=(255,255,255))
        draw.text((ancho//2 - 80, 55), "REPORTE GLOBAL DE CREDITOS", font=font_normal, fill=(255,255,255))
        
        y = 100
        
        draw.text((30, y), "Cliente: " + cliente['nombre'], font=font_normal, fill=color_primario)
        y += 22
        draw.text((30, y), "Telefono: " + (cliente.get('telefono') or 'No registrado'), font=font_normal, fill=color_texto)
        y += 22
        draw.text((30, y), "Fecha: " + datetime.now().strftime('%d/%m/%Y %H:%M'), font=font_normal, fill=color_gris)
        y += 30
        
        draw.line([30, y, ancho-30, y], fill=color_gris, width=1)
        y += 15
        
        draw.text((30, y), "DETALLE DE CREDITOS", font=font_normal, fill=color_primario)
        y += 25
        
        total_adeudado = 0
        total_original = 0
        
        for i, venta in enumerate(ventas):
            venta = dict(venta)
            
            cursor.execute("""
                SELECT p.descripcion, dv.cantidad
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = ?
            """, (venta['id'],))
            productos = cursor.fetchall()
            
            total_usd = venta['total'] / venta['tasa'] if venta['tasa'] > 0 else 0
            total_actualizado = total_usd * tasa_actual
            total_pagado = venta.get('total_pagado', 0)
            saldo_pendiente = total_actualizado - total_pagado
            
            total_adeudado += max(0, saldo_pendiente)
            total_original += venta['total']
            
            if i % 2 == 0:
                draw.rectangle([30, y-5, ancho-30, y+100], fill=(248, 248, 248))
            
            fecha_venta = venta['fecha_venta'].split(' ')[0]
            draw.text((45, y), "Venta #" + str(venta['id']) + " - " + fecha_venta, font=font_normal, fill=color_primario)
            y += 18
            
            prod_text = ""
            for idx, p in enumerate(productos[:2]):
                if idx > 0:
                    prod_text += ", "
                prod_text += p[0] + " x" + str(p[1])
            if len(productos) > 2:
                prod_text += " +" + str(len(productos)-2) + " mas"
            draw.text((45, y), prod_text, font=font_normal, fill=color_gris)
            y += 16
            
            draw.text((45, y), "Original: Bs " + format(total_actualizado, ',.2f'), font=font_normal, fill=color_texto)
            y += 16
            
            draw.text((45, y), "Pagado: Bs " + format(total_pagado, ',.2f'), font=font_normal, fill=color_exito)
            draw.text((280, y), "Saldo: Bs " + format(max(0, saldo_pendiente), ',.2f'), font=font_normal, fill=color_warning)
            y += 18
            
            draw.line([45, y, ancho-45, y], fill=color_gris, width=1)
            y += 12
        
        y += 10
        draw.rectangle([30, y-10, ancho-30, y+40], fill=color_primario)
        draw.text((ancho//2 - 120, y), "TOTAL ADEUDADO: Bs " + format(total_adeudado, ',.2f'), font=font_normal, fill=(255,255,255))
        y += 45
        
        draw.line([30, alto-40, ancho-30, alto-40], fill=color_gris, width=1)
        draw.text((ancho//2 - 100, alto-25), "Documento valido como comprobante", font=font_normal, fill=color_gris)
        draw.text((ancho//2 - 80, alto-12), "Gracias por confiar en Ventas Pro", font=font_normal, fill=color_gris)
        
        conn.close()
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return send_file(
            img_bytes,
            mimetype='image/png',
            as_attachment=False
        )
        
    except Exception as e:
        print(f"Error generando reporte cliente: {e}")
        return jsonify({'error': str(e)}), 500


# ========== API: RECIBOS ==========
@app.route('/api/ventas/recibo/<int:id_venta>', methods=['GET'])
def api_generar_recibo(id_venta):
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
        
        return send_file(
            img_bytes,
            mimetype='image/png',
            as_attachment=False,
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
        
        cursor.execute("SELECT nombre, telefono FROM clientes WHERE id = ?", (id_cliente,))
        cliente = cursor.fetchone()
        if not cliente:
            conn.close()
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        cliente = dict(cliente)
        
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
        
        tasa_actual = obtener_tasa_actual().get("bcv_usd", 55.0)
        
        deudas = []
        for venta in ventas:
            venta = dict(venta)
            
            cursor.execute("""
                SELECT p.descripcion, dv.cantidad
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = ?
            """, (venta['id'],))
            productos = cursor.fetchall()
            
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
                'saldo_pendiente': max(0, saldo_pendiente),
                'productos': [{'descripcion': p[0], 'cantidad': p[1]} for p in productos]
            })
        
        conn.close()
        
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
        print(f"Error generando recibo cliente: {e}")
        return jsonify({'error': str(e)}), 500


# ========== INICIAR SERVIDOR ==========
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)