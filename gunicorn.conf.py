# gunicorn.conf.py
import multiprocessing

# Configuración para Render (plan gratuito)
bind = "0.0.0.0:10000"
workers = 1  # Reducir a 1 worker para ahorrar memoria
threads = 2  # Usar threads en lugar de más workers
timeout = 60
worker_class = "gthread"  # Usar worker con threads
max_requests = 100
max_requests_jitter = 10