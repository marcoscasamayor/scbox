# Importaciones (se mantienen igual)
import ftplib
import os
import json
from ftplib import FTP
import io
from datetime import datetime, timezone, timedelta
import getpass
import time
import fnmatch
import sys
import logging
from socket import timeout as SocketTimeout

import logging
from datetime import datetime

# Constantes (se mantienen igual)
ARCHIVO_CONFIG = 'scb.config'
ARCHIVO_OPTIONS = 'scb.options'
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"

DESCARGAS_PERMITIDAS_RECONEXION = 100


def conectar_ftp(xConfig):
    """Conecta al servidor FTP con timeout y manejo de errores mejorado."""
    try:
        ftp = FTP(timeout=30)  # Timeout de 30 segundos
        ftp.connect(xConfig['FTP']['ftp_server'])
        ftp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
        return ftp
    except SocketTimeout:
        logging.error("Timeout al conectar al servidor FTP")
        raise
    except ftplib.all_errors as e:
        logging.error(f"Error FTP al conectar: {e}")
        raise

def leer_configuracion(xRuta_config):
    """
    Lee el archivo de configuracion y lo retorna como un diccionario.
    """
    try:
        # Abre el archivo de configuracion para lectura
        with open(xRuta_config, 'r') as file:
            # Carga y devuelve los datos JSON como un diccionario
            return json.load(file)
    except Exception as e:
        # Imprime mensaje de error si falla la lectura
        print(f"Error al leer configuracion: {e}")
        # Sale del programa
        exit()

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """
    Busca el archivo de configuracion en el directorio actual y en los directorios ancestrales.
    """
    # Bucle hasta que el directorio actual sea None o la raíz
    while xDirectorio_actual and xDirectorio_actual != os.path.dirname(xDirectorio_actual):
        # Verifica si el archivo existe en el directorio actual
        if xNombre_archivo in os.listdir(xDirectorio_actual):
            # Devuelve la ruta completa si se encuentra
            return os.path.join(xDirectorio_actual, xNombre_archivo)
        # Mueve al directorio padre
        xDirectorio_actual = os.path.dirname(xDirectorio_actual)
    # Devuelve None si no se encuentra el archivo
    return None

def leer_ignore_list(xRuta_options):
    """
    Lee el archivo scb.options y retorna la lista de archivos a ignorar.
    Si el archivo no existe, crea uno con la estructura predeterminada.
    """
    # Verifica si el archivo de opciones existe
    if not os.path.exists(xRuta_options):
        # Si no existe el archivo, crearlo con la estructura predeterminada
        opciones = {
            "ignore_list": [
                "ejemplo123.txt",  # Ejemplo de archivo ignorado
            ]
        }
        # Abre el archivo de opciones para escritura
        with open(xRuta_options, 'w') as f:
            # Escribe las opciones como JSON con indentacion
            json.dump(opciones, f, indent=4)
        # Imprime mensaje de éxito
        print(f"El archivo {xRuta_options} no existía, se ha creado con la estructura predeterminada.")
        # Devuelve la lista de ignorados
        return opciones['ignore_list']
    else:
        try:
            # Abre el archivo de opciones para lectura
            with open(xRuta_options, 'r') as f:
                # Carga los datos JSON
                opciones = json.load(f)
                # Devuelve la lista de ignorados o una lista vacía si no se encuentra
                return opciones.get('ignore_list', [])
        except Exception as e:
            # Imprime mensaje de error si falla la lectura
            print(f"Error leyendo el archivo {xRuta_options}: {e}")
            # Sale del programa
            exit()

def agregar_historial_log(xContenido_existente, xUsuario, xAccion, xTipo, xDescripcion):
    """
    Agrega una nueva línea al historial del log con la información proporcionada.
    """
    # Obtiene la fecha actual
    xFecha_actual = datetime.now().strftime("%d-%m-%Y")
    # Obtiene la hora actual
    xHora_actual = datetime.now().strftime("%H:%M")
    # Formatea la línea del log con la información proporcionada
    xLinea_historial = HISTORIAL_TEMPLATE.format(
        fecha=xFecha_actual, hora=xHora_actual, usuario=xUsuario, accion=xAccion, tipo=xTipo, descripcion=xDescripcion
    )
    # Devuelve el contenido del log actualizado
    return f"{xContenido_existente}\n{xLinea_historial}"

def crear_scb_log(xFtp, accion, descripcion, tipo="archivo", usuario=None):
    """Registro en scb.log con formato específico"""
    if usuario is None:
        usuario = getpass.getuser()
    
    registro = HISTORIAL_TEMPLATE.format(
        fecha=datetime.now().strftime("%d-%m-%Y"),
        hora=datetime.now().strftime("%H:%M"),
        usuario=usuario,
        accion=accion,
        tipo=tipo,
        descripcion=descripcion
    )
    
    try:
        # Append local + upload completo al FTP
        with open('scb.log', 'a', encoding='utf-8') as f:
            f.write(registro + '\n')
        with open('scb.log', 'rb') as f:
            xFtp.storbinary('STOR scb.log', f)
    except Exception as e:
        logging.error(f"Error al escribir en scb.log: {e}")

# Funcion mejorada para verificar conexion
def verificar_conexion(xFtp):
    """Verifica y reconecta si es necesario."""
    try:
        xFtp.voidcmd("NOOP")
        return xFtp
    except:
        logging.warning("Conexion FTP perdida. Reconectando...")
        try:
            config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            return conectar_ftp(config)
        except Exception as e:
            logging.error(f"Error al reconectar: {e}")
            return None

# Funciones de validacion de rutas
def validar_ruta_local(ruta):
    """Evita path traversal en rutas locales."""
    ruta_abs = os.path.abspath(ruta)
    if not ruta_abs.startswith(os.path.abspath(os.getcwd())):
        raise ValueError(f"Ruta local no permitida: {ruta}")

def validar_ruta_ftp(ruta):
    """Evita comandos FTP maliciosos."""
    if ".." in ruta or "~" in ruta:
        raise ValueError(f"Ruta FTP no permitida: {ruta}")

# Funcion de comparacion de fechas con tolerancia
def comparar_fechas(ts_local, ts_ftp, tolerancia_seg=2):
    """Compara fechas con tolerancia para evitar falsos positivos."""
    if ts_local is None or ts_ftp is None:
        return True
    return abs(ts_local - ts_ftp) > tolerancia_seg



def obtener_fecha_modificacion(xFtp=None, ruta_local=None, ruta_ftp=None):
    """
    Obtiene fechas SIN conversion de zona horaria:
    - Para archivos locales: usa el timestamp directamente
    - Para archivos FTP: interpreta la hora del servidor como local
    """
    # Archivo local
    if ruta_local:
        if not os.path.exists(ruta_local):
            return None
        try:
            return os.path.getmtime(ruta_local)
        except Exception as e:
            print(f"⚠️ Error con archivo local {ruta_local}: {e}")
            return None

    # Archivo FTP (tratar la hora del servidor como local)
    elif xFtp and ruta_ftp:
        try:
            if not hasattr(xFtp, 'sock') or xFtp.sock is None:
                raise ftplib.Error("Conexion perdida")

            respuesta = xFtp.sendcmd(f"MDTM {ruta_ftp}")
            fecha_str = respuesta[4:].strip()
            
            # Parsear fecha del servidor SIN conversion de zona
            fecha_servidor = datetime.strptime(fecha_str, "%Y%m%d%H%M%S")
            return datetime.timestamp(fecha_servidor)

        except ftplib.error_perm as e:
            if "550" in str(e):
                return None
            print(f"⚠️ Error con archivo FTP {ruta_ftp}: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error desconocido con FTP {ruta_ftp}: {e}")
            return None

    return None

def set_fecha_modificacion(ftp: ftplib.FTP, ruta_ftp: str, fecha_local: datetime):
    """
    Establece la fecha de modificación en el servidor FTP (versión corregida sin conversión de zona horaria).
    """
    try:
        # Usar la fecha directamente sin conversión de zona horaria
        comando = f"MFMT {fecha_local.strftime('%Y%m%d%H%M%S')} {ruta_ftp}"
        ftp.sendcmd(comando)
    except Exception as e:
        print(f"❌ Error al actualizar fecha en FTP: {e}")

def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_dir_ftp='/'):
    """
    Crea la estructura de carpetas en el servidor FTP basada en las carpetas locales.
    """
    # Obtiene la ruta relativa del directorio de origen
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    # Divide la ruta en carpetas
    xCarpetas = xRuta_relativa.split(os.sep)
    # Inicializa la ruta actual en FTP
    xRuta_actual_ftp = xDestino_dir_ftp

    # Itera sobre cada carpeta
    for xCarpeta in xCarpetas:
        # Si el nombre de la carpeta no está vacío
        if xCarpeta:
            # Actualiza la ruta actual en FTP
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")
            try:
                # Cambia al directorio FTP actual
                xFtp.cwd(xRuta_actual_ftp)
                # Mueve al directorio padre
                xFtp.cwd("..")
            except Exception:
                try:
                    # Crea la carpeta en el servidor FTP
                    xFtp.mkd(xRuta_actual_ftp)
                    # Registra la creacion de la carpeta
                    crear_scb_log(xFtp, xRuta_actual_ftp, "creo", xCarpeta, tipo="carpeta")
                    # Imprime mensaje de éxito
                    print(f"Carpeta creada: {xRuta_actual_ftp}")
                except Exception as e:
                    # Imprime mensaje de error si falla la creacion
                    print(f"No se pudo crear la carpeta {xRuta_actual_ftp}: {e}")

    # Devuelve la ruta actual en FTP
    return xRuta_actual_ftp  

def archivos_necesitan_sync(
    ts_local: float | None, 
    ts_ftp: float | None, 
    tolerancia_seg: int = 2
) -> bool:
    """
    Determina con precisión si se necesita sincronización entre archivos locales y remotos.
    
    Args:
        ts_local: Timestamp del archivo local (None si no existe)
        ts_ftp: Timestamp del archivo FTP (None si no existe)
        tolerancia_seg: Margen de diferencia permitido en segundos (default: 2)
    
    Returns:
        bool: True si se requiere sincronización, False si están actualizados
    """
    if ts_local is None or ts_ftp is None:
        return True
    
    # Conversión a datetime con zona horaria UTC
    fecha_local = datetime.fromtimestamp(ts_local, timezone.utc)
    fecha_ftp = datetime.fromtimestamp(ts_ftp, timezone.utc)
    
    # Cálculo preciso de diferencia
    diferencia = abs((fecha_local - fecha_ftp).total_seconds())
    return diferencia > tolerancia_seg

def obtener_timestamp_ftp(ftp: ftplib.FTP, ruta_ftp: str) -> float | None:
    """
    Obtiene el timestamp de un archivo FTP en segundos desde epoch (UTC).
    """
    try:
        respuesta = ftp.sendcmd(f"MDTM {ruta_ftp}")
        fecha_str = respuesta[4:].strip()
        fecha_ftp = datetime.strptime(fecha_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return fecha_ftp.timestamp()
    except ftplib.error_perm:
        return None

def obtener_timestamp_local(ruta_local: str) -> float | None:
    """
    Obtiene el timestamp de un archivo local en segundos desde epoch (UTC).
    """
    if not os.path.exists(ruta_local):
        return None
    return os.path.getmtime(ruta_local)

def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list, xContador=[0]):
    """Descarga archivos recursivamente mostrando rutas completas"""
    usuario = getpass.getuser()
    
    # Verificación de conexión
    if not hasattr(xFtp, 'sock') or xFtp.sock is None:
        print("⚠️ Conexión FTP perdida. Reconectando...")
        try:
            config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            xFtp = conectar_ftp(config)
            xContador[0] = 0
        except Exception as e:
            print(f"❌ Error al reconectar: {e}")
            return None

    os.makedirs(xRuta_local, exist_ok=True)

    try:
        elementos = xFtp.nlst(xRuta_ftp)
    except ftplib.error_perm as e:
        if "550" in str(e):
            return xFtp
        print(f"❌ Error listando {xRuta_ftp}: {e}")
        return xFtp
    except Exception as e:
        print(f"❌ Error inesperado al listar {xRuta_ftp}: {e}")
        return xFtp

    for elemento in elementos:
        ruta_completa_ftp = os.path.join(xRuta_ftp, elemento).replace('\\', '/')
        ruta_completa_local = os.path.join(xRuta_local, os.path.basename(elemento))
        nombre_archivo = os.path.basename(ruta_completa_ftp)

        # Filtrado de elementos
        if any(part in ['.', '..'] for part in ruta_completa_ftp.split('/')):
            continue
        if nombre_archivo == 'scb.log':
            continue
        if any(fnmatch.fnmatch(nombre_archivo, pattern) for pattern in xIgnore_list):
            continue

        try:
            xFtp.cwd(ruta_completa_ftp)
            if not os.path.exists(ruta_completa_local):
                os.makedirs(ruta_completa_local)
                print(f"📁 Carpeta creada: {ruta_completa_local}")
                crear_scb_log(xFtp, "creó", nombre_archivo, "carpeta", usuario)

            xFtp = descargar_archivos_recursivo(xFtp, ruta_completa_ftp, ruta_completa_local, xIgnore_list, xContador)
            if xFtp is None:
                return None
            xFtp.cwd('..')

        except ftplib.error_perm:
            ts_ftp = obtener_timestamp_ftp(xFtp, ruta_completa_ftp)
            ts_local = obtener_timestamp_local(ruta_completa_local)

            if archivos_necesitan_sync(ts_local, ts_ftp):
                print(f"🔽 Descargando: {ruta_completa_ftp}")
                
                with open(ruta_completa_local, 'wb') as f:
                    xFtp.retrbinary(f"RETR {ruta_completa_ftp}", f.write)
                
                if ts_ftp is not None:
                    os.utime(ruta_completa_local, (ts_ftp, ts_ftp))
                
                crear_scb_log(xFtp, "descargó", nombre_archivo, "archivo", usuario)
                
                xContador[0] += 1
                if xContador[0] >= DESCARGAS_PERMITIDAS_RECONEXION:
                    xFtp.quit()
                    config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
                    xFtp = conectar_ftp(config)
                    xContador[0] = 0

    return xFtp
def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp, xIgnore_list):
    """
    Sube archivos recursivamente al FTP mostrando solo novedades.
    """
    usuario = getpass.getuser()
    
    for nombre in os.listdir(xRuta_local):
        ruta_local = os.path.join(xRuta_local, nombre)
        ruta_ftp_completa = os.path.join(xRuta_ftp, nombre).replace("\\", "/")

        # Ignorar según lista
        if any(fnmatch.fnmatch(nombre, patron) for patron in xIgnore_list):
            continue

        if os.path.isfile(ruta_local):
            ts_local = obtener_timestamp_local(ruta_local)
            ts_ftp = obtener_timestamp_ftp(xFtp, ruta_ftp_completa)

            if ts_ftp is None or (ts_local and ts_local > ts_ftp):
                try:
                    with open(ruta_local, 'rb') as f:
                        xFtp.storbinary(f'STOR {ruta_ftp_completa}', f)
                    
                    # Mensaje unificado con emoji y ruta completa
                    print(f"🔼 Subiendo: {ruta_ftp_completa}")
                    crear_scb_log(xFtp, "subió", nombre, "archivo", usuario)
                    
                except Exception as e:
                    print(f"❌ Error al subir {ruta_ftp_completa}: {e}")

        elif os.path.isdir(ruta_local):
            try:
                xFtp.cwd(ruta_ftp_completa)
            except:
                try:
                    xFtp.mkd(ruta_ftp_completa)
                    print(f"📁 Carpeta creada: {ruta_ftp_completa}")
                    crear_scb_log(xFtp, "creó", nombre, "carpeta", usuario)
                except Exception as e:
                    print(f"❌ Error creando carpeta {ruta_ftp_completa}: {e}")
                    continue

            subir_archivos_recursivo(xFtp, ruta_local, ruta_ftp_completa, xIgnore_list)
            xFtp.cwd("..")
            
def subir_archivos():
    """Funcion principal para subir archivos"""
    try:
        
        # Buscar configuracion
        ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
        if not ruta_config:
            print("❌ Archivo de configuracion no encontrado")
            return

        # Obtener lista de ignorados
        directorio_base = os.path.dirname(ruta_config)
        ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, directorio_base)
        ignore_list = leer_ignore_list(ruta_opciones) if ruta_opciones else []

        # Conectar al FTP
        config = leer_configuracion(ruta_config)
        ftp = conectar_ftp(config)
        if not ftp:
            print("❌ No se pudo conectar al FTP")
            return

        # Crear estructura de carpetas
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), directorio_base)

        # Subir archivos
        subir_archivos_recursivo(ftp, os.getcwd(), ruta_final_ftp, ignore_list)
        
        print("✅ Subida completada")

    except KeyboardInterrupt:
        print("\n🛑 Descarga cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {str(e)}")
    finally:
        if 'ftp' in locals() and hasattr(ftp, 'sock') and ftp.sock:
            try:
                ftp.quit()
            except:
                pass
            
def bajar_archivos():
    """Funcion principal para descargar archivos"""
    try:
        
        # Buscar configuracion
        ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
        if not ruta_config:
            print("❌ Archivo de configuracion no encontrado")
            return

        # Obtener lista de ignorados
        directorio_base = os.path.dirname(ruta_config)
        ruta_opciones = buscar_archivo_ancestro(ARCHIVO_OPTIONS, directorio_base)
        ignore_list = leer_ignore_list(ruta_opciones) if ruta_opciones else []

        # Conectar al FTP
        config = leer_configuracion(ruta_config)
        ftp = conectar_ftp(config)
        if not ftp:
            print("❌ No se pudo conectar al FTP")
            return

        # Determinar ruta remota
        ruta_relativa = os.path.relpath(os.getcwd(), directorio_base)
        ruta_inicial_ftp = ftp.pwd() if ruta_relativa == "." else os.path.join(ftp.pwd(), ruta_relativa).replace('\\', '/')

        # Descargar archivos
        ftp = descargar_archivos_recursivo(ftp, ruta_inicial_ftp, os.getcwd(), ignore_list)
        
        if ftp:
            print("✅ Descarga completada")
        else:
            print("⚠️ Descarga completada con errores")

    except KeyboardInterrupt:
        print("\n🛑 Descarga cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {str(e)}")
    finally:
        if 'ftp' in locals() and hasattr(ftp, 'sock') and ftp.sock:
            try:
                ftp.quit()
            except:
                pass
def main():
    """
    Funcion principal que maneja la ejecucion del script.
    Procesa argumentos y llama a las funciones correspondientes.
    """
    if len(sys.argv) != 2:
        print("Uso: scbox [u | d | s]")
        print("  u: Subir archivos")
        print("  d: Descargar archivos")
        print("  s: Sincronizacion completa (descarga + subida)")
        sys.exit(1)

    operacion = sys.argv[1].strip().lower()

    try:
        if operacion == "u":
            print("\n🔼 Iniciando Upload.. [scbox 25.04]")  # Solo imprime en consola
            subir_archivos()
            
        elif operacion == "d":
            print("\n🔽 Iniciando Download.. [scbox 25.04]")  # Solo imprime en consola
            bajar_archivos()
            
        elif operacion == "s":
            print("\n🔄 Iniciando Sincronizacion.. [scbox 25.04]")  # Solo imprime en consola
            # Primero descargar los cambios del servidor
            bajar_archivos()
            # Luego subir los cambios locales
            subir_archivos()
            
        else:
            print(f" 🛑 Operacion no válida: {operacion}")
            print("Opcion no válida. Debes ingresar 'u' para subir, 'd' para descargar o 's' para sincronizar")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Operacion interrumpida por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"Error crítico: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Inicialización del archivo de log si no existe
    if not os.path.exists('scb.log'):
        with open('scb.log', 'w', encoding='utf-8') as f:
            f.write(f"Log iniciado - scbox 25.04 - {datetime.now().strftime('%d-%m-%Y %H:%M')}\n")
    
    # Configuracion básica del logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scb.log', mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    main()