from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import io

def generar_recibo_profesional(datos_venta):
    """
    Genera un recibo profesional con información detallada del crédito
    """
    
    # Configuración
    ancho = 550
    alto = 850
    color_fondo = (255, 255, 255)
    color_primario = (25, 118, 210)  # Azul
    color_secundario = (255, 152, 0)  # Naranja para advertencias
    color_exito = (76, 175, 80)       # Verde
    color_texto = (51, 51, 51)
    color_gris = (117, 117, 117)
    color_linea = (200, 200, 200)
    
    img = Image.new('RGB', (ancho, alto), color_fondo)
    draw = ImageDraw.Draw(img)
    
    # Fuentes
    try:
        font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 20)
        font_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 16)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 13)
        font_pequeno = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 11)
    except:
        font_titulo = ImageFont.load_default()
        font_subtitulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_pequeno = ImageFont.load_default()
    
    y = 20
    
    # ========== ENCABEZADO ==========
    draw.text((ancho//2 - 70, y), "VENTAS PRO", font=font_titulo, fill=color_primario)
    y += 25
    draw.text((ancho//2 - 85, y), "RECIBO DE CRÉDITO", font=font_subtitulo, fill=color_primario)
    y += 25
    draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
    y += 15
    
    # ========== DATOS DEL CLIENTE ==========
    cliente = datos_venta.get('cliente', 'Cliente')
    tipo = datos_venta.get('tipo', 'CRÉDITO').upper()
    
    draw.text((20, y), f"Cliente: {cliente}", font=font_normal, fill=color_texto)
    y += 20
    draw.text((20, y), f"Tipo: {tipo}", font=font_normal, fill=color_secundario)
    y += 30
    
    # ========== INFORMACIÓN DE LA DEUDA ORIGINAL ==========
    draw.text((20, y), "📋 INFORMACIÓN DE LA COMPRA", font=font_subtitulo, fill=color_primario)
    y += 22
    
    total_original = datos_venta.get('total', 0)
    tasa_venta = datos_venta.get('tasa', 0)
    total_usd = total_original / tasa_venta if tasa_venta > 0 else 0
    
    draw.text((20, y), f"💰 Deuda original: Bs {total_original:,.2f}", font=font_normal, fill=color_texto)
    y += 20
    draw.text((20, y), f"📅 Tasa al vender: Bs {tasa_venta:,.2f}", font=font_normal, fill=color_texto)
    y += 20
    draw.text((20, y), f"💵 Total en USD: ${total_usd:,.2f}", font=font_normal, fill=color_texto)
    y += 30
    
    # ========== PAGO ACTUALIZADO ==========
    draw.text((20, y), "💰 AL PAGAR HOY", font=font_subtitulo, fill=color_primario)
    y += 22
    
    tasa_actual = datos_venta.get('tasa_actual', tasa_venta)
    total_actualizado = total_usd * tasa_actual
    
    draw.text((20, y), f"💵 Al pagar HOY: Bs {total_actualizado:,.2f}", font=font_normal, fill=color_exito)
    y += 20
    draw.text((20, y), f"📈 Tasa actual BCV: Bs {tasa_actual:,.2f}", font=font_normal, fill=color_texto)
    y += 30
    
    # ========== SALDO PENDIENTE ==========
    saldo_pendiente = datos_venta.get('saldo_pendiente', total_actualizado)
    
    if saldo_pendiente > 0:
        draw.text((20, y), "⚠️ SALDO PENDIENTE", font=font_subtitulo, fill=color_secundario)
        y += 22
        draw.text((20, y), f"Bs {saldo_pendiente:,.2f}", font=font_normal, fill=color_secundario)
        y += 30
    
    # ========== PRODUCTOS ==========
    draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
    y += 10
    draw.text((20, y), "📦 PRODUCTOS", font=font_subtitulo, fill=color_primario)
    y += 22
    
    productos = datos_venta.get('productos', [])
    for prod in productos:
        descripcion = prod.get('descripcion', 'Producto')
        cantidad = prod.get('cantidad', 1)
        draw.text((20, y), f"{descripcion} x{cantidad}", font=font_normal, fill=color_texto)
        y += 20
    
    y += 10
    
    # ========== FECHA ==========
    draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
    y += 15
    fecha = datos_venta.get('fecha', datetime.now().strftime('%d/%m/%Y'))
    draw.text((20, y), f"📅 Fecha de compra: {fecha}", font=font_pequeno, fill=color_gris)
    y += 25
    
    # ========== FOOTER ==========
    draw.line([20, alto-50, ancho-20, alto-50], fill=color_linea, width=1)
    draw.text((ancho//2 - 80, alto-35), "¡Gracias por su compra!", font=font_pequeno, fill=color_gris)
    draw.text((ancho//2 - 100, alto-20), "Este comprobante es válido", font=font_pequeno, fill=color_gris)
    
    # Guardar en memoria
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes