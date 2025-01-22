import os
import json
from ftplib import FTP
from datetime import datetime

# --- Constantes ---
ARCHIVO_CONFIG = 'scb.config'
RAIZ_FTP = '/SC3/ArchivosOrigen'  # Raíz del servidor FTP que se replica localmente

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

def navegar_a_raiz_ftp(ftp, raiz_esperada):
    """Navega dinámicamente a la raíz esperada en el FTP, si es posible."""
    try:
        ftp.cwd(raiz_esperada)
        print(f"Navegación exitosa a la raíz configurada: {raiz_esperada}")
        return True
    except Exception:
        print(f"No se pudo acceder a la raíz configurada ({raiz_esperada}). Continuando desde el directorio actual del FTP.")
        return False

def descargar_archivo(ftp, ruta_ftp, ruta_local):
    try:
        with open(ruta_local, 'wb') as archivo_local:
            ftp.retrbinary(f"RETR {ruta_ftp}", archivo_local.write)
        print(f"Archivo descargado: {ruta_ftp} -> {ruta_local}")
    except Exception as e:
        print(f"Error descargando el archivo {ruta_ftp}: {e}")

def verificar_y_crear_estructura(ruta_local):
    if not os.path.exists(ruta_local):
        os.makedirs(ruta_local, exist_ok=True)

def es_directorio(ftp, ruta):
    """Verifica si una ruta en el FTP es un directorio."""
    actual = ftp.pwd()
    try:
        ftp.cwd(ruta)
        ftp.cwd(actual)  # Regresa al directorio original
        return True
    except Exception:
        return False

def calcular_ruta_local(ruta_ftp, ruta_local_base):
    """Calcula la ruta local correspondiente eliminando el prefijo de RAIZ_FTP."""
    ruta_relativa = os.path.relpath(ruta_ftp, RAIZ_FTP)
    return os.path.normpath(os.path.join(ruta_local_base, ruta_relativa))

def descargar_carpetas_recursivamente(ftp, ruta_ftp_base, ruta_local_base, profundidad=0, max_profundidad=100):
    if profundidad > max_profundidad:
        print(f"Se alcanzó la profundidad máxima permitida ({max_profundidad}) en {ruta_ftp_base}.")
        return

    try:
        elementos = ftp.nlst(ruta_ftp_base)
    except Exception as e:
        print(f"Error listando contenido en {ruta_ftp_base}: {e}")
        return

    for elemento in elementos:
        # Ignorar directorios especiales
        if elemento in ['.', '..']:
            continue

        ruta_remota = os.path.normpath(os.path.join(ruta_ftp_base, elemento)).replace("\\", "/")
        ruta_local = calcular_ruta_local(ruta_remota, ruta_local_base)

        try:
            if es_directorio(ftp, ruta_remota):
                verificar_y_crear_estructura(ruta_local)  # Verificar y crear estructura solo si no existe
                descargar_carpetas_recursivamente(ftp, ruta_remota, ruta_local, profundidad + 1, max_profundidad)
            else:
                verificar_y_crear_estructura(os.path.dirname(ruta_local))  # Asegurar que el directorio padre exista
                descargar_archivo(ftp, ruta_remota, ruta_local)
        except Exception as e:
            print(f"Error procesando {ruta_remota}: {e}")

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

    # Navegar a la raíz esperada del FTP si es posible
    if not navegar_a_raiz_ftp(ftp, RAIZ_FTP):
        RAIZ_FTP = ruta_remota_actual  # Actualizar la raíz al directorio actual si no se pudo navegar

    # Descargar desde la posición actual hacia abajo
    print("Iniciando descarga desde la posición actual del servidor FTP hacia la estructura local correspondiente...")
    descargar_carpetas_recursivamente(ftp, RAIZ_FTP, directorio_actual)
 
    ftp.quit()
