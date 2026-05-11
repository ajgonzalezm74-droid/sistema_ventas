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
        """Obtiene tasas de cambio - CORREGIDO: actualiza siempre cuando se force o expiró"""
        
        # Si no se fuerza actualización, intentar usar caché
        if not force_update:
            tasa_guardada = self.get_last_valid_rate()
            if tasa_guardada and tasa_guardada > 0:
                ultima_fecha = self.get_last_rate_date()
                if ultima_fecha:
                    horas_transcurridas = (datetime.now() - ultima_fecha).total_seconds() / 3600
                    if horas_transcurridas < 16:
                        print(f"📊 Usando tasa guardada: {tasa_guardada} (de hace {horas_transcurridas:.1f} horas)")
                        return {
                            "bcv_usd": tasa_guardada,
                            "bcv_eur": round(tasa_guardada * 1.05, 2)
                        }
        
        # Siempre consultar API cuando se fuerza o no hay caché válida
        print("🔄 Obteniendo tasa actual desde APIs...")
        tasa_api = self.get_usd_rate_from_api()
        
        # Si API falla, usar última guardada
        if tasa_api == 0:
            tasa_api = self.get_last_valid_rate()
            if tasa_api == 0:
                tasa_api = 55.0
                print(f"⚠️ Usando tasa por defecto: {tasa_api}")
            else:
                print(f"⚠️ Usando última tasa válida guardada: {tasa_api}")
        
        # Guardar SIEMPRE que la tasa sea diferente a la última guardada
        if tasa_api > 0:
            ultima_guardada = self.get_last_valid_rate()
            # Comparación con tolerancia para evitar guardar cambios mínimos
            if ultima_guardada == 0 or abs(ultima_guardada - tasa_api) > 0.01:
                self.save_rates_to_db(tasa_api)
                print(f"✅ Nueva tasa guardada: {tasa_api}")
            else:
                print(f"📊 Tasa sin cambios: {tasa_api}")
        
        return {
            "bcv_usd": tasa_api,
            "bcv_eur": round(tasa_api * 1.05, 2)
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
        """Guarda tasas en PostgreSQL - CORREGIDO: sin bloqueo por fecha"""
        try:
            if tasa_usd <= 0:
                print("❌ No se guarda tasa en cero")
                return False
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Verificar si la ÚLTIMA tasa guardada es EXACTAMENTE igual
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            ultima = cursor.fetchone()
            
            # Comparación exacta para evitar duplicados IDÉNTICOS
            if ultima and ultima[0] == tasa_usd:
                print(f"📊 Tasa {tasa_usd} idéntica a la última guardada, omitiendo duplicado")
                conn.close()
                return False
            
            # Insertar nueva tasa (SIN restricción de fecha)
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
            print(f"💾 Tasa guardada en BD: {tasa_usd}")
            return True
        except Exception as e:
            print(f"❌ Error guardando tasas: {e}")
            return False
