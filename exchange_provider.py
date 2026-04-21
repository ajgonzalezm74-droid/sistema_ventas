import requests
import sqlite3
from datetime import datetime
import ssl
import urllib3

# Deshabilitar advertencias SSL (solo para BCV)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ExchangeProvider:
    def __init__(self):
        self.db_name = "ventas.db"
        self.ultima_tasa = None
        self.ultima_actualizacion = None
        
    def get_all_rates(self, force_update=False):
        """Obtiene tasas de cambio solo si es necesario"""
        
        # Si no es actualización forzada, verificar si ya tenemos tasa válida reciente
        if not force_update:
            tasa_guardada = self.get_last_valid_rate()
            if tasa_guardada and tasa_guardada > 0:
                # Verificar si la tasa tiene menos de 24 horas
                ultima_fecha = self.get_last_rate_date()
                if ultima_fecha:
                    horas_transcurridas = (datetime.now() - ultima_fecha).total_seconds() / 3600
                    if horas_transcurridas < 12:
                        print(f"📊 Usando tasa guardada: {tasa_guardada} (de hace {horas_transcurridas:.1f} horas)")
                        return {
                            "bcv_usd": tasa_guardada,
                            "bcv_eur": tasa_guardada * 1.05
                        }
        
        print("🔄 Obteniendo tasa actual...")
        
        # Intentar obtener tasa actual
        tasa = self.get_usd_rate_from_api()
        
        # Si la tasa es 0, usar la última válida
        if tasa == 0:
            tasa = self.get_last_valid_rate()
            if tasa == 0:
                tasa = 55.0  # Valor por defecto como último recurso
                print(f"⚠️ Usando tasa por defecto: {tasa}")
            else:
                print(f"⚠️ Usando última tasa válida: {tasa}")
        
        # Solo guardar si la tasa es mayor a 0 y diferente a la última guardada
        if tasa > 0:
            ultima_guardada = self.get_last_valid_rate()
            if ultima_guardada != tasa:
                self.save_rates_to_db(tasa)
                print(f"✅ Nueva tasa guardada: {tasa}")
            else:
                print(f"✅ Tasa sin cambios: {tasa}")
        
        return {
            "bcv_usd": tasa,
            "bcv_eur": round(tasa * 1.05, 2)
        }
    
    def get_usd_rate_from_api(self):
        """Obtiene tasa USD/VES desde múltiples APIs gratuitas"""
        
        # Lista de APIs gratuitas (sin API key)
        apis = [
            {
                "url": "https://api.exchangerate-api.com/v4/latest/USD",
                "path": ["rates", "VES"],
                "name": "ExchangeRate-API"
            },
            {
                "url": "https://v6.exchangerate-api.com/v6/latest/USD",
                "path": ["conversion_rates", "VES"],
                "name": "ExchangeRate-API v6"
            },
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
                
                # Navegar por el path
                value = data
                for key in api['path']:
                    value = value.get(key, {})
                    if not value:
                        break
                
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
        """Obtiene la última tasa válida guardada (mayor a 0)"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' AND valor > 0
                ORDER BY fecha DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                return row[0]
            return 0
            
        except Exception as e:
            print(f"❌ Error obteniendo última tasa: {e}")
            return 0
    
    def get_last_rate_date(self):
        """Obtiene la fecha de la última tasa guardada"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fecha FROM tasas 
                WHERE moneda = 'bcv_usd' AND valor > 0
                ORDER BY fecha DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            return None
            
        except:
            return None
    
    def save_rates_to_db(self, tasa_usd):
        """Guarda tasas SOLO si son válidas y diferentes"""
        try:
            # Verificar que la tasa es válida
            if tasa_usd <= 0:
                print("❌ No se guarda tasa en cero")
                return False
            
            # Verificar si ya existe la misma tasa hoy
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Crear tabla si no existe
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    moneda TEXT,
                    valor REAL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verificar si la tasa ya fue guardada hoy
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' 
                AND DATE(fecha) = DATE('now')
                ORDER BY fecha DESC LIMIT 1
            """)
            ultima = cursor.fetchone()
            
            if ultima and abs(ultima[0] - tasa_usd) < 0.01:
                print("📊 Tasa idéntica ya guardada hoy, omitiendo")
                conn.close()
                return False
            
            # Guardar nueva tasa
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (?, ?)",
                ("bcv_usd", tasa_usd)
            )
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (?, ?)",
                ("bcv_eur", round(tasa_usd * 1.05, 2))
            )
            
            conn.commit()
            conn.close()
            print(f"💾 Nueva tasa guardada: {tasa_usd}")
            return True
            
        except Exception as e:
            print(f"❌ Error guardando tasas: {e}")
            return False


# Para pruebas
if __name__ == "__main__":
    provider = ExchangeProvider()
    
    # Primera llamada (obtiene de API)
    print("\n=== PRIMERA LLAMADA ===")
    rates = provider.get_all_rates(force_update=True)
    print(f"Resultado: USD={rates['bcv_usd']}, EUR={rates['bcv_eur']}")
    
    # Segunda llamada (debería usar caché)
    print("\n=== SEGUNDA LLAMADA (caché) ===")
    rates2 = provider.get_all_rates(force_update=False)
    print(f"Resultado: USD={rates2['bcv_usd']}, EUR={rates2['bcv_eur']}")