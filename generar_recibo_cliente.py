from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import io

def generar_recibo_cliente(datos_recibo):
    """
    Genera un recibo con todas las deudas del cliente
    Versión optimizada para Supabase/Render
    """
    try:
        # Validar datos de entrada
        if not datos_recibo or 'deudas' not in datos_recibo:
            raise ValueError("Datos de recibo inválidos")
        
        # Configuración
        ancho = 600
        # Alto dinámico según cantidad de deudas
        cantidad_deudas = len(datos_recibo.get('deudas', []))
        alto = 400 + (cantidad_deudas * 180)
        color_fondo = (255, 255, 255)
        color_primario = (25, 118, 210)
        color_secundario = (255, 152, 0)
        color_exito = (76, 175, 80)
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
        
        # Lista de rutas posibles para fuentes
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
            font_titulo = cargar_fuente(font_paths_bold, 22)
            font_subtitulo = cargar_fuente(font_paths_bold, 16)
            font_normal = cargar_fuente(font_paths_regular, 12)
            font_pequeno = cargar_fuente(font_paths_regular, 10)
        except:
            pass
        
        y = 20
        
        # ========== ENCABEZADO ==========
        draw.text((ancho//2 - 80, y), "VENTAS PRO", font=font_titulo, fill=color_primario)
        y += 28
        draw.text((ancho//2 - 100, y), "ESTADO DE CUENTA - CRÉDITO", font=font_subtitulo, fill=color_primario)
        y += 25
        draw.line([20, y, ancho-20, y], fill=color_linea, width=1)
        y += 15
        
        # ========== DATOS DEL CLIENTE ==========
        cliente = datos_recibo.get('cliente', 'Cliente')
        telefono = datos_recibo.get('telefono', 'No registrado')
        fecha_generacion = datos_recibo.get('fecha_generacion', datetime.now().strftime('%d/%m/%Y %H:%M'))
        
        draw.text((20, y), f"Cliente: {cliente}", font=font_normal, fill=color_texto)
        y += 18
        draw.text((20, y), f"Teléfono: {telefono}", font=font_normal, fill=color_texto)
        y += 18
        draw.text((20, y), f"Fecha: {fecha_generacion}", font=font_pequeno, fill=color_gris)
        y += 25
        
        # ========== LISTA DE DEUDAS ==========
        draw.text((20, y), "📋 DETALLE DE DEUDAS PENDIENTES", font=font_subtitulo, fill=color_primario)
        y += 25
        
        deudas = datos_recibo.get('deudas', [])
        tasa_actual = datos_recibo.get('tasa_actual', 55.0)
        total_general = 0
        
        for i, deuda in enumerate(deudas):
            # Fondo alternado
            if i % 2 == 0:
                draw.rectangle([20, y-5, ancho-20, y+165], fill=(248, 248, 248))
            
            # Datos de la deuda
            fecha = deuda.get('fecha', 'Fecha no disponible')
            total_original = float(deuda.get('total_original', 0))
            tasa_venta = float(deuda.get('tasa_venta', 0))
            total_usd = float(deuda.get('total_usd', 0))
            total_actualizado = float(deuda.get('total_actualizado', 0))
            saldo_pendiente = float(deuda.get('saldo_pendiente', total_actualizado))
            
            total_general += saldo_pendiente
            
            # Fecha
            draw.text((30, y), f"📅 Fecha: {fecha}", font=font_normal, fill=color_primario)
            y += 20
            
            # Deuda original
            draw.text((30, y), f"💰 Deuda original: Bs {total_original:,.2f}", font=font_normal, fill=color_texto)
            draw.text((280, y), f"📉 Tasa al vender: Bs {tasa_venta:,.2f}", font=font_normal, fill=color_texto)
            y += 18
            
            draw.text((30, y), f"💵 Total en USD: ${total_usd:,.2f}", font=font_normal, fill=color_texto)
            y += 20
            
            # Al pagar hoy
            draw.text((30, y), f"💵 Al pagar HOY: Bs {total_actualizado:,.2f}", font=font_normal, fill=color_exito)
            draw.text((280, y), f"📈 Tasa actual: Bs {tasa_actual:,.2f}", font=font_normal, fill=color_texto)
            y += 18
            
            # Saldo pendiente
            draw.text((30, y), f"⚠️ Saldo pendiente: Bs {saldo_pendiente:,.2f}", font=font_normal, fill=color_secundario)
            y += 20
            
            # Productos
            productos = deuda.get('productos', [])
            if productos:
                productos_text = ", ".join([f"{p.get('descripcion', 'Producto')} x{p.get('cantidad', 1)}" for p in productos[:3]])
                if len(productos) > 3:
                    productos_text += f" +{len(productos)-3} más"
                draw.text((30, y), f"📦 {productos_text}", font=font_pequeno, fill=color_gris)
            y += 25
            
            # Línea separadora entre deudas
            draw.line([30, y, ancho-30, y], fill=color_linea, width=1)
            y += 15
        
        # ========== TOTAL GENERAL ==========
        y += 10
        draw.rectangle([20, y-10, ancho-20, y+30], fill=color_primario)
        
        texto_total = f"TOTAL GENERAL ADEUDADO: Bs {total_general:,.2f}"
        try:
            # Intentar centrar el texto
            bbox = draw.textbbox((0, 0), texto_total, font=font_subtitulo)
            texto_ancho = bbox[2] - bbox[0]
            draw.text(((ancho - texto_ancho) // 2, y), texto_total, font=font_subtitulo, fill=(255,255,255))
        except:
            draw.text((ancho//2 - 130, y), texto_total, font=font_subtitulo, fill=(255,255,255))
        
        y += 50
        
        # ========== FOOTER ==========
        # Asegurar que el footer esté dentro de la imagen
        footer_y = alto - 50
        if footer_y < y:
            footer_y = y + 20
        
        draw.line([20, footer_y, ancho-20, footer_y], fill=color_linea, width=1)
        draw.text((ancho//2 - 100, footer_y+15), "¡Gracias por su preferencia!", font=font_pequeno, fill=color_gris)
        draw.text((ancho//2 - 110, footer_y+30), "Este documento es válido como comprobante", font=font_pequeno, fill=color_gris)
        
        # Guardar en memoria
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        return img_bytes
        
    except Exception as e:
        print(f"❌ Error generando recibo cliente: {e}")
        import traceback
        traceback.print_exc()
        
        # ========== RECIBO DE EMERGENCIA ==========
        try:
            img = Image.new('RGB', (500, 400), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            
            draw.text((50, 50), "ESTADO DE CUENTA", font=font, fill=(0,0,0))
            draw.text((50, 100), f"Cliente: {datos_recibo.get('cliente', 'N/A')}", font=font, fill=(0,0,0))
            draw.text((50, 150), f"Total deudas: {len(datos_recibo.get('deudas', []))}", font=font, fill=(0,0,0))
            draw.text((50, 200), f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", font=font, fill=(0,0,0))
            draw.text((50, 250), "Documento generado automáticamente", font=font, fill=(100,100,100))
            
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            return img_bytes
        except:
            return io.BytesIO()