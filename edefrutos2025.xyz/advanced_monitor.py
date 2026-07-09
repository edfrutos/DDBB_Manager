# Ruta: /var/www/vhosts/edefrutos2025.xyz/httpdocs/advanced_monitor.py

#!/usr/bin/env python3
import os
import sys
import time
import socket
import logging
import subprocess
import traceback
import requests
import psutil
import pymongo
from dotenv import load_dotenv
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuración
APP_DIR = '/var/www/vhosts/edefrutos2025.xyz/httpdocs'
SOCKET_PATH = os.path.join(APP_DIR, 'app.sock')
LOG_FILE = os.path.join(APP_DIR, 'logs', 'advanced_monitor.log')
WSGI_SERVICE = 'wsgi'  # Cambiar a "gunicorn" si usas Gunicorn
RESTART_THRESHOLD = 3  # Número de errores consecutivos antes de reiniciar
ERROR_COUNT = 0
NOTIFY_EMAIL = 'tu@email.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'tu_correo@gmail.com'
SMTP_PASSWORD = 'tu_contraseña'

# Configurar logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Cargar variables de entorno
load_dotenv(os.path.join(APP_DIR, '.env'))
MONGO_URI = os.getenv('MONGO_URI')

def send_notification(subject, message):
    """Envía una notificación por correo electrónico"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = NOTIFY_EMAIL
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logging.info(f"Notificación enviada: {subject}")
    except Exception as e:
        logging.error(f"Error al enviar notificación: {str(e)}")

def restart_service():
    """Reinicia el servicio WSGI"""
    global ERROR_COUNT
    
    try:
        logging.warning(f"Reiniciando servicio {WSGI_SERVICE}")
        subprocess.run(['systemctl', 'restart', WSGI_SERVICE], check=True)
        logging.info(f"Servicio {WSGI_SERVICE} reiniciado correctamente")
        
        # Notificar reinicio
        send_notification(
            f"Reinicio del servicio en {socket.gethostname()}",
            f"El servicio {WSGI_SERVICE} ha sido reiniciado automáticamente a las {datetime.now()}.\n\n"
            f"Errores consecutivos detectados: {ERROR_COUNT}\n\n"
            f"Este correo es automático, por favor no responder."
        )
        
        # Resetear contador de errores
        ERROR_COUNT = 0
        return True
    except subprocess.SubprocessError as e:
        logging.error(f"Error al reiniciar servicio: {str(e)}")
        return False

def check_socket():
    """Verifica el estado del socket"""
    global ERROR_COUNT
    
    if not os.path.exists(SOCKET_PATH):
        logging.error("Socket no encontrado")
        ERROR_COUNT += 1
        return False
    
    # Verificar permisos
    try:
        perms = oct(os.stat(SOCKET_PATH).st_mode)[-3:]
        owner = os.stat(SOCKET_PATH).st_uid
        
        if perms != '666':
            logging.warning(f"Permisos incorrectos en socket: {perms}, corrigiendo")
            os.chmod(SOCKET_PATH, 0o666)
        
        return True
    except Exception as e:
        logging.error(f"Error al verificar socket: {str(e)}")
        ERROR_COUNT += 1
        return False

def check_mongo_connection():
    """Verifica la conexión a MongoDB"""
    global ERROR_COUNT
    
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        logging.info("Conexión a MongoDB correcta")
        return True
    except Exception as e:
        logging.error(f"Error de conexión a MongoDB: {str(e)}")
        ERROR_COUNT += 1
        return False

def check_memory_usage():
    """Verifica el uso de memoria del proceso"""
    global ERROR_COUNT
    
    try:
        # Buscar procesos relacionados con la aplicación
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if WSGI_SERVICE in proc.info['name'] or 'python' in proc.info['name']:
                if any('app.py' in cmd for cmd in proc.info['cmdline'] if cmd):
                    processes.append(proc)
        
        if not processes:
            logging.error("No se encontraron procesos de la aplicación")
            ERROR_COUNT += 1
            return False
        
        # Verificar uso de memoria
        total_memory = 0
        for proc in processes:
            try:
                mem_info = proc.memory_info()
                memory_mb = mem_info.rss / (1024 * 1024)  # Convertir a MB
                total_memory += memory_mb
                logging.info(f"Proceso {proc.pid}: {memory_mb:.2f} MB")
            except psutil.NoSuchProcess:
                pass
        
        logging.info(f"Uso total de memoria: {total_memory:.2f} MB")
        
        # Si el uso de memoria es excesivo (más de 1GB), incrementar contador de errores
        if total_memory > 1024:
            logging.warning(f"Uso excesivo de memoria: {total_memory:.2f} MB")
            ERROR_COUNT += 1
            return False
        
        return True
    except Exception as e:
        logging.error(f"Error al verificar uso de memoria: {str(e)}")
        ERROR_COUNT += 1
        return False

def check_response_time():
    """Verifica el tiempo de respuesta de la aplicación"""
    global ERROR_COUNT
    
    try:
        start_time = time.time()
        response = requests.get('http://localhost/health', timeout=5)
        elapsed_time = time.time() - start_time
        
        logging.info(f"Tiempo de respuesta: {elapsed_time:.3f} segundos")
        
        if elapsed_time > 2:
            logging.warning(f"Tiempo de respuesta lento: {elapsed_time:.3f} segundos")
        
        if response.status_code != 200:
            logging.error(f"Respuesta HTTP incorrecta: {response.status_code}")
            ERROR_COUNT += 1
            return False
        
        return True
    except requests.RequestException as e:
        logging.error(f"Error al verificar tiempo de respuesta: {str(e)}")
        ERROR_COUNT += 1
        return False

def main():
    """Función principal"""
    global ERROR_COUNT
    
    logging.info("Iniciando monitoreo avanzado")
    
    # Verificar socket
    socket_ok = check_socket()
    
    # Verificar conexión a MongoDB
    mongo_ok = check_mongo_connection()
    
    # Verificar uso de memoria
    memory_ok = check_memory_usage()
    
    # Verificar tiempo de respuesta
    response_ok = check_response_time()
    
    # Resumen de verificaciones
    checks = [
        ("Socket", socket_ok),
        ("MongoDB", mongo_ok),
        ("Memoria", memory_ok),
        ("Tiempo de respuesta", response_ok)
    ]
    
    # Registrar resumen
    logging.info("Resumen de verificaciones:")
    for name, status in checks:
        logging.info(f"  - {name}: {'OK' if status else 'ERROR'}")
    
    # Verificar si es necesario reiniciar el servicio
    if ERROR_COUNT >= RESTART_THRESHOLD:
        logging.warning(f"Se detectaron {ERROR_COUNT} errores consecutivos. Reiniciando servicio.")
        restart_service()
    elif not all(status for _, status in checks):
        logging.warning("Se detectaron problemas, pero no suficientes para reiniciar el servicio.")
    else:
        logging.info("Todos los sistemas funcionan correctamente.")
        ERROR_COUNT = 0  # Resetear contador si todo está bien
    
    # Verificar procesos zombies
    try:
        zombies = [p for p in psutil.process_iter(['pid', 'name', 'status']) 
                  if p.info['status'] == 'zombie']
        if zombies:
            zombie_pids = [str(p.info['pid']) for p in zombies]
            logging.warning(f"Procesos zombie detectados: {', '.join(zombie_pids)}")
            
            # Intentar eliminar zombies
            for pid in zombie_pids:
                try:
                    subprocess.run(['kill', '-9', pid], check=True)
                    logging.info(f"Proceso zombie {pid} eliminado")
                except subprocess.SubprocessError:
                    pass
    except Exception as e:
        logging.error(f"Error al verificar procesos zombie: {str(e)}")
    
    # Verificar archivos de log
    try:
        log_files = [
            os.path.join(APP_DIR, 'logs', 'wsgi.log'),
            os.path.join(APP_DIR, 'logs', 'socket_monitor.log'),
            os.path.join(APP_DIR, 'logs', 'advanced_monitor.log')
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                size_mb = os.path.getsize(log_file) / (1024 * 1024)
                if size_mb > 100:  # 100 MB
                    logging.warning(f"Archivo de log grande: {log_file} ({size_mb:.2f} MB)")
                    
                    # Rotar archivo de log
                    backup_file = f"{log_file}.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    os.rename(log_file, backup_file)
                    open(log_file, 'w').close()  # Crear archivo vacío
                    logging.info(f"Archivo de log rotado a {backup_file}")
    except Exception as e:
        logging.error(f"Error al verificar archivos de log: {str(e)}")
    
    # Verificar conexiones abiertas
    try:
        connections = psutil.net_connections()
        app_connections = [c for c in connections if c.status == 'ESTABLISHED' 
                          and any(proc.pid == c.pid for proc in psutil.process_iter(['pid']) 
                                if 'python' in ' '.join(proc.cmdline()))]
        
        logging.info(f"Conexiones activas de la aplicación: {len(app_connections)}")
        
        if len(app_connections) > 500:  # Umbral alto de conexiones
            logging.warning(f"Número excesivo de conexiones: {len(app_connections)}")
            ERROR_COUNT += 1
    except Exception as e:
        logging.error(f"Error al verificar conexiones: {str(e)}")
    
    logging.info("Monitoreo completado")
    logging.info("-" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Error crítico en el script de monitoreo: {str(e)}")
        logging.critical(traceback.format_exc())
        
        # Notificar error crítico
        send_notification(
            f"Error crítico en el monitoreo del servidor {socket.gethostname()}",
            f"Se ha producido un error crítico en el script de monitoreo a las {datetime.now()}:\n\n"
            f"{str(e)}\n\n"
            f"Por favor, verifique el servidor lo antes posible.\n\n"
            f"Este correo es automático, por favor no responder."
        )