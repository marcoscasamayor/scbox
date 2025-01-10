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

# Función para crear la estructura de carpetas en el servidor FTP
def crear_estructura_carpetas_ftp(ftp, origen_dir, carpeta_principal, destino_dir_ftp='/'):
    """
    Crea la estructura de carpetas en el servidor FTP desde el directorio raíz hasta el directorio actual.

    Parámetros:
    - ftp: Objeto FTP conectado al servidor.
    - origen_dir: Directorio actual en el sistema local.
    - carpeta_principal: Directorio principal donde se encuentra el archivo de configuración.
    - destino_dir_ftp: Directorio raíz en el servidor FTP (por defecto '/').

    Retorna:
    - ruta_actual_ftp: Ruta final en el servidor FTP donde se creó la estructura de carpetas.
    """
    # Calcular la ruta relativa entre el directorio actual y la carpeta principal
    ruta_relativa = os.path.relpath(origen_dir, carpeta_principal)
    
    # Dividir la ruta relativa en segmentos de carpetas
    carpetas = ruta_relativa.split(os.sep)
    
    # Inicializar la ruta actual en el servidor FTP
    ruta_actual_ftp = destino_dir_ftp
    
    # Recorrer cada carpeta y crearla en el servidor FTP
    for carpeta in carpetas:
        if carpeta:  # Evitar carpetas vacías
            ruta_actual_ftp += carpeta + '/'
            try:
                ftp.mkd(ruta_actual_ftp)
                print(f"Carpeta creada: {ruta_actual_ftp}")
            except Exception as e:
                print(f"No se pudo crear la carpeta {ruta_actual_ftp}: {e}")
    
    return ruta_actual_ftp

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
        aArchivos  = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]
        for archivo in aArchivos:
            ruta_archivo_local = os.path.join(origen_dir, archivo)
            try:
                with open(ruta_archivo_local, 'rb') as file:
                    ftp.storbinary(f'STOR {archivo}', file)
                print(f"Archivo {archivo} copiado al servidor FTP.")
            except Exception as e:
                print(f"No se pudo copiar el archivo {archivo}: {e}")

    elif opcion == 2:
        # Eliminar archivo del servidor FTP
        archivo_a_eliminar = input("Ingrese el nombre del archivo a eliminar del servidor FTP: ")
        try:
            ftp.delete(archivo_a_eliminar)
            print(f"Archivo {archivo_a_eliminar} eliminado del servidor FTP.")
        except Exception as e:
            print(f"No se pudo eliminar el archivo {archivo_a_eliminar}: {e}")

    elif opcion == 3:
    # Sincronizar carpetas entre origen y servidor FTP
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, origen_dir, carpeta_principal)
    
    # Función para subir archivos recursivamente
    def subir_archivos_recursivo(ftp, ruta_local, ruta_ftp):
        """
        Sube archivos recursivamente desde la ruta local al servidor FTP.

        Parámetros:
        - ftp: Objeto FTP conectado al servidor.
        - ruta_local: Ruta local del directorio actual.
        - ruta_ftp: Ruta FTP correspondiente al directorio actual.
        """
        # Recorrer archivos y subdirectorios en la ruta local
        for nombre in os.listdir(ruta_local):
            ruta_completa_local = os.path.join(ruta_local, nombre)
            
            # Formatear la ruta FTP para usar barras normales
            ruta_completa_ftp = os.path.join(ruta_ftp, nombre).replace("\\", "/")
            
            if os.path.isfile(ruta_completa_local):
                # Si es un archivo, subirlo al servidor FTP
                try:
                    with open(ruta_completa_local, 'rb') as file:
                        ftp.storbinary(f'STOR {ruta_completa_ftp}', file)
                    print(f"Archivo subido: {ruta_completa_local} -> {ruta_completa_ftp}")
                except Exception as e:
                    print(f"No se pudo subir el archivo {ruta_completa_local}: {e}")
            elif os.path.isdir(ruta_completa_local):
                # Si es un directorio, crear la carpeta en el servidor FTP y subir su contenido
                try:
                    ftp.mkd(ruta_completa_ftp)
                    print(f"Carpeta creada en FTP: {ruta_completa_ftp}")
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_completa_ftp}: {e}")
                
                # Llamada recursiva para subir el contenido del subdirectorio
                subir_archivos_recursivo(ftp, ruta_completa_local, ruta_completa_ftp)
    
    # Llamar a la función recursiva para subir archivos desde el directorio actual
    subir_archivos_recursivo(ftp, origen_dir, ruta_final_ftp)
    
    # Llamar a la función recursiva para subir archivos desde el directorio actual
    subir_archivos_recursivo(ftp, origen_dir, ruta_final_ftp)

    # Cerrar la conexión FTP3
    ftp.quit()
    