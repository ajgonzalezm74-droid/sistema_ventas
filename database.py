import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# URL de respaldo (asegúrate de que en el panel de Render la variable DATABASE_URL use el puerto 6543)
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:A6f%5BpVeh%23%23.@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require')

def get_connection():
    """Obtiene conexión PostgreSQL con ajustes de red para Render/Supabase"""
    return psycopg2.connect(DATABASE_URL, gssencmode="disable", connect_timeout=10)

def obtener_columnas_tabla(cursor, tabla):
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{tabla}'
    """)
    return [row[0] for row in cursor.fetchall()]

def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Clientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                telefono TEXT,
                direccion TEXT,
                activo BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        columnas_clientes = obtener_columnas_tabla(cursor, "clientes")
        if 'direccion' not in columnas_clientes:
            cursor.execute("ALTER TABLE clientes ADD COLUMN direccion TEXT")

        # 2. Productos e Inventario
        cursor.execute('''CREATE TABLE IF NOT EXISTS productos (id SERIAL PRIMARY KEY, descripcion TEXT NOT NULL, fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP, activo BOOLEAN DEFAULT TRUE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS inventario (id_producto INTEGER PRIMARY KEY, cantidad INTEGER DEFAULT 0, costo REAL DEFAULT 0, devolucion INTEGER DEFAULT 0, fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (id_producto) REFERENCES productos(id))''')
        
        # 3. Ventas y Saldo
        cursor.execute('''CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, id_cliente INTEGER, fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total REAL DEFAULT 0, tasa REAL, credito BOOLEAN DEFAULT FALSE, pagado BOOLEAN DEFAULT FALSE, cancelada BOOLEAN DEFAULT FALSE, fecha_pago TIMESTAMP, tasa_pago REAL, FOREIGN KEY (id_cliente) REFERENCES clientes(id))''')
        
        columnas_ventas = obtener_columnas_tabla(cursor, "ventas")
        if 'saldo_pendiente' not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN saldo_pendiente REAL DEFAULT 0")
        if 'pagado_parcial' not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN pagado_parcial BOOLEAN DEFAULT FALSE")
        
        # 4. Detalles, Tasas y Pagos
        cursor.execute('''CREATE TABLE IF NOT EXISTS detalles_venta (id SERIAL PRIMARY KEY, id_venta INTEGER, id_producto INTEGER, cantidad INTEGER, precio_unitario REAL, subtotal REAL, FOREIGN KEY (id_venta) REFERENCES ventas(id), FOREIGN KEY (id_producto) REFERENCES productos(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasas (id SERIAL PRIMARY KEY, moneda TEXT, valor REAL, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pagos_credito (id SERIAL PRIMARY KEY, id_venta INTEGER, monto_pagado REAL, tasa_pago REAL, fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP, observacion TEXT, FOREIGN KEY (id_venta) REFERENCES ventas(id))''')
        
        conn.commit()
        conn.close()
        print("✅ Base de datos PostgreSQL sincronizada")
    except Exception as e:
        print(f"❌ Error inicializando DB: {e}")

# ========== CRUD CLIENTES ==========
def add_client_validado(nombre, telefono, direccion=""):
    try:
        if telefono:
            existente = buscar_cliente_por_telefono(telefono)
            if existente:
                return {"success": False, "error": f"Teléfono ya registrado", "cliente_existente": existente}
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nombre, telefono, direccion) VALUES (%s, %s, %s) RETURNING id", (nombre, telefono, direccion))
        id_cliente = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return {"success": True, "id": id_cliente}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_clients(activo=True):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE activo = %s ORDER BY nombre ASC", (activo,))
        res = cursor.fetchall()
        conn.close()
        return [dict(row) for row in res]
    except: return []

def buscar_cliente_por_telefono(telefono):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE telefono = %s AND activo = TRUE", (telefono,))
        res = cursor.fetchone()
        conn.close()
        return dict(res) if res else None
    except: return None

# ========== CRUD PRODUCTOS ==========
def add_product(descripcion, costo, stock=0):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO productos (descripcion) VALUES (%s) RETURNING id", (descripcion,))
        id_prod = cursor.fetchone()[0]
        cursor.execute("INSERT INTO inventario (id_producto, costo, cantidad) VALUES (%s, %s, %s)", (id_prod, costo, stock))
        conn.commit()
        conn.close()
        return {"success": True, "id": id_prod}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_productos():
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT p.id, p.descripcion, i.cantidad, i.costo 
            FROM productos p 
            JOIN inventario i ON p.id = i.id_producto 
            WHERE p.activo = TRUE ORDER BY p.descripcion ASC
        """)
        res = cursor.fetchall()
        conn.close()
        return [dict(row) for row in res]
    except: return []

def reponer_stock(id_producto, cantidad, costo=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if costo:
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s, costo = %s WHERE id_producto = %s", (cantidad, costo, id_producto))
        else:
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s WHERE id_producto = %s", (cantidad, id_producto))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
