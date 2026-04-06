import sqlite3

conn = sqlite3.connect('ventas.db')
cursor = conn.cursor()

print("=== VENTAS ===")
cursor.execute("SELECT id, id_cliente, total, credito, pagado, cancelada FROM ventas")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, ClienteID: {row[1]}, Total: {row[2]}, Credito: {row[3]}, Pagado: {row[4]}, Cancelada: {row[5]}")

print("\n=== CLIENTES ===")
cursor.execute("SELECT id, nombre, telefono FROM clientes")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Nombre: {row[1]}, Telefono: {row[2]}")

print("\n=== DETALLES VENTA ===")
cursor.execute("SELECT id_venta, id_producto, cantidad, subtotal FROM detalles_venta")
for row in cursor.fetchall():
    print(f"VentaID: {row[0]}, ProductoID: {row[1]}, Cantidad: {row[2]}, Subtotal: {row[3]}")

conn.close()
