import os  
import json  
from ftplib import FTP  
import io  
from datetime import datetime 
import getpass 

# --- Constantes ---
ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"  # Plantilla para generar logs
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} la carpeta {descripcion}"  # Plantilla para historial de cambios

# --- Utilidades generales ---

def buscar_archivo_ancestro(nombre_archivo, directorio_actual):
    """
    Busca el archivo de configuración en los directorios ancestrales.
    """
    while directorio_actual != os.path.dirname(directorio_actual):  # Mientras no se llegue al directorio raíz
        for root, _, files in os.walk(directorio_actual):  # Recorre los directorios
            if nombre_archivo in files:  # Si encuentra el archivo
                return os.path.join(root, nombre_archivo)  # Retorna la ruta completa del archivo
        directorio_actual = os.path.dirname(directorio_actual)  # Sube un nivel en el directorio
    return None  # Retorna None si no se encuentra el archivo

def leer_configuracion(ruta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(ruta_config, 'r') as file:  # Abre el archivo de configuración
            return json.load(file)  # Retorna el contenido del archivo como un diccionario
    except Exception as e:  # Captura cualquier excepción
        print(f"Error leyendo el archivo de configuración: {e}")  # Imprime el error
        exit()  # Sale del programa

# --- Funciones FTP ---

def conectar_ftp(config):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(config['FTP']['ftp_server'])  # Crea una instancia de FTP con el servidor
    ftp.login(user=config['FTP']['ftp_user'], passwd=config['FTP']['ftp_password'])  # Inicia sesión en el servidor FTP
    return ftp  # Retorna la conexión FTP

def agregar_historial_log(contenido_existente, usuario, accion, descripcion):
    """
    Agrega una nueva línea al historial del log con la información proporcionada.
    """
    fecha_actual = datetime.now().strftime("%d-%m-%Y")  # Obtiene la fecha actual
    hora_actual = datetime.now().strftime("%H:%M")  # Obtiene la hora actual
    linea_historial = HISTORIAL_TEMPLATE.format(fecha=fecha_actual, hora=hora_actual, usuario=usuario, accion=accion, descripcion=descripcion)  # Formatea la línea del historial
    return f"{contenido_existente}\n{linea_historial}"  # Retorna el contenido existente más la nueva línea

def crear_scb_log(ftp, ruta_ftp=None, accion=None, descripcion=None):
    """
    Crea o actualiza el archivo de log en el servidor FTP.
    """
    if ruta_ftp is None:  # Si no se proporciona una ruta
        ruta_ftp = ftp.pwd()  # Usa la ruta actual del FTP

    usuario = getpass.getuser()  # Obtiene el nombre de usuario
    ruta_log = f"{ruta_ftp}/scb.log"  # Define la ruta del archivo de log
    encabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=ruta_ftp)  # Crea el encabezado del log

    contenido_existente = ""  # Inicializa el contenido existente
    try:
        with io.BytesIO() as archivo_existente:  # Crea un flujo de bytes
            ftp.retrbinary(f"RETR {ruta_log}", archivo_existente.write)  # Intenta recuperar el archivo de log existente
            contenido_existente = archivo_existente.getvalue().decode('utf-8')  # Decodifica el contenido
    except Exception:  # Si ocurre un error
        contenido_existente = encabezado_log  # Usa el encabezado como contenido

    if accion and descripcion:  # Si se proporciona acción y descripción
        contenido_actualizado = agregar_historial_log(contenido_existente, usuario, accion, descripcion)  # Agrega al log
    else:
        contenido_actualizado = contenido_existente  # Mantiene el contenido existente

    ftp.storbinary(f"STOR {ruta_log}", io.BytesIO(contenido_actualizado.encode('utf-8')))  # Almacena el log actualizado en el servidor FTP
    # No se imprime ningún mensaje relacionado con la fecha

def set_fecha_modificacion(ftp, ruta_ftp, fecha_local):
    """
    Establece la fecha de modificación del archivo en el servidor FTP.
    """
    try:
        comando_mfmt = f"MFMT {fecha_local.strftime('%Y%m%d%H%M%S')} {ruta_ftp}"  # Crea el comando para modificar la fecha
        respuesta = ftp.sendcmd(comando_mfmt)  # Envía el comando al servidor FTP
    except Exception as e:  # Si ocurre un error
        print(f"No se pudo modificar la fecha para {ruta_ftp}: {e}")  # Imprime el error

def crear_estructura_carpetas_ftp(ftp, origen_dir, carpeta_principal, destino_dir_ftp='/'):
    """
    Crea la estructura de carpetas en el servidor FTP basada en las carpetas locales.
    """
    ruta_relativa = os.path.relpath(origen_dir, carpeta_principal)  # Obtiene la ruta relativa
    carpetas = ruta_relativa.split(os.sep)  # Divide la ruta en carpetas
    ruta_actual_ftp = destino_dir_ftp  # Inicializa la ruta actual en el FTP

    for carpeta in carpetas:  # Recorre cada carpeta
        if carpeta:  # Si la carpeta no está vacía
            ruta_actual_ftp = os.path.join(ruta_actual_ftp, carpeta).replace("\\", "/")  # Actualiza la ruta actual
            try:
                ftp.cwd(ruta_actual_ftp)  # Intenta cambiar al directorio
                ftp.cwd("..")  # Sube un nivel
            except Exception:  # Si ocurre un error
                try:
                    ftp.mkd(ruta_actual_ftp)  # Crea la carpeta en el FTP
                    # Solo registrar la creación de la carpeta
                    crear_scb_log(ftp, ruta_actual_ftp, "creó", carpeta)  # Registra la creación en el log
                except Exception as e:  # Si ocurre un error
                    print(f"No se pudo crear la carpeta {ruta_actual_ftp}: {e}")  # Imprime el error

    return ruta_actual_ftp  # Retorna la ruta actual en el FTP

def subir_archivos_recursivo(ftp, ruta_local, ruta_ftp):
    """
    Subir archivos recursivamente desde la ruta local al servidor FTP.
    """
    for nombre in os.listdir(ruta_local):  # Recorre los archivos en la ruta local
        ruta_completa_local = os.path.join(ruta_local, nombre)  # Obtiene la ruta completa del archivo local
        ruta_completa_ftp = os.path.join(ruta_ftp, nombre).replace("\\", "/")  # Obtiene la ruta completa en el FTP

        if os.path.isfile(ruta_completa_local):  # Si es un archivo
            fecha_creacion_local = datetime.fromtimestamp(os.path.getctime(ruta_completa_local))  # Obtiene la fecha de creación
            try:
                # Verificar si el archivo ya existe en el FTP
                tamaño_archivo_ftp = ftp.size(ruta_completa_ftp)  # Obtiene el tamaño del archivo en el FTP
                tamaño_archivo_local = os.path.getsize(ruta_completa_local)  # Obtiene el tamaño del archivo local

                if tamaño_archivo_local != tamaño_archivo_ftp:  # Si el tamaño es diferente, se considera modificado
                    with open(ruta_completa_local, 'rb') as file:  # Abre el archivo local
                        ftp.storbinary(f'STOR {ruta_completa_ftp}', file)  # Sube el archivo al FTP
                    set_fecha_modificacion(ftp, ruta_completa_ftp, fecha_creacion_local)  # Usa la fecha de creación
                    # Registrar el historial en el log después de subir el archivo
                    crear_scb_log(ftp, ruta_ftp, "modificó", nombre)  # Registra la modificación en el log
                    print(f"Archivo actualizado: {ruta_completa_local} -> {ruta_completa_ftp}")  # Imprime el mensaje de actualización
            except Exception:  # Si ocurre un error
                try:
                    with open(ruta_completa_local, 'rb') as file:  # Abre el archivo local
                        ftp.storbinary(f'STOR {ruta_completa_ftp}', file)  # Sube el archivo al FTP
                    set_fecha_modificacion(ftp, ruta_completa_ftp, fecha_creacion_local)  # Usa la fecha de creación
                    # Registrar el historial en el log después de subir el archivo
                    crear_scb_log(ftp, ruta_ftp, "creó", nombre)  # Registra la creación en el log
                    print(f"Archivo creado: {ruta_completa_local} -> {ruta_completa_ftp}")  # Imprime el mensaje de creación
                except Exception as e:  # Si ocurre un error
                    print(f"No se pudo subir el archivo {ruta_completa_local}: {e}")  # Imprime el error
        elif os.path.isdir(ruta_completa_local):  # Si es una carpeta
            try:
                ftp.cwd(ruta_completa_ftp)  # Intenta cambiar al directorio en el FTP
                ftp.cwd("..")  # Sube un nivel
            except Exception:  # Si ocurre un error
                try:
                    ftp.mkd(ruta_completa_ftp)  # Crea la carpeta en el FTP
                    # Registrar la creación de la carpeta en el log
                    crear_scb_log(ftp, ruta_ftp, "creó", nombre)  # Registra la creación en el log
                    print(f"Carpeta creada en FTP: {ruta_completa_ftp}")  # Imprime el mensaje de creación
                except Exception as e:  # Si ocurre un error
                    print(f"No se pudo crear la carpeta {ruta_completa_ftp}: {e}")  # Imprime el error

            # Llamada recursiva para subir los archivos de la subcarpeta
            subir_archivos_recursivo(ftp, ruta_completa_local, ruta_completa_ftp)  # Llama a la función recursivamente

# --- Programa principal ---
if __name__ == "__main__":  # Si el archivo se ejecuta directamente
    # Obtener ruta del archivo de configuración
    directorio_actual = os.getcwd()  # Obtiene el directorio actual
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, directorio_actual)  # Busca el archivo de configuración

    if not ruta_config:  # Si no se encuentra el archivo de configuración
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")  # Imprime el mensaje de error
        exit()  # Sale del programa

    # Leer configuración
    config = leer_configuracion(ruta_config)  # Lee la configuración
    ftp = conectar_ftp(config)  # Conecta al servidor FTP

    # Menú de opciones
    print("Seleccione una opción:")  # Imprime el menú
    print("1. Copiar archivo desde origen a servidor FTP y actualizar scb.log.")  # Opción 1
    print("2. Sincronizar carpetas entre origen y servidor FTP y actualizar scb.log.")  # Opción 2

    opcion = int(input("Ingrese su opción: "))  # Solicita la opción al usuario

    if opcion == 1:  # Si la opción es 1
        for archivo in os.listdir(os.getcwd()):  # Recorre los archivos en el directorio actual
            if os.path.isfile(archivo):  # Si es un archivo
                subir_archivos_recursivo(ftp, os.getcwd(), '/')  # Llama a la función para subir archivos
    elif opcion == 2:  # Si la opción es 2
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(ruta_config))  # Crea la estructura de carpetas en el FTP
        subir_archivos_recursivo(ftp, os.getcwd(), ruta_final_ftp)  # Llama a la función para subir archivos

    ftp.quit()  # Cierra la conexión FTP