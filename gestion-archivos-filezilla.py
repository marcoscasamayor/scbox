import os
import json
from ftplib import FTP
import io
from datetime import datetime
import getpass

# Constantes
ARCHIVO_CONFIG = 'scb.config'  # Nombre del archivo de configuración
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"  # Plantilla para generar logs
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} el archivo {descripcion}"  # Plantilla para historial de cambios

# Utilidades generales
def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        for root, _, files in os.walk(xDirectorio_actual):
            if xNombre_archivo in files:
                return os.path.join(root, xNombre_archivo)
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    return None

def leer_configuracion(xRuta_config):
    try:
        with open(xRuta_config, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error leyendo el archivo de configuración: {e}")
        exit()

# Funciones FTP
def conectar_ftp(xConfig):
    ftp = FTP(xConfig['FTP']['ftp_server'])
    ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
    return ftp

def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xDescripcion):
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    hora_actual = datetime.now().strftime("%H:%M")
    linea_historial = HISTORIAL_TEMPLATE.format(fecha=fecha_actual, hora=hora_actual, usuario=xUsuario, accion=xAccion, descripcion=xDescripcion)
    return f"{xContenido_existente}\n{linea_historial}"

def crear_scb_log(xFtp, xRuta_ftp=None, xAccion=None, xDescripcion=None):
    if xRuta_ftp is None:
        xRuta_ftp = xFtp.pwd()

    usuario = getpass.getuser()
    ruta_log = f"{xRuta_ftp}/scb.log"
    encabezado_log = LOG_TEMPLATE.format(fecha=datetime.now().isoformat(), carpeta=xRuta_ftp)

    contenido_existente = ""
    try:
        with io.BytesIO() as archivo_existente:
            xFtp.retrbinary(f"RETR {ruta_log}", archivo_existente.write)
            contenido_existente = archivo_existente.getvalue().decode('utf-8')
    except Exception:
        contenido_existente = encabezado_log

    if xAccion and xDescripcion:
        contenido_actualizado = agregar_historial_log(contenido_existente, usuario, xAccion, xDescripcion)
    else:
        contenido_actualizado = contenido_existente

    xFtp.storbinary(f"STOR {ruta_log}", io.BytesIO(contenido_actualizado.encode('utf-8')))
    print(f"Archivo actualizado o creado: {ruta_log}")

def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    ruta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    carpetas = ruta_relativa.split(os.sep)
    ruta_actual_ftp = xDestino_dir_ftp

    for carpeta in carpetas:
        if carpeta:
            ruta_actual_ftp = os.path.join(ruta_actual_ftp, carpeta).replace("\\", "/")
            try:
                xFtp.cwd(ruta_actual_ftp)
                xFtp.cwd("..")
            except Exception:
                try:
                    xFtp.mkd(ruta_actual_ftp)
                    print(f"Carpeta creada: {ruta_actual_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_actual_ftp}: {e}")

    return ruta_actual_ftp

def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp):
    for nombre in os.listdir(xRuta_local):
        ruta_completa_local = os.path.join(xRuta_local, nombre)
        ruta_completa_ftp = os.path.join(xRuta_ftp, nombre).replace("\\", "/")

        if os.path.isfile(ruta_completa_local):  # Si es un archivo
            try:
                # Verificar si el archivo ya existe en el FTP
                tamaño_archivo_ftp = xFtp.size(ruta_completa_ftp)
                tamaño_archivo_local = os.path.getsize(ruta_completa_local)

                if tamaño_archivo_local != tamaño_archivo_ftp:  # Si el tamaño es diferente, se considera modificado
                    with open(ruta_completa_local, 'rb') as file:
                        xFtp.storbinary(f'STOR {ruta_completa_ftp}', file)
                    print(f"Archivo actualizado: {ruta_completa_local} -> {ruta_completa_ftp}")
                    # Registrar el historial en el log después de subir el archivo
                    crear_scb_log(xFtp, xRuta_ftp, "modificó", nombre)
            except Exception:
                try:
                    with open(ruta_completa_local, 'rb') as file:
                        xFtp.storbinary(f'STOR {ruta_completa_ftp}', file)
                    print(f"Archivo creado: {ruta_completa_local} -> {ruta_completa_ftp}")
                    # Registrar el historial en el log después de subir el archivo
                    crear_scb_log(xFtp, xRuta_ftp, "creó", nombre)
                except Exception as e:
                    print(f"No se pudo subir el archivo {ruta_completa_local}: {e}")
        elif os.path.isdir(ruta_completa_local):  # Si es una carpeta
            try:
                xFtp.cwd(ruta_completa_ftp)
                xFtp.cwd("..")
            except Exception:
                try:
                    xFtp.mkd(ruta_completa_ftp)
                    print(f"Carpeta creada en FTP: {ruta_completa_ftp}")
                    # Registrar la creación de la carpeta en el log
                    crear_scb_log(xFtp, xRuta_ftp, "creó la carpeta", nombre)
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_completa_ftp}: {e}")

            # Llamada recursiva para subir los archivos de la subcarpeta
            subir_archivos_recursivo(xFtp, ruta_completa_local, ruta_completa_ftp)


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
    print("1. Copiar archivo desde origen a servidor FTP y actualizar scb.log.")
    print("2. Sincronizar carpetas entre origen y servidor FTP y actualizar scb.log.")

    opcion = int(input("Ingrese su opción: "))

    if opcion == 1:
        for archivo in os.listdir(os.getcwd()):
            if os.path.isfile(archivo):
                subir_archivos_recursivo(ftp, os.getcwd(), '/')
    elif opcion == 2:
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), os.path.dirname(ruta_config))
        subir_archivos_recursivo(ftp, os.getcwd(), ruta_final_ftp)

    ftp.quit()
