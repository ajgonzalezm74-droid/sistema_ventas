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
    """Obtiene créditos con retraso (vencidos) - Versión PostgreSQL"""
    try:
        creditos_retraso = ventas_con_retraso()
        return jsonify(creditos_retraso)
    except Exception as e:
        print(f"❌ Error en créditos con retraso: {str(e)}")
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
        import traceback
        print(f"🔵 Generando recibo para venta ID: {id_venta}")
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Obtener datos de la venta
        print("🔵 Consultando venta...")
        cursor.execute("""
            SELECT v.*, c.nombre, c.telefono 
            FROM ventas v 
            JOIN clientes c ON v.id_cliente = c.id 
            WHERE v.id = %s
        """, (id_venta,))
        datos = cursor.fetchone()
        
        if not datos:
            conn.close()
            print("❌ Venta no encontrada")
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        print(f"✅ Venta encontrada: {datos.get('id')}")
        
        # 2. Obtener productos
        print("🔵 Consultando productos...")
        cursor.execute("""
            SELECT p.descripcion, dv.cantidad, dv.precio_unitario 
            FROM detalles_venta dv 
            JOIN productos p ON dv.id_producto = p.id 
            WHERE dv.id_venta = %s
        """, (id_venta,))
        productos = cursor.fetchall()
        conn.close()
        
        print(f"✅ Productos encontrados: {len(productos)}")
        
        # 3. Obtener tasa actual
        print("🔵 Obteniendo tasa actual...")
        tasa_response = obtener_tasa_actual()
        tasa_actual = tasa_response.get("bcv_usd", 55.0)
        print(f"✅ Tasa actual: {tasa_actual}")
        
        # 4. Preparar datos del recibo
        print("🔵 Preparando datos del recibo...")
        
        # Manejar fecha
        fecha_venta = datos.get('fecha_venta')
        if fecha_venta:
            if hasattr(fecha_venta, 'strftime'):
                fecha_str = fecha_venta.strftime('%d/%m/%Y')
            else:
                fecha_str = str(fecha_venta)[:10]
        else:
            fecha_str = ''
        
        datos_recibo = {
            'cliente': datos.get('nombre', 'Cliente'),
            'telefono': datos.get('telefono', ''),
            'fecha': fecha_str,
            'productos': [
                {
                    'descripcion': p['descripcion'], 
                    'cantidad': p['cantidad'],
                    'precio_usd': float(p['precio_unitario']) if p['precio_unitario'] else 0
                } 
                for p in productos
            ],
            'total': float(datos.get('total', 0)),
            'tasa': float(datos.get('tasa', 0)) if datos.get('tasa') else 0,
            'tasa_actual': tasa_actual,
            'tipo': 'CRÉDITO' if datos.get('credito') else 'CONTADO',
            'saldo_pendiente': float(datos.get('saldo_pendiente', 0)) if datos.get('saldo_pendiente') else 0
        }
        
        # 5. Generar recibo
        print("🔵 Generando recibo profesional...")
        try:
            from generar_recibo_profesional import generar_recibo_profesional
            img_bytes = generar_recibo_profesional(datos_recibo)
            print("✅ Recibo generado exitosamente")
            return send_file(img_bytes, mimetype='image/png', as_attachment=False)
        except ImportError:
            print("⚠️ generar_recibo_profesional no encontrado, usando versión simple")
            from generar_recibo import generar_recibo_imagen
            img_bytes = generar_recibo_imagen(datos_recibo)
            return send_file(img_bytes, mimetype='image/png', as_attachment=False)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/ventas/actualizar-fecha-historica/<int:id_venta>', methods=['POST'])
def api_actualizar_fecha_historica(id_venta):
    """
    Actualiza fecha, tasa y productos de una venta histórica
    Adaptado para PostgreSQL/Supabase
    """
    try:
        data = request.json
        fecha = data.get('fecha')
        tasa = float(data.get('tasa', 0))
        productos = data.get('productos', [])
        
        if not fecha:
            return jsonify({'success': False, 'error': 'Fecha requerida'}), 400
        
        if tasa <= 0:
            return jsonify({'success': False, 'error': 'Tasa inválida'}), 400
        
        if not productos or len(productos) == 0:
            return jsonify({'success': False, 'error': 'Productos requeridos'}), 400
        
        # Calcular total correcto
        total_correcto = sum(float(p.get('subtotal', 0)) for p in productos)
        
        if total_correcto <= 0:
            return jsonify({'success': False, 'error': 'Total inválido'}), 400
        
        # Conectar a Supabase (PostgreSQL)
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Iniciar transacción
            cursor.execute("BEGIN")
            
            # 1. Actualizar la venta principal
            # PostgreSQL usa %s como placeholder y requiere casting de fecha
            cursor.execute("""
                UPDATE ventas 
                SET fecha_venta = %s::timestamp, 
                    tasa = %s, 
                    total = %s 
                WHERE id = %s
            """, (fecha, tasa, total_correcto, id_venta))
            
            # Verificar si se actualizó alguna fila
            if cursor.rowcount == 0:
                cursor.execute("ROLLBACK")
                conn.close()
                return jsonify({'success': False, 'error': f'Venta {id_venta} no encontrada'}), 404
            
            # 2. Actualizar detalles de la venta
            for prod in productos:
                id_producto = prod.get('id_producto')
                cantidad = int(prod.get('cantidad', 0))
                subtotal = float(prod.get('subtotal', 0))
                
                if cantidad <= 0 or subtotal <= 0:
                    continue
                
                precio_unitario = subtotal / cantidad
                
                # Actualizar o insertar detalle
                cursor.execute("""
                    UPDATE detalles_venta 
                    SET cantidad = %s, 
                        precio_unitario = %s, 
                        subtotal = %s 
                    WHERE id_venta = %s AND id_producto = %s
                """, (cantidad, precio_unitario, subtotal, id_venta, id_producto))
                
                # Si no existía el detalle, insertarlo
                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO detalles_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_venta, id_producto, cantidad, precio_unitario, subtotal))
            
            # 3. Si la venta es a crédito, recalcular el saldo pendiente
            cursor.execute("""
                SELECT credito, monto_pagado FROM ventas WHERE id = %s
            """, (id_venta,))
            venta = cursor.fetchone()
            
            if venta and venta[0] == True:  # Si es crédito
                monto_pagado = venta[1] if venta[1] else 0
                nuevo_saldo = total_correcto - monto_pagado
                
                cursor.execute("""
                    UPDATE ventas 
                    SET saldo_pendiente = %s,
                        estado = CASE 
                            WHEN %s <= 0 THEN 'pagado'
                            ELSE 'pendiente'
                        END
                    WHERE id = %s
                """, (nuevo_saldo, nuevo_saldo, id_venta))
            
            # Commit de la transacción
            cursor.execute("COMMIT")
            
            print(f"✅ Venta {id_venta} actualizada - Total: Bs {total_correcto:.2f}")
            
            return jsonify({
                'success': True, 
                'total': total_correcto,
                'mensaje': f'Venta actualizada correctamente'
            })
            
        except Exception as e:
            # Rollback en caso de error
            cursor.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Error actualizando venta {id_venta}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500



# ========== API: REPORTE CRÉDITOS CLIENTE PDF ==========
@app.route('/api/creditos/reporte_cliente_pdf/<int:cliente_id>', methods=['GET'])
def api_reporte_cliente_pdf(cliente_id):
    """Genera reporte de créditos en HTML - Versión corregida que sí muestra datos"""
    try:
        from datetime import datetime
        
        print(f"\n🔵 ===== REPORTE CRÉDITOS CLIENTE {cliente_id} =====")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener cliente
        cursor.execute("SELECT id, nombre, telefono FROM clientes WHERE id = %s", (cliente_id,))
        cliente = cursor.fetchone()
        
        if not cliente:
            conn.close()
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        print(f"✅ Cliente: {cliente[1]}")
        
        # Obtener TODAS las ventas a crédito NO pagadas
        cursor.execute("""
            SELECT v.id, v.fecha_venta, v.total, v.tasa
            FROM ventas v
            WHERE v.id_cliente = %s AND v.credito = true AND v.pagado = false
            ORDER BY v.fecha_venta DESC
        """, (cliente_id,))
        
        creditos = cursor.fetchall()
        print(f"💰 Créditos encontrados: {len(creditos)}")
        
        # Obtener tasa actual
        tasa_response = obtener_tasa_actual()
        tasa_actual = tasa_response.get('bcv_usd', 55.0)
        print(f"📈 Tasa actual: Bs {tasa_actual}")
        
        # Procesar deudas y construir HTML directamente
        total_global = 0
        html_content = ""
        
        for credito in creditos:
            id_venta = credito[0]
            fecha_venta = credito[1]
            total = float(credito[2]) if credito[2] else 0
            tasa_venta = float(credito[3]) if credito[3] else 55.0
            
            print(f"\n   📋 Venta #{id_venta}: total={total}, tasa_venta={tasa_venta}")
            
            # Obtener pagos
            cursor.execute("""
                SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                FROM pagos_credito
                WHERE id_venta = %s
            """, (id_venta,))
            total_pagado = float(cursor.fetchone()[0] or 0)
            print(f"      Pagos registrados: Bs {total_pagado}")
            
            # Calcular saldo
            saldo = total - total_pagado
            print(f"      Saldo calculado: Bs {saldo}")
            
            if saldo <= 0.01:
                print(f"      ⏭️ Saldo cero, saltando")
                continue
            
            total_global += saldo
            
            # Obtener productos
            cursor.execute("""
                SELECT p.descripcion, dv.cantidad
                FROM detalles_venta dv
                JOIN productos p ON dv.id_producto = p.id
                WHERE dv.id_venta = %s
            """, (id_venta,))
            productos = cursor.fetchall()
            
            fecha_str = fecha_venta.strftime('%d/%m/%Y') if fecha_venta else '-'
            productos_str = ", ".join([f"{p[0]} x{p[1]}" for p in productos]) if productos else "Sin productos"
            
            # Agregar al HTML
            html_content += f"""
            <div style="border:1px solid #ddd; margin:15px; padding:15px; border-radius:8px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <strong style="color:#1976D2;">📅 {fecha_str}</strong>
                    <strong style="color:#e74c3c;">Saldo: Bs {saldo:,.2f}</strong>
                </div>
                <table style="width:100%; border-collapse:collapse;">
                    <tr>
                        <td style="padding:5px;"><strong>💰 Deuda original:</strong></td>
                        <td style="padding:5px;">Bs {total:,.2f}</td>
                        <td style="padding:5px;"><strong>✅ Pagado:</strong></td>
                        <td style="padding:5px;">Bs {total_pagado:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding:5px;"><strong>📈 Tasa al vender:</strong></td>
                        <td style="padding:5px;">Bs {tasa_venta:,.2f}</td>
                        <td style="padding:5px;"><strong>💵 Tasa actual:</strong></td>
                        <td style="padding:5px;">Bs {tasa_actual:,.2f}</td>
                    </tr>
                </table>
                <div style="background:#f5f5f5; padding:8px; margin-top:10px; border-radius:5px;">
                    <strong>📦 Productos:</strong> {productos_str}
                </div>
            </div>
            """
        
        conn.close()
        
        print(f"\n💰 TOTAL GLOBAL ADEUDADO: Bs {total_global}")
        print(f"📊 Deudas procesadas: {len(creditos) if creditos else 0}")
        
        # Construir HTML completo
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Reporte de Créditos - {cliente[1]}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background: #f0f2f5;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: #1976D2;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .header p {{
                    margin: 5px 0 0;
                    opacity: 0.9;
                }}
                .info {{
                    background: #f8f9fa;
                    padding: 15px 20px;
                    border-bottom: 1px solid #ddd;
                }}
                .info p {{
                    margin: 5px 0;
                }}
                .total {{
                    background: #2c3e50;
                    color: white;
                    padding: 15px 20px;
                    text-align: right;
                    font-size: 18px;
                    font-weight: bold;
                }}
                .total span {{
                    color: #27ae60;
                }}
                .btn-print {{
                    display: block;
                    width: 200px;
                    margin: 20px auto;
                    padding: 10px;
                    background: #1976D2;
                    color: white;
                    text-align: center;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                }}
                .btn-print:hover {{
                    background: #0d3d6b;
                }}
                .no-deudas {{
                    text-align: center;
                    padding: 40px;
                    color: #27ae60;
                    font-size: 18px;
                }}
                @media print {{
                    body {{
                        background: white;
                        margin: 0;
                        padding: 0;
                    }}
                    .btn-print {{
                        display: none;
                    }}
                    .container {{
                        box-shadow: none;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📄 VENTAS PRO</h1>
                    <p>Estado de Cuenta - Créditos Pendientes</p>
                </div>
                
                <div class="info">
                    <p><strong>Cliente:</strong> {cliente[1]}</p>
                    <p><strong>Teléfono:</strong> {cliente[2] if cliente[2] else 'No registrado'}</p>
                    <p><strong>Fecha reporte:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                    <p><strong>Tasa BCV actual:</strong> Bs {tasa_actual:,.2f}</p>
                </div>
        """
        
        if html_content:
            html += html_content
            html += f"""
                <div class="total">
                    💰 TOTAL ADEUDADO: <span>Bs {total_global:,.2f}</span>
                </div>
            """
        else:
            html += """
                <div class="no-deudas">
                    ✅ ¡No hay deudas pendientes!<br>
                    <small>Todos los créditos están al día</small>
                </div>
            """
        
        html += """
                <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Guardar PDF</button>
            </div>
        </body>
        </html>
        """
        
        return html, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
    
# ========== FUNCIÓN PARA RECIBO DE CANCELACIÓN GLOBAL ==========
def generar_recibo_cancelacion_global(datos_cliente, lista_deudas, tasa_actual):
    """
    Genera un recibo profesional UNIFICADO para cancelación global de todas las deudas de un cliente
    Versión mejorada - compatible con Supabase y manejo de errores
    """
    from PIL import Image, ImageDraw, ImageFont
    import io
    from datetime import datetime
    
    try:
        # Validaciones iniciales
        if not datos_cliente:
            raise ValueError("Datos del cliente son requeridos")
        
        if not lista_deudas or len(lista_deudas) == 0:
            raise ValueError("No hay deudas para cancelar")
        
        if tasa_actual <= 0:
            raise ValueError("Tasa actual inválida")
        
        # Configuración
        ancho = 700
        # Calcular altura dinámicamente basada en número de deudas
        alto = 500 + (len(lista_deudas) * 70)
        
        color_fondo = (255, 255, 255)
        color_primario = (25, 118, 210)
        color_exito = (76, 175, 80)
        color_texto = (51, 51, 51)
        color_gris = (117, 117, 117)
        color_warning = (255, 152, 0)
        
        img = Image.new('RGB', (ancho, alto), color_fondo)
        draw = ImageDraw.Draw(img)
        
        # Fuentes con múltiples fallbacks
        font_titulo = None
        font_subtitulo = None
        font_normal = None
        font_pequeno = None
        
        # Intentar diferentes rutas de fuentes (común en diferentes sistemas)
        font_paths = [
            # Linux (Render, Ubuntu, Debian)
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            # Windows
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ]
        
        def get_font(font_paths, size, bold=False):
            for path in font_paths:
                try:
                    if (bold and 'Bold' in path) or (not bold and 'Regular' in path) or \
                       (bold and 'bd' in path.lower()) or (not bold and 'arial.ttf' in path):
                        return ImageFont.truetype(path, size)
                except:
                    continue
            # Fallback a fuentes específicas
            for path in font_paths:
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue
            return ImageFont.load_default()
        
        # Cargar fuentes
        try:
            font_titulo = get_font(font_paths, 24, bold=True)
            font_subtitulo = get_font(font_paths, 18, bold=True)
            font_normal = get_font(font_paths, 14, bold=False)
            font_pequeno = get_font(font_paths, 11, bold=False)
        except:
            font_titulo = font_subtitulo = font_normal = font_pequeno = ImageFont.load_default()
        
        y = 25
        
        # Encabezado
        draw.rectangle([0, 0, ancho, 100], fill=color_primario)
        
        # Centrar texto del título
        titulo_texto = "VENTAS PRO"
        try:
            titulo_bbox = draw.textbbox((0, 0), titulo_texto, font=font_titulo)
            titulo_ancho = titulo_bbox[2] - titulo_bbox[0]
        except:
            titulo_ancho = 150
        
        draw.text(((ancho - titulo_ancho) // 2, 30), titulo_texto, font=font_titulo, fill=(255,255,255))
        
        subtitulo_texto = "CANCELACIÓN TOTAL DE CRÉDITOS"
        try:
            subtitulo_bbox = draw.textbbox((0, 0), subtitulo_texto, font=font_subtitulo)
            subtitulo_ancho = subtitulo_bbox[2] - subtitulo_bbox[0]
        except:
            subtitulo_ancho = 250
        
        draw.text(((ancho - subtitulo_ancho) // 2, 65), subtitulo_texto, font=font_subtitulo, fill=(255,255,255))
        
        y = 120
        
        # Datos del cliente (con manejo de campos nulos)
        nombre_cliente = datos_cliente.get('nombre', 'Cliente')
        if not nombre_cliente:
            nombre_cliente = 'Cliente'
        
        draw.text((30, y), f"Cliente: {nombre_cliente}", font=font_subtitulo, fill=color_primario)
        y += 25
        
        telefono = datos_cliente.get('telefono', 'N/A')
        if not telefono:
            telefono = 'No registrado'
        draw.text((30, y), f"Teléfono: {telefono}", font=font_normal, fill=color_texto)
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
            try:
                # Validar datos de la deuda
                if not deuda:
                    continue
                
                # Colores alternados para filas
                if i % 2 == 0:
                    draw.rectangle([30, y-5, ancho-30, y+65], fill=(248, 248, 248))
                
                # Obtener valores con defaults seguros
                total_deuda = float(deuda.get('total', 0))
                tasa_deuda = float(deuda.get('tasa', 0))
                total_usd = total_deuda / tasa_deuda if tasa_deuda > 0 else 0
                total_actualizado = total_usd * float(tasa_actual)
                
                # Manejo de fecha
                fecha_venta = deuda.get('fecha_venta', '')
                if fecha_venta:
                    if isinstance(fecha_venta, str):
                        fecha_venta = fecha_venta.split(' ')[0]
                    elif hasattr(fecha_venta, 'strftime'):
                        fecha_venta = fecha_venta.strftime('%d/%m/%Y')
                    else:
                        fecha_venta = str(fecha_venta)[:10]
                else:
                    fecha_venta = 'Fecha no disponible'
                
                draw.text((45, y), f"Venta del: {fecha_venta}", font=font_normal, fill=color_primario)
                y += 22
                
                # Productos
                productos = deuda.get('productos', [])
                if productos and len(productos) > 0:
                    prod_text = ""
                    for idx, p in enumerate(productos[:2]):
                        desc = p.get('descripcion', 'Producto')
                        cant = p.get('cantidad', 1)
                        if idx > 0:
                            prod_text += ", "
                        prod_text += f"{desc} x{cant}"
                    if len(productos) > 2:
                        prod_text += f" +{len(productos)-2} más"
                    draw.text((45, y), prod_text, font=font_pequeno, fill=color_gris)
                else:
                    draw.text((45, y), "Sin detalles de productos", font=font_pequeno, fill=color_gris)
                y += 20
                
                draw.text((45, y), f"Deuda original: Bs {total_deuda:,.2f}", font=font_normal, fill=color_texto)
                draw.text((280, y), f"Tasa venta: Bs {tasa_deuda:,.2f}", font=font_normal, fill=color_texto)
                y += 18
                
                draw.text((45, y), f"Cancelado HOY: Bs {total_actualizado:,.2f}", font=font_normal, fill=color_exito)
                draw.text((280, y), f"(USD ${total_usd:,.2f} x Tasa Bs {tasa_actual:,.2f})", font=font_pequeno, fill=color_gris)
                y += 25
                
                draw.line([45, y, ancho-45, y], fill=color_gris, width=1)
                y += 15
                
                total_general_usd += total_usd
                total_general_bs += total_actualizado
                
            except Exception as e:
                print(f"Error procesando deuda {i}: {e}")
                continue
        
        # Total general
        y += 10
        draw.rectangle([30, y-10, ancho-30, y+40], fill=color_exito)
        
        total_texto = f"TOTAL CANCELADO: Bs {total_general_bs:,.2f}"
        try:
            total_bbox = draw.textbbox((0, 0), total_texto, font=font_subtitulo)
            total_ancho = total_bbox[2] - total_bbox[0]
        except:
            total_ancho = 300
        
        draw.text(((ancho - total_ancho) // 2, y), total_texto, font=font_subtitulo, fill=(255,255,255))
        y += 55
        
        usd_texto = f"(Equivalente a USD ${total_general_usd:,.2f})"
        try:
            usd_bbox = draw.textbbox((0, 0), usd_texto, font=font_pequeno)
            usd_ancho = usd_bbox[2] - usd_bbox[0]
        except:
            usd_ancho = 200
        
        draw.text(((ancho - usd_ancho) // 2, y), usd_texto, font=font_pequeno, fill=color_gris)
        
        # Footer
        y = alto - 60
        draw.line([30, y, ancho-30, y], fill=color_gris, width=1)
        
        mensaje_success = "✓ Todas las deudas han sido canceladas"
        draw.text((30, y+15), mensaje_success, font=font_pequeno, fill=color_exito)
        
        mensaje_gracias = "Gracias por confiar en nosotros!"
        try:
            gracias_bbox = draw.textbbox((0, 0), mensaje_gracias, font=font_pequeno)
            gracias_ancho = gracias_bbox[2] - gracias_bbox[0]
        except:
            gracias_ancho = 200
        
        draw.text((ancho - gracias_ancho - 30, y+15), mensaje_gracias, font=font_pequeno, fill=color_gris)
        
        # Convertir a bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        return img_bytes
        
    except Exception as e:
        print(f"Error generando recibo de cancelación global: {e}")
        import traceback
        traceback.print_exc()
        
        # Generar un recibo de emergencia simple
        from PIL import Image, ImageDraw
        
        img = Image.new('RGB', (600, 400), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "RECIBO DE CANCELACIÓN", fill=(0,0,0))
        draw.text((50, 100), f"Cliente: {datos_cliente.get('nombre', 'N/A')}", fill=(0,0,0))
        draw.text((50, 150), f"Total Cancelado: Bs {sum(d.get('total',0) for d in lista_deudas):,.2f}", fill=(0,0,0))
        draw.text((50, 200), f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", fill=(0,0,0))
        draw.text((50, 250), "Documento generado automáticamente", fill=(100,100,100))
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes

# ========== API: CANCELACIÓN GLOBAL DE CRÉDITOS ==========
@app.route('/api/creditos/cancelar_global', methods=['POST'])
def cancelar_creditos_global():
    """Cancela TODAS las deudas de un cliente de una sola vez - Versión PostgreSQL/Supabase"""
    try:
        data = request.json
        cliente_id = data.get('cliente_id')
        tasa_actual = data.get('tasa_actual', 0)

        if not cliente_id:
            return jsonify({'error': 'Cliente no especificado'}), 400

        if tasa_actual <= 0:
            return jsonify({'error': 'Tasa actual inválida'}), 400

        # Conectar a Supabase
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Iniciar transacción
            cursor.execute("BEGIN")

            # Obtener deudas pendientes del cliente (adaptado para PostgreSQL)
            cursor.execute("""
                SELECT 
                    v.id,
                    v.fecha_venta,
                    v.total,
                    v.tasa,
                    v.monto_pagado,
                    c.nombre as cliente_nombre,
                    c.telefono,
                    c.direccion
                FROM ventas v
                JOIN clientes c ON v.id_cliente = c.id
                WHERE v.id_cliente = %s
                AND v.credito = true
                AND (v.pagado = false OR v.pagado IS NULL)
                AND (v.cancelada = false OR v.cancelada IS NULL)
                AND (v.monto_pagado IS NULL OR v.monto_pagado < v.total)
            """, (cliente_id,))

            deudas = cursor.fetchall()

            if not deudas:
                cursor.execute("ROLLBACK")
                conn.close()
                return jsonify({'error': 'No hay deudas pendientes para este cliente'}), 400

            total_cancelado_bs = 0
            deudas_canceladas = []
            now = datetime.now()

            for deuda in deudas:
                # Extraer datos
                id_venta = deuda[0]
                fecha_venta = deuda[1]
                total_venta = float(deuda[2])
                tasa_venta = float(deuda[3]) if deuda[3] else 0
                monto_pagado_anterior = float(deuda[4]) if deuda[4] else 0
                
                # Calcular monto a cancelar
                if tasa_venta > 0:
                    total_usd = total_venta / tasa_venta
                else:
                    total_usd = total_venta / 55.0  # Tasa por defecto
                
                monto_cancelar = total_usd * tasa_actual
                
                # Insertar registro de pago (tabla pagos_credito)
                cursor.execute("""
                    INSERT INTO pagos_credito (id_venta, monto_pagado, tasa_pago, observacion, fecha_pago)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    id_venta,
                    monto_cancelar,
                    tasa_actual,
                    f'CANCELACIÓN GLOBAL - {now.strftime("%Y-%m-%d %H:%M:%S")}',
                    now
                ))
                
                # Actualizar la venta
                nuevo_monto_pagado = monto_pagado_anterior + monto_cancelar
                
                cursor.execute("""
                    UPDATE ventas
                    SET pagado = true,
                        monto_pagado = %s,
                        saldo_pendiente = 0,
                        pagado_parcial = false,
                        fecha_pago = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (nuevo_monto_pagado, now, now, id_venta))
                
                total_cancelado_bs += monto_cancelar
                
                # Obtener productos de la venta
                cursor.execute("""
                    SELECT p.descripcion, dv.cantidad
                    FROM detalles_venta dv
                    JOIN productos p ON dv.id_producto = p.id
                    WHERE dv.id_venta = %s
                """, (id_venta,))
                productos = cursor.fetchall()
                
                # Formatear fecha para mostrar
                fecha_venta_str = fecha_venta.strftime('%Y-%m-%d %H:%M:%S') if fecha_venta and hasattr(fecha_venta, 'strftime') else str(fecha_venta)
                
                deudas_canceladas.append({
                    'id_venta': id_venta,
                    'fecha_venta': fecha_venta_str,
                    'total': total_venta,
                    'tasa': tasa_venta,
                    'productos': [{'descripcion': p[0], 'cantidad': p[1]} for p in productos]
                })
            
            # Obtener datos del cliente para el recibo
            cliente_nombre = deudas[0][5]  # cliente_nombre está en índice 5
            cliente_telefono = deudas[0][6] if deudas[0][6] else ''
            
            datos_cliente = {
                'id': cliente_id,
                'nombre': cliente_nombre,
                'telefono': cliente_telefono,
                'direccion': deudas[0][7] if len(deudas[0]) > 7 and deudas[0][7] else ''
            }
            
            # Commit de la transacción
            cursor.execute("COMMIT")
            conn.close()
            
            # Generar recibo
            recibo_img = generar_recibo_cancelacion_global(datos_cliente, deudas_canceladas, tasa_actual)
            
            return send_file(
                recibo_img,
                mimetype='image/png',
                as_attachment=False,
                download_name=f"cancelacion_global_{datos_cliente['nombre'].replace(' ', '_')}_{now.strftime('%Y%m%d_%H%M%S')}.png"
            )
            
        except Exception as e:
            # Rollback en caso de error
            cursor.execute("ROLLBACK")
            conn.close()
            raise e
            
    except Exception as e:
        print(f"❌ Error en cancelación global: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ========== API: PAGAR CRÉDITO CON TASA ACTUAL ==========
@app.route('/api/creditos/pagar', methods=['POST'])
def api_pagar_credito_con_tasa():
    """Registra pago de un crédito individual con la tasa actual - Versión PostgreSQL"""
    try:
        data = request.json
        id_venta = data.get('id_venta')
        monto = data.get('monto', 0)
        observacion = data.get('observacion', '')
        tasa_actual = data.get('tasa_actual', 0)

        # Validaciones
        if not id_venta:
            return jsonify({'success': False, 'error': 'ID de venta requerido'}), 400
        
        if monto <= 0:
            return jsonify({'success': False, 'error': 'Monto debe ser mayor a 0'}), 400
        
        if tasa_actual <= 0:
            return jsonify({'success': False, 'error': 'Tasa actual inválida'}), 400

        # Llamar a la función de pago (adaptada para PostgreSQL)
        resultado = pagar_credito_con_tasa(id_venta, monto, observacion, tasa_actual)

        if resultado.get('success'):
            # Preparar datos para el recibo
            datos_recibo = {
                'cliente': resultado.get('cliente_nombre', 'Cliente'),
                'telefono': resultado.get('cliente_telefono', ''),
                'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'productos': resultado.get('productos', []),
                'total': float(resultado.get('total_venta', 0)),
                'tasa': float(resultado.get('tasa_venta', 0)),
                'tasa_actual': float(resultado.get('tasa_aplicada', tasa_actual)),
                'tipo': 'CRÉDITO',
                'saldo_pendiente': float(resultado.get('saldo_pendiente', 0)),
                'monto_pagado': float(monto)
            }

            # Generar recibo
            try:
                img_bytes = generar_recibo_profesional(datos_recibo)
                
                return send_file(
                    img_bytes,
                    mimetype='image/png',
                    as_attachment=False,
                    download_name=f"recibo_pago_{id_venta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
            except Exception as e:
                print(f"Error generando recibo: {e}")
                # Si falla el recibo, igual retornar éxito
                return jsonify({
                    'success': True, 
                    'mensaje': resultado.get('mensaje', 'Pago registrado exitosamente'),
                    'sin_recibo': True
                }), 200
        else:
            return jsonify(resultado), 400

    except Exception as e:
        print(f"❌ Error en pago de crédito: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API: CRÉDITOS (Versión PostgreSQL) ==========

@app.route('/api/creditos/pagar-parcial', methods=['POST'])
def api_pagar_credito_parcial():
    """Registra un pago parcial de un crédito - Versión PostgreSQL"""
    try:
        data = request.json
        id_venta = data.get('id_venta')
        monto = data.get('monto')
        observacion = data.get('observacion', '')
        
        # Validaciones
        if not id_venta:
            return jsonify({'success': False, 'error': 'ID de venta requerido'}), 400
        
        if not monto or float(monto) <= 0:
            return jsonify({'success': False, 'error': 'Monto debe ser mayor a 0'}), 400
        
        resultado = pagar_credito_parcial(int(id_venta), float(monto), observacion)
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en pago parcial: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/creditos/historial/<int:id_venta>', methods=['GET'])
def api_historial_pagos(id_venta):
    """Obtiene el historial de pagos de un crédito - Versión PostgreSQL"""
    try:
        resultado = obtener_historial_pagos(id_venta)
        return jsonify(resultado)
    except Exception as e:
        print(f"❌ Error en historial de pagos: {str(e)}")
        return jsonify({'error': str(e), 'historial': []}), 500


@app.route('/api/creditos/nota-debito/<int:id_venta>', methods=['GET'])
def api_generar_nota_debito(id_venta):
    """Genera nota de débito para un crédito - Versión PostgreSQL"""
    try:
        resultado = generar_nota_debito(id_venta)
        return jsonify(resultado)
    except Exception as e:
        print(f"❌ Error generando nota de débito: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/creditos/estado/<int:id_venta>', methods=['GET'])
def api_estado_credito(id_venta):
    """Obtiene el estado detallado de un crédito - Versión PostgreSQL"""
    try:
        resultado = obtener_estado_credito(id_venta)
        if resultado:
            return jsonify(resultado)
        else:
            return jsonify({'error': 'Crédito no encontrado'}), 404
    except Exception as e:
        print(f"❌ Error obteniendo estado del crédito: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/creditos/reporte', methods=['GET'])
def api_reporte_creditos():
    """Genera reporte general de todos los créditos - Versión PostgreSQL"""
    try:
        creditos = ventas_con_retraso()
        total_deuda = sum(float(c.get('saldo_pendiente', 0)) for c in creditos if c.get('saldo_pendiente'))
        
        return jsonify({
            'success': True,
            'total_creditos': len(creditos),
            'total_deuda_pendiente': total_deuda,
            'creditos': creditos
        })
    except Exception as e:
        print(f"❌ Error en reporte de créditos: {str(e)}")
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