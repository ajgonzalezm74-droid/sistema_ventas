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
        """Obtiene tasas de cambio actualizadas"""
        
        # Si no se fuerza actualización, intentar usar caché (2 horas)
        if not force_update:
            tasa_guardada = self.get_last_valid_rate()
            if tasa_guardada and tasa_guardada > 0:
                ultima_fecha = self.get_last_rate_date()
                if ultima_fecha:
                    horas_transcurridas = (datetime.now() - ultima_fecha).total_seconds() / 3600
                    if horas_transcurridas < 2:  # Caché de 2 horas
                        print(f"📊 Usando caché: {tasa_guardada}")
                        return {
                            "bcv_usd": tasa_guardada,
                            "bcv_eur": round(tasa_guardada * 1.08, 2)
                        }
        
        # Consultar API
        print("🔄 Obteniendo tasa actual desde APIs...")
        tasa_nueva = self.get_usd_rate_from_api()
        
        if tasa_nueva <= 0:
            tasa_nueva = self.get_last_valid_rate()
            if tasa_nueva <= 0:
                tasa_nueva = 60.0
                print(f"⚠️ Usando tasa por defecto: {tasa_nueva}")
        
        # Guardar SIEMPRE que la tasa sea DIFERENTE (sin importar la fecha)
        if tasa_nueva > 0:
            tasa_actual_bd = self.get_last_valid_rate()
            # Comparación con tolerancia
            if tasa_actual_bd == 0 or abs(tasa_actual_bd - tasa_nueva) > 0.05:
                self.save_rates_to_db(tasa_nueva)
                print(f"✅ Tasa guardada: {tasa_nueva} (anterior: {tasa_actual_bd})")
            else:
                print(f"📊 Tasa sin cambios: {tasa_nueva}")
        else:
            print("❌ No se pudo obtener tasa válida")
        
        return {
            "bcv_usd": tasa_nueva,
            "bcv_eur": round(tasa_nueva * 1.08, 2)
        }
    
    def get_usd_rate_from_api(self):
        """Obtiene tasa USD/VES desde APIs"""
        apis = [
            {
                "url": "https://pydolarve.org/api/v1/dollar?page=bcv",
                "path": ["monitors", "bcv", "price"],
                "name": "PyDolarVZLA (BCV)"
            },
            {
                "url": "https://api.exchangerate-api.com/v4/latest/USD",
                "path": ["rates", "VES"],
                "name": "ExchangeRate-API"
            },
            {
                "url": "https://v6.exchangerate-api.com/v6/latest/USD",
                "path": ["conversion_rates", "VES"],
                "name": "ExchangeRate-API v6"
            }
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
                    print(f"✅ Tasa obtenida: {tasa}")
                    return tasa
            except Exception as e:
                print(f"❌ Error: {str(e)[:50]}")
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
        """Obtiene la fecha de la última tasa"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fecha FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def save_rates_to_db(self, tasa_usd):
        """Guarda tasas - SIN BLOQUEO POR FECHA"""
        try:
            if tasa_usd <= 0:
                print("❌ Tasa inválida")
                return False
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # SOLO verificar el último registro (SIN filtro de fecha)
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            ultima = cursor.fetchone()
            
            # Solo evitar duplicados IDÉNTICOS
            if ultima and ultima[0] == tasa_usd:
                print(f"📊 Tasa {tasa_usd} ya es la última, omitiendo")
                conn.close()
                return False
            
            # Guardar nueva tasa (permite múltiples el mismo día)
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (%s, %s)",
                ("bcv_usd", tasa_usd)
            )
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (%s, %s)",
                ("bcv_eur", round(tasa_usd * 1.08, 2))
            )
            
            conn.commit()
            conn.close()
            print(f"💾 Tasa guardada: {tasa_usd}")
            return True
        except Exception as e:
            print(f"❌ Error guardando: {e}")
            return False


# Función global para obtener tasa actualizada
def get_current_rate(force_update=False):
    provider = ExchangeProvider()
    rates = provider.get_all_rates(force_update=force_update)
    return rates["bcv_usd"]
