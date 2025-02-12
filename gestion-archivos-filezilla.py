import os  # Importando el módulo os para interactuar con el sistema operativo
import json  # Importando el módulo json para manejar datos JSON
from ftplib import FTP  # Importando la clase FTP para operaciones FTP
import io  # Importando el módulo io para manejar flujos de bytes
from datetime import datetime  # Importando datetime para manipulación de fechas y horas
import getpass  # Importando getpass para obtener de forma segura la contraseña del usuario

# --- Constantes ---
ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
ARCHIVO_OPTIONS = 'scb.options'  # Nombre del archivo de opciones
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"  # Plantilla para generar logs
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"  # Plantilla para historial de cambios

# --- Utilidades generales ---

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en el directorio actual y en los directorios ancestrales.
    """
    if xNombre_archivo in os.listdir(xDirectorio_actual):  # Verifica si el archivo existe en el directorio actual
        return os.path.join(xDirectorio_actual, xNombre_archivo)  # Devuelve la ruta completa si se encuentra

    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):  # Bucle hasta que el directorio actual sea la raíz
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)  # Mueve al directorio padre
        if xNombre_archivo in os.listdir(xDirectorio_actual):  # Verifica si el archivo existe en el directorio padre
            return os.path.join(xDirectorio_actual, xNombre_archivo)  # Devuelve la ruta completa si se encuentra

    return None  # Devuelve None si no se encuentra el archivo

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(xRuta_config, 'r') as file:  # Abre el archivo de configuración para lectura
            return json.load(file)  # Carga y devuelve los datos JSON como un diccionario
    except Exception as e:
        print(f"Error leyendo el archivo de configuración: {e}")  # Imprime mensaje de error si falla la lectura
        exit()  # Sale del programa

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

# --- Funciones FTP ---

def conectar_ftp(xConfig):


    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])  # Crea un objeto FTP con la dirección del servidor
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])  # Inicia sesión con las credenciales del usuario
    print(f"Conectado a repositorio SCBOX")  # Imprime mensaje de éxito
    return ftp  # Devuelve el objeto FTP

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

def set_fecha_modificacion(xFtp, xRuta_ftp, xFecha_local):


    """
    Establece la fecha de modificación del archivo en el servidor FTP.
    """
    try:
        comando_mfmt = f"MFMT {xFecha_local.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}"  # Crea el comando para establecer la fecha de modificación
        xFtp.sendcmd(comando_mfmt)  # Envía el comando al servidor FTP
    except Exception as e:
        print(f"No se pudo modificar la fecha para {xRuta_ftp}: {e}")  # Imprime mensaje de error si falla la modificación

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
                    crear_scb_log(ftp, xRuta_actual_ftp, "creó", xCarpeta, tipo="carpeta")  # Registra la creación de la carpeta
                    print(f"Carpeta creada: {xRuta_actual_ftp}")  # Imprime mensaje de éxito
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")  # Imprime mensaje de error si falla la creación

    return xRuta_actual_ftp  # Devuelve la ruta actual en FTP

def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp, xIgnore_list):


    """
    Sube archivos y carpetas recursivamente desde la ruta local al servidor FTP,
    verificando si deben ser ignorados.
    """
    for xNombre in os.listdir(xRuta_local):  # Itera sobre cada elemento en el directorio local
        if xNombre == "scb.log":  # Salta el archivo de log
            continue

        xRuta_completa_local = os.path.join(xRuta_local, xNombre)  # Obtiene la ruta completa local
        xRuta_completa_ftp = os.path.join(xRuta_ftp, xNombre).replace("\\", "/")  # Obtiene la ruta completa en FTP

        # Verifica si el archivo o carpeta está en la lista de ignorados
        if xNombre in xIgnore_list:  # Si el nombre está en la lista de ignorados
            print(f"Ignorando: {xRuta_completa_local}")  # Imprime mensaje de ignorar
            continue  # Salta al siguiente elemento

        if os.path.isfile(xRuta_completa_local):  # Si el elemento es un archivo
            xFecha_creacion_local = datetime.fromtimestamp(os.path.getctime(xRuta_completa_local))  # Obtiene la fecha de creación del archivo local
            try:
                xTamaño_archivo_ftp = xFtp.size(xRuta_completa_ftp)  # Obtiene el tamaño del archivo en el servidor FTP
                xTamaño_archivo_local = os.path.getsize(xRuta_completa_local)  # Obtiene el tamaño del archivo local

                if xTamaño_archivo_local != xTamaño_archivo_ftp:  # Si los tamaños son diferentes
                    with open(xRuta_completa_local, 'rb') as file:  # Abre el archivo local para lectura
                        xFtp.storbinary(f'STOR {xRuta_completa_ftp}', file)  # Sube el archivo al servidor FTP
                    set_fecha_modificacion(xFtp, xRuta_completa_ftp, xFecha_creacion_local)  # Establece la fecha de modificación en el servidor FTP
                    crear_scb_log(xFtp, xRuta_ftp, "actualizó", xNombre, tipo="archivo")  # Registra la actualización del archivo
                    
                    print(f"Archivo actualizado: {xRuta_completa_local} -> {xRuta_completa_ftp}")  # Imprime mensaje de actualización
            except Exception:
                with open(xRuta_completa_local, 'rb') as file:  # Abre el archivo local para lectura
                    xFtp.storbinary(f'STOR {xRuta_completa_ftp}', file)  # Sube el archivo al servidor FTP
                set_fecha_modificacion(xFtp, xRuta_completa_ftp, xFecha_creacion_local)  # Establece la fecha de modificación en el servidor FTP
                crear_scb_log(xFtp, xRuta_ftp, "creó", xNombre, tipo="archivo")  # Registra la creación del archivo
                print(f"Archivo creado: {xRuta_completa_local} -> {xRuta_completa_ftp}")  # Imprime mensaje de creación
        elif os.path.isdir(xRuta_completa_local):  # Si el elemento es un directorio
            try:
                xFtp.cwd(xRuta_completa_ftp)  # Cambia al directorio FTP
                xFtp.cwd("..")  # Mueve al directorio padre
            except Exception:
                try:
                    xFtp.mkd(xRuta_completa_ftp)  # Crea el directorio en el servidor FTP
                    crear_scb_log(xFtp, xRuta_ftp, "creó", xNombre, tipo="carpeta")  # Registra la creación de la carpeta
                    print(f"Carpeta creada en FTP: {xRuta_completa_ftp}")  # Imprime mensaje de éxito
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_completa_ftp}: {e}")  # Imprime mensaje de error si falla la creación

            subir_archivos_recursivo(xFtp, xRuta_completa_local, xRuta_completa_ftp, xIgnore_list)  # Llamada recursiva para subir archivos en el directorio


# --- Programa principal ---
if __name__ == "__main__":  # La ejecución del programa principal comienza aquí
    xDirectorio_actual = os.getcwd()  # Obtiene el directorio de trabajo actual
    xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, xDirectorio_actual)  # Busca el archivo de configuración
    xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, xDirectorio_actual)  # Busca el archivo de opciones

    if not xRuta_config:  # Si no se encuentra el archivo de configuración
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")  # Imprime mensaje de error
        exit()  # Sale del programa

    if not xRuta_options:  # Si no se encuentra el archivo de opciones
        print(f"No se encontró el archivo de opciones: {ARCHIVO_OPTIONS}")  # Imprime mensaje de error
        leer_ignore_list(os.path.join(os.path.dirname(xRuta_config), ARCHIVO_OPTIONS))  # Crea el archivo de opciones con la estructura predeterminada
        xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(xRuta_config))  # Busca nuevamente el archivo de opciones

        xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(xRuta_config))  # Busca nuevamente el archivo de opciones

        xRuta_options = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(xRuta_config))  # Busca nuevamente el archivo de opciones


    # Leer configuración y lista de ignorados
    xConfig = leer_configuracion(xRuta_config)  # Lee la configuración
    ignore_list = leer_ignore_list(xRuta_options)  # Lee la lista de ignorados
    ftp = conectar_ftp(xConfig)  # Conecta al servidor FTP

    # Ejecutar directamente la opción 2
    xRuta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(xRuta_config))  # Crea la estructura de carpetas en FTP
    subir_archivos_recursivo(ftp, os.getcwd(), xRuta_final_ftp, ignore_list)  # Comienza a subir archivos


    ftp.quit()  # Desconecta del servidor FTP
    print("Operación completada con éxito.")  # Imprime mensaje de éxito
