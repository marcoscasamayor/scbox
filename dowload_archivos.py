import os
import json
from ftplib import FTP
from datetime import datetime

# --- Constantes ---
ARCHIVO_CONFIG = 'scb.config'

# --- Utilidades generales ---

def buscar_archivo_ancestro(nombre_archivo, directorio_actual):
    while directorio_actual != os.path.dirname(directorio_actual):
        for root, _, files in os.walk(directorio_actual):
            if nombre_archivo in files:
                return os.path.join(root, nombre_archivo)
        directorio_actual = os.path.dirname(directorio_actual)
    return None

def leer_configuracion(ruta_config):
    try:
        with open(ruta_config, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error leyendo el archivo de configuración: {e}")
        exit()

# --- Funciones FTP ---

def conectar_ftp(config):
    ftp = FTP(config['FTP']['ftp_server'])
    ftp.login(user=config['FTP']['ftp_user'], passwd=config['FTP']['ftp_password'])
    return ftp

def descargar_archivo(ftp, ruta_ftp, ruta_local):
    try:
        with open(ruta_local, 'wb') as archivo_local:
            ftp.retrbinary(f"RETR {ruta_ftp}", archivo_local.write)
        print(f"Archivo descargado: {ruta_ftp} -> {ruta_local}")
    except Exception as e:
        print(f"Error descargando el archivo {ruta_ftp}: {e}")

def descargar_carpetas_recursivamente(ftp, ruta_ftp_base, ruta_local_base):
    try:
        elementos = ftp.nlst()
    except Exception as e:
        print(f"Error listando contenido en {ruta_ftp_base}: {e}")
        return

    for elemento in elementos:
        # Ignorar directorios especiales
        if elemento in ['.', '..']:
            continue

        ruta_remota = os.path.join(ruta_ftp_base, elemento).replace("\\", "/")
        ruta_local = os.path.join(ruta_local_base, elemento).replace("\\", "/")

        try:
            ftp.cwd(ruta_remota)  # Si no lanza excepción, es un directorio
            os.makedirs(ruta_local, exist_ok=True)  # Crear estructura local si es carpeta
            descargar_carpetas_recursivamente(ftp, ruta_remota, ruta_local)
            ftp.cwd("..")  # Volver al directorio padre
        except Exception:  # Es un archivo
            descargar_archivo(ftp, ruta_remota, ruta_local)

# --- Programa principal ---
if __name__ == "__main__":
    directorio_actual = os.getcwd()
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, directorio_actual)

    if not ruta_config:
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")
        exit()

    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    # Detectar posición actual en el FTP
    ruta_remota_actual = ftp.pwd()
    print(f"Posición actual en el servidor FTP: {ruta_remota_actual}")

    # Descargar desde la posición actual hacia abajo
    print("Iniciando descarga desde la posición actual del servidor FTP hacia la estructura local correspondiente...")
    descargar_carpetas_recursivamente(ftp, ruta_remota_actual, directorio_actual)
 
    ftp.quit()
