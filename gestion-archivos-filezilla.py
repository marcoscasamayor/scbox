import os  
import json  
from ftplib import FTP  
import io  
from datetime import datetime 
import getpass 
from ignore_list import IGNORE_LIST  # Importar la lista de ignorados

# --- Constantes ---
ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"  # Plantilla para generar logs
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"  # Plantilla para historial de cambios

# --- Utilidades generales ---

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuración en el directorio actual y en los directorios ancestrales.
    """
    if xNombre_archivo in os.listdir(xDirectorio_actual):
        return os.path.join(xDirectorio_actual, xNombre_archivo)

    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
        if xNombre_archivo in os.listdir(xDirectorio_actual):
            return os.path.join(xDirectorio_actual, xNombre_archivo)

    return None

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuración y lo retorna como un diccionario.
    """
    try:
        with open(xRuta_config, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error leyendo el archivo de configuración: {e}")
        exit()

# --- Funciones FTP ---

def conectar_ftp(xConfig):
    """
    Conecta al servidor FTP utilizando la configuración proporcionada.
    """
    ftp = FTP(xConfig['FTP']['ftp_server'])
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    print(f"Conectado al servidor FTP: {xConfig['FTP']['ftp_server']}")
    return ftp

def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xTipo, xDescripcion):
    """
    Agrega una nueva línea al historial del log con la información proporcionada.
    """
    xFecha_actual = datetime.now().strftime("%d-%m-%Y")
    xHora_actual = datetime.now().strftime("%H:%M")
    xLinea_historial = HISTORIAL_TEMPLATE.format(
        fecha=xFecha_actual, hora=xHora_actual, usuario=xUsuario, accion=xAccion, tipo=xTipo, descripcion=xDescripcion
    )
    return f"{xContenido_existente}\n{xLinea_historial}"

def crear_scb_log(ftp, xRuta_ftp=None, xAccion=None, xDescripcion=None, tipo="archivo"):
    """
    Crea o actualiza el archivo de log en el servidor FTP.
    """
    if xRuta_ftp is None:
        xRuta_ftp = ftp.pwd()

    xUsuario = getpass.getuser()
    xRuta_log = f"{xRuta_ftp}/scb.log"
    xEncabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)

    xContenido_existente = ""
    try:
        with io.BytesIO() as archivo_existente:
            ftp.retrbinary(f"RETR {xRuta_log}", archivo_existente.write)
            xContenido_existente = archivo_existente.getvalue().decode('utf-8')
    except Exception:
        xContenido_existente = xEncabezado_log

    if xAccion and xDescripcion:
        xContenido_actualizado = agregar_historial_log(xContenido_existente, xUsuario, xAccion, tipo, xDescripcion)
    else:
        xContenido_actualizado = xContenido_existente

    ftp.storbinary(f"STOR {xRuta_log}", io.BytesIO(xContenido_actualizado.encode('utf-8')))

def set_fecha_modificacion(ftp, xRuta_ftp, xFecha_local):
    """
    Establece la fecha de modificación del archivo en el servidor FTP.
    """
    try:
        comando_mfmt = f"MFMT {xFecha_local.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}"
        ftp.sendcmd(comando_mfmt)
    except Exception as e:
        print(f"No se pudo modificar la fecha para {xRuta_ftp}: {e}")

def crear_estructura_carpetas_ftp(ftp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    """
    Crea la estructura de carpetas en el servidor FTP basada en las carpetas locales.
    """
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    xCarpetas = xRuta_relativa.split(os.sep)
    xRuta_actual_ftp = xDestino_dir_ftp

    for xCarpeta in xCarpetas:
        if xCarpeta:
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")
            try:
                ftp.cwd(xRuta_actual_ftp)
                ftp.cwd("..")
            except Exception:
                try:
                    ftp.mkd(xRuta_actual_ftp)
                    crear_scb_log(ftp, xRuta_actual_ftp, "creó", xCarpeta, tipo="carpeta")
                    print(f"Carpeta creada: {xRuta_actual_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")

    return xRuta_actual_ftp

def subir_archivos_recursivo(ftp, xRuta_local, xRuta_ftp):
    """
    Sube archivos y carpetas recursivamente desde la ruta local al servidor FTP,
    verificando si deben ser ignorados.
    """
    for xNombre in os.listdir(xRuta_local):
        if xNombre == "scb.log":
            continue
 
        xRuta_completa_local = os.path.join(xRuta_local, xNombre)
        xRuta_completa_ftp = os.path.join(xRuta_ftp, xNombre).replace("\\", "/")

        # Verificar si el archivo o carpeta está en la lista de ignorados
        if any(ignored in xRuta_completa_local for ignored in IGNORE_LIST):
            continue  # Ignorar el archivo o carpeta

        if os.path.isfile(xRuta_completa_local):
            xFecha_creacion_local = datetime.fromtimestamp(os.path.getctime(xRuta_completa_local))
            try:
                xTamaño_archivo_ftp = ftp.size(xRuta_completa_ftp)
                xTamaño_archivo_local = os.path.getsize(xRuta_completa_local)

                if xTamaño_archivo_local != xTamaño_archivo_ftp:
                    with open(xRuta_completa_local, 'rb') as file:
                        ftp.storbinary(f'STOR {xRuta_completa_ftp}', file)
                    set_fecha_modificacion(ftp, xRuta_completa_ftp, xFecha_creacion_local)
                    crear_scb_log(ftp, xRuta_ftp, "actualizó", xNombre, tipo="archivo")
                    
                    print(f"Archivo actualizado: {xRuta_completa_local} -> {xRuta_completa_ftp}")
            except Exception:
                with open(xRuta_completa_local, 'rb') as file:
                    ftp.storbinary(f'STOR {xRuta_completa_ftp}', file)
                set_fecha_modificacion(ftp, xRuta_completa_ftp, xFecha_creacion_local)
                crear_scb_log(ftp, xRuta_ftp, "creó", xNombre, tipo="archivo")
                print(f"Archivo creado: {xRuta_completa_local} -> {xRuta_completa_ftp}")
        elif os.path.isdir(xRuta_completa_local):
            try:
                ftp.cwd(xRuta_completa_ftp)
                ftp.cwd("..")
            except Exception:
                try:
                    ftp.mkd(xRuta_completa_ftp)
                    crear_scb_log(ftp, xRuta_ftp, "creó", xNombre, tipo="carpeta")
                    print(f"Carpeta creada en FTP: {xRuta_completa_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {xRuta_completa_ftp}: {e}")

            subir_archivos_recursivo(ftp, xRuta_completa_local, xRuta_completa_ftp)

# --- Programa principal ---
if __name__ == "__main__":
    xDirectorio_actual = os.getcwd()
    xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, xDirectorio_actual)

    if not xRuta_config:
        print(f"No se encontró el archivo de configuración: {ARCHIVO_CONFIG}")
        exit()

    xConfig = leer_configuracion(xRuta_config)
    ftp = conectar_ftp(xConfig)

    print("Seleccione una opción:")
    print("1. Copiar archivo desde origen a servidor FTP y actualizar scb.log.")
    print("2. Sincronizar carpetas entre origen y servidor FTP y actualizar scb.log.")

    xOpcion = int(input("Ingrese su opción: "))

    if xOpcion == 1:
        subir_archivos_recursivo(ftp, os.getcwd(), '/')
    elif xOpcion == 2:
        xRuta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(xRuta_config))
        subir_archivos_recursivo(ftp, os.getcwd(), xRuta_final_ftp)

    ftp.quit()
    print("Operación completada con éxito.")
