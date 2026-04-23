from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import io

def generar_recibo_profesional(datos_venta):
    """
    Genera un recibo profesional con información detallada del crédito
    Versión optimizada para Supabase/Render
    """
    try:
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
        
        # ========== CONFIGURACIÓN DE FUENTES ==========
        font_titulo = ImageFont.load_default()
        font_subtitulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_pequeno = ImageFont.load_default()
        
        # Lista de rutas posibles para fuentes en diferentes entornos
        font_paths_bold = [
            # Render / Linux
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            # Windows
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\Arial.ttf",
        ]
        
        font_paths_regular = [
            # Render / Linux
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            # Windows
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        
        def cargar_fuente(rutas, tamaño):
            for ruta in rutas:
                try:
                    return ImageFont.truetype(ruta, tamaño)
                except:
                    continue
            return ImageFont.load_default()
        
        try:
            font_titulo = cargar_fuente(font_paths_bold, 20)
            font_subtitulo = cargar_fuente(font_paths_bold, 16)
            font_normal = cargar_fuente(font_paths_regular, 13)
            font_pequeno = cargar_fuente(font_paths_regular, 11)
        except:
            pass  # Usar default
        
        # ========== VALIDAR DATOS ==========
        cliente = datos_venta.get('cliente', 'Cliente')
        tipo = datos_venta.get('tipo', 'CRÉDITO').upper()
        total_original = float(datos_venta.get('total', 0))
        tasa_venta = float(datos_venta.get('tasa', 0))
        tasa_actual = float(datos_venta.get('tasa_actual', tasa_venta))
        
        # Si no hay tasa_venta, usar tasa_actual como fallback
        if tasa_venta <= 0:
            tasa_venta = tasa_actual if tasa_actual > 0 else 55.0
        
        total_usd = total_original / tasa_venta if tasa_venta > 0 else 0
        total_actualizado = total_usd * tasa_actual if tasa_actual > 0 else total_original
        
        y = 20
        
        # ========== ENCABEZADO ==========
        draw.text((ancho//2 - 70, y), "VENTAS PRO", font=font_titulo, fill=color_primario)
        y += 25
        draw.text((ancho//2 - 85, y), "RECIBO DE CRÉDITO", font=font_subtitulo, fill=color_primario)
        y += 25
        
        # Dibujar línea
        draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
        y += 15
        
        # ========== DATOS DEL CLIENTE ==========
        # Fondo para datos del cliente
        draw.rectangle([15, y-5, ancho-15, y+45], fill=(248, 248, 248))
        draw.text((20, y), f"Cliente: {cliente}", font=font_normal, fill=color_texto)
        y += 20
        draw.text((20, y), f"Tipo: {tipo}", font=font_normal, fill=color_secundario if tipo == 'CRÉDITO' else color_exito)
        y += 35
        
        # ========== INFORMACIÓN DE LA DEUDA ORIGINAL ==========
        draw.text((20, y), "📋 INFORMACIÓN DE LA COMPRA", font=font_subtitulo, fill=color_primario)
        y += 22
        
        draw.rectangle([15, y-5, ancho-15, y+65], fill=(248, 248, 248))
        draw.text((20, y), f"💰 Deuda original: Bs {total_original:,.2f}", font=font_normal, fill=color_texto)
        y += 20
        draw.text((20, y), f"📅 Tasa al vender: Bs {tasa_venta:,.2f}", font=font_normal, fill=color_texto)
        y += 20
        draw.text((20, y), f"💵 Total en USD: ${total_usd:,.2f}", font=font_normal, fill=color_texto)
        y += 35
        
        # ========== PAGO ACTUALIZADO ==========
        draw.text((20, y), "💰 AL PAGAR HOY", font=font_subtitulo, fill=color_primario)
        y += 22
        
        draw.rectangle([15, y-5, ancho-15, y+45], fill=(230, 245, 230))
        draw.text((20, y), f"💵 Al pagar HOY: Bs {total_actualizado:,.2f}", font=font_normal, fill=color_exito)
        y += 20
        draw.text((20, y), f"📈 Tasa actual BCV: Bs {tasa_actual:,.2f}", font=font_normal, fill=color_texto)
        y += 35
        
        # ========== SALDO PENDIENTE ==========
        saldo_pendiente = datos_venta.get('saldo_pendiente', total_actualizado)
        if saldo_pendiente and float(saldo_pendiente) > 0:
            draw.text((20, y), "⚠️ SALDO PENDIENTE", font=font_subtitulo, fill=color_secundario)
            y += 22
            draw.rectangle([15, y-5, ancho-15, y+25], fill=(255, 243, 224))
            draw.text((20, y), f"Bs {float(saldo_pendiente):,.2f}", font=font_normal, fill=color_secundario)
            y += 35
        
        # ========== PRODUCTOS ==========
        draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
        y += 10
        draw.text((20, y), "📦 PRODUCTOS", font=font_subtitulo, fill=color_primario)
        y += 22
        
        productos = datos_venta.get('productos', [])
        if productos:
            # Mostrar hasta 5 productos
            for i, prod in enumerate(productos[:5]):
                descripcion = prod.get('descripcion', 'Producto')
                cantidad = prod.get('cantidad', 1)
                precio_usd = prod.get('precio_usd', prod.get('precio', 0))
                
                draw.text((20, y), f"{descripcion[:30]} x{cantidad}", font=font_normal, fill=color_texto)
                if precio_usd > 0:
                    draw.text((ancho - 150, y), f"${precio_usd:,.2f}", font=font_pequeno, fill=color_gris)
                y += 18
            
            if len(productos) > 5:
                draw.text((20, y), f"... y {len(productos) - 5} producto(s) más", font=font_pequeno, fill=color_gris)
                y += 15
        else:
            draw.text((20, y), "Sin productos registrados", font=font_normal, fill=color_gris)
            y += 20
        
        y += 10
        
        # ========== FECHA ==========
        draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
        y += 15
        fecha = datos_venta.get('fecha', '')
        if not fecha:
            fecha = datetime.now().strftime('%d/%m/%Y %H:%M')
        draw.text((20, y), f"📅 Fecha: {fecha}", font=font_pequeno, fill=color_gris)
        y += 25
        
        # ========== FOOTER ==========
        draw.line([20, alto-50, ancho-20, alto-50], fill=color_linea, width=1)
        draw.text((ancho//2 - 80, alto-35), "¡Gracias por su compra!", font=font_pequeno, fill=color_gris)
        draw.text((ancho//2 - 100, alto-20), "Este comprobante es válido", font=font_pequeno, fill=color_gris)
        
        # Guardar en memoria
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        return img_bytes
        
    except Exception as e:
        print(f"❌ Error generando recibo profesional: {e}")
        import traceback
        traceback.print_exc()
        
        # ========== RECIBO DE EMERGENCIA ==========
        try:
            img = Image.new('RGB', (500, 400), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            
            draw.text((50, 50), "RECIBO DE PAGO", font=font, fill=(0,0,0))
            draw.text((50, 100), f"Cliente: {datos_venta.get('cliente', 'N/A')}", font=font, fill=(0,0,0))
            draw.text((50, 150), f"Monto: Bs {datos_venta.get('total', 0):,.2f}", font=font, fill=(0,0,0))
            draw.text((50, 200), f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", font=font, fill=(0,0,0))
            draw.text((50, 250), "Pago registrado exitosamente", font=font, fill=(0,150,0))
            
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            return img_bytes
        except:
            # Si todo falla, crear un bytes vacío
            return io.BytesIO()