import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB_NAME = "ventas.db"

# Usar la dirección IPv4 de Supabase
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:A6f%5BpVeh%23%23.@aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require')

def get_connection():
    return psycopg2.connect(DATABASE_URL)


def obtener_columnas_tabla(cursor, tabla):
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{tabla}'
    """)
    return [row[0] for row in cursor.fetchall()]


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Tabla clientes
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
        print("✅ Columna 'direccion' agregada a la tabla clientes")

    # 2. Tabla productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            descripcion TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # 3. Tabla inventario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id_producto INTEGER PRIMARY KEY,
            cantidad INTEGER DEFAULT 0,
            costo REAL DEFAULT 0,
            devolucion INTEGER DEFAULT 0,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_producto) REFERENCES productos(id)
        )
    ''')
    
    # 4. Tabla ventas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id SERIAL PRIMARY KEY,
            id_cliente INTEGER,
            fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total REAL DEFAULT 0,
            tasa REAL,
            credito BOOLEAN DEFAULT FALSE,
            pagado BOOLEAN DEFAULT FALSE,
            cancelada BOOLEAN DEFAULT FALSE,
            fecha_pago TIMESTAMP,
            tasa_pago REAL,
            FOREIGN KEY (id_cliente) REFERENCES clientes(id)
        )
    ''')
    
    columnas_ventas = obtener_columnas_tabla(cursor, "ventas")
    if 'saldo_pendiente' not in columnas_ventas:
        cursor.execute("ALTER TABLE ventas ADD COLUMN saldo_pendiente REAL DEFAULT 0")
        print("✅ Columna 'saldo_pendiente' agregada")
    if 'pagado_parcial' not in columnas_ventas:
        cursor.execute("ALTER TABLE ventas ADD COLUMN pagado_parcial BOOLEAN DEFAULT FALSE")
        print("✅ Columna 'pagado_parcial' agregada")
    
    # 5. Tabla detalles_venta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalles_venta (
            id SERIAL PRIMARY KEY,
            id_venta INTEGER,
            id_producto INTEGER,
            cantidad INTEGER,
            precio_unitario REAL,
            subtotal REAL,
            FOREIGN KEY (id_venta) REFERENCES ventas(id),
            FOREIGN KEY (id_producto) REFERENCES productos(id)
        )
    ''')
    
    # 6. Tabla tasas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasas (
            id SERIAL PRIMARY KEY,
            moneda TEXT,
            valor REAL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 7. Tabla pagos_credito
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos_credito (
            id SERIAL PRIMARY KEY,
            id_venta INTEGER,
            monto_pagado REAL,
            tasa_pago REAL,
            fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            observacion TEXT,
            FOREIGN KEY (id_venta) REFERENCES ventas(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Base de datos PostgreSQL sincronizada")


# ========== CRUD Clientes ==========
def add_client(nombre, telefono):
    """Agrega un nuevo cliente (sin dirección)"""
    return add_client_validado(nombre, telefono, "")


def add_client_validado(nombre, telefono, direccion=""):
    """Agrega un nuevo cliente verificando duplicados"""
    try:
        if telefono:
            existente = buscar_cliente_por_telefono(telefono)
            if existente:
                return {
                    "success": False, 
                    "error": f"Ya existe un cliente con el teléfono {telefono}",
                    "cliente_existente": existente
                }
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO clientes (nombre, telefono, direccion) VALUES (%s, %s, %s) RETURNING id", 
            (nombre, telefono, direccion)
        )
        id_cliente = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return {"success": True, "id": id_cliente}
    except Exception as e:
        print(f"❌ Error en add_client_validado: {e}")
        return {"success": False, "error": str(e)}


def get_clients(activo=True):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE activo = %s ORDER BY nombre ASC", (activo,))
        clientes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in clientes]
    except Exception as e:
        return []


def buscar_cliente_por_telefono(telefono):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE telefono = %s AND activo = TRUE", (telefono,))
        cliente = cursor.fetchone()
        conn.close()
        return dict(cliente) if cliente else None
    except Exception as e:
        return None


def buscar_cliente_por_nombre(nombre):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE nombre LIKE %s AND activo = TRUE", (f'%{nombre}%',))
        clientes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in clientes]
    except Exception as e:
        return []


# ========== CRUD Productos ==========
def buscar_producto_por_descripcion(descripcion):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM productos WHERE descripcion = %s AND activo = TRUE", (descripcion,))
        producto = cursor.fetchone()
        conn.close()
        return dict(producto) if producto else None
    except Exception as e:
        return None


def add_product(descripcion, costo, stock=0):
    try:
        producto_existente = buscar_producto_por_descripcion(descripcion)
        if producto_existente:
            return {
                "success": False, 
                "error": f"El producto '{descripcion}' ya existe",
                "id": producto_existente['id']
            }
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO productos (descripcion) VALUES (%s) RETURNING id", (descripcion,))
        id_producto = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO inventario (id_producto, costo, cantidad) VALUES (%s, %s, %s)",
            (id_producto, costo, stock)
        )
        conn.commit()
        conn.close()
        return {"success": True, "id": id_producto}
    except Exception as e:
        return {"success": False, "error": str(e)}


def reponer_stock(id_producto, cantidad, costo=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM productos WHERE id = %s AND activo = TRUE", (id_producto,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": "Producto no encontrado"}
        
        cursor.execute("SELECT cantidad FROM inventario WHERE id_producto = %s", (id_producto,))
        inventario = cursor.fetchone()
        
        if inventario:
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s WHERE id_producto = %s", (cantidad, id_producto))
        else:
            cursor.execute("INSERT INTO inventario (id_producto, cantidad, costo) VALUES (%s, %s, %s)", (id_producto, cantidad, costo or 0))
        
        if costo is not None and costo > 0:
            cursor.execute("UPDATE inventario SET costo = %s WHERE id_producto = %s", (costo, id_producto))
        
        conn.commit()
        conn.close()
        return {"success": True, "nuevo_stock": cantidad}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_productos():
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT p.*, i.cantidad, i.costo 
            FROM productos p 
            LEFT JOIN inventario i ON p.id = i.id_producto 
            WHERE p.activo = TRUE
            ORDER BY p.descripcion ASC
        ''')
        productos = cursor.fetchall()
        conn.close()
        return [dict(row) for row in productos]
    except Exception as e:
        return []


# ========== ALIAS PARA COMPATIBILIDAD ==========
get_products = get_productosDB_NAME = "ventas.db"
