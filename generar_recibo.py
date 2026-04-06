from PIL import Image, ImageDraw, ImageFont
import qrcode
from datetime import datetime
import os

def generar_recibo_imagen(datos_venta):
    """
    Genera una imagen de recibo para compartir con el cliente
    
    datos_venta = {
        'cliente': 'María González',
        'telefono': '04141234567',
        'fecha': '2025-04-04',
        'productos': [{'descripcion': 'Zapatos', 'cantidad': 1, 'precio': 45.0}],
        'total': 2750.00,
        'tasa': 55.0,
        'tipo': 'crédito' | 'contado',
        'saldo_pendiente': 0,
        'id_venta': 123
    }
    """
    
    # Configuración de la imagen
    ancho = 800
    alto = 1200
    color_fondo = (255, 255, 255)
    color_primario = (25, 118, 210)  # Azul #1976D2
    color_secundario = (76, 175, 80)  # Verde #4CAF50
    color_texto = (51, 51, 51)
    color_texto_claro = (117, 117, 117)
    
    # Crear imagen
    img = Image.new('RGB', (ancho, alto), color_fondo)
    draw = ImageDraw.Draw(img)
    
    # Intentar cargar fuentes (si no existen, usar default)
    try:
        # Fuentes comunes en Linux
        font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 32)
        font_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 24)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 18)
        font_pequeno = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 14)
    except:
        try:
            # Fuentes alternativas
            font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            font_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_pequeno = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            # Default
            font_titulo = ImageFont.load_default()
            font_subtitulo = ImageFont.load_default()
            font_normal = ImageFont.load_default()
            font_pequeno = ImageFont.load_default()
    
    y = 40
    
    # === HEADER ===
    draw.rectangle([0, 0, ancho, 120], fill=color_primario)
    # Título principal
    draw.text((ancho//2 - 120, 40), "🏪 VENTAS PRO", font=font_titulo, fill=(255,255,255))
    draw.text((ancho//2 - 100, 85), "Comprobante de Pago", font=font_subtitulo, fill=(255,255,255))
    
    y = 150
    
    # === INFORMACIÓN DEL CLIENTE ===
    draw.rectangle([40, y, ancho-40, y+100], outline=color_primario, width=2)
    draw.text((60, y+15), "📋 INFORMACIÓN DEL CLIENTE", font=font_subtitulo, fill=color_primario)
    draw.text((60, y+50), f"Cliente: {datos_venta.get('cliente', 'N/A')}", font=font_normal, fill=color_texto)
    draw.text((60, y+75), f"Teléfono: {datos_venta.get('telefono', 'N/A')}", font=font_normal, fill=color_texto)
    
    y += 130
    
    # === DETALLE DE PRODUCTOS ===
    draw.rectangle([40, y, ancho-40, y+50], fill=color_primario)
    draw.text((60, y+12), "🛒 DETALLE DE LA COMPRA", font=font_subtitulo, fill=(255,255,255))
    
    y += 60
    
    # Cabecera de tabla
    draw.text((60, y), "Producto", font=font_normal, fill=color_texto)
    draw.text((350, y), "Cant.", font=font_normal, fill=color_texto)
    draw.text((450, y), "Precio Bs", font=font_normal, fill=color_texto)
    draw.text((580, y), "Subtotal", font=font_normal, fill=color_texto)
    
    y += 30
    draw.line([40, y, ancho-40, y], fill=color_texto_claro, width=1)
    y += 10
    
    total = 0
    productos = datos_venta.get('productos', [])
    
    if not productos:
        # Si no hay productos, mostrar mensaje
        draw.text((60, y), "No hay productos registrados", font=font_normal, fill=color_texto_claro)
        y += 30
    else:
        for prod in productos:
            descripcion = prod.get('descripcion', 'Producto')[:25]
            cantidad = prod.get('cantidad', 1)
            precio = prod.get('precio', 0)
            subtotal = cantidad * precio
            total += subtotal
            
            draw.text((60, y), descripcion, font=font_normal, fill=color_texto)
            draw.text((350, y), str(cantidad), font=font_normal, fill=color_texto)
            draw.text((450, y), f"Bs {precio:,.2f}", font=font_normal, fill=color_texto)
            draw.text((580, y), f"Bs {subtotal:,.2f}", font=font_normal, fill=color_texto)
            y += 30
    
    draw.line([40, y, ancho-40, y], fill=color_texto_claro, width=1)
    y += 15
    
    # Totales
    draw.text((450, y), "TOTAL:", font=font_subtitulo, fill=color_texto)
    draw.text((580, y), f"Bs {total:,.2f}", font=font_subtitulo, fill=color_secundario)
    
    y += 60
    
    # === INFORMACIÓN DE PAGO ===
    draw.rectangle([40, y, ancho-40, y+120], outline=color_primario, width=2)
    draw.text((60, y+15), "💰 INFORMACIÓN DE PAGO", font=font_subtitulo, fill=color_primario)
    
    tipo_pago = datos_venta.get('tipo', 'contado').upper()
    color_tipo = color_secundario if tipo_pago == 'CONTADO' else (255, 152, 0)
    
    draw.text((60, y+50), f"Tipo: {tipo_pago}", font=font_normal, fill=color_tipo)
    draw.text((60, y+75), f"Tasa BCV: Bs {datos_venta.get('tasa', 0):,.2f}", font=font_normal, fill=color_texto)
    draw.text((350, y+75), f"Fecha: {datos_venta.get('fecha', datetime.now().strftime('%d/%m/%Y'))}", font=font_normal, fill=color_texto)
    
    y += 150
    
    # === SALDO PENDIENTE (si aplica) ===
    saldo = datos_venta.get('saldo_pendiente', 0)
    if saldo > 0:
        draw.rectangle([40, y, ancho-40, y+80], fill=(255, 243, 224))
        draw.text((60, y+15), "⚠️ SALDO PENDIENTE", font=font_subtitulo, fill=(255, 152, 0))
        draw.text((60, y+50), f"Monto pendiente: Bs {saldo:,.2f}", font=font_normal, fill=(255, 152, 0))
        y += 100
    
    # === CÓDIGO QR ===
    try:
        # Generar QR con ID de venta
        qr_data = f"Venta ID: {datos_venta.get('id_venta', 'N/A')}\nCliente: {datos_venta.get('cliente', 'N/A')}\nTotal: Bs {total:,.2f}"
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=color_primario, back_color="white")
        qr_img = qr_img.resize((120, 120))
        
        # Pegar QR en la imagen
        img.paste(qr_img, (ancho-180, y))
        
        # Texto de QR
        draw.text((ancho-180, y+130), "Escanee para", font=font_pequeno, fill=color_texto_claro)
        draw.text((ancho-180, y+150), "ver detalles", font=font_pequeno, fill=color_texto_claro)
    except Exception as e:
        print(f"Error generando QR: {e}")
    
    # === FOOTER ===
    draw.text((ancho//2 - 120, alto-50), "¡Gracias por su compra!", font=font_normal, fill=color_texto_claro)
    draw.text((ancho//2 - 180, alto-25), "Este comprobante es válido como recibo de pago", font=font_pequeno, fill=color_texto_claro)
    
    # Guardar imagen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"recibo_{datos_venta.get('id_venta', timestamp)}_{timestamp}.png"
    ruta = os.path.join("static", "recibos", nombre_archivo)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    img.save(ruta)
    
    return ruta, nombre_archivo


def generar_recibo_pago(id_venta, datos_venta, monto_pagado=None):
    """Genera recibo específico para un pago"""
    
    ancho = 800
    alto = 600
    color_fondo = (255, 255, 255)
    color_primario = (25, 118, 210)
    color_exito = (76, 175, 80)
    
    img = Image.new('RGB', (ancho, alto), color_fondo)
    draw = ImageDraw.Draw(img)
    
    try:
        font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 28)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 18)
    except:
        font_titulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
    
    # Header
    draw.rectangle([0, 0, ancho, 100], fill=color_primario)
    draw.text((ancho//2 - 100, 35), "✅ RECIBO DE PAGO", font=font_titulo, fill=(255,255,255))
    
    y = 140
    
    # Mensaje de confirmación
    draw.text((ancho//2 - 150, y), "¡PAGO REGISTRADO EXITOSAMENTE!", font=font_titulo, fill=color_exito)
    y += 60
    
    # Detalles del pago
    draw.text((60, y), f"Venta ID: {id_venta}", font=font_normal, fill=color_texto)
    y += 35
    draw.text((60, y), f"Cliente: {datos_venta.get('cliente', 'N/A')}", font=font_normal, fill=color_texto)
    y += 35
    
    if monto_pagado:
        draw.text((60, y), f"Monto pagado: Bs {monto_pagado:,.2f}", font=font_normal, fill=color_exito)
        y += 35
    
    draw.text((60, y), f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", font=font_normal, fill=color_texto)
    
    # Footer
    draw.text((ancho//2 - 100, alto-50), "¡Gracias por su pago!", font=font_normal, fill=color_texto_claro)
    
    nombre_archivo = f"recibo_pago_{id_venta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    ruta = os.path.join("static", "recibos", nombre_archivo)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    img.save(ruta)
    
    return ruta, nombre_archivo