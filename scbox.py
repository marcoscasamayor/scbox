# Importa la biblioteca ftplib para manejar conexiones FTP
import ftplib
# Importa la biblioteca os para interactuar con el sistema operativo
import os
# Importa la biblioteca json para manejar datos en formato JSON
import json
# Importa la clase FTP de la biblioteca ftplib
from ftplib import FTP
# Importa la biblioteca io para manejar flujos de entrada/salida
import io
# Importa las clases datetime y timezone de la biblioteca datetime para manejar fechas y horas
from datetime import datetime
# Importa la biblioteca getpass para obtener el nombre de usuario del sistema
import getpass
# Importa la biblioteca time para manejar funciones relacionadas con el tiempo
import time
# Importa la biblioteca fnmatch para hacer coincidencias de patrones en nombres de archivos
import fnmatch
# Importa la biblioteca sys para interactuar con el intérprete de Python
import sys
# Importa la biblioteca os nuevamente (no es necesario, se puede eliminar)
import os
# Importa las clases datetime y timezone de la biblioteca datetime nuevamente (no es necesario, se puede eliminar)
from datetime import datetime, timezone, timedelta

# Define el nombre del archivo de configuración
ARCHIVO_CONFIG = 'scb.config'
# Define el nombre del archivo de opciones
ARCHIVO_OPTIONS = 'scb.options'
# Define una plantilla para generar logs
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"
# Define una plantilla para el historial de cambios
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"

# Función que busca el archivo de configuración en el directorio actual y en los directorios ancestrales
def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en el directorio actual y en los directorios ancestrales.
    """
    # Bucle hasta que el directorio actual sea None o la raíz
    while xDirectorio_actual and xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        # Verifica si el archivo existe en el directorio actual
        if xNombre_archivo in os.listdir(xDirectorio_actual):
            # Devuelve la ruta completa si se encuentra
            return os.path.join(xDirectorio_actual, xNombre_archivo)
        # Mueve al directorio padre
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    # Devuelve None si no se encuentra el archivo
    return None

# Función que lee el archivo de configuración y lo retorna como un diccionario
def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        # Abre el archivo de configuración para lectura
        with open(xRuta_config, 'r') as file:
            # Carga y devuelve los datos JSON como un diccionario
            return json.load(file)
    except Exception as e:
        # Imprime mensaje de error si falla la lectura
        print(f"Error al leer configuración: {e}")
        # Sale del programa
        exit()

# Función que lee el archivo de opciones y retorna la lista de archivos a ignorar
def leer_opciones(xRuta_opciones):
    """
    Lee el archivo de opciones y retorna la lista de archivos a ignorar.
    """
    try:
        # Abre el archivo de opciones para lectura
        with open(xRuta_opciones, 'r') as file:
            # Carga los datos JSON
            opciones = json.load(file)
            # Devuelve la lista de ignorados o una lista vacía si no se encuentra
            return opciones.get("ignore_list", [])
    except Exception as e:
        # Imprime mensaje de error si falla la lectura
        print(f"Error al leer el archivo de opciones: {e}")
        # Devuelve una lista vacía
        return []

# Función que conecta al servidor FTP utilizando la configuración proporcionada
def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    # Crea un objeto FTP con la dirección del servidor
    ftp = FTP(xConfig['FTP']['ftp_server'])
    # Inicia sesión con las credenciales del usuario
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    # Devuelve el objeto FTP
    return ftp

# Función que crea un archivo de opciones con una lista de archivos a ignorar
def crear_archivo_opciones(xRuta_opciones):
    """
    Crea un archivo de opciones con una lista de archivos a ignorar.
    """
    # Define las opciones con un archivo de ejemplo a ignorar
    opciones = {
        "ignore_list": [
            "ejemplo123.txt"  # Ejemplo de archivo ignorado
        ]
    }
    
    try:
        # Abre el archivo de opciones para escritura
        with open(xRuta_opciones, 'w') as file:
            # Escribe las opciones como JSON con indentación
            json.dump(opciones, file, indent=2)
        # Imprime mensaje de éxito
        print(f"Archivo de opciones creado: {xRuta_opciones}")
    except Exception as e:
        # Imprime mensaje de error si falla la creación
        print(f"Error al crear el archivo de opciones: {e}")

# Función que obtiene la fecha de modificación de un archivo y la convierte a UTC
def obtener_fecha_modificacion_utc(xFtp=None, ruta_local=None, ruta_ftp=None):
    """
    Obtiene la fecha de modificación de un archivo y la convierte a UTC.
    - Si recibe `ruta_local`, obtiene la fecha del archivo local.
    - Si recibe `xFtp` y `ruta_ftp`, obtiene la fecha del archivo en el FTP.
    
    Retorna un timestamp en UTC o None si hay error o el archivo no existe.
    """
    # 📂 Obtener fecha de archivo local
    if ruta_local:
        # Verifica si el archivo local existe
        if not os.path.exists(ruta_local):  
            return None
        try:
            # Obtiene la fecha de modificación del archivo local y la convierte a UTC
            fecha_local = datetime.fromtimestamp(os.path.getmtime(ruta_local), timezone.utc)
            return int(fecha_local.timestamp())  
        except Exception as e:
            # Imprime mensaje de error si falla la obtención de la fecha
            print(f"⚠️ Error obteniendo fecha local de {ruta_local}: {e}")
            return None

    # 🌐 Obtener fecha de archivo en FTP
    elif xFtp and ruta_ftp:
        try:
            # Envía el comando MDTM para obtener la fecha de modificación del archivo en el FTP
            respuesta = xFtp.sendcmd(f"MDTM {ruta_ftp}")
            # Convierte la respuesta a un objeto datetime
            fecha_ftp = datetime.strptime(respuesta[4:].strip(), "%Y%m%d%H%M%S")
            # Establece la zona horaria a UTC
            fecha_ftp = fecha_ftp.replace(tzinfo=timezone.utc)
            return int(fecha_ftp.timestamp())  
        except ftplib.error_perm as e:
            # Verifica si el archivo no fue encontrado en el FTP
            if "550" in str(e):
                return None
            # Imprime mensaje de error si falla la obtención de la fecha
            print(f"⚠️ Error obteniendo fecha FTP de {ruta_ftp}: {e}")
            return None
        except Exception as e:
            # Imprime mensaje de error desconocido si falla la obtención de la fecha
            print(f"⚠️ Error desconocido obteniendo fecha FTP de {ruta_ftp}: {e}")
            return None

    return None  

# Función que crea la estructura de carpetas en el servidor FTP basada en las carpetas locales
def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    """
    Crea la estructura de carpetas en el servidor FTP basada en las carpetas locales.
    """
    # Obtiene la ruta relativa del directorio de origen
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    # Divide la ruta en carpetas
    xCarpetas = xRuta_relativa.split(os.sep)
    # Inicializa la ruta actual en FTP
    xRuta_actual_ftp = xDestino_dir_ftp

    # Itera sobre cada carpeta
    for xCarpeta in xCarpetas:
        # Si el nombre de la carpeta no está vacío
        if xCarpeta:
            # Actualiza la ruta actual en FTP
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")
            try:
                # Cambia al directorio FTP actual
                xFtp.cwd(xRuta_actual_ftp)
                # Mueve al directorio padre
                xFtp.cwd("..")
            except Exception:
                try:
                    # Crea la carpeta en el servidor FTP
                    xFtp.mkd(xRuta_actual_ftp)
                    # Registra la creación de la carpeta
                    crear_scb_log(xFtp, xRuta_actual_ftp, "creó", xCarpeta, tipo="carpeta")
                    # Imprime mensaje de éxito
                    print(f"Carpeta creada: {xRuta_actual_ftp}")
                except Exception as e:
                    # Imprime mensaje de error si falla la creación
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")

    # Devuelve la ruta actual en FTP
    return xRuta_actual_ftp  

# Función que descarga archivos y carpetas recursivamente desde el servidor FTP a la ruta local
def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list):
    """
    Descarga archivos y carpetas recursivamente desde el servidor FTP a la ruta local,
    verificando si deben ser ignorados y comparando fechas en UTC.
    Al guardar los archivos en local, ajusta la fecha a horario argentino (UTC-3).
    """
    # Asegurar que la carpeta local existe
    os.makedirs(xRuta_local, exist_ok=True)

    try:
        # Lista los archivos y carpetas en el FTP
        elementos = xFtp.nlst(xRuta_ftp)
    except Exception as e:
        # Imprime mensaje de error si falla la lista de elementos
        print(f"❌ Error listando elementos en {xRuta_ftp}: {e}")
        return

    # Si no hay elementos, salir de la función
    if not elementos:
        return

    # Itera sobre cada elemento
    for elemento in elementos:
        # Obtiene la ruta completa en FTP
        ruta_completa_ftp = os.path.join(xRuta_ftp, elemento).replace('\\', '/')
        # Obtiene la ruta completa local
        ruta_completa_local = os.path.join(xRuta_local, os.path.basename(elemento))
        # Obtiene el nombre base del elemento
        base_name = os.path.basename(ruta_completa_ftp)

        # Ignorar directorios especiales
        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')):  
            continue  

        # Verifica si el elemento debe ser ignorado
        if any(fnmatch.fnmatch(base_name, pattern) for pattern in xIgnore_list):
            continue

        try:
            # Si no da error, es un directorio
            xFtp.cwd(ruta_completa_ftp)
            # Si no existe la carpeta local, crearla
            if not os.path.exists(ruta_completa_local):  
                os.makedirs(ruta_completa_local)
                print(f"📁 Carpeta creada: {ruta_completa_local}")
            # Llamado recursivo para descargar archivos
            descargar_archivos_recursivo(xFtp, ruta_completa_ftp, ruta_completa_local, xIgnore_list)
        except Exception:
            # 📌 Comparación de fechas en UTC
            fecha_ftp_utc = obtener_fecha_modificacion_utc(xFtp=xFtp, ruta_ftp=ruta_completa_ftp)
            fecha_local_utc = obtener_fecha_modificacion_utc(ruta_local=ruta_completa_local)

            # Si la fecha del FTP es válida
            if fecha_ftp_utc is not None:
                # Si el archivo local no existe o es más antiguo que el del FTP
                if fecha_local_utc is None or fecha_local_utc < fecha_ftp_utc:
                    print(f"⬇️ Descargando archivo más reciente: {ruta_completa_local}")
                    try:
                        # Abre el archivo local para escritura
                        with open(ruta_completa_local, 'wb') as archivo_local:
                            # Descarga el archivo desde el FTP
                            xFtp.retrbinary(f"RETR {ruta_completa_ftp}", archivo_local.write)

                        # Actualiza la fecha de modificación del archivo local
                        os.utime(ruta_completa_local, (fecha_ftp_utc, fecha_ftp_utc))  

                        ''' 🔥 Verificación extra para ver si `os.utime()` funcionó
                        nueva_fecha_local = int(os.path.getmtime(ruta_completa_local))
                        diferencia = abs(nueva_fecha_local - fecha_ftp_utc)
                        if diferencia > 2:  # Tolerancia de 2s por diferencias de sistema
                            print(f"⚠️ Advertencia: No se pudo actualizar la fecha de {ruta_completa_local} (Dif: {diferencia}s).")'''
                    except Exception as e:
                        # Imprime mensaje de error si falla la descarga
                        print(f"❌ Error al descargar {ruta_completa_ftp}: {e}")

# Función que establece la fecha de modificación del archivo en el servidor FTP en UTC
def set_fecha_modificacion(xFtp, xRuta_ftp, xFecha_local):
    """
    Establece la fecha de modificación del archivo en el servidor FTP en UTC.
    Pero cuando se usa localmente, se mantiene en horario argentino (UTC-3).
    """
    try:
        # 🔥 Convertimos la fecha de ART (UTC-3) a UTC para enviarla al FTP
        fecha_utc = xFecha_local + timedelta(hours=3)  

        # Comando para modificar la fecha en el FTP
        comando_mfmt = f"MFMT {fecha_utc.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}"
        # Envía el comando al servidor FTP
        respuesta = xFtp.sendcmd(comando_mfmt)

        ''' 🔥 Verificación después de intentar modificar la fecha
        nueva_fecha_ftp = obtener_fecha_modificacion_utc(xFtp=xFtp, ruta_ftp=xRuta_ftp)
        if nueva_fecha_ftp is None or nueva_fecha_ftp != int(fecha_utc.timestamp()):
            print(f"⚠️ Advertencia: No se pudo modificar la fecha en el FTP para {xRuta_ftp}")'''

    except ftplib.error_perm as e:
        # Imprime mensaje de error si se deniega el permiso para modificar la fecha
        print(f"⚠️ Permiso denegado para modificar la fecha de {xRuta_ftp}: {e}")
    
    except Exception as e:
        # Imprime mensaje de error inesperado si falla la modificación de la fecha
        print(f"❌ Error inesperado al modificar la fecha de {xRuta_ftp}: {e}")

# Función que agrega una nueva línea al historial del log con la información proporcionada
def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xTipo, xDescripcion):
    """
    Agrega una nueva línea al historial del log con la información proporcionada.
    """
    # Obtiene la fecha actual
    xFecha_actual = datetime.now().strftime("%d-%m-%Y")
    # Obtiene la hora actual
    xHora_actual = datetime.now().strftime("%H:%M")
    # Formatea la línea del log con la información proporcionada
    xLinea_historial = HISTORIAL_TEMPLATE.format(
        fecha=xFecha_actual, hora=xHora_actual, usuario=xUsuario, accion=xAccion, tipo=xTipo, descripcion=xDescripcion
    )
    # Devuelve el contenido del log actualizado
    return f"{xContenido_existente}\n{xLinea_historial}"

# Función que crea o actualiza el archivo de log en el servidor FTP
def crear_scb_log(xFtp, xRuta_ftp=None, xAccion=None, xDescripcion=None, tipo="archivo"):
    """
    Crea o actualiza el archivo de log en el servidor FTP.
    """
    # Si no se proporciona la ruta FTP, usar el directorio de trabajo actual
    if xRuta_ftp is None:
        xRuta_ftp = xFtp.pwd()

    # Obtiene el nombre de usuario del usuario actual
    xUsuario = getpass.getuser()
    # Define la ruta del archivo de log
    xRuta_log = f"{xRuta_ftp}/scb.log"
    # Crea el encabezado del log
    xEncabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)

    # Inicializa el contenido existente del log
    xContenido_existente = ""
    try:
        # Crea un flujo de bytes para el log existente
        with io.BytesIO() as archivo_existente:
            # Recupera el log existente del servidor FTP
            xFtp.retrbinary(f"RETR {xRuta_log}", archivo_existente.write)
            # Decodifica el contenido del log
            xContenido_existente = archivo_existente.getvalue().decode('utf-8')
    except Exception:
        # Si el log no existe, usar el encabezado como contenido
        xContenido_existente = xEncabezado_log

    # Si se proporcionan acción y descripción
    if xAccion and xDescripcion:
        # Actualiza el contenido del log
        xContenido_actualizado = agregar_historial_log(xContenido_existente, xUsuario, xAccion, tipo, xDescripcion)
    else:
        # Usa el contenido existente si no se necesitan actualizaciones
        xContenido_actualizado = xContenido_existente

    # Almacena el log actualizado en el servidor FTP
    xFtp.storbinary(f"STOR {xRuta_log}", io.BytesIO(xContenido_actualizado.encode('utf-8')))

# Función que lee el archivo scb.options y retorna la lista de archivos a ignorar
def leer_ignore_list(xRuta_options):
    """
    Lee el archivo scb.options y retorna la lista de archivos a ignorar.
    Si el archivo no existe, crea uno con la estructura predeterminada.
    """
    # Verifica si el archivo de opciones existe
    if not os.path.exists(xRuta_options):
        # Si no existe el archivo, crearlo con la estructura predeterminada
        opciones = {
            "ignore_list": [
                "ejemplo123.txt",  # Ejemplo de archivo ignorado
            ]
        }
        # Abre el archivo de opciones para escritura
        with open(xRuta_options, 'w') as f:
            # Escribe las opciones como JSON con indentación
            json.dump(opciones, f, indent=4)
        # Imprime mensaje de éxito
        print(f"El archivo {xRuta_options} no existía, se ha creado con la estructura predeterminada.")
        # Devuelve la lista de ignorados
        return opciones['ignore_list']
    else:
        try:
            # Abre el archivo de opciones para lectura
            with open(xRuta_options, 'r') as f:
                # Carga los datos JSON
                opciones = json.load(f)
                # Devuelve la lista de ignorados o una lista vacía si no se encuentra
                return opciones.get('ignore_list', [])
        except Exception as e:
            # Imprime mensaje de error si falla la lectura
            print(f"Error leyendo el archivo {xRuta_options}: {e}")
            # Sale del programa
            exit()

# Función que sube archivos y carpetas recursivamente desde la ruta local al servidor FTP
def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp, xIgnore_list):
    """
    Sube archivos y carpetas recursivamente desde la ruta local al servidor FTP,
    comparando fechas en UTC en lugar de tamaño.
    """
    # Itera sobre cada nombre en el directorio local
    for xNombre in os.listdir(xRuta_local):
        # Evitar subir logs
        if xNombre == "scb.log":
            continue

        # Obtiene la ruta completa local
        xRuta_completa_local = os.path.join(xRuta_local, xNombre)
        # Obtiene la ruta completa en FTP
        xRuta_completa_ftp = os.path.join(xRuta_ftp, xNombre).replace("\\", "/")

        # Verifica si el elemento debe ser ignorado
        if xNombre in xIgnore_list:
            continue

        # Si es un archivo
        if os.path.isfile(xRuta_completa_local):
            # Obtiene la fecha de modificación del archivo local
            fecha_mod_local = obtener_fecha_modificacion_utc(ruta_local=xRuta_completa_local)
            # Obtiene la fecha de modificación del archivo en el FTP
            fecha_mod_ftp = obtener_fecha_modificacion_utc(xFtp=xFtp, ruta_ftp=xRuta_completa_ftp)

            # Si el archivo en FTP no existe o el local es más reciente
            if fecha_mod_ftp is None or (fecha_mod_local and fecha_mod_local > fecha_mod_ftp):
                try:
                    # Abre el archivo local para lectura
                    with open(xRuta_completa_local, 'rb') as file:
                        # Sube el archivo al FTP
                        xFtp.storbinary(f'STOR {xRuta_completa_ftp}', file)

                    # Establece la fecha de modificación en el FTP
                    set_fecha_modificacion(xFtp, xRuta_completa_ftp, datetime.fromtimestamp(fecha_mod_local))
                    # Crea un log de la acción
                    crear_scb_log(xFtp, xRuta_ftp, "actualizó" if fecha_mod_ftp else "creó", xNombre, tipo="archivo")

                    # Imprime mensaje de éxito
                    print(f"⬆️ Archivo subido: {xRuta_completa_local} -> {xRuta_completa_ftp}")
                except Exception as e:
                    # Imprime mensaje de error si falla la subida
                    print(f"❌ Error al subir {xRuta_completa_local}: {e}")

        # Si es un directorio
        elif os.path.isdir(xRuta_completa_local):  
            try:
                # Si no da error, la carpeta ya existe
                xFtp.cwd(xRuta_completa_ftp)
            except Exception:
                try:
                    # Crear la carpeta en el servidor
                    xFtp.mkd(xRuta_completa_ftp)
                    # Crea un log de la acción
                    crear_scb_log(xFtp, xRuta_ftp, "creó", xNombre, tipo="carpeta")
                    # Imprime mensaje de éxito
                    print(f"📁 Carpeta creada en FTP: {xRuta_completa_ftp}")
                except Exception as e:
                    # Imprime mensaje de error si falla la creación
                    print(f"❌ No se pudo crear la carpeta {xRuta_completa_ftp}: {e}")

            # Llamado recursivo para subir archivos
            subir_archivos_recursivo(xFtp, xRuta_completa_local, xRuta_completa_ftp, xIgnore_list)

# Función que maneja la subida de archivos (sin cambiar la lógica original)
def subir_archivos():
    # Obtiene el directorio de trabajo actual
    xDirectorio_actual = os.getcwd()
    # Busca el archivo de configuración
    xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, xDirectorio_actual)
    # Busca el archivo de opciones
    xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, xDirectorio_actual)

    # Si no se encuentra el archivo de configuración
    if not xRuta_config:
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")
        exit()

    # Si no se encuentra el archivo de opciones
    if not xRuta_options:
        print(f"No se encontró el archivo de opciones: {ARCHIVO_OPTIONS}")
        # Crea el archivo de opciones
        leer_ignore_list(os.path.join(os.path.dirname(xRuta_config), ARCHIVO_OPTIONS))
        # Busca nuevamente el archivo de opciones
        xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(xRuta_config))

    # Leer configuración y lista de ignorados
    xConfig = leer_configuracion(xRuta_config)  # Lee la configuración
    ignore_list = leer_ignore_list(xRuta_options)  # Lee la lista de ignorados
    ftp = conectar_ftp(xConfig)  # Conecta al servidor FTP

    # Ejecutar directamente la opción 2
    xRuta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(xRuta_config))  # Crea la estructura de carpetas en FTP
    subir_archivos_recursivo(ftp, os.getcwd(), xRuta_final_ftp, ignore_list)  # Comienza a subir archivos

    ftp.quit()  # Desconecta del servidor FTP
    # Imprime mensaje de éxito
    print("Operación de subida completada con éxito.")

# Función que maneja la bajada de archivos (sin cambiar la lógica original)
def bajar_archivos():
    # Busca el archivo de configuración
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
    # Si no se encuentra el archivo de configuración
    if not ruta_config:
        print("No se encontró el archivo de configuración. Saliendo...")
        exit()

    # Busca el archivo de opciones
    ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(ruta_config))
    # Si no se encuentra el archivo de opciones
    if not ruta_opciones:
        # Crea el archivo de opciones
        crear_archivo_opciones(os.path.join(os.path.dirname(ruta_config), ARCHIVO_OPTIONS))
        # Busca nuevamente el archivo de opciones
        ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(ruta_config))

    # Si se encuentra el archivo de opciones
    if ruta_opciones:
        print(f"Usando archivo de opciones existente en: {ruta_opciones}")
        ignore_list = leer_opciones(ruta_opciones)  # Lee la lista de ignorados
    else:
        print("No se encontró el archivo de opciones.")
        ignore_list = []

    # Lee la configuración
    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    # 🔥 CORRECCIÓN: Mejor cálculo de la ruta FTP inicial
    # Directorio donde está scb.config
    directorio_base = os.path.dirname(ruta_config)
    # Relación entre cwd y base
    ruta_relativa = os.path.relpath(os.getcwd(), directorio_base)

    # Si ruta_relativa es ".", significa que estamos en la base, no concatenamos nada
    ruta_inicial_ftp = ftp.pwd() if ruta_relativa == "." else os.path.join(ftp.pwd(), ruta_relativa).replace('\\', '/')

    # Obtiene la ruta local
    ruta_local = os.getcwd()

    # Llama a la función para descargar archivos
    descargar_archivos_recursivo(ftp, ruta_inicial_ftp, ruta_local, ignore_list)

    ftp.quit()  # Desconecta del servidor FTP
    # Imprime mensaje de éxito
    print("Operación de descarga completada con éxito.")

# Función principal que maneja la ejecución del script
def main():
    # Verifica que se haya pasado un argumento al script
    if len(sys.argv) != 2:
        print("Uso: scbox [ u | d | s ]")

    # Obtiene la operación a realizar
    operacion = sys.argv[1].strip().lower()

    # Si la operación es 'u', inicia la subida de archivos
    if operacion == "u":
        print("Iniciando Upload.. [scbox 25.03]")
        subir_archivos()  # Llamada a la función de subida
    # Si la operación es 'd', inicia la bajada de archivos
    elif operacion == "d":
        print("Iniciando Dowload.. [scbox 25.03]")
        bajar_archivos()  # Llamada a la función de bajada
    # Si la operación es 's', inicia la sincronización
    elif operacion == "s":
        print("Iniciando Sincronizacion.. [scbox 25.03]")
        bajar_archivos()  # Llama a la función de bajada
        subir_archivos()  # Llama a la función de subida
    else:
        # Imprime mensaje de error si la opción no es válida
        print("Opción no válida. Debes ingresar 'u' para subir - 'd' para bajar - 's' para sincronizar")
        exit()

# Verifica si el script se está ejecutando directamente
if __name__ == "__main__":
    main()  # Llama a la función principal
