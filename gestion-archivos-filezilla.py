import os
import json
from ftplib import FTP
import ftplib

# Verificar si el archivo scb.config o scb.json existe en la raíz
config_file = 'scb.config'

if not os.path.isfile(config_file):
    config_file = 'scb.json'
    
if not os.path.isfile(config_file):
    print(f"El archivo de configuración no se encontró: {config_file}")
    print("Por favor, verifica el archivo o crea uno con la configuración correcta.")
    exit()

# Cargar configuraciones del archivo scb.config 
with open(config_file, 'r') as file:
    config = json.load(file)

ftp_server = config['FTP']['ftp_server']
ftp_user = config['FTP']['ftp_user']
ftp_password = config['FTP']['ftp_password']

# Directorios de origen y destino
origen_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosOrigen'
destino_dir_ftp = '/'

# Verifico si los directorios existen
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
        archivos = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]

        if not archivos:
            print("No se encontraron archivos en el directorio de origen.")
        else:
            print("Archivos disponibles en el directorio de origen:")
            for i, archivo in enumerate(archivos, start=1):
                print(f"{i}. {archivo}")

            try:
                seleccion = int(input("Ingrese el número del archivo que desea copiar: "))
                if seleccion < 1 or seleccion > len(archivos):
                    print("Selección no válida.")
                else:
                    archivo_seleccionado = archivos[seleccion - 1]
                    src = os.path.join(origen_dir, archivo_seleccionado)

                    # Obtener lista de archivos en el servidor FTP
                    archivos_servidor = ftp.nlst()

                    # Filtrar los elementos '.' y '..' de la lista de archivos
                    archivos_servidor = [f for f in archivos_servidor if f not in ('.', '..')]

                    if archivo_seleccionado in archivos_servidor:
                        print(f"El archivo '{archivo_seleccionado}' ya existe en el servidor FTP. No se subirá de nuevo.")
                    else:
                        # Transferencia del archivo
                        with open(src, 'rb') as file:
                            ftp.storbinary(f'STOR {archivo_seleccionado}', file)
                        print(f"Archivo copiado con éxito al servidor FTP: {archivo_seleccionado}")

            except ValueError:
                print("Debe ingresar un número válido.")

    elif opcion == 2:
        # Obtener lista de archivos en el servidor FTP
        archivos_servidor = ftp.nlst()

        # Filtrar los elementos '.' y '..' de la lista de archivos
        archivos_servidor = [f for f in archivos_servidor if f not in ('.', '..')]

        if not archivos_servidor: print("No se encontraron archivos en el servidor FTP.")
        else:
            print("Archivos disponibles en el servidor FTP:")
            for i, archivo in enumerate(archivos_servidor, start=1):
                print(f"{i}. {archivo}")

            try:
                seleccion = int(input("Ingrese el número del archivo que desea eliminar: "))
                if seleccion < 1 or seleccion > len(archivos_servidor):
                    print("Selección no válida.")
                else:
                    archivo_seleccionado = archivos_servidor[seleccion - 1]
                    ftp.delete(archivo_seleccionado)
                    print(f"Archivo eliminado con éxito del servidor FTP: {archivo_seleccionado}")

            except ValueError:
                print("Debe ingresar un número válido.")

    elif opcion == 3:
        # Función para sincronizar carpetas
        def sincronizar_carpetas(origen, destino):
            # Crear la carpeta en el servidor FTP
            try:
                ftp.mkd(destino)
            except ftplib.error_perm as e:
                print(f"No se pudo crear la carpeta en el servidor FTP: {e}")

            # Listar archivos en el directorio de origen
            for item in os.listdir(origen):
                ruta_item = os.path.join(origen, item)
                if os.path.isdir(ruta_item):
                    # Llamada recursiva para carpetas
                    sincronizar_carpetas(ruta_item, destino + item + '/')
                else:
                    # Subir archivos
                    with open(ruta_item, 'rb') as file:
                        ftp.storbinary(f'STOR {destino + item}', file)
                    print(f"Archivo copiado con éxito al servidor FTP: {destino + item}")

        # Iniciar la sincronización
        sincronizar_carpetas(origen_dir, destino_dir_ftp)

    ftp.quit()
    #hasta aca tengo bien echa la sincronizacion