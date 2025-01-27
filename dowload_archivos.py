import os
from ftplib import FTP
import json

ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en los directorios ancestrales.
    """
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):  # Mientras no se llegue al directorio raíz
        for root, _, files in os.walk(xDirectorio_actual):  # Recorre los directorios
            if xNombre_archivo in files:  # Si encuentra el archivo
                return os.path.join(root, xNombre_archivo)  # Retorna la ruta completa del archivo
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)  # Sube un nivel en el directorio
    return None  # Retorna None si no se encuentra el archivo

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(xRuta_config, 'r') as file:  # Abre el archivo de configuración
            return json.load(file)  # Retorna el contenido del archivo como un diccionario
    except Exception as e:  # Captura cualquier excepción
        print(f"Error leyendo el archivo de configuración: {e}")  # Imprime el error
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
        return respuesta[4:].strip()  # Devuelve la fecha en formato AAAAMMDDHHMMSS
    except Exception as e:
        print(f"Error al obtener la fecha de modificación para {archivo}: {e}")
        return None

def descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local):
    """
    Descarga archivos de un servidor FTP recursivamente desde una carpeta específica hacia abajo,
    verificando si los archivos ya existen y están actualizados. Solo muestra mensajes si se actualizan o crean archivos o carpetas.
    """
    os.makedirs(ruta_local, exist_ok=True)  # Crear la carpeta local si no existe

    try:
        elementos = ftp.nlst(ruta_ftp)  # Listar los archivos y carpetas en la ruta actual del FTP
    except Exception as e:
        print(f"Error al listar los elementos en {ruta_ftp}: {e}")
        return

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
            except Exception:
                continue  # No imprimir mensaje, simplemente saltar esta carpeta
            if not os.path.exists(ruta_completa_local):
                os.makedirs(ruta_completa_local)
                print(f"Carpeta creada: {ruta_completa_local}")
            descargar_archivos_recursivo(ftp, ruta_completa_ftp, ruta_completa_local)  # Llamada recursiva
        except Exception:
            # Es un archivo, verificar si ya existe y está actualizado
            fecha_ftp = obtener_fecha_modificacion_ftp(ftp, ruta_completa_ftp)
            if fecha_ftp:
                fecha_ftp = int(fecha_ftp)  # Convertir a entero para comparar
                if os.path.exists(ruta_completa_local):
                    fecha_local = int(os.path.getmtime(ruta_completa_local))
                    if fecha_local >= fecha_ftp:
                        print(f"Archivo {ruta_completa_local} ya está actualizado, se omite la descarga.")
                        continue

            try:
                print(f"Descargando archivo: {ruta_completa_local}")
                with open(ruta_completa_local, 'wb') as archivo_local:
                    ftp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)  # Descargar archivo
                os.utime(ruta_completa_local, (fecha_ftp, fecha_ftp))  # Actualizar fecha de modificación local
                print(f"Archivo {ruta_completa_local} creado o actualizado.")
            except Exception as e:
                print(f"Error al descargar el archivo: {ruta_completa_local}. Detalles: {e}. Verifique si el archivo existe y tiene permisos adecuados.")
if __name__ == "__main__":
    # Buscar el archivo de configuración
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()) 
    if not ruta_config:
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")
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
