import os
import json
from ftplib import FTP

# Función para buscar el archivo de configuración
def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    #Compara el directorio actual con su directorio padre. Si son iguales, significa que se ha llegado a la raíz del sistema de archivos y el bucle termina
    while xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        #devuelve el directorio padre de xDirectorio_actual
        for root, dirt, files in os.walk(xDirectorio_actual):
            #os.walk es una función que genera los nombres de los archivos en un árbol de directorios
            if xNombre_archivo in files:               
                return os.path.join(root, xNombre_archivo)
            #con esto enlazo root con nombre_archivop para formar el path completo del archivo
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
        #Actualiza xDirectorio_actual al directorio padre del directorio actual. Esto permite que el bucle while continúe subiendo en la jerarquía de directorios.
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
    print("2. Sincronizar carpetas entre origen y servidor FTP.")
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
    # Sincronizar carpetas entre origen y servidor FTP
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, origen_dir, carpeta_principal)
    # Llama a la función 'crear_estructura_carpetas_ftp' para crear la estructura de carpetas en el servidor FTP
    # 'ruta_final_ftp' es la ruta en el servidor FTP donde se creó la estructura de carpetas

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
            # 'os.listdir(ruta_local)' devuelve una lista de nombres de archivos y carpetas en 'ruta_local'

            ruta_completa_local = os.path.join(ruta_local, nombre)
            # Combina 'ruta_local' y 'nombre' para obtener la ruta completa del archivo o carpeta local

            # Formatear la ruta FTP para usar barras normales
            ruta_completa_ftp = os.path.join(ruta_ftp, nombre).replace("\\", "/")
            # Combina 'ruta_ftp' y 'nombre' para obtener la ruta completa en el servidor FTP
            # .replace("\\", "/") reemplaza las barras invertidas (\) por barras normales (/) para compatibilidad con FTP

            if os.path.isfile(ruta_completa_local):
                # Verifica si 'ruta_completa_local' es un archivo (no una carpeta)
                try:
                    with open(ruta_completa_local, 'rb') as file:
                        # Abre el archivo local en modo binario de lectura ('rb')
                        ftp.storbinary(f'STOR {ruta_completa_ftp}', file)
                        # Sube el archivo al servidor FTP usando el comando STOR
                    print(f"Archivo subido: {ruta_completa_local} -> {ruta_completa_ftp}")
                    # Imprime un mensaje indicando que el archivo se subió correctamente
                except Exception as e:
                    print(f"No se pudo subir el archivo {ruta_completa_local}: {e}")
                    # Imprime un mensaje de error si falla la subida del archivo

            elif os.path.isdir(ruta_completa_local):
                # Verifica si 'ruta_completa_local' es una carpeta (no un archivo)
                try:
                    ftp.mkd(ruta_completa_ftp)
                    # Crea una carpeta en el servidor FTP usando el comando MKD
                    print(f"Carpeta creada en FTP: {ruta_completa_ftp}")
                    # Imprime un mensaje indicando que la carpeta se creó correctamente
                except Exception as e:
                    print(f"No se pudo crear la carpeta {ruta_completa_ftp}: {e}")
                    # Imprime un mensaje de error si falla la creación de la carpeta

                # Llamada recursiva para subir el contenido del subdirectorio
                subir_archivos_recursivo(ftp, ruta_completa_local, ruta_completa_ftp)
                # Llama a la función 'subir_archivos_recursivo' para subir los archivos dentro de la carpeta actual

    # Llamar a la función recursiva para subir archivos desde el directorio actual
    subir_archivos_recursivo(ftp, origen_dir, ruta_final_ftp)
    # Inicia el proceso de subida recursiva de archivos desde el directorio local al servidor FTP

    # Cerrar la conexión FTP
    ftp.quit()
    # Cierra la conexión con el servidor FTP
    
    
    
    