import ftplib
import os
import json
from ftplib import FTP
import io
from datetime import datetime
import getpass
import time
import fnmatch
import sys
import os
from datetime import datetime, timezone, timedelta

ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
ARCHIVO_OPTIONS = 'scb.options'  # Nombre del archivo de opciones
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"  # Plantilla para generar logs
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"  # Plantilla para historial de cambios

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en el directorio actual y en los directorios ancestrales.
    """
    while xDirectorio_actual and xDirectorio_actual != os.path.dirname(xDirectorio_actual):  # Bucle hasta que el directorio actual sea None o la raíz

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

def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])  # Crea un objeto FTP con la dirección del servidor
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])  # Inicia sesión con las credenciales del usuario
    return ftp  # Devuelve el objeto FTP

def crear_archivo_opciones(xRuta_opciones):
    """
    Crea un archivo de opciones con una lista de archivos a ignorar.
    """
    opciones = {
        "ignore_list": [
            "ejemplo123.txt"  # Ejemplo de archivo ignorado
        ]
    }
    
    try:
        with open(xRuta_opciones, 'w') as file:  # Abre el archivo de opciones para escritura
            json.dump(opciones, file, indent=2)  # Escribe las opciones como JSON con indentación
        print(f"Archivo de opciones creado: {xRuta_opciones}")  # Imprime mensaje de éxito
    except Exception as e:
        print(f"Error al crear el archivo de opciones: {e}")  # Imprime mensaje de error si falla la creación



def obtener_fecha_modificacion_utc(xFtp=None, ruta_local=None, ruta_ftp=None):
    """
    Obtiene la fecha de modificación de un archivo y la convierte a UTC.
    - Si recibe `ruta_local`, obtiene la fecha del archivo local.
    - Si recibe `xFtp` y `ruta_ftp`, obtiene la fecha del archivo en el FTP.
    
    Retorna un timestamp en UTC o None si hay error o el archivo no existe.
    """
    if ruta_local:  # 📂 Obtener fecha de archivo local
        if not os.path.exists(ruta_local):  
            return None
        try:
            fecha_local = datetime.fromtimestamp(os.path.getmtime(ruta_local), timezone.utc)
            return int(fecha_local.timestamp())  
        except Exception as e:
            print(f"⚠️ Error obteniendo fecha local de {ruta_local}: {e}")
            return None

    elif xFtp and ruta_ftp:  # 🌐 Obtener fecha de archivo en FTP
        try:
            respuesta = xFtp.sendcmd(f"MDTM {ruta_ftp}")
            fecha_ftp = datetime.strptime(respuesta[4:].strip(), "%Y%m%d%H%M%S")
            fecha_ftp = fecha_ftp.replace(tzinfo=timezone.utc)
            return int(fecha_ftp.timestamp())  
        except ftplib.error_perm as e:
            if "550" in str(e):  # Archivo no encontrado en el FTP
                return None
            print(f"⚠️ Error obteniendo fecha FTP de {ruta_ftp}: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error desconocido obteniendo fecha FTP de {ruta_ftp}: {e}")
            return None

    return None  



def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):


    """
    Crea la estructura de carpetas en el servidor FTP basada en las carpetas locales.
    """
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)  # Obtiene la ruta relativa del directorio de origen
    xCarpetas = xRuta_relativa.split(os.sep)  # Divide la ruta en carpetas
    xRuta_actual_ftp = xDestino_dir_ftp  # Inicializa la ruta actual en FTP

    for xCarpeta in xCarpetas:  # Itera sobre cada carpeta
        if xCarpeta:  # Si el nombre de la carpeta no está vacío
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")  # Actualiza la ruta actual en FTP
            try:
                xFtp.cwd(xRuta_actual_ftp)  # Cambia al directorio FTP actual
                xFtp.cwd("..")  # Mueve al directorio padre
            except Exception:
                try:
                    xFtp.mkd(xRuta_actual_ftp)  # Crea la carpeta en el servidor FTP
                    crear_scb_log(xFtp, xRuta_actual_ftp, "creó", xCarpeta, tipo="carpeta")  # Registra la creación de la carpeta
                    print(f"Carpeta creada: {xRuta_actual_ftp}")  # Imprime mensaje de éxito
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")  # Imprime mensaje de error si falla la creación

    return xRuta_actual_ftp  # Devuelve la ruta actual en FTP


def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list):
    """
    Descarga archivos y carpetas recursivamente desde el servidor FTP a la ruta local,
    verificando si deben ser ignorados y comparando fechas en UTC.
    Al guardar los archivos en local, ajusta la fecha a horario argentino (UTC-3).
    """
    os.makedirs(xRuta_local, exist_ok=True)  # Asegurar que la carpeta local existe

    try:
        elementos = xFtp.nlst(xRuta_ftp)  # Lista los archivos y carpetas en el FTP
    except Exception as e:
        print(f"❌ Error listando elementos en {xRuta_ftp}: {e}")
        return

    if not elementos:
        return

    for elemento in elementos:
        ruta_completa_ftp = os.path.join(xRuta_ftp, elemento).replace('\\', '/')
        ruta_completa_local = os.path.join(xRuta_local, os.path.basename(elemento))
        base_name = os.path.basename(ruta_completa_ftp)

        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')):  
            continue  # Ignorar directorios especiales

        if any(fnmatch.fnmatch(base_name, pattern) for pattern in xIgnore_list):
            continue

        try:
            xFtp.cwd(ruta_completa_ftp)  # Si no da error, es un directorio
            if not os.path.exists(ruta_completa_local):  
                os.makedirs(ruta_completa_local)
                print(f"📁 Carpeta creada: {ruta_completa_local}")
            descargar_archivos_recursivo(xFtp, ruta_completa_ftp, ruta_completa_local, xIgnore_list)  # Llamado recursivo
        except Exception:
            # 📌 Comparación de fechas en UTC
            fecha_ftp_utc = obtener_fecha_modificacion_utc(xFtp=xFtp, ruta_ftp=ruta_completa_ftp)
            fecha_local_utc = obtener_fecha_modificacion_utc(ruta_local=ruta_completa_local)

            if fecha_ftp_utc is not None:
                if fecha_local_utc is None or fecha_local_utc < fecha_ftp_utc:
                    print(f"⬇️ Descargando archivo más reciente: {ruta_completa_local}")
                    try:
                        with open(ruta_completa_local, 'wb') as archivo_local:
                            xFtp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)

                        # 🔥 Convertimos la fecha UTC a hora de Argentina (UTC-3) antes de guardarla
                        fecha_ftp_arg = fecha_ftp_utc - 3 * 3600  # Restamos 3 horas en segundos
                        os.utime(ruta_completa_local, (fecha_ftp_arg, fecha_ftp_arg))  

                        # 🔥 Verificación extra para ver si `os.utime()` funcionó
                        nueva_fecha_local = int(os.path.getmtime(ruta_completa_local))
                        diferencia = abs(nueva_fecha_local - fecha_ftp_arg)
                        if diferencia > 2:  # Tolerancia de 2s por diferencias de sistema
                            print(f"⚠️ Advertencia: No se pudo actualizar la fecha de {ruta_completa_local} (Dif: {diferencia}s).")

                    except Exception as e:
                        print(f"❌ Error al descargar {ruta_completa_ftp}: {e}")






def set_fecha_modificacion(xFtp, xRuta_ftp, xFecha_local):
    """
    Establece la fecha de modificación del archivo en el servidor FTP en UTC.
    Pero cuando se usa localmente, se mantiene en horario argentino (UTC-3).
    """
    try:
        # 🔥 Convertimos la fecha de ART (UTC-3) a UTC para enviarla al FTP
        fecha_utc = xFecha_local + timedelta(hours=3)  

        comando_mfmt = f"MFMT {fecha_utc.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}"
        respuesta = xFtp.sendcmd(comando_mfmt)

        # 🔥 Verificación después de intentar modificar la fecha
        nueva_fecha_ftp = obtener_fecha_modificacion_utc(xFtp=xFtp, ruta_ftp=xRuta_ftp)
        if nueva_fecha_ftp is None or nueva_fecha_ftp != int(fecha_utc.timestamp()):
            print(f"⚠️ Advertencia: No se pudo modificar la fecha en el FTP para {xRuta_ftp}")

    except ftplib.error_perm as e:
        print(f"⚠️ Permiso denegado para modificar la fecha de {xRuta_ftp}: {e}")
    except Exception as e:
        print(f"❌ Error inesperado al modificar la fecha de {xRuta_ftp}: {e}")





def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xTipo, xDescripcion):

    """
    Agrega una nueva línea al historial del log con la información proporcionada.
    """
    xFecha_actual = datetime.now().strftime("%d-%m-%Y")  # Obtiene la fecha actual
    xHora_actual = datetime.now().strftime("%H:%M")  # Obtiene la hora actual
    xLinea_historial = HISTORIAL_TEMPLATE.format(  # Formatea la línea del log con la información proporcionada
        fecha=xFecha_actual, hora=xHora_actual, usuario=xUsuario, accion=xAccion, tipo=xTipo, descripcion=xDescripcion
    )
    return f"{xContenido_existente}\n{xLinea_historial}"  # Devuelve el contenido del log actualizado


def crear_scb_log(xFtp, xRuta_ftp=None, xAccion=None, xDescripcion=None, tipo="archivo"):


    """
    Crea o actualiza el archivo de log en el servidor FTP.
    """
    if xRuta_ftp is None:  # Si no se proporciona la ruta FTP, usar el directorio de trabajo actual
        xRuta_ftp = xFtp.pwd()

    xUsuario = getpass.getuser()  # Obtiene el nombre de usuario del usuario actual
    xRuta_log = f"{xRuta_ftp}/scb.log"  # Define la ruta del archivo de log
    xEncabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)  # Crea el encabezado del log

    xContenido_existente = ""  # Inicializa el contenido existente del log
    try:
        with io.BytesIO() as archivo_existente:  # Crea un flujo de bytes para el log existente
            xFtp.retrbinary(f"RETR {xRuta_log}", archivo_existente.write)  # Recupera el log existente del servidor FTP
            xContenido_existente = archivo_existente.getvalue().decode('utf-8')  # Decodifica el contenido del log
    except Exception:
        xContenido_existente = xEncabezado_log  # Si el log no existe, usar el encabezado como contenido

    if xAccion and xDescripcion:  # Si se proporcionan acción y descripción
        xContenido_actualizado = agregar_historial_log(xContenido_existente, xUsuario, xAccion, tipo, xDescripcion)  # Actualiza el contenido del log
    else:
        xContenido_actualizado = xContenido_existente  # Usa el contenido existente si no se necesitan actualizaciones

    xFtp.storbinary(f"STOR {xRuta_log}", io.BytesIO(xContenido_actualizado.encode('utf-8')))  # Almacena el log actualizado en el servidor FTP

def leer_ignore_list(xRuta_options):
    """
    Lee el archivo scb.options y retorna la lista de archivos a ignorar.
    Si el archivo no existe, crea uno con la estructura predeterminada.
    """
    if not os.path.exists(xRuta_options):  # Verifica si el archivo de opciones existe
        # Si no existe el archivo, crearlo con la estructura predeterminada
        opciones = {
            "ignore_list": [
                "ejemplo123.txt",  # Ejemplo de archivo ignorado
            ]
        }
        with open(xRuta_options, 'w') as f:  # Abre el archivo de opciones para escritura
            json.dump(opciones, f, indent=4)  # Escribe las opciones como JSON con indentación
        print(f"El archivo {xRuta_options} no existía, se ha creado con la estructura predeterminada.")  # Imprime mensaje de éxito
        return opciones['ignore_list']  # Devuelve la lista de ignorados
    else:
        try:
            with open(xRuta_options, 'r') as f:  # Abre el archivo de opciones para lectura
                opciones = json.load(f)  # Carga los datos JSON
                return opciones.get('ignore_list', [])  # Devuelve la lista de ignorados o una lista vacía si no se encuentra
        except Exception as e:
            print(f"Error leyendo el archivo {xRuta_options}: {e}")  # Imprime mensaje de error si falla la lectura
            exit()  # Sale del programa


def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp, xIgnore_list):
    """
    Sube archivos y carpetas recursivamente desde la ruta local al servidor FTP,
    comparando fechas en UTC en lugar de tamaño.
    """
    for xNombre in os.listdir(xRuta_local):
        if xNombre == "scb.log":  # Evitar subir logs
            continue

        xRuta_completa_local = os.path.join(xRuta_local, xNombre)
        xRuta_completa_ftp = os.path.join(xRuta_ftp, xNombre).replace("\\", "/")

        if xNombre in xIgnore_list:
            continue

        if os.path.isfile(xRuta_completa_local):
            fecha_mod_local = obtener_fecha_modificacion_utc(ruta_local=xRuta_completa_local)
            fecha_mod_ftp = obtener_fecha_modificacion_utc(xFtp=xFtp, ruta_ftp=xRuta_completa_ftp)

            if fecha_mod_ftp is None or (fecha_mod_local and fecha_mod_local > fecha_mod_ftp):
                try:
                    with open(xRuta_completa_local, 'rb') as file:
                        xFtp.storbinary(f'STOR {xRuta_completa_ftp}', file)

                    set_fecha_modificacion(xFtp, xRuta_completa_ftp, datetime.fromtimestamp(fecha_mod_local))
                    crear_scb_log(xFtp, xRuta_ftp, "actualizó" if fecha_mod_ftp else "creó", xNombre, tipo="archivo")

                    print(f"⬆️ Archivo subido: {xRuta_completa_local} -> {xRuta_completa_ftp}")
                except Exception as e:
                    print(f"❌ Error al subir {xRuta_completa_local}: {e}")

        elif os.path.isdir(xRuta_completa_local):  
            try:
                xFtp.cwd(xRuta_completa_ftp)  # Si no da error, la carpeta ya existe
            except Exception:
                try:
                    xFtp.mkd(xRuta_completa_ftp)  # Crear la carpeta en el servidor
                    crear_scb_log(xFtp, xRuta_ftp, "creó", xNombre, tipo="carpeta")
                    print(f"📁 Carpeta creada en FTP: {xRuta_completa_ftp}")
                except Exception as e:
                    print(f"❌ No se pudo crear la carpeta {xRuta_completa_ftp}: {e}")

            subir_archivos_recursivo(xFtp, xRuta_completa_local, xRuta_completa_ftp, xIgnore_list)




# Función que maneja la subida de archivos (sin cambiar la lógica original)
def subir_archivos():
    xDirectorio_actual = os.getcwd()  # Obtiene el directorio de trabajo actual
    xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, xDirectorio_actual)  # Busca el archivo de configuración
    xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, xDirectorio_actual)  # Busca el archivo de opciones

    if not xRuta_config:  # Si no se encuentra el archivo de configuración
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")
        exit()

    if not xRuta_options:  # Si no se encuentra el archivo de opciones
        print(f"No se encontró el archivo de opciones: {ARCHIVO_OPTIONS}")
        leer_ignore_list(os.path.join(os.path.dirname(xRuta_config), ARCHIVO_OPTIONS))  # Crea el archivo de opciones
        xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(xRuta_config))  # Busca nuevamente el archivo de opciones

    # Leer configuración y lista de ignorados
    xConfig = leer_configuracion(xRuta_config)  # Lee la configuración
    ignore_list = leer_ignore_list(xRuta_options)  # Lee la lista de ignorados
    ftp = conectar_ftp(xConfig)  # Conecta al servidor FTP

    # Ejecutar directamente la opción 2
    xRuta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(xRuta_config))  # Crea la estructura de carpetas en FTP
    subir_archivos_recursivo(ftp, os.getcwd(), xRuta_final_ftp, ignore_list)  # Comienza a subir archivos

    ftp.quit()  # Desconecta del servidor FTP
    print("Operación de subida completada con éxito.")  # Imprime mensaje de éxito

# Función que maneja la bajada de archivos (sin cambiar la lógica original)
def bajar_archivos():
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())  # Busca el archivo de configuración
    if not ruta_config:
        print("No se encontró el archivo de configuración. Saliendo...")
        exit()

    ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(ruta_config))
    if not ruta_opciones:
        crear_archivo_opciones(os.path.join(os.path.dirname(ruta_config), ARCHIVO_OPTIONS))
        ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(ruta_config))

    if ruta_opciones:
        print(f"Usando archivo de opciones existente en: {ruta_opciones}")
        ignore_list = leer_opciones(ruta_opciones)
    else:
        print("No se encontró el archivo de opciones.")
        ignore_list = []

    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    # 🔥 CORRECCIÓN: Mejor cálculo de la ruta FTP inicial
    directorio_base = os.path.dirname(ruta_config)  # Directorio donde está scb.config
    ruta_relativa = os.path.relpath(os.getcwd(), directorio_base)  # Relación entre cwd y base

    # Si ruta_relativa es ".", significa que estamos en la base, no concatenamos nada
    ruta_inicial_ftp = ftp.pwd() if ruta_relativa == "." else os.path.join(ftp.pwd(), ruta_relativa).replace('\\', '/')

    ruta_local = os.getcwd()

    print(f"Ruta FTP desde donde se descargará: {ruta_inicial_ftp}")
    print(f"Ruta local destino: {ruta_local}")

    descargar_archivos_recursivo(ftp, ruta_inicial_ftp, ruta_local, ignore_list)

    ftp.quit()
    print("Operación de descarga completada con éxito.")


def main():
    if len(sys.argv) != 2:
        print("Uso: scbox [u|d]")
        exit()

    operacion = sys.argv[1].strip().lower()

    if operacion == "u":
        print("Iniciando Upload..")
        subir_archivos()  # Llamada a la función de subida
    elif operacion == "d":
        print("Iniciando Dowload..")
        bajar_archivos()  # Llamada a la función de bajada
        
    elif operacion == "s":
        print("Iniciando Sincronizacion..")
        bajar_archivos()
        subir_archivos()
        
    else:
        print("Opción no válida. Debes ingresar 'u' para subir o 'd' para bajar.")
        exit()


if __name__ == "__main__":
    main()
