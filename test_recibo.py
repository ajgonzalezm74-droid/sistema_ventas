# Cambia esto:
# from sistema_ventas.generar_recibo import generar_recibo_imagen

# Por esto:
from generar_recibo import generar_recibo_imagen

# Datos de prueba
datos_prueba = {
    'cliente': 'María González',
    'telefono': '04141234567',
    'fecha': '2025-04-04',
    'productos': [
        {'descripcion': 'Zapatos Deportivos', 'cantidad': 1, 'precio': 2750.00},
        {'descripcion': 'Camisa Polo', 'cantidad': 2, 'precio': 1375.00}
    ],
    'total': 5500.00,
    'tasa': 55.0,
    'tipo': 'crédito',
    'saldo_pendiente': 2750.00,
    'id_venta': 1
}

ruta, nombre = generar_recibo_imagen(datos_prueba)
print(f"✅ Recibo generado: {ruta}")