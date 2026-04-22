import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Para compatibilidad con ventas_logic.py
DB_NAME = "ventas.db"

# ✅ URL CORRECTA del Session Pooler
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres.hdmothdsswjtfniqvgay:A6f%5BpVeh%23%23.@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require')

def get_connection():
    """Obtiene una conexión a la base de datos PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Inicializa todas las tablas de la base de datos"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Tabla clientes
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
        
        # Tabla productos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Tabla inventario
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
        
        # Tabla ventas
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
                saldo_pendiente REAL DEFAULT 0,
                pagado_parcial BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (id_cliente) REFERENCES clientes(id)
            )
        ''')
        
        # Tabla detalles_venta
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
        
        # Tabla tasas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasas (
                id SERIAL PRIMARY KEY,
                moneda TEXT,
                valor REAL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla pagos_credito
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
        print("✅ Base de datos PostgreSQL inicializada")
        
    except Exception as e:
        print(f"❌ Error inicializando DB: {e}")


# ========== CRUD Clientes ==========
def get_clients(activo=True):
    """Obtiene lista de clientes"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE activo = %s ORDER BY nombre ASC", (activo,))
        clientes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in clientes]
    except Exception as e:
        print(f"❌ Error obteniendo clientes: {e}")
        return []


def add_client(nombre, telefono):
    """Agrega un nuevo cliente"""
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
            "INSERT INTO clientes (nombre, telefono) VALUES (%s, %s) RETURNING id", 
            (nombre, telefono)
        )
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if row is None:
            return {"success": False, "error": "No se pudo crear el cliente"}
        
        return {"success": True, "id": row[0]}
    except Exception as e:
        print(f"❌ Error en add_client_validado: {e}")
        return {"success": False, "error": str(e)}

def buscar_cliente_por_telefono(telefono):
    """Busca un cliente por teléfono"""
    try:
        if not telefono:
            return None
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE telefono = %s AND activo = TRUE", (telefono,))
        cliente = cursor.fetchone()
        conn.close()
        return dict(cliente) if cliente else None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def buscar_cliente_por_nombre(nombre):
    """Busca clientes por nombre (coincidencia parcial)"""
    try:
        if not nombre:
            return []
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM clientes WHERE nombre LIKE %s AND activo = TRUE", (f'%{nombre}%',))
        clientes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in clientes]
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


# ========== CRUD Productos ==========
def get_productos():
    """Obtiene lista de productos con su inventario"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT p.id, p.descripcion, p.activo, 
                   COALESCE(i.cantidad, 0) as cantidad, 
                   COALESCE(i.costo, 0) as costo
            FROM productos p
            LEFT JOIN inventario i ON p.id = i.id_producto
            WHERE p.activo = TRUE
            ORDER BY p.descripcion ASC
        ''')
        productos = cursor.fetchall()
        conn.close()
        return [dict(row) for row in productos]
    except Exception as e:
        print(f"❌ Error obteniendo productos: {e}")
        return []


def buscar_producto_por_descripcion(descripcion):
    """Busca un producto por su descripción exacta"""
    try:
        if not descripcion:
            return None
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM productos WHERE descripcion = %s AND activo = TRUE", (descripcion,))
        producto = cursor.fetchone()
        conn.close()
        return dict(producto) if producto else None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def add_product(descripcion, costo, stock=0):
    """Agrega un nuevo producto"""
    try:
        # Verificar si ya existe
        existente = buscar_producto_por_descripcion(descripcion)
        if existente:
            return {"success": False, "error": f"El producto '{descripcion}' ya existe", "id": existente['id']}
        
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
    """Repone stock de un producto"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT cantidad FROM inventario WHERE id_producto = %s", (id_producto,))
        inventario = cursor.fetchone()
        
        if inventario:
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s WHERE id_producto = %s", (cantidad, id_producto))
        else:
            cursor.execute("INSERT INTO inventario (id_producto, cantidad, costo) VALUES (%s, %s, %s)", 
                          (id_producto, cantidad, costo or 0))
        
        if costo is not None and costo > 0:
            cursor.execute("UPDATE inventario SET costo = %s WHERE id_producto = %s", (costo, id_producto))
        
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== ALIAS PARA COMPATIBILIDAD ==========
get_products = get_productos