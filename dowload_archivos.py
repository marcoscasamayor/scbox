import os
from ftplib import FTP
import json
import time
from datetime import datetime

ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en el directorio actual y en los directorios ancestrales.
    """
    # Primero verifica en el directorio actual
    if xNombre_archivo in os.listdir(xDirectorio_actual):
        return os.path.join(xDirectorio_actual, xNombre_archivo)

    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):  # Mientras no se llegue al directorio raíz
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)  # Sube un nivel en el directorio
        if xNombre_archivo in os.listdir(xDirectorio_actual):  # Si encuentra el archivo
            return os.path.join(xDirectorio_actual, xNombre_archivo)  # Retorna la ruta completa del archivo

    return None  # Retorna None si no se encuentra el archivo

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(xRuta_config, 'r') as file:  # Abre el archivo de configuración
            return json.load(file)  # Retorna el contenido del archivo como un diccionario
    except Exception:
        exit()  # Sale del programa

def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])  # Crea una instancia de FTP con el servidor
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])  # Inicia sesión en el servidor FTP
    return ftp  # Retorna la conexión FTP

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

def descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local):
    """
    Descarga archivos de un servidor FTP recursivamente desde una carpeta específica hacia abajo,
    verificando si los archivos ya existen y están actualizados.
    """
    os.makedirs(ruta_local, exist_ok=True)  # Crear la carpeta local si no existe

    try:
        elementos = ftp.nlst(ruta_ftp)  # Listar los archivos y carpetas en la ruta actual del FTP
    except Exception:
        return

    if not elementos:
        return  # Si no hay archivos ni carpetas, salir

    for elemento in elementos:
        ruta_completa_ftp = os.path.join(ruta_ftp, elemento).replace('\\', '/')
        ruta_completa_local = os.path.join(ruta_local, os.path.basename(elemento))

        # Filtrado de archivos/carpetas problemáticas
        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')): 
            continue  # Saltar los directorios problemáticos

        # Manejo de carpeta vacía o inaccesible
        try:
            ftp.cwd(ruta_completa_ftp)  # Intentar cambiar al directorio
            try:
                ftp.nlst()  # Intentar listar archivos en la carpeta
                # Si llegamos aquí es que el directorio tiene contenido, hacer recursión
                if not os.path.exists(ruta_completa_local):
                    os.makedirs(ruta_completa_local)
                descargar_archivos_recursivo(ftp, ruta_completa_ftp, ruta_completa_local)  # Llamada recursiva
            except Exception:
                # Si no hay contenido, continuar con el siguiente directorio o archivo
                continue
        except Exception:
            # Es un archivo, verificar si ya existe y está actualizado
            fecha_ftp = obtener_fecha_modificacion_ftp(ftp, ruta_completa_ftp)
            if fecha_ftp:
                if os.path.exists(ruta_completa_local):
                    fecha_local = int(os.path.getmtime(ruta_completa_local))
                    if fecha_local >= fecha_ftp:
                        continue  # Si no necesita actualización, omitir
                    else:
                        # Si el archivo existe pero está desactualizado, actualizarlo
                        print(f"Archivo actualizado: {ruta_completa_local}")
                else:
                    # Si el archivo no existe, es un archivo nuevo
                    print(f"Archivo creado: {ruta_completa_local}")
                
                try:
                    with open(ruta_completa_local, 'wb') as archivo_local:
                        ftp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)  # Descargar archivo
                    os.utime(ruta_completa_local, (fecha_ftp, fecha_ftp))  # Actualizar fecha de modificación local
                except Exception:
                    pass

if __name__ == "__main__":
    # Buscar el archivo de configuración
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()) 
    if not ruta_config:
        exit()

    # Establecer la carpeta de inicio
    carpeta_inicio = os.path.dirname(ruta_config)
    os.chdir(carpeta_inicio)

    # Leer configuración y conectar al servidor FTP
    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    # Descargar archivos desde la carpeta inicial en el servidor FTP
    ruta_inicial_ftp = ftp.pwd()
    ruta_local = os.getcwd()

    descargar_archivos_recursivo(ftp, ruta_inicial_ftp, ruta_local)

    ftp.quit()
