import os
from ftplib import FTP
import json
import time
from datetime import datetime

ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
ARCHIVO_OPCIONES = 'scb.options'  # Nombre del archivo de opciones

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo en el directorio actual y en los directorios ancestrales.
    """
    if xNombre_archivo in os.listdir(xDirectorio_actual):
        return os.path.join(xDirectorio_actual, xNombre_archivo)

    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
        if xNombre_archivo in os.listdir(xDirectorio_actual):
            return os.path.join(xDirectorio_actual, xNombre_archivo)

    return None

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(xRuta_config, 'r') as file:
            return json.load(file)
    except Exception:
        exit()

def leer_opciones(xRuta_opciones):
    """
    Lee el archivo de opciones y extrae la lista de archivos a ignorar.
    """
    try:
        with open(xRuta_opciones, 'r') as file:
            opciones = json.load(file)
            return opciones.get("ignore_list", [])
    except Exception:
        return []

def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    return ftp

def obtener_fecha_modificacion_ftp(ftp, archivo):
    """
    Obtiene la fecha de modificación de un archivo en el servidor FTP.
    """
    try:
        respuesta = ftp.sendcmd(f"MDTM {archivo}")
        fecha_str = respuesta[4:].strip()  # AAAAMMDDHHMMSS
        fecha = datetime.strptime(fecha_str, "%Y%m%d%H%M%S")
        return int(time.mktime(fecha.timetuple()))  # Convertir a timestamp en UTC
    except Exception:
        return None

def descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local, ignore_list):
    """
    Descarga archivos de un servidor FTP recursivamente desde una carpeta específica,
    verificando si los archivos ya existen y están actualizados, y si deben ser ignorados.
    """
    os.makedirs(ruta_local, exist_ok=True)

    try:
        elementos = ftp.nlst(ruta_ftp)
    except Exception:
        return

    if not elementos:
        return

    for elemento in elementos:
        ruta_completa_ftp = os.path.join(ruta_ftp, elemento).replace('\\', '/')
        ruta_completa_local = os.path.join(ruta_local, os.path.basename(elemento))

        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')):
            continue

        if any(ignored == os.path.basename(ruta_completa_ftp) for ignored in ignore_list):
            continue

        try:
            ftp.cwd(ruta_completa_ftp)
            try:
                ftp.nlst()
                if not os.path.exists(ruta_completa_local):
                    os.makedirs(ruta_completa_local)
                    print(f"Carpeta creada: {ruta_completa_local}")
                descargar_archivos_recursivo(ftp, ruta_completa_ftp, ruta_completa_local, ignore_list)
            except Exception:
                continue
        except Exception:
            fecha_ftp = obtener_fecha_modificacion_ftp(ftp, ruta_completa_ftp)
            if fecha_ftp:
                if os.path.exists(ruta_completa_local):
                    fecha_local = int(os.path.getmtime(ruta_completa_local))
                    if fecha_local >= fecha_ftp:
                        continue
                    else:
                        print(f"Archivo actualizado: {ruta_completa_local}")
                else:
                    print(f"Archivo creado: {ruta_completa_local}")
                try:
                    with open(ruta_completa_local, 'wb') as archivo_local:
                        ftp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)
                    os.utime(ruta_completa_local, (fecha_ftp, fecha_ftp))
                except Exception:
                    pass

if __name__ == "__main__":
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
    if not ruta_config:
        exit()
    
    ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPCIONES, os.getcwd())
    if not ruta_opciones:
        ignore_list = []
    else:
        ignore_list = leer_opciones(ruta_opciones)
    
    carpeta_inicio = os.path.dirname(ruta_config)
    os.chdir(carpeta_inicio)

    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    ruta_inicial_ftp = ftp.pwd()
    ruta_local = os.getcwd()
    
    descargar_archivos_recursivo(ftp, ruta_inicial_ftp, ruta_local, ignore_list)

    ftp.quit()


"""


"""