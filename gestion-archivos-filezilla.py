import os
import json
from ftplib import FTP

# Función para buscar el archivo de configuración
def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        for root, dirt, files in os.walk(xDirectorio_actual):
            if xNombre_archivo in files:
                return os.path.join(root, xNombre_archivo)
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    return None

# Nombre del archivo de configuración
archivo_config = 'scb.config'

# Directorio actual
directorio_actual = os.getcwd()

# Buscar el archivo de configuración
ruta_config = buscar_archivo_ancestro(archivo_config, directorio_actual)

if not ruta_config:
    print(f"El archivo de configuración no se encontró: {ruta_config}")
    print("Por favor, verifica el archivo o crea uno con la configuración correcta.")
    exit()

# Cargar configuraciones del archivo scb.config o scb.json
with open(ruta_config, 'r') as file:
    config = json.load(file)

ftp_server = config['FTP']['ftp_server']
ftp_user = config['FTP']['ftp_user']
ftp_password = config['FTP']['ftp_password']

# Directorio de origen dinámico (directorio actual)
origen_dir = os.getcwd()
destino_dir_ftp = '/'

# Obtener la ruta de la carpeta principal (donde está el archivo de configuración)
carpeta_principal = os.path.dirname(ruta_config)

# Verificar si el directorio de origen existe
if not os.path.exists(origen_dir):
    print(f"El directorio de origen no existe: {origen_dir}")
else:
    print("Seleccione una opción:")
    print("1. Copiar archivo desde origen a servidor FTP.")
    print("2. Eliminar archivo del servidor FTP.")
    print("3. Sincronizar carpetas entre origen y servidor FTP.")
    opcion = int(input("Ingrese su opción: "))

    ftp = FTP(ftp_server)
    ftp.login(user=ftp_user, passwd=ftp_password)

    if opcion == 1:
        # Listar los archivos en el directorio de origen
        aArchivos = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]

        if not aArchivos:
            print("No se encontraron archivos en el directorio de origen.")
        else:
            print("Archivos disponibles en el directorio de origen:")
            for i, archivo in enumerate(aArchivos, start=1):
                print(f"{i}. {archivo}")

            try:
                seleccion = int(input("Ingrese el número del archivo que desea copiar: "))
                archivo_seleccionado = aArchivos[seleccion - 1]
                ruta_archivo = os.path.join(origen_dir, archivo_seleccionado)

                with open(ruta_archivo, 'rb') as file:
                    ftp.storbinary(f'STOR {archivo_seleccionado}', file)
                print(f"Archivo {archivo_seleccionado} copiado al servidor FTP.")
            except (IndexError, ValueError):
                print("Selección inválida. Por favor, intente de nuevo.")

    elif opcion == 2:
        # Listar archivos en el servidor FTP
        aArchivos_servidor = ftp.nlst()
        aArchivos_servidor = [f for f in aArchivos_servidor if f not in ('.', '..')]

        if not aArchivos_servidor:
            print("No se encontraron archivos en el servidor FTP.")
        else:
            print("Archivos disponibles en el servidor FTP:")
            for i, archivo in enumerate(aArchivos_servidor, start=1):
                print(f"{i}. {archivo}")

            try:
                seleccion = int(input("Ingrese el número del archivo que desea eliminar : "))
                archivo_seleccionado = aArchivos_servidor[seleccion - 1]
                ftp.delete(archivo_seleccionado)
                print(f"Archivo {archivo_seleccionado} eliminado del servidor FTP.")
            except (IndexError, ValueError):
                print("Selección inválida. Por favor, intente de nuevo.")

    elif opcion == 3:
        # Sincronizar carpetas entre origen y servidor FTP
        ruta_relativa = os.path.relpath(origen_dir, carpeta_principal)

        # Crear la estructura de carpetas en el servidor FTP automáticamente
        carpetas = ruta_relativa.split(os.sep)
        ruta_actual_ftp = destino_dir_ftp

        for carpeta in carpetas:
            if carpeta:  # Evitar carpetas vacías
                ruta_actual_ftp += carpeta + '/'
                try:
                    ftp.mkd(ruta_actual_ftp)
                    print(f"Carpeta creada: {ruta_actual_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_actual_ftp}: {e}")

        # Copiar archivos que no existen en el servidor FTP
        aArchivos = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]
        for archivo in aArchivos:
            ruta_archivo_local = os.path.join(origen_dir, archivo)
            ruta_archivo_ftp = os.path.join(ruta_actual_ftp, archivo)

            try:
                # Verificar si el archivo ya existe en el servidor FTP
                if archivo not in ftp.nlst(ruta_actual_ftp):
                    with open(ruta_archivo_local, 'rb') as file:
                        ftp.storbinary(f'STOR {ruta_archivo_ftp}', file)
                    print(f"Archivo {archivo} copiado al servidor FTP.")
                else:
                    print(f"El archivo {archivo} ya existe en el servidor FTP.")
            except Exception as e:
                print(f"No se pudo copiar el archivo {archivo}: {e}")

    ftp.quit()