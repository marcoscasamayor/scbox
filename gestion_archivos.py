import os
import json
from ftplib import FTP
import io
from datetime import datetime
import getpass
import time
import fnmatch
import sys

# --- Constantes ---
ARCHIVO_CONFIG = 'scb.config'
ARCHIVO_OPTIONS = 'scb.options'
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"

# --- Funciones comunes ---

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """Busca el archivo de configuración en el directorio actual y en los directorios ancestrales."""
    while xDirectorio_actual and xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        if xNombre_archivo in os.listdir(xDirectorio_actual):
            return os.path.join(xDirectorio_actual, xNombre_archivo)
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    return None

def leer_configuracion(xRuta_config):
    """Lee el archivo de configuración y lo retorna como un diccionario."""
    try:
        with open(xRuta_config, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error leyendo el archivo de configuración: {e}")
        exit()

def crear_archivo_opciones(xRuta_opciones):
    """Crea un archivo de opciones con una lista de archivos a ignorar."""
    opciones = {
        "ignore_list": [
            "ejemplo123.txt"
        ]
    }
    
    try:
        with open(xRuta_opciones, 'w') as file:
            json.dump(opciones, file, indent=2)
        print(f"Archivo de opciones creado: {xRuta_opciones}")
    except Exception as e:
        print(f"Error al crear el archivo de opciones: {e}")

def leer_ignore_list(xRuta_options):
    """Lee el archivo scb.options y retorna la lista de archivos a ignorar."""
    if not os.path.exists(xRuta_options):
        crear_archivo_opciones(xRuta_options)
        return ["ejemplo123.txt"]
    else:
        try:
            with open(xRuta_options, 'r') as f:
                opciones = json.load(f)
                return opciones.get('ignore_list', [])
        except Exception as e:
            print(f"Error leyendo el archivo {xRuta_options}: {e}")
            exit()


def conectar_ftp(xConfig):
    """Conecta al servidor FTP utilizando la configuración proporcionada."""
    ftp = FTP(xConfig['FTP']['ftp_server'])
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    print(f"Conectado a repositorio SCBOX")
    return ftp

# --- Funciones de subida ---

def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xTipo, xDescripcion):
    """Agrega una nueva línea al historial del log."""
    xFecha_actual = datetime.now().strftime("%d-%m-%Y")
    xHora_actual = datetime.now().strftime("%H:%M")
    xLinea_historial = HISTORIAL_TEMPLATE.format(
        fecha=xFecha_actual, hora=xHora_actual, usuario=xUsuario, accion=xAccion, tipo=xTipo, descripcion=xDescripcion
    )
    return f"{xContenido_existente}\n{xLinea_historial}"

def crear_scb_log(xFtp, xRuta_ftp=None, xAccion=None, xDescripcion=None, tipo="archivo"):
    """Crea o actualiza el archivo de log en el servidor FTP."""
    if xRuta_ftp is None:
        xRuta_ftp = xFtp.pwd()

    xUsuario = getpass.getuser()
    xRuta_log = f"{xRuta_ftp}/scb.log"
    xEncabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)

    xContenido_existente = ""
    try:
        with io.BytesIO() as archivo_existente:
            xFtp.retrbinary(f"RETR {xRuta_log}", archivo_existente.write)
            xContenido_existente = archivo_existente.getvalue().decode('utf-8')
    except Exception:
        xContenido_existente = xEncabezado_log

    if xAccion and xDescripcion:
        xContenido_actualizado = agregar_historial_log(xContenido_existente, xUsuario, xAccion, tipo, xDescripcion)
    else:
        xContenido_actualizado = xContenido_existente

    xFtp.storbinary(f"STOR {xRuta_log}", io.BytesIO(xContenido_actualizado.encode('utf-8')))

def set_fecha_modificacion(xFtp, xRuta_ftp, xFecha_local):
    """Establece la fecha de modificación del archivo en el servidor FTP."""
    try:
        comando_mfmt = f"MFMT {xFecha_local.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}"
        xFtp.sendcmd(comando_mfmt)
    except Exception as e:
        print(f"No se pudo modificar la fecha para {xRuta_ftp}: {e}")

def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    """Crea la estructura de carpetas en el servidor FTP."""
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    xCarpetas = xRuta_relativa.split(os.sep)
    xRuta_actual_ftp = xDestino_dir_ftp

    for xCarpeta in xCarpetas:
        if xCarpeta:
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")
            try:
                xFtp.cwd(xRuta_actual_ftp)
                xFtp.cwd("..")
            except Exception:
                try:
                    xFtp.mkd(xRuta_actual_ftp)
                    crear_scb_log(xFtp, xRuta_actual_ftp, "creó", xCarpeta, tipo="carpeta")
                    print(f"Carpeta creada: {xRuta_actual_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")

    return xRuta_actual_ftp

def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp, xIgnore_list):
    """Sube archivos y carpetas recursivamente al servidor FTP."""
    for xNombre in os.listdir(xRuta_local):
        if xNombre == "scb.log":
            continue

        xRuta_completa_local = os.path.join(xRuta_local, xNombre)
        xRuta_completa_ftp = os.path.join(xRuta_ftp, xNombre).replace("\\", "/")

        if xNombre in xIgnore_list:
            print(f"Ignorando: {xRuta_completa_local}")
            continue

        if os.path.isfile(xRuta_completa_local):
            xFecha_creacion_local = datetime.fromtimestamp(os.path.getctime(xRuta_completa_local))
            try:
                xTamaño_archivo_ftp = xFtp.size(xRuta_completa_ftp)
                xTamaño_archivo_local = os.path.getsize(xRuta_completa_local)

                if xTamaño_archivo_local != xTamaño_archivo_ftp:
                    with open(xRuta_completa_local, 'rb') as file:
                        xFtp.storbinary(f'STOR {xRuta_completa_ftp}', file)
                    set_fecha_modificacion(xFtp, xRuta_completa_ftp, xFecha_creacion_local)
                    crear_scb_log(xFtp, xRuta_ftp, "actualizó", xNombre, tipo="archivo")
                    print(f"Archivo actualizado: {xRuta_completa_local} -> {xRuta_completa_ftp}")
            except Exception:
                with open(xRuta_completa_local, 'rb') as file:
                    xFtp.storbinary(f'STOR {xRuta_completa_ftp}', file)
                set_fecha_modificacion(xFtp, xRuta_completa_ftp, xFecha_creacion_local)
                crear_scb_log(xFtp, xRuta_ftp, "creó", xNombre, tipo="archivo")
                print(f"Archivo creado: {xRuta_completa_local} -> {xRuta_completa_ftp}")
        elif os.path.isdir(xRuta_completa_local):
            try:
                xFtp.cwd(xRuta_completa_ftp)
                xFtp.cwd("..")
            except Exception:
                try:
                    xFtp.mkd(xRuta_completa_ftp)
                    crear_scb_log(xFtp, xRuta_ftp, "creó", xNombre, tipo="carpeta")
                    print(f"Carpeta creada en FTP: {xRuta_completa_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_completa_ftp}: {e}")

            subir_archivos_recursivo(xFtp, xRuta_completa_local, xRuta_completa_ftp, xIgnore_list)

# --- Funciones de descarga ---

def obtener_fecha_modificacion_ftp(ftp, archivo):
    """Obtiene la fecha de modificación de un archivo en el servidor FTP."""
    try:
        respuesta = ftp.sendcmd(f"MDTM {archivo}")
        fecha_str = respuesta[4:].strip()
        fecha = datetime.strptime(fecha_str, "%Y%m%d%H%M%S")
        return int(time.mktime(fecha.timetuple()))
    except Exception:
        return None

def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list):
    """Descarga archivos y carpetas recursivamente desde el servidor FTP."""
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

# --- Menú principal ---

def procesar_comando():
    if len(sys.argv) != 2:
        print("Uso incorrecto. Debes especificar 'u' para subir o 'd' para descargar.")
        sys.exit(1)

    accion = sys.argv[1]  # El segundo argumento será la acción

    if accion not in ['u', 'd']:
        print("Opción no válida. Usa 'u' para subir o 'd' para descargar.")
        sys.exit(1)

    # Buscar archivo de configuración y opciones
    ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
    if not ruta_config:
        print("No se encontró el archivo de configuración. Saliendo...")
        sys.exit(1)
    
    ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, os.path.dirname(ruta_config))
    if not ruta_opciones:
        ruta_opciones = os.path.join(os.path.dirname(ruta_config), ARCHIVO_OPTIONS)
        crear_archivo_opciones(ruta_opciones)

    if not ruta_opciones:
        print("No se encontró el archivo de opciones.")
        ignore_list = []
    else:
        ignore_list = leer_ignore_list(ruta_opciones)

    config = leer_configuracion(ruta_config)
    ftp = conectar_ftp(config)

    if accion == 'u':
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(ruta_config))
        subir_archivos_recursivo(ftp, os.getcwd(), ruta_final_ftp, ignore_list)
    elif accion == 'd':
        descargar_archivos_recursivo(ftp, ftp.pwd(), os.getcwd(), ignore_list)

    ftp.quit()
    print("Operación completada con éxito.")

if __name__ == "__main__":
    procesar_comando()