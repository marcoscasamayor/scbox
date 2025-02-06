import os  # Importando el módulo os para interactuar con el sistema operativo
from ftplib import FTP  # Importando la clase FTP para operaciones FTP
import json  # Importando el módulo json para manejar datos JSON
import time  # Importando el módulo time para funciones relacionadas con el tiempo
from datetime import datetime  # Importando datetime para manipulación de fechas y horas
import fnmatch  # Importando fnmatch para coincidencia de patrones en nombres de archivos

ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
ARCHIVO_OPCIONES = 'scb.options'  # Nombre del archivo de opciones

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en el directorio actual y en los directorios ancestrales.
    """
    while xDirectorio_actual:  # Bucle hasta que el directorio actual sea None
        if xNombre_archivo in os.listdir(xDirectorio_actual):  # Verifica si el archivo existe en el directorio actual
            return os.path.join(xDirectorio_actual, xNombre_archivo)  # Devuelve la ruta completa si se encuentra
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)  # Mueve al directorio padre
    return None  # Devuelve None si no se encuentra el archivo

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(xRuta_config, 'r') as file:  # Abre el archivo de configuración para lectura
            return json.load(file)  # Carga y devuelve los datos JSON como un diccionario
    except Exception as e:
        print(f"Error al leer configuración: {e}")  # Imprime mensaje de error si falla la lectura
        exit()  # Sale del programa

def leer_opciones(xRuta_opciones):
    """
    Lee el archivo de opciones y retorna la lista de archivos a ignorar.
    """
    try:
        with open(xRuta_opciones, 'r') as file:  # Abre el archivo de opciones para lectura
            opciones = json.load(file)  # Carga los datos JSON
            return opciones.get("ignore_list", [])  # Devuelve la lista de ignorados o una lista vacía si no se encuentra
    except Exception as e:
        print(f"Error al leer el archivo de opciones: {e}")  # Imprime mensaje de error si falla la lectura
        return []  # Devuelve una lista vacía

def crear_archivo_opciones(xRuta_opciones):
    """
    Crea un archivo de opciones con una lista de archivos a ignorar.
    """
    opciones = {
        "ignore_list": [
            "*.zip",  # Ignorar archivos zip
            "*a",  # Ignorar archivos que terminan en 'a'
            "archivoIgnorado.txt"  # Ejemplo de archivo ignorado
        ]
    }
    
    try:
        with open(xRuta_opciones, 'w') as file:  # Abre el archivo de opciones para escritura
            json.dump(opciones, file, indent=2)  # Escribe las opciones como JSON con indentación
        print(f"Archivo de opciones creado: {xRuta_opciones}")  # Imprime mensaje de éxito
    except Exception as e:
        print(f"Error al crear el archivo de opciones: {e}")  # Imprime mensaje de error si falla la creación

def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])  # Crea un objeto FTP con la dirección del servidor
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])  # Inicia sesión con las credenciales del usuario
    return ftp  # Devuelve el objeto FTP

def obtener_fecha_modificacion_ftp(ftp, archivo):
    """
    Obtiene la fecha de modificación de un archivo en el servidor FTP.
    """
    try:
        respuesta = ftp.sendcmd(f"MDTM {archivo}")  # Envía el comando para obtener la hora de modificación
        fecha_str = respuesta[4:].strip()  # Extrae la cadena de fecha de la respuesta
        fecha = datetime.strptime(fecha_str, "%Y%m%d%H%M%S")  # Convierte la cadena a un objeto datetime
        return int(time.mktime(fecha.timetuple()))  # Devuelve la marca de tiempo
    except Exception:
        return None  # Devuelve None si ocurre un error

def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list):
    """
    Descarga archivos y carpetas recursivamente desde el servidor FTP a la ruta local,
    verificando si deben ser ignorados.
    """
    os.makedirs(xRuta_local, exist_ok=True)  # Crea el directorio local si no existe

    try:
        elementos = xFtp.nlst(xRuta_ftp)  # Lista los elementos en la ruta FTP
    except Exception as e:
        print(f"Error listando elementos en {xRuta_ftp}: {e}")  # Imprime mensaje de error si falla la lista
        return  # Sale de la función

    if not elementos:  # Si no hay elementos, salir
        return

    for elemento in elementos:  # Itera sobre cada elemento
        ruta_completa_ftp = os.path.join(xRuta_ftp, elemento).replace('\\', '/')  # Obtiene la ruta completa en FTP
        ruta_completa_local = os.path.join(xRuta_local, os.path.basename(elemento))  # Obtiene la ruta local
        base_name = os.path.basename(ruta_completa_ftp)  # Obtiene el nombre base de la ruta FTP

        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')):  # Ignorar directorios especiales
            continue

        if any(fnmatch.fnmatch(base_name, pattern) for pattern in xIgnore_list):  # Verifica si debe ser ignorado
            print(f"Ignorando {base_name} porque coincide con un patrón en ignore_list.")  # Imprime mensaje de ignorar
            continue  # Salta al siguiente elemento

        try:
            xFtp.cwd(ruta_completa_ftp)  # Cambia al directorio FTP
            try:
                xFtp.nlst()  # Intenta listar elementos en el directorio
                if not os.path.exists(ruta_completa_local):  # Si el directorio local no existe, crearlo
                    os.makedirs(ruta_completa_local)
                    print(f"Carpeta creada: {ruta_completa_local}")  # Imprime mensaje de éxito
                descargar_archivos_recursivo(xFtp, ruta_completa_ftp, ruta_completa_local, xIgnore_list)  # Llamada recursiva
            except Exception:
                continue  # Salta si ocurre un error
        except Exception:
            fecha_ftp = obtener_fecha_modificacion_ftp(xFtp, ruta_completa_ftp)  # Obtiene la fecha de modificación
            if fecha_ftp:  # Si la fecha es válida
                if os.path.exists(ruta_completa_local):  # Si el archivo local existe
                    fecha_local = int(os.path.getmtime(ruta_completa_local))  # Obtiene la fecha de modificación local
                    if fecha_local >= fecha_ftp:  # Si el archivo local está actualizado, saltar
                        continue
                    else:
                        print(f"Archivo actualizado: {ruta_completa_local}")  # Imprime mensaje de actualización
                else:
                    print(f"Archivo creado: {ruta_completa_local}")  # Imprime mensaje de creación
                try:
                    with open(ruta_completa_local, 'wb') as archivo_local:  # Abre el archivo local para escritura
                        xFtp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)  # Descarga el archivo
                    os.utime(ruta_completa_local, (fecha_ftp, fecha_ftp))  # Actualiza la fecha de modificación
                except Exception as e:
                    print(f"Error al descargar {ruta_completa_ftp}: {e}")  # Imprime mensaje de error si falla la descarga

if __name__ == "__main__":  # La ejecución del programa principal comienza aquí
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())  # Busca el archivo de configuración
    if not ruta_config:  # Si no se encuentra el archivo de configuración
        print("No se encontró el archivo de configuración. Saliendo...")  # Imprime mensaje de error
        exit()  # Sale del programa
    
    ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPCIONES, os.getcwd())  # Busca el archivo de opciones

    if ruta_opciones:  # Si se encuentra el archivo de opciones
        print(f"Usando archivo de opciones existente en: {ruta_opciones}")  # Imprime mensaje de éxito
        ignore_list = leer_opciones(ruta_opciones)  # Lee la lista de ignorados
    else:
        print("No se encontró el archivo de opciones.")  # Imprime mensaje de error
        ignore_list = []  # Establece la lista de ignorados como vacía

    carpeta_inicio = os.path.dirname(ruta_config)  # Obtiene el directorio del archivo de configuración
    os.chdir(carpeta_inicio)  # Cambia a ese directorio

    config = leer_configuracion(ruta_config)  # Lee la configuración
    ftp = conectar_ftp(config)  # Conecta al servidor FTP

    ruta_inicial_ftp = ftp.pwd()  # Obtiene la ruta inicial en FTP
    ruta_local = os.getcwd()  # Obtiene la ruta local actual
    
    descargar_archivos_recursivo(ftp, ruta_inicial_ftp, ruta_local, ignore_list)  # Comienza a descargar archivos

    ftp.quit()  # Desconecta del servidor FTP
    print("Operación completada con éxito.")  # Imprime mensaje de éxito
