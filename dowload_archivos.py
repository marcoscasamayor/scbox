import os
from ftplib import FTP
import json
import time
from datetime import datetime
import fnmatch

ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
ARCHIVO_OPCIONES = 'scb.options'  # Nombre del archivo de opciones

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    while xDirectorio_actual:
        if xNombre_archivo in os.listdir(xDirectorio_actual):
            return os.path.join(xDirectorio_actual, xNombre_archivo)
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    return None

def leer_configuracion(xRuta_config):
    try:
        with open(xRuta_config, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error al leer configuración: {e}")
        exit()

def leer_opciones(xRuta_opciones):
    try:
        with open(xRuta_opciones, 'r') as file:
            opciones = json.load(file)
            return opciones.get("ignore_list", [])
    except Exception as e:
        print(f"Error al leer el archivo de opciones: {e}")
        return []

def crear_archivo_opciones(xRuta_opciones):
    opciones = {
        "ignore_list": [
            "*.zip",
            "*a",
            "archivoIgnorado.txt"
        ]
    }
    
    try:
        with open(xRuta_opciones, 'w') as file:
            json.dump(opciones, file, indent=2)
        print(f"Archivo de opciones creado: {xRuta_opciones}")
    except Exception as e:
        print(f"Error al crear el archivo de opciones: {e}")

def conectar_ftp(xConfig):
    ftp = FTP(xConfig['FTP']['ftp_server'])
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    return ftp

def obtener_fecha_modificacion_ftp(ftp, archivo):
    try:
        respuesta = ftp.sendcmd(f"MDTM {archivo}")
        fecha_str = respuesta[4:].strip()
        fecha = datetime.strptime(fecha_str, "%Y%m%d%H%M%S")
        return int(time.mktime(fecha.timetuple()))
    except Exception:
        return None

def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list):
    os.makedirs(xRuta_local, exist_ok=True)

    try:
        elementos = xFtp.nlst(xRuta_ftp)
    except Exception as e:
        print(f"Error listando elementos en {xRuta_ftp}: {e}")
        return

    if not elementos:
        return

    for elemento in elementos:
        ruta_completa_ftp = os.path.join(xRuta_ftp, elemento).replace('\\', '/')
        ruta_completa_local = os.path.join(xRuta_local, os.path.basename(elemento))
        base_name = os.path.basename(ruta_completa_ftp)

        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')):
            continue

        if any(fnmatch.fnmatch(base_name, pattern) for pattern in xIgnore_list):
            print(f"Ignorando {base_name} porque coincide con un patrón en ignore_list.")
            continue

        try:
            xFtp.cwd(ruta_completa_ftp)
            try:
                xFtp.nlst()
                if not os.path.exists(ruta_completa_local):
                    os.makedirs(ruta_completa_local)
                    print(f"Carpeta creada: {ruta_completa_local}")
                descargar_archivos_recursivo(xFtp, ruta_completa_ftp, ruta_completa_local, xIgnore_list)
            except Exception:
                continue
        except Exception:
            fecha_ftp = obtener_fecha_modificacion_ftp(xFtp, ruta_completa_ftp)
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
                        xFtp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)
                    os.utime(ruta_completa_local, (fecha_ftp, fecha_ftp))
                except Exception as e:
                    print(f"Error al descargar {ruta_completa_ftp}: {e}")

if __name__ == "__main__":
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
    if not ruta_config:
        print("No se encontró el archivo de configuración. Saliendo...")
        exit()
    
    ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPCIONES, os.getcwd())

    if ruta_opciones:
        print(f"Usando archivo de opciones existente en: {ruta_opciones}")
        ignore_list = leer_opciones(ruta_opciones)
    else:
        print(f"No se encontró el archivo de opciones.")
        ignore_list = []

    carpeta_inicio = os.path.dirname(ruta_config)
    os.chdir(carpeta_inicio)

    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    ruta_inicial_ftp = ftp.pwd()
    ruta_local = os.getcwd()
    
    descargar_archivos_recursivo(ftp, ruta_inicial_ftp, ruta_local, ignore_list)

    ftp.quit()
