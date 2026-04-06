import sqlite3
from datetime import datetime

DB_NAME = "ventas.db"

def obtener_columnas_tabla(cursor, tabla):
    """Obtiene los nombres de las columnas de una tabla"""
    cursor.execute(f"PRAGMA table_info({tabla})")
    return [col[1] for col in cursor.fetchall()]


def init_db():
    """Inicializa todas las tablas de la base de datos"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            activo BOOLEAN DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT 1
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
    
    # Tabla ventas (CON COLUMNA total)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER,
            fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total REAL DEFAULT 0,
            tasa REAL,
            credito BOOLEAN DEFAULT 0,
            pagado BOOLEAN DEFAULT 0,
            cancelada BOOLEAN DEFAULT 0,
            fecha_pago TIMESTAMP,
            tasa_pago REAL,
            FOREIGN KEY (id_cliente) REFERENCES clientes(id)
        )
    ''')
    
    # Verificar columnas existentes en ventas
    columnas_ventas = obtener_columnas_tabla(cursor, "ventas")
    
    # Agregar columna saldo_pendiente si no existe
    if 'saldo_pendiente' not in columnas_ventas:
        cursor.execute("ALTER TABLE ventas ADD COLUMN saldo_pendiente REAL DEFAULT 0")
        print("✅ Columna 'saldo_pendiente' agregada")
    
    # Agregar columna pagado_parcial si no existe
    if 'pagado_parcial' not in columnas_ventas:
        cursor.execute("ALTER TABLE ventas ADD COLUMN pagado_parcial BOOLEAN DEFAULT 0")
        print("✅ Columna 'pagado_parcial' agregada")
    
    # Tabla detalles_venta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalles_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moneda TEXT,
            valor REAL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla para pagos parciales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos_credito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    print("✅ Base de datos inicializada")


# ========== CRUD Clientes ==========
def add_client(nombre, telefono):
    """Agrega un nuevo cliente"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (?, ?)", (nombre, telefono))
        conn.commit()
        id_cliente = cursor.lastrowid
        conn.close()
        print(f"✅ Cliente agregado: {nombre} (ID: {id_cliente})")
        return id_cliente
    except Exception as e:
        print(f"❌ Error agregando cliente: {e}")
        raise


def get_clients(activo=True):
    """Obtiene lista de clientes"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE activo = ?", (1 if activo else 0,))
        clientes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return clientes
    except Exception as e:
        print(f"❌ Error obteniendo clientes: {e}")
        return []


# ========== VALIDACIÓN DE CLIENTES ==========
def buscar_cliente_por_telefono(telefono):
    """Busca un cliente por su número de teléfono"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE telefono = ? AND activo = 1", (telefono,))
        cliente = cursor.fetchone()
        conn.close()
        return dict(cliente) if cliente else None
    except Exception as e:
        print(f"❌ Error buscando cliente por teléfono: {e}")
        return None


def buscar_cliente_por_nombre(nombre):
    """Busca clientes por nombre (coincidencia parcial)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE nombre LIKE ? AND activo = 1", (f'%{nombre}%',))
        clientes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return clientes
    except Exception as e:
        print(f"❌ Error buscando cliente por nombre: {e}")
        return []


def add_client_validado(nombre, telefono):
    """Agrega un nuevo cliente verificando que no exista por teléfono"""
    try:
        # Verificar si ya existe un cliente con ese teléfono
        existente = buscar_cliente_por_telefono(telefono)
        if existente:
            return {
                "success": False, 
                "error": f"Ya existe un cliente con el teléfono {telefono}: {existente['nombre']}",
                "cliente_existente": existente
            }
        
        # Si no existe, agregar nuevo cliente
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (?, ?)", (nombre, telefono))
        conn.commit()
        id_cliente = cursor.lastrowid
        conn.close()
        print(f"✅ Cliente agregado: {nombre} (ID: {id_cliente})")
        return {"success": True, "id": id_cliente}
    except Exception as e:
        print(f"❌ Error agregando cliente: {e}")
        return {"success": False, "error": str(e)}

# ========== CRUD Productos ==========
def buscar_producto_por_descripcion(descripcion):
    """Busca un producto por su descripción exacta"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE descripcion = ? AND activo = 1", (descripcion,))
        producto = cursor.fetchone()
        conn.close()
        return dict(producto) if producto else None
    except Exception as e:
        print(f"❌ Error buscando producto: {e}")
        return None


def add_product(descripcion, costo, stock=0):
    """Agrega un nuevo producto con su inventario inicial (si no existe)"""
    try:
        # Verificar si el producto ya existe
        producto_existente = buscar_producto_por_descripcion(descripcion)
        
        if producto_existente:
            print(f"⚠️ El producto '{descripcion}' ya existe (ID: {producto_existente['id']})")
            return {
                "success": False, 
                "error": f"El producto '{descripcion}' ya existe",
                "id": producto_existente['id']
            }
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO productos (descripcion) VALUES (?)", (descripcion,))
        id_producto = cursor.lastrowid
        
        cursor.execute(
            "INSERT INTO inventario (id_producto, costo, cantidad) VALUES (?, ?, ?)",
            (id_producto, costo, stock)
        )
        conn.commit()
        conn.close()
        print(f"✅ Producto agregado: {descripcion} (ID: {id_producto})")
        return {"success": True, "id": id_producto}
    except Exception as e:
        print(f"❌ Error agregando producto: {e}")
        return {"success": False, "error": str(e)}


def reponer_stock(id_producto, cantidad, costo=None):
    """Repone stock de un producto existente (suma al inventario)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Verificar si el producto existe
        cursor.execute("SELECT id FROM productos WHERE id = ? AND activo = 1", (id_producto,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": "Producto no encontrado"}
        
        # Verificar si existe registro en inventario
        cursor.execute("SELECT cantidad FROM inventario WHERE id_producto = ?", (id_producto,))
        inventario = cursor.fetchone()
        
        if inventario:
            # Actualizar stock existente
            cursor.execute("""
                UPDATE inventario 
                SET cantidad = cantidad + ? 
                WHERE id_producto = ?
            """, (cantidad, id_producto))
        else:
            # Crear registro de inventario si no existe
            cursor.execute("""
                INSERT INTO inventario (id_producto, cantidad, costo) 
                VALUES (?, ?, ?)
            """, (id_producto, cantidad, costo or 0))
        
        # Si se proporciona un nuevo costo, actualizarlo
        if costo is not None and costo > 0:
            cursor.execute("""
                UPDATE inventario 
                SET costo = ? 
                WHERE id_producto = ?
            """, (costo, id_producto))
        
        conn.commit()
        conn.close()
        print(f"✅ Stock repuesto: Producto ID {id_producto} +{cantidad} unidades")
        return {"success": True, "nuevo_stock": cantidad}
    except Exception as e:
        print(f"❌ Error reponiendo stock: {e}")
        return {"success": False, "error": str(e)}


def get_productos():
    """Obtiene lista de productos con su inventario"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, i.cantidad, i.costo 
            FROM productos p 
            LEFT JOIN inventario i ON p.id = i.id_producto 
            WHERE p.activo = 1
            ORDER BY p.descripcion ASC
        ''')
        productos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return productos
    except Exception as e:
        print(f"❌ Error obteniendo productos: {e}")
        return []


# ========== ALIAS PARA COMPATIBILIDAD ==========
get_products = get_productos