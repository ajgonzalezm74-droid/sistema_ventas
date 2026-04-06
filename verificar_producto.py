import sqlite3

conn = sqlite3.connect('ventas.db')
cursor = conn.cursor()

print("=== PRODUCTOS ===")
cursor.execute("SELECT id, descripcion FROM productos")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Nombre: {row[1]}")

print("\n=== INVENTARIO (costo en USD) ===")
cursor.execute("SELECT id_producto, costo, cantidad FROM inventario")
for row in cursor.fetchall():
    print(f"Producto ID: {row[0]}, Costo USD: {row[1]}, Stock: {row[2]}")

# Si el costo es 0, actualizarlo
cursor.execute("UPDATE inventario SET costo = 10.00 WHERE costo = 0 OR costo IS NULL")
conn.commit()
print("\n✅ Costos actualizados a USD 10.00 donde estaban en 0")

conn.close()
