import sqlite3

conn = sqlite3.connect('ventas.db')
cursor = conn.cursor()

# Ver ventas actuales
print("=== VENTAS ACTUALES ===")
cursor.execute("SELECT id, id_cliente, total, tasa, credito, pagado FROM ventas")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Cliente: {row[1]}, Total: {row[2]}, Tasa: {row[3]}, Credito: {row[4]}, Pagado: {row[5]}")

# Ver productos
print("\n=== PRODUCTOS ===")
cursor.execute("SELECT id, descripcion, activo FROM productos")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Producto: {row[1]}, Activo: {row[2]}")

# Ver inventario
print("\n=== INVENTARIO ===")
cursor.execute("SELECT id_producto, costo, cantidad FROM inventario")
for row in cursor.fetchall():
    print(f"Producto ID: {row[0]}, Costo USD: {row[1]}, Stock: {row[2]}")

# Ver detalles_venta
print("\n=== DETALLES VENTA ===")
cursor.execute("SELECT id_venta, id_producto, cantidad, subtotal FROM detalles_venta")
for row in cursor.fetchall():
    print(f"Venta ID: {row[0]}, Producto: {row[1]}, Cantidad: {row[2]}, Subtotal: {row[3]}")

conn.close()
