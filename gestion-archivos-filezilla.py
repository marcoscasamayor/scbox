import os
import json
from ftplib import FTP
import io
from datetime import datetime
import getpass

# Constantes
ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}"  # Plantilla para generar logs
HISTORIAL_TEMPLATE = "{fecha} el usuario {usuario} modificó {descripcion}"  # Plantilla para historial de cambios

# Utilidades generales
def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca un archivo en los directorios ascendentes.
    
    Parámetros:
    - xNombre_archivo: El nombre del archivo a buscar.
    - xDirectorio_actual: El directorio donde comenzar la búsqueda.
    
    Retorna:
    - La ruta completa del archivo si se encuentra, de lo contrario, retorna None.
    """
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        for root, _, files in os.walk(xDirectorio_actual):
            if xNombre_archivo in files:
                return os.path.join(root, xNombre_archivo)
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    return None

def extraer_fecha_log(xContenido):
    """
    Extrae la fecha de un archivo de log.
    
    Parámetros:
    - contenido: El contenido del archivo de log como cadena.
    
    Retorna:
    - La fecha extraída como objeto datetime, o datetime.min si no se encuentra una fecha.
    """
    try:
        for linea in xContenido.splitlines():
            if "Log generado el" in linea:
                fecha_str = linea.split(": ", 1)[1]
                return datetime.fromisoformat(fecha_str)
    except Exception:
        pass
    return datetime.min

def leer_configuracion(xRuta_config):
    """
    Lee la configuración desde un archivo JSON.
    
    Parámetros:
    - ruta_config: Ruta del archivo de configuración JSON.
    
    Retorna:
    - El contenido del archivo de configuración como diccionario, o termina el programa si ocurre un error.
    """
    try:
        with open(xRuta_config, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error leyendo el archivo de configuración: {e}")
        exit()

# Funciones FTP
def conectar_ftp(xConfig):
    """
    Establece conexión con el servidor FTP.
    
    Parámetros:
    - config: Diccionario de configuración que contiene los datos del servidor FTP.
    
    Retorna:
    - Un objeto FTP conectado al servidor.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    return ftp

def debe_actualizar_log(xFtp, xRuta_log, xContenido_nuevo):
    """
    Determina si el log debe actualizarse basado en las fechas.
    
    Parámetros:
    - xFtp: Objeto FTP conectado al servidor.
    - xRuta_log: Ruta del archivo de log en el servidor FTP.
    - xContenido_nuevo: El nuevo contenido del log a comparar.
    
    Retorna:
    - True si el log debe actualizarse, False en caso contrario.
    """
    try:
        with io.BytesIO() as archivo_existente:
            xFtp.retrbinary(f"RETR {xRuta_log}", archivo_existente.write)
            contenido_existente = archivo_existente.getvalue().decode('utf-8')
        fecha_existente = extraer_fecha_log(contenido_existente)
        fecha_nueva = extraer_fecha_log(xContenido_nuevo)
        return fecha_nueva > fecha_existente
    except Exception:
        return True

def agregar_historial_log(xContenido_log, xUsuario, xDescripcion):
    """
    Agrega una entrada al historial de modificaciones en el contenido del log.
    
    Parámetros:
    - xContenido_log: El contenido actual del log.
    - usuario: El nombre del usuario que realiza la modificación.
    - descripcion: Descripción de la modificación.
    
    Retorna:
    - El contenido del log con la nueva entrada de historial.
    """
    fecha_actual = datetime.now().strftime("%d-%m-%Y %H:%M")
    linea_historial = HISTORIAL_TEMPLATE.format(fecha=fecha_actual, usuario=xUsuario, descripcion=xDescripcion)
    return f"{xContenido_log}\n{linea_historial}"

def es_carpeta(xFtp, xElemento):
    """
    Verifica si un elemento en el servidor FTP es una carpeta.
    
    Parámetros:
    - ftp: Objeto FTP conectado al servidor.
    - elemento: El nombre del elemento a verificar.
    
    Retorna:
    - True si el elemento es una carpeta, False en caso contrario.
    """
    try:
        xFtp.cwd(xElemento)
        xFtp.cwd("..")
        return True
    except Exception:
        return False

def crear_scb_log_por_carpeta(xFtp, xRuta_ftp=None):
    """
    Crea o actualiza un archivo scb.log en la carpeta actual del servidor FTP.
    
    Parámetros:
    - xFtp: Objeto FTP conectado al servidor.
    - xRuta_ftp: Ruta en el servidor FTP donde se encuentra la carpeta. Si no se proporciona, se utiliza la ruta actual.
    """
    if xRuta_ftp is None:
        xRuta_ftp = xFtp.pwd()  # Obtener la ruta actual en el servidor FTP

    usuario = getpass.getuser()
    contenido_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)
    contenido_log = agregar_historial_log(contenido_log, usuario, "creación o actualización del archivo log")
    ruta_log = f"{xRuta_ftp}/scb.log"

    if debe_actualizar_log(xFtp, ruta_log, contenido_log):
        xFtp.storbinary(f"STOR {ruta_log}", io.BytesIO(contenido_log.encode('utf-8')))
        print(f"Archivo actualizado o creado: {ruta_log}")
    else:
        print(f"El archivo existente es más reciente: {ruta_log}")

        
def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    """Crea la estructura de carpetas en el servidor FTP sin imprimir mensajes innecesarios."""
    # Calcular la ruta relativa entre el directorio actual y la carpeta principal
    ruta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    
    # Dividir la ruta relativa en segmentos de carpetas
    carpetas = ruta_relativa.split(os.sep)
    
    # Inicializar la ruta actual en el servidor FTP
    ruta_actual_ftp = xDestino_dir_ftp
    
    # Recorrer cada carpeta y crearla en el servidor FTP
    for carpeta in carpetas:
        if carpeta:  # Evitar carpetas vacías
            ruta_actual_ftp = os.path.join(ruta_actual_ftp, carpeta).replace("\\", "/")
            
            # Verificar si la carpeta ya existe
            try:
                xFtp.cwd(ruta_actual_ftp)  # Intentar entrar a la carpeta
                xFtp.cwd("..")  # Volver a la carpeta anterior
            except Exception:
                try:
                    xFtp.mkd(ruta_actual_ftp)  # Crear la carpeta si no existe
                    print(f"Carpeta creada: {ruta_actual_ftp}")  # Solo imprime si se crea la carpeta
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_actual_ftp}: {e}")
    
    return ruta_actual_ftp


def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp):
    """Sube archivos y carpetas al servidor FTP de manera recursiva, y muestra un mensaje si no hay archivos nuevos para subir."""
    archivos_subidos = False  # Variable para controlar si se suben archivos

    for nombre in os.listdir(xRuta_local):
        ruta_completa_local = os.path.join(xRuta_local, nombre)
        ruta_completa_ftp = os.path.join(xRuta_ftp, nombre).replace("\\", "/")

        if os.path.isfile(ruta_completa_local):
            # Verificar si el archivo ya existe en el FTP
            try:
                xFtp.size(ruta_completa_ftp)  # Intentar obtener el tamaño del archivo en el FTP
                # Si no hay excepción, el archivo ya existe, por lo que no se sube
            except Exception:
                # Si ocurre una excepción, significa que el archivo no existe, entonces lo subimos
                try:
                    with open(ruta_completa_local, 'rb') as file:
                        xFtp.storbinary(f'STOR {ruta_completa_ftp}', file)
                    print(f"Archivo subido: {ruta_completa_local} -> {ruta_completa_ftp}")
                    archivos_subidos = True  # Se marca que se subió un archivo
                except Exception as e:
                    print(f"No se pudo subir el archivo {ruta_completa_local}: {e}")
        elif os.path.isdir(ruta_completa_local):
            try:
                # Verificar si la carpeta ya existe
                xFtp.cwd(ruta_completa_ftp)  # Intentar entrar a la carpeta
                xFtp.cwd("..")  # Volver a la carpeta anterior
            except Exception:
                try:
                    xFtp.mkd(ruta_completa_ftp)  # Crear la carpeta si no existe
                    print(f"Carpeta creada en FTP: {ruta_completa_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_completa_ftp}: {e}")
            
            # Subir archivos en la subcarpeta
            subir_archivos_recursivo(ftp, ruta_completa_local, ruta_completa_ftp)

    if not archivos_subidos and xRuta_local == os.getcwd():
        print("Sin archivos para subir.") 

# Programa principal
if __name__ == "__main__":
    xDirectorio_actual = os.getcwd()
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, xDirectorio_actual)

    if not ruta_config:
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")
        exit()

    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    print("Seleccione una opción:")
    print("1. Copiar archivo desde origen a servidor FTP.")
    print("2. Sincronizar carpetas entre origen y servidor FTP.")
    print("3. Crear o actualizar archivos scb.log en todas las carpetas del servidor FTP.")

    opcion = int(input("Ingrese su opción: "))

    if opcion == 1:
        for archivo in os.listdir(os.getcwd()):
            if os.path.isfile(archivo):
                subir_archivos_recursivo(ftp, os.getcwd(), '/')
    elif opcion == 2:
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(ruta_config))
        subir_archivos_recursivo(ftp, os.getcwd(), ruta_final_ftp)
    elif opcion == 3:
        ruta_actual_local = os.getcwd()
        ruta_actual_ftp = crear_estructura_carpetas_ftp(ftp, ruta_actual_local, os.path.dirname(ruta_config))
        crear_scb_log_por_carpeta(ftp, ruta_actual_ftp)

    ftp.quit()
