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
        """
        Obtiene tasas de cambio actualizadas
        force_update=True: SIEMPRE consulta API y guarda si cambió
        force_update=False: Usa caché de 1 hora
        """
        
        # Si NO se fuerza actualización, intentar usar caché (1 hora)
        if not force_update:
            tasa_guardada = self.get_last_valid_rate()
            if tasa_guardada and tasa_guardada > 0:
                ultima_fecha = self.get_last_rate_date()
                if ultima_fecha:
                    minutos_transcurridos = (datetime.now() - ultima_fecha).total_seconds() / 60
                    # Caché de 60 minutos (1 hora) - más actualizado
                    if minutos_transcurridos < 60:
                        print(f"📊 Usando caché: {tasa_guardada} (hace {minutos_transcurridos:.0f} min)")
                        return {
                            "bcv_usd": tasa_guardada,
                            "bcv_eur": self.get_eur_rate_from_api(tasa_guardada)
                        }
                    else:
                        print(f"🔄 Caché expirada (hace {minutos_transcurridos:.0f} min), actualizando...")
        
        # SIEMPRE consultar API cuando:
        # - force_update=True, o
        # - caché expiró, o
        # - no hay tasa guardada
        print("🔄 Consultando tasa actual desde APIs...")
        tasa_nueva = self.get_usd_rate_from_api()
        
        # Si todas las APIs fallan, usar última tasa guardada
        if tasa_nueva <= 0:
            tasa_nueva = self.get_last_valid_rate()
            if tasa_nueva <= 0:
                tasa_nueva = 60.0  # Tasa por defecto actualizada
                print(f"⚠️ Usando tasa por defecto: {tasa_nueva}")
            else:
                print(f"⚠️ API falló, usando última tasa válida: {tasa_nueva}")
        
        # Guardar SIEMPRE que la tasa sea diferente (sin bloqueos de fecha)
        if tasa_nueva > 0:
            tasa_actual_bd = self.get_last_valid_rate()
            
            # Guardar si:
            # - No hay tasa en BD, o
            # - La diferencia es mayor a 0.05 Bs (evita ruido)
            if tasa_actual_bd == 0 or abs(tasa_actual_bd - tasa_nueva) > 0.05:
                self.save_rates_to_db(tasa_nueva)
                print(f"✅ Tasa actualizada: {tasa_nueva} (anterior: {tasa_actual_bd})")
            else:
                print(f"📊 Tasa sin cambios significativos: {tasa_nueva}")
        else:
            print("❌ No se pudo obtener tasa válida")
        
        # Obtener tasa EUR actualizada
        tasa_eur = self.get_eur_rate_from_api(tasa_nueva)
        
        return {
            "bcv_usd": tasa_nueva,
            "bcv_eur": tasa_eur
        }
    
    def get_usd_rate_from_api(self):
        """Obtiene tasa USD/VES desde múltiples APIs (priorizando fuentes venezolanas)"""
        apis = [
            # API #1: PyDolarVZLA (BCV oficial - más confiable para Venezuela)
            {
                "url": "https://pydolarve.org/api/v1/dollar?page=bcv",
                "path": ["monitors", "bcv", "price"],
                "name": "PyDolarVZLA (BCV Oficial)"
            },
            # API #2: PyDolarVZLA - EnParalelo (alternativa)
            {
                "url": "https://pydolarve.org/api/v1/dollar?page=enparalelovzla",
                "path": ["monitors", "enparalelovzla", "price"],
                "name": "PyDolarVZLA (EnParalelo)"
            },
            # API #3: ExchangeRate-API
            {
                "url": "https://api.exchangerate-api.com/v4/latest/USD",
                "path": ["rates", "VES"],
                "name": "ExchangeRate-API"
            },
            # API #4: Coinbase (respaldo)
            {
                "url": "https://api.coinbase.com/v2/exchange-rates?currency=USD",
                "path": ["data", "rates", "VES"],
                "name": "Coinbase"
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
                    print(f"✅ Tasa obtenida de {api['name']}: {tasa}")
                    return tasa
            except Exception as e:
                print(f"❌ Error con {api['name']}: {str(e)[:50]}")
                continue
        
        print("❌ No se pudo obtener tasa de ninguna API")
        return 0
    
    def get_eur_rate_from_api(self, tasa_usd_fallback=60.0):
        """Obtiene tasa EUR/VES desde API o calcula como fallback"""
        try:
            # Intentar obtener EUR directamente desde PyDolarVZLA
            response = requests.get("https://pydolarve.org/api/v1/dollar?page=bcv", timeout=5, verify=False)
            if response.status_code == 200:
                data = response.json()
                if "monitors" in data and "eur" in data["monitors"]:
                    eur_rate = float(data["monitors"]["eur"]["price"])
                    return round(eur_rate, 2)
        except:
            pass
        
        # Fallback: usar tasa USD * 1.08 (tasa EUR/USD aproximada)
        return round(tasa_usd_fallback * 1.08, 2)
    
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
            cursor.execute("""
                SELECT fecha FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            print(f"❌ Error obteniendo fecha de tasa: {e}")
            return None
    
    def save_rates_to_db(self, tasa_usd):
        """
        Guarda tasas en PostgreSQL - CORREGIDO: Sin bloqueos por fecha
        Solo evita duplicados IDÉNTICOS en el último registro
        """
        try:
            if tasa_usd <= 0:
                print("❌ No se guarda tasa menor o igual a 0")
                return False
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Verificar solo el ÚLTIMO registro (SIN filtro de fecha)
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            ultima = cursor.fetchone()
            
            # Solo evitar si es EXACTAMENTE igual (comparación directa)
            if ultima and ultima[0] == tasa_usd:
                print(f"📊 Tasa {tasa_usd} idéntica a la última, omitiendo duplicado")
                conn.close()
                return False
            
            # Obtener tasa EUR actualizada
            tasa_eur = self.get_eur_rate_from_api(tasa_usd)
            
            # Insertar nueva tasa (PERMITE múltiples el mismo día)
            cursor.execute(
                "INSERT INTO tasas (moneda, valor, fecha) VALUES (%s, %s, %s)",
                ("bcv_usd", tasa_usd, datetime.now())
            )
            cursor.execute(
                "INSERT INTO tasas (moneda, valor, fecha) VALUES (%s, %s, %s)",
                ("bcv_eur", tasa_eur, datetime.now())
            )
            
            conn.commit()
            conn.close()
            print(f"💾 Tasas guardadas - USD: {tasa_usd}, EUR: {tasa_eur}")
            return True
        except Exception as e:
            print(f"❌ Error guardando tasas: {e}")
            return False


# ========== FUNCIONES GLOBALES PARA FÁCIL USO ==========

def get_current_usd_rate(force_update=True):
    """
    Obtiene la tasa USD actual
    force_update=True: obtiene siempre la última (recomendado)
    """
    provider = ExchangeProvider()
    rates = provider.get_all_rates(force_update=force_update)
    return rates["bcv_usd"]

def get_current_eur_rate(force_update=True):
    """Obtiene la tasa EUR actual"""
    provider = ExchangeProvider()
    rates = provider.get_all_rates(force_update=force_update)
    return rates["bcv_eur"]

def force_update_rates():
    """Fuerza una actualización inmediata de las tasas"""
    provider = ExchangeProvider()
    return provider.get_all_rates(force_update=True)



    print(f"   Tasa: {ultima} Bs")
    print(f"   Fecha: {fecha}")
