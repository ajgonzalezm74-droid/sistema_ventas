import sqlite3

conn = sqlite3.connect('ventas.db')
cursor = conn.cursor()

# Obtener costo del producto tizana (ID asumiendo 1)
cursor.execute("SELECT costo FROM inventario WHERE id_producto = 1")
costo = cursor.fetchone()
if costo:
    costo_usd = costo[0]
    tasa_venta = 55.0
    cantidad = 1
    total_calculado = costo_usd * tasa_venta * cantidad
    
    print(f"Costo USD: {costo_usd}, Tasa: {tasa_venta}, Total: {total_calculado}")
    
    # Actualizar venta ID 1
    cursor.execute("UPDATE ventas SET total = ?, tasa = ? WHERE id = 1", (total_calculado, tasa_venta))
    
    # Actualizar detalles_venta
    cursor.execute("UPDATE detalles_venta SET precio_unitario = ?, subtotal = ? WHERE id_venta = 1", (total_calculado, total_calculado))
    
    conn.commit()
    print("✅ Venta corregida")
else:
    print("Producto no encontrado")

conn.close()
