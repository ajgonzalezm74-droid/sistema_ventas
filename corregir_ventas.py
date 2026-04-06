import sqlite3

conn = sqlite3.connect('ventas.db')
cursor = conn.cursor()

# Ver las ventas actuales
print("📊 Ventas actuales:")
cursor.execute("SELECT id, id_cliente, total, credito, pagado FROM ventas")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}, Cliente: {row[1]}, Total: {row[2]}, Crédito: {row[3]}, Pagado: {row[4]}")

# Corregir venta ID 2 (coco) - debe ser contado
cursor.execute("UPDATE ventas SET credito = 0, pagado = 1 WHERE id = 2")
print("\n✅ Venta ID 2 corregida (contado pagado)")

# Verificar detalles_venta
print("\n📊 Detalles de venta:")
cursor.execute("""
    SELECT dv.id_venta, p.descripcion, dv.cantidad, dv.subtotal 
    FROM detalles_venta dv
    JOIN productos p ON dv.id_producto = p.id
""")
for row in cursor.fetchall():
    print(f"  Venta ID: {row[0]}, Producto: {row[1]}, Cantidad: {row[2]}, Subtotal: {row[3]}")

conn.commit()
conn.close()
print("\n✅ Corrección completada")
