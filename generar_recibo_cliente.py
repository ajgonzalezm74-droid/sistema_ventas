from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import io

def generar_recibo_cliente(datos_recibo):
    """
    Genera un recibo con todas las deudas del cliente
    """
    
    # Configuración
    ancho = 600
    # Alto dinámico según cantidad de deudas
    alto = 400 + (len(datos_recibo['deudas']) * 200)
    color_fondo = (255, 255, 255)
    color_primario = (25, 118, 210)
    color_secundario = (255, 152, 0)
    color_exito = (76, 175, 80)
    color_texto = (51, 51, 51)
    color_gris = (117, 117, 117)
    color_linea = (200, 200, 200)
    
    img = Image.new('RGB', (ancho, alto), color_fondo)
    draw = ImageDraw.Draw(img)
    
    # Fuentes
    try:
        font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 22)
        font_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 16)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 12)
        font_pequeno = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 10)
    except:
        font_titulo = ImageFont.load_default()
        font_subtitulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_pequeno = ImageFont.load_default()
    
    y = 20
    
    # ========== ENCABEZADO ==========
    draw.text((ancho//2 - 80, y), "VENTAS PRO", font=font_titulo, fill=color_primario)
    y += 28
    draw.text((ancho//2 - 100, y), "ESTADO DE CUENTA - CRÉDITO", font=font_subtitulo, fill=color_primario)
    y += 25
    draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
    y += 15
    
    # ========== DATOS DEL CLIENTE ==========
    draw.text((20, y), f"Cliente: {datos_recibo['cliente']}", font=font_normal, fill=color_texto)
    y += 18
    draw.text((20, y), f"Teléfono: {datos_recibo['telefono']}", font=font_normal, fill=color_texto)
    y += 18
    draw.text((20, y), f"Fecha: {datos_recibo['fecha_generacion']}", font=font_pequeno, fill=color_gris)
    y += 25
    
    # ========== LISTA DE DEUDAS ==========
    draw.text((20, y), "📋 DETALLE DE DEUDAS PENDIENTES", font=font_subtitulo, fill=color_primario)
    y += 25
    
    for i, deuda in enumerate(datos_recibo['deudas']):
        # Fondo alternado
        if i % 2 == 0:
            draw.rectangle([20, y-5, ancho-20, y+170], fill=(250, 250, 250))
        
        # Fecha
        draw.text((30, y), f"📅 Fecha: {deuda['fecha']}", font=font_normal, fill=color_primario)
        y += 20
        
        # Deuda original
        draw.text((30, y), f"💰 Deuda original: Bs {deuda['total_original']:,.2f}", font=font_normal, fill=color_texto)
        draw.text((280, y), f"📉 Tasa al vender: Bs {deuda['tasa_venta']:,.2f}", font=font_normal, fill=color_texto)
        y += 18
        draw.text((30, y), f"💵 Total en USD: ${deuda['total_usd']:,.2f}", font=font_normal, fill=color_texto)
        y += 20
        
        # Al pagar hoy
        draw.text((30, y), f"💵 Al pagar HOY: Bs {deuda['total_actualizado']:,.2f}", font=font_normal, fill=color_exito)
        draw.text((280, y), f"📈 Tasa actual: Bs {datos_recibo['tasa_actual']:,.2f}", font=font_normal, fill=color_texto)
        y += 18
        
        # Saldo pendiente
        draw.text((30, y), f"⚠️ Saldo pendiente: Bs {deuda['saldo_pendiente']:,.2f}", font=font_normal, fill=color_secundario)
        y += 20
        
        # Productos
        productos_text = ", ".join([f"{p['descripcion']} x{p['cantidad']}" for p in deuda['productos']])
        draw.text((30, y), f"📦 {productos_text}", font=font_pequeno, fill=color_gris)
        y += 25
        
        # Línea separadora entre deudas
        draw.line([30, y, ancho-30, y], fill=color_linea, width=1)
        y += 15
    
    # ========== TOTAL GENERAL ==========
    y += 10
    draw.rectangle([20, y-10, ancho-20, y+30], fill=color_primario)
    draw.text((ancho//2 - 100, y), f"TOTAL GENERAL ADEUDADO: Bs {datos_recibo['total_general']:,.2f}", 
              font=font_subtitulo, fill=(255,255,255))
    y += 50
    
    # ========== FOOTER ==========
    draw.line([20, alto-50, ancho-20, alto-50], fill=color_linea, width=1)
    draw.text((ancho//2 - 100, alto-35), "¡Gracias por su preferencia!", font=font_pequeno, fill=color_gris)
    draw.text((ancho//2 - 90, alto-20), "Este documento es válido como comprobante", font=font_pequeno, fill=color_gris)
    
    # Guardar en memoria
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes