import os
import json
from ftplib import FTP
import ftplib

def buscar_archivo_config(xNombre_archivo, xDirectorio_actual):
    # Escalar hacia arriba
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        # Buscar en el directorio actual
        for root, dirs, files in os.walk(xDirectorio_actual):
            if xNombre_archivo in files:
                return os.path.join(root, xNombre_archivo)
        
        # Subir un nivel en la jerarquía de directorios
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    
    return None

# Nombre del archivo de configuración
xNombre_archivo = 'scb.config'

# Directorio actual
xDirectorio_actual = os.getcwd()

# Buscar el archivo de configuración
xRuta_config = buscar_archivo_config(xNombre_archivo, xDirectorio_actual)

if not xRuta_config:
    xNombre_archivo = 'scb.json'
    xRuta_config = buscar_archivo_config(xNombre_archivo, xDirectorio_actual)

if not xRuta_config:
    print(f"El archivo de configuración no se encontró: {xNombre_archivo}")
    print("Por favor, verifica el archivo o crea uno con la configuración correcta.")
    exit()

# Cargar configuraciones del archivo scb.config o scb.json
with open(xRuta_config, 'r') as file:
    config = json.load(file)

xFtp_server = config['FTP']['ftp_server']
xFtp_user = config['FTP']['ftp_user']
xFtp_password = config['FTP']['ftp_password']

# Directorios de origen y destino
xOrigen_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosOrigen'
xDestino_dir_ftp = '/'

# Verifico si los directorios existen
if not os.path.exists(xOrigen_dir):
    print(f"El directorio de origen no existe: {xOrigen_dir}")
else:
    print("Seleccione una opción:")
    print("1. Copiar archivo desde origen a servidor FTP.")
    print("2. Eliminar archivo del servidor FTP.")
    print("3. Sincronizar carpetas entre origen y servidor FTP.")
    opcion = int(input("Ingrese su opción: "))

    ftp = FTP(xFtp_server)
    ftp.login(user=xFtp_user, passwd=xFtp_password)

    if opcion == 1:
        # Listar los archivos en el directorio de origen
        aArchivos = [f for f in os.listdir(xOrigen_dir) if os.path.isfile(os.path.join(xOrigen_dir, f))]

        if not aArchivos:
            print("No se encontraron archivos en el directorio de origen.")
        else:
            print("Archivos disponibles en el directorio de origen:")
            for i, archivo in enumerate(aArchivos, start=1):
                print(f"{i}. {archivo}")

            try:
                seleccion = int(input("Ingrese el número del archivo que desea copiar: "))
                archivo_seleccionado = aArchivos[seleccion - 1]
                ruta_archivo = os.path.join(xOrigen_dir, archivo_seleccionado)

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
                seleccion = int(input("Ingrese el número del archivo que desea eliminar: "))
                archivo_seleccionado = aArchivos_servidor[seleccion - 1]
                ftp.delete(archivo_seleccionado)
                print(f"Archivo {archivo_seleccionado} eliminado del servidor FTP.")
            except (IndexError, ValueError):
                print("Selección inválida. Por favor, intente de nuevo.")

    elif opcion == 3:
        # Sincronizar carpetas entre origen y servidor FTP
        aArchivos = [f for f in os.listdir(xOrigen_dir) if os.path.isfile(os.path.join(xOrigen_dir, f))]
        aArchivos_servidor = ftp.nlst()

        for archivo in aArchivos:
            if archivo not in aArchivos_servidor:
                with open(os.path.join(xOrigen_dir, archivo), 'rb') as file:
                    ftp.storbinary(f'STOR {archivo}', file)
                print(f"Archivo {archivo} subido al servidor FTP.")

        print("Upload completado.") 

    ftp.quit()