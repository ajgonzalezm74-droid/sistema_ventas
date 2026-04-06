import sqlite3

DB_NAME = "ventas.db"

def migrar_base_datos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Verificar si la columna 'total' existe en ventas
    cursor.execute("PRAGMA table_info(ventas)")
    columnas = [col[1] for col in cursor.fetchall()]
    
    if 'total' not in columnas:
        print("📌 Agregando columna 'total' a la tabla ventas...")
        
        # Crear tabla temporal
        cursor.execute('''
            CREATE TABLE ventas_temp (
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
        
        # Copiar datos existentes (si hay)
        try:
            cursor.execute('''
                INSERT INTO ventas_temp (id, id_cliente, fecha_venta, tasa, credito, pagado, cancelada, fecha_pago, tasa_pago)
                SELECT id, id_cliente, fecha_venta, tasa, credito, pagado, cancelada, fecha_pago, tasa_pago
                FROM ventas
            ''')
            print("✅ Datos copiados")
        except:
            print("⚠️ No hay datos para copiar")
        
        # Eliminar tabla antigua
        cursor.execute("DROP TABLE ventas")
        
        # Renombrar tabla nueva
        cursor.execute("ALTER TABLE ventas_temp RENAME TO ventas")
        
        print("✅ Migración completada")
    
    # Verificar si existe la tabla detalles_venta
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='detalles_venta'")
    if not cursor.fetchone():
        print("📌 Creando tabla detalles_venta...")
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
        print("✅ Tabla detalles_venta creada")
    
    conn.commit()
    conn.close()
    print("✅ Base de datos actualizada")

if __name__ == "__main__":
    migrar_base_datos()