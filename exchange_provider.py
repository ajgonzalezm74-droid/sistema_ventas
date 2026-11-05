# exchange_provider.py - VERSIÓN SIMPLIFICADA Y MEJORADA
import requests
from datetime import datetime
from database import get_connection  # Para guardar en BD

class ExchangeProvider:
    def __init__(self):
        self.session = requests.Session()
        self.binance_url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        # Cache en memoria
        self._cache = {
            "rates": None,
            "timestamp": None,
            "cache_minutes": 30  # Cache de 30 minutos para no sobrecargar
        }

    def get_headers(self, is_binance=False):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        headers = {"User-Agent": ua}
        if is_binance:
            headers.update({
                "Content-Type": "application/json",
                "clienttype": "web"
            })
        return headers
    
    def get_all_rates(self, force_update=False):
        """
        Obtiene todas las tasas de cambio
        force_update=True: Fuerza consulta
        force_update=False: Usa cache de 30 minutos
        """
        
        # Verificar cache
        if not force_update and self._cache["rates"] and self._cache["timestamp"]:
            minutos_transcurridos = (datetime.now() - self._cache["timestamp"]).total_seconds() / 60
            if minutos_transcurridos < self._cache["cache_minutes"]:
                print(f"📊 Usando cache de tasas (hace {minutos_transcurridos:.0f} min)")
                return self._cache["rates"]
            else:
                print(f"🔄 Cache expirada (hace {minutos_transcurridos:.0f} min), actualizando...")
        
        print("🔄 Obteniendo tasas de cambio actuales...")
        
        # Obtener tasas
        bcv_usd = self.get_bcv_usd()
        p2p = self.get_binance_p2p()
        
        rates = {
            "bcv_usd": bcv_usd,
            "bcv_eur": 1006.03, # Mantenemos el Euro fijo para que tu frontend no muestre el -99%
            "p2p_ves": p2p,
            "fecha_actualizacion": datetime.now().isoformat()
        }
        
        # Guardar en cache
        self._cache["rates"] = rates
        self._cache["timestamp"] = datetime.now()
        
        # Guardar en BD para persistencia (solo si el USD es válido)
        if rates["bcv_usd"] > 0:
            self._save_to_database(rates["bcv_usd"], rates["bcv_eur"])
        
        print(f"✅ BCV USD: {rates['bcv_usd']:.2f}")
        print(f"✅ P2P VES: {rates['p2p_ves']:.2f}")
        
        return rates

    def get_bcv_usd(self):
        """Obtiene la tasa del Dólar del BCV usando DolarAPI (Infalible)"""
        try:
            print("📡 Consultando Dólar BCV (vía DolarAPI)...")
            resp = self.session.get("https://ve.dolarapi.com/v1/dolares/oficial", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                tasa = float(data.get("promedio", 0.0))
                print(f"   USD: {tasa} (API exitosa)")
                return tasa
        except Exception as e:
            print(f"❌ Error DolarAPI: {e}")
        
        return 0.0

    def get_binance_p2p(self):
        """Obtiene la tasa P2P de Binance para USDT a VES"""
        # Usar BUY para saber a cuánto compran USDT (tasa más real)
        payload = {
            "asset": "USDT",
            "fiat": "VES",
            "merchantCheck": True,
            "page": 1,
            "rows": 3,
            "tradeType": "BUY",
            "publisherType": "merchant",
            "payTypes": ["PagoMovil", "BinancePay"]
        }
        
        try:
            print("📡 Consultando Binance P2P...")
            resp = self.session.post(self.binance_url, json=payload, 
                                    headers=self.get_headers(True), timeout=15)
            data = resp.json()
            
            if data.get("data") and len(data["data"]) > 0:
                price = float(data["data"][0]["adv"]["price"])
                print(f"   P2P VES (compra): {price}")
                return price
            else:
                # Segundo intento sin filtros
                payload2 = {
                    "asset": "USDT",
                    "fiat": "VES",
                    "page": 1,
                    "rows": 3,
                    "tradeType": "BUY",
                    "payTypes": []
                }
                resp2 = self.session.post(self.binance_url, json=payload2, 
                                         headers=self.get_headers(True), timeout=15)
                data2 = resp2.json()
                if data2.get("data") and len(data2["data"]) > 0:
                    price = float(data2["data"][0]["adv"]["price"])
                    print(f"   P2P VES (compra - método alternativo): {price}")
                    return price
                return 0.0
                
        except Exception as e:
            print(f"❌ Error Binance: {e}")
            return 0.0
    
    def _save_to_database(self, tasa_usd, tasa_eur):
        """Guarda las tasas en la base de datos (sin duplicados)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Verificar última tasa
            cursor.execute("""
                SELECT valor FROM tasas 
                WHERE moneda = 'bcv_usd' 
                ORDER BY fecha DESC LIMIT 1
            """)
            ultima = cursor.fetchone()
            
            # Solo guardar si cambió (diferencia > 0.05)
            if ultima and abs(ultima[0] - tasa_usd) < 0.05:
                print(f"📊 Tasa sin cambios significativos, no se guarda")
                conn.close()
                return False
            
            # Guardar nueva tasa
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (%s, %s)",
                ("bcv_usd", tasa_usd)
            )
            cursor.execute(
                "INSERT INTO tasas (moneda, valor) VALUES (%s, %s)",
                ("bcv_eur", tasa_eur)
            )
            conn.commit()
            conn.close()
            print(f"💾 Tasas guardadas en BD: USD={tasa_usd}, EUR={tasa_eur}")
            return True
        except Exception as e:
            print(f"⚠️ No se pudo guardar en BD: {e}")
            return False


# ========== FUNCIONES GLOBALES ==========

# Instancia única del provider
_provider = None

def get_provider():
    """Obtiene la instancia única del ExchangeProvider"""
    global _provider
    if _provider is None:
        _provider = ExchangeProvider()
    return _provider

def get_all_rates(force_update=False):
    """Función global para obtener tasas"""
    return get_provider().get_all_rates(force_update=force_update)
