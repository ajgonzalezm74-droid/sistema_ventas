import requests
import psycopg2
from datetime import datetime
import urllib3
from database import get_connection

# Deshabilitar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ExchangeProvider:
    def __init__(self):
        self.ultima_tasa = None
        self.ultima_actualizacion = None
        
    def get_all_rates(self, force_update=False):
        """Obtiene tasas de cambio - CORREGIDO: actualiza solo si cambia"""
        
        # Caso 1: Usar caché si no se fuerza actualización y la tasa es reciente
        if not force_update:
            tasa_guardada = self.get_last_valid_rate()
            if tasa_guardada > 0:
                ultima_fecha = self.get_last_rate_date()
                if ultima_fecha:
                    horas_transcurridas = (datetime.now() - ultima_fecha).total_seconds() / 3600
                    if horas_transcurridas < 16:
                        print(f"📊 Usando tasa guardada: {tasa_guardada} (de hace {horas_transcurridas:.1f} horas)")
                        return {
                            "bcv_usd": tasa_guardada,
                            "bcv_eur": round(tasa_guardada * 1.05, 2)
                        }
                    else:
                        print(f"🔄 Caché expirada (hace {horas_transcurridas:.1f} horas), consultando API...")
        
        # Caso 2: Consultar API (si force_update=True o caché expirada o no hay tasa)
        print("🔄 Consultando tasa actual desde APIs...")
        tasa_nueva = self.get_usd_rate_from_api()
        
        # Si falla la API, usar la última tasa válida de BD
        if tasa_nueva <= 0:
            tasa_nueva = self.get_last_valid_rate()
            if tasa_nueva <= 0:
                # Último recurso: tasa por defecto (debes actualizar este valor)
                tasa_nueva = 55.0
                print(f"⚠️ Usando tasa por defecto: {tasa_nueva}")
            else:
                print(f"⚠️ API falló, usando última tasa válida: {tasa_nueva}")
        
        # Caso 3: Guardar SOLO si la tasa cambió significativamente
        if tasa_nueva > 0:
            tasa_actual_bd = self.get_last_valid_rate()
            
            # Comparación exacta para evitar duplicados
            if tasa_actual_bd is None or abs(tasa_actual_bd - tasa_nueva) > 0.01:
                self.save_rates_to_db(tasa_nueva)
                print(f"✅ Tasa actualizada: {tasa_nueva} (anterior: {tasa_actual_bd})")
            else:
                print(f"📊 Tasa sin cambios significativos: {tasa_nueva}")
        
        return {
            "bcv_usd": tasa_nueva,
            "bcv_eur": round(tasa_nueva * 1.05, 2)
        }
    
    def get_usd_rate_from_api(self):
        """Obtiene tasa USD/VES desde APIs múltiples"""
        apis = [
            {"url": "https://api.exchangerate-api.com/v4/latest/USD", "path": ["rates", "VES"], "name": "ExchangeRate-API"},
            {"url": "https://v6.exchangerate-api.com/v6/latest/USD", "path": ["conversion_rates", "VES"], "name": "ExchangeRate-API v6"},
            {"url": "https://api.coinbase.com/v2/exchange-rates?currency=USD", "path": ["data", "rates", "VES"], "name": "Coinbase"}
        ]
        
        for api in apis:
            try:
                print(f"📡 Intentando {api['name']}...")
                response = requests.get(api['url'], timeout=10, verify=False)
                response.raise_for_status()
                data = response.json()
                value = data
                for key in api['path']:
                    value = value.get(key, {})
                if value and float(value) > 0:
                    tasa = round(float(value), 2)
                    print(f"✅ Tasa obtenida de {api['name']}: {tasa}")
                    return tasa
            except Exception as e:
                print(f"❌ Error con {api['name']}: {str(e)[:50]}")
                continue
        
        print("❌ No se pudo obtener tasa de ninguna API")
        return 0
    
    def get_last_valid_rate(self):
        """Obtiene la última tasa válida desde PostgreSQL"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' AND valor > 0
                ORDER BY fecha DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception as e:
            print(f"❌ Error obteniendo última tasa: {e}")
            return 0
    
    def get_last_rate_date(self):
        """Obtiene la fecha de la última tasa desde PostgreSQL"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT fecha FROM tasas WHERE moneda = 'bcv_usd' ORDER BY fecha DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            print(f"❌ Error obteniendo fecha de tasa: {e}")
            return None
    
    def save_rates_to_db(self, tasa_usd):
        """Guarda tasas en PostgreSQL SOLO si no existe exactamente igual"""
        try:
            if tasa_usd <= 0:
                print("❌ No se guarda tasa en cero")
                return False
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Verificar si la última tasa guardada es IDÉNTICA
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            ultima = cursor.fetchone()
            
            # Comparación exacta para evitar duplicados
            if ultima and ultima[0] == tasa_usd:
                print(f"📊 Tasa {tasa_usd} ya existe como último registro, omitiendo duplicado")
                conn.close()
                return False
            
            # Insertar nueva tasa
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (%s, %s)",
                ("bcv_usd", tasa_usd)
            )
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (%s, %s)",
                ("bcv_eur", round(tasa_usd * 1.05, 2))
            )
            
            conn.commit()
            conn.close()
            print(f"💾 Nuevas tasas guardadas - USD: {tasa_usd}, EUR: {round(tasa_usd * 1.05, 2)}")
            return True
        except Exception as e:
            print(f"❌ Error guardando tasas: {e}")
            return False
