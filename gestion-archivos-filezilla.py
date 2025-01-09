import os
import json
from ftplib import FTP

# busco el archivo dado, se va escalando hacia los padres, devuelve la direccion del archivo
# si no se encuentra el archivo, devuelvo None
def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    # Escalar hacia arriba
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        # Buscar en el directorio actual
        for root, dirt, files in os.walk(xDirectorio_actual):
            if xNombre_archivo in files:
                return os.path.join(root, xNombre_archivo)
        # Subir un nivel en la jerarquía de directorios
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

# Directorios de origen y destino
#origen_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosOrigen'
# Directorio de origen dinámico (directorio actual)
origen_dir = os.getcwd()
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
                seleccion = int(input("Ingrese el número del archivo que desea eliminar: "))
                archivo_seleccionado = aArchivos_servidor[seleccion - 1]
                ftp.delete(archivo_seleccionado)
                print(f"Archivo {archivo_seleccionado} eliminado del servidor FTP.")
            except (IndexError, ValueError):
                print("Selección inválida. Por favor, intente de nuevo.")

    elif opcion == 3:
        # Sincronizar carpetas entre origen y servidor FTP
        def obtener_jerarquia_local(xDirectorio):
            jerarquia = {}
            for root, dirs, files in os.walk(xDirectorio):
                ruta_relativa = os.path.relpath(root, xDirectorio)
                jerarquia[ruta_relativa] = {'dirs': dirs, 'files': files}
            return jerarquia

        def crear_carpetas_ftp(xFtp, xRuta):
            try:
                xFtp.mkd(xRuta)
                print(f"Carpeta creada en FTP: {xRuta}")
            except Exception as e:
                print(f"Error al crear carpeta {xRuta} en FTP: {e}")

        def sincronizar_ftp(xFtp, xDirectorio_local, xDirectorio_ftp):
            jerarquia_local = obtener_jerarquia_local(xDirectorio_local)

            for ruta_relativa, contenido in jerarquia_local.items():
                ruta_ftp = os.path.join(xDirectorio_ftp, ruta_relativa).replace('\\', '/')

                # Crear carpetas en FTP si no existen
                try:
                    xFtp.cwd(ruta_ftp)
                except:
                    crear_carpetas_ftp(ftp, ruta_ftp)
                    xFtp.cwd(ruta_ftp)

                # Subir archivos que no existen en FTP
                for archivo in contenido['files']:
                    ruta_archivo_local = os.path.join(xDirectorio_local, ruta_relativa, archivo)
                    ruta_archivo_ftp = os.path.join(ruta_ftp, archivo).replace('\\', '/')

                    try:
                        with open(ruta_archivo_local, 'rb') as file:
                            xFtp.storbinary(f'STOR {ruta_archivo_ftp}', file)
                        print(f"Archivo subido a FTP: {ruta_archivo_ftp}")
                    except Exception as e:
                        print(f"Error al subir archivo {ruta_archivo_ftp} a FTP: {e}")

        # Sincronizar carpetas y archivos
        sincronizar_ftp(ftp, origen_dir, destino_dir_ftp)

    # Cerrar conexión FTP
    ftp.quit()