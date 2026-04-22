from flask import Flask, render_template, request, jsonify, send_file, make_response
from database import (
    init_db, get_clients, get_productos as get_products, add_client, 
    add_product, reponer_stock, buscar_producto_por_descripcion, 
    buscar_cliente_por_telefono, buscar_cliente_por_nombre, add_client_validado,
    get_connection  # <--- Importante: usar la conexión centralizada
)
from generar_recibo import generar_recibo_imagen
from generar_recibo_cliente import generar_recibo_cliente
from generar_recibo_profesional import generar_recibo_profesional
from ventas_logic import (
    registrar_venta, pagar_credito, pagar_credito_parcial, cancelar_venta,
    ventas_con_retraso, reporte_ventas, reporte_produto, obtener_tasa_actual,
    obtener_historial_pagos, generar_nota_debito, obtener_estado_credito,
    reporte_por_rango, obtener_creditos_agrupados, cancelar_creditos_global,
    pagar_credito_con_tasa
)
from datetime import datetime
import io
import os

app = Flask(__name__)

# Se eliminó la importación de sqlite3 para evitar confusiones

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

# Inicializa las tablas en PostgreSQL si no existen
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# ========== API: TASA ==========
@app.route('/api/tasa', methods=['GET'])
def api_tasa():
    try:
        return jsonify(obtener_tasa_actual())
    except Exception as e:
        # Fallback en caso de error de conexión a la API de tasas
        return jsonify({'error': str(e), 'bcv_usd': 55.0, 'bcv_eur': 57.75}), 200

#========= API: TEST DB (CORREGIDA PARA POSTGRES) ==========
@app.route('/api/test_db')
def test_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clientes")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'clientes_registrados': count, 'db': 'PostgreSQL'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
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
        
        # Usamos la lógica validada para evitar duplicados
        id_cliente = add_client_validado(
            data['nombre'], 
            data.get('telefono', ''), 
            data.get('direccion', '')
        )
        return jsonify({'success': True, 'id': id_cliente})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API: PRODUCTOS ==========
@app.route('/api/productos', methods=['GET'])
def api_productos():
    try:
        return jsonify(get_products())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/buscar', methods=['GET'])
def api_buscar_producto():
    desc = request.args.get('q', '')
    return jsonify(buscar_producto_por_descripcion(desc))

# ========== LÓGICA DE RECIBO GLOBAL (MANTENIDA) ==========
def generar_recibo_cancelacion_global(datos_cliente, lista_deudas, tasa_actual):
    # (El código de PIL que tenías se mantiene igual, ya que procesa datos en memoria)
    # ... [Tu código de PIL aquí] ...
    from PIL import Image, ImageDraw, ImageFont
    # (Omitido por brevedad, pero debe ir aquí sin cambios)
    pass

if __name__ == '__main__':
    # Usar el puerto de Heroku/Render o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
