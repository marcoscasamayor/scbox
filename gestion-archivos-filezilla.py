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

# --- Funciones FTP ---

def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])  # Crea una instancia de FTP con el servidor
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])  # Inicia sesión en el servidor FTP
    return ftp  # Retorna la conexión FTP

def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xDescripcion):
    """
    Agrega una nueva línea al historial del log con la información proporcionada.
    """
    xFecha_actual = datetime.now().strftime("%d-%m-%Y")  # Obtiene la fecha actual
    xHora_actual = datetime.now().strftime("%H:%M")  # Obtiene la hora actual
    xLinea_historial = HISTORIAL_TEMPLATE.format(fecha=xFecha_actual, hora=xHora_actual, usuario=xUsuario, accion=xAccion, descripcion=xDescripcion)  # Formatea la línea del historial
    return f"{xContenido_existente}\n{xLinea_historial}"  # Retorna el contenido existente más la nueva línea

def crear_scb_log(ftp, xRuta_ftp=None, xAccion=None, xDescripcion=None):
    """
    Crea o actualiza el archivo de log en el servidor FTP.
    """
    if xRuta_ftp is None:  # Si no se proporciona una ruta
        xRuta_ftp = ftp.pwd()  # Usa la ruta actual del FTP

    xUsuario = getpass.getuser()  # Obtiene el nombre de usuario
    xRuta_log = f"{xRuta_ftp}/scb.log"  # Define la ruta del archivo de log
    xEncabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)  # Crea el encabezado del log

    xContenido_existente = ""  # Inicializa el contenido existente
    try:
        with io.BytesIO() as archivo_existente:  # Crea un flujo de bytes
            ftp.retrbinary(f"RETR {xRuta_log}", archivo_existente.write)  # Intenta recuperar el archivo de log existente
            xContenido_existente = archivo_existente.getvalue().decode('utf-8')  # Decodifica el contenido
    except Exception:  # Si ocurre un error
        xContenido_existente = xEncabezado_log  # Usa el encabezado como contenido

    if xAccion and xDescripcion:  # Si se proporciona acción y descripción
        xContenido_actualizado = agregar_historial_log(xContenido_existente, xUsuario, xAccion, xDescripcion)  # Agrega al log
    else:
        xContenido_actualizado = xContenido_existente  # Mantiene el contenido existente

    ftp.storbinary(f"STOR {xRuta_log}", io.BytesIO(xContenido_actualizado.encode('utf-8')))  # Almacena el log actualizado en el servidor FTP
    # No se imprime ningún mensaje relacionado con la fecha

def set_fecha_modificacion(ftp, xRuta_ftp, xFecha_local):
    """
    Establece la fecha de modificación del archivo en el servidor FTP.
    """
    try:
        comando_mfmt = f"MFMT {xFecha_local.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}"  # Crea el comando para modificar la fecha
        respuesta = ftp.sendcmd(comando_mfmt)  # Envía el comando al servidor FTP
    except Exception as e:  # Si ocurre un error
        print(f"No se pudo modificar la fecha para {xRuta_ftp}: {e}")  # Imprime el error

def crear_estructura_carpetas_ftp(ftp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    """
    Crea la estructura de carpetas en el servidor FTP basada en las carpetas locales.
    """
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)  # Obtiene la ruta relativa
    xCarpetas = xRuta_relativa.split(os.sep)  # Divide la ruta en carpetas
    xRuta_actual_ftp = xDestino_dir_ftp  # Inicializa la ruta actual en el FTP

    for xCarpeta in xCarpetas:  # Recorre cada carpeta
        if xCarpeta:  # Si la carpeta no está vacía
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")  # Actualiza la ruta actual
            try:
                ftp.cwd(xRuta_actual_ftp)  # Intenta cambiar al directorio
                ftp.cwd("..")  # Sube un nivel
            except Exception:  # Si ocurre un error
                try:
                    ftp.mkd(xRuta_actual_ftp)  # Crea la carpeta en el FTP
                    # Solo registrar la creación de la carpeta
                    crear_scb_log(ftp, xRuta_actual_ftp, "creó", xCarpeta)  # Registra la creación en el log
                except Exception as e:  # Si ocurre un error
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")  # Imprime el error

    return xRuta_actual_ftp  # Retorna la ruta actual en el FTP

def subir_archivos_recursivo(ftp, xRuta_local, xRuta_ftp):
    """
    Subir archivos recursivamente desde la ruta local al servidor FTP.
    """
    for xNombre in os.listdir(xRuta_local):  # Recorre los archivos en la ruta local
        xRuta_completa_local = os.path.join(xRuta_local, xNombre)  # Obtiene la ruta completa del archivo local
        xRuta_completa_ftp = os.path.join(xRuta_ftp, xNombre).replace("\\", "/")  # Obtiene la ruta completa en el FTP

        if os.path.isfile(xRuta_completa_local):  # Si es un archivo
            xFecha_creacion_local = datetime.fromtimestamp(os.path.getctime(xRuta_completa_local))  # Obtiene la fecha de creación
            try:
                # Verificar si el archivo ya existe en el FTP
                xTamaño_archivo_ftp = ftp.size(xRuta_completa_ftp)  # Obtiene el tamaño del archivo en el FTP
                xTamaño_archivo_local = os.path.getsize(xRuta_completa_local)  # Obtiene el tamaño del archivo local

                if xTamaño_archivo_local != xTamaño_archivo_ftp:  # Si el tamaño es diferente, se considera modificado
                    with open(xRuta_completa_local, 'rb') as file:  # Abre el archivo local
                        ftp.storbinary(f'STOR {xRuta_completa_ftp}', file)  # Sube el archivo al FTP
                    set_fecha_modificacion(ftp, xRuta_completa_ftp, xFecha_creacion_local)  # Usa la fecha de creación
                    # Registrar el historial en el log después de subir el archivo
                    crear_scb_log(ftp, xRuta_ftp, "modificó", xNombre)  # Registra la modificación en el log
                    print(f"Archivo actualizado: {xRuta_completa_local} -> {xRuta_completa_ftp}")  # Imprime el mensaje de actualización
            except Exception:  # Si ocurre un error
                try:
                    with open(xRuta_completa_local, 'rb') as file:  # Abre el archivo local
                        ftp.storbinary(f'STOR {xRuta_completa_ftp}', file)  # Sube el archivo al FTP
                    set_fecha_modificacion(ftp, xRuta_completa_ftp, xFecha_creacion_local)  # Usa la fecha de creación
                    # Registrar el historial en el log después de subir el archivo
                    crear_scb_log(ftp, xRuta_ftp, "creó", xNombre)  # Registra la creación en el log
                    print(f"Archivo creado: {xRuta_completa_local} -> {xRuta_completa_ftp}")  # Imprime el mensaje de creación
                except Exception as e:  # Si ocurre un error
                    print(f"No se pudo subir el archivo {xRuta_completa_local}: {e}")  # Imprime el error
        elif os.path.isdir(xRuta_completa_local):  # Si es una carpeta
            try:
                ftp.cwd(xRuta_completa_ftp)  # Intenta cambiar al directorio en el FTP
                ftp.cwd("..")  # Sube un nivel
            except Exception:  # Si ocurre un error
                try:
                    ftp.mkd(xRuta_completa_ftp)  # Crea la carpeta en el FTP
                    # Registrar la creación de la carpeta en el log
                    crear_scb_log(ftp, xRuta_ftp, "creó", xNombre)  # Registra la creación en el log
                    print(f"Carpeta creada en FTP: {xRuta_completa_ftp}")  # Imprime el mensaje de creación
                except Exception as e:  # Si ocurre un error
                    print(f"No se pudo crear la carpeta {xRuta_completa_ftp}: {e}")  # Imprime el error

            # Llamada recursiva para subir los archivos de la subcarpeta
            subir_archivos_recursivo(ftp, xRuta_completa_local, xRuta_completa_ftp)  # Llama a la función recursivamente

# --- Programa principal ---
if __name__ == "__main__":  # Si el archivo se ejecuta directamente
    # Obtener ruta del archivo de configuración
    xDirectorio_actual = os.getcwd()  # Obtiene el directorio actual
    xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, xDirectorio_actual)  # Busca el archivo de configuración

    if not xRuta_config:  # Si no se encuentra el archivo de configuración
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")  # Imprime el mensaje de error
        exit()  # Sale del programa

    # Leer configuración
    xConfig = leer_configuracion(xRuta_config)  # Lee la configuración
    ftp = conectar_ftp(xConfig)  # Conecta al servidor FTP

    # Menú de opciones
    print("Seleccione una opción:")  # Imprime el menú
    print("1. Copiar archivo desde origen a servidor FTP y actualizar scb.log.")  # Opción 1
    print("2. Sincronizar carpetas entre origen y servidor FTP y actualizar scb.log.")  # Opción 2

    xOpcion = int(input("Ingrese su opción: "))  # Solicita la opción al usuario

    if xOpcion == 1:  # Si la opción es 1
        for archivo in os.listdir(os.getcwd()):  # Recorre los archivos en el directorio actual
            if os.path.isfile(archivo):  # Si es un archivo
                subir_archivos_recursivo(ftp, os.getcwd(), '/')  # Llama a la función para subir archivos
    elif xOpcion == 2:  # Si la opción es 2
        xRuta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(xRuta_config))  # Crea la estructura de carpetas en el FTP
        subir_archivos_recursivo(ftp, os.getcwd(), xRuta_final_ftp)  # Llama a la función para subir archivos

    ftp.quit()  # Cierra la conexión FTP
