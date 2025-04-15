"""
SCBox - Sistema de Sincronización FTP

Este sistema proporciona sincronización bidireccional entre archivos locales y un servidor FTP,
con manejo robusto de errores y verificación de integridad de archivos.
"""

import ftplib
import os
import json
from ftplib import FTP
import time
from datetime import datetime, timezone
import getpass
import fnmatch
import sys
import logging
from socket import gaierror, timeout as SocketTimeout

# ==============================================
# CONSTANTES GLOBALES
# ==============================================
ARCHIVO_CONFIG = 'scb.config'  # Archivo de configuración principal
ARCHIVO_OPTIONS = 'scb.options'  # Archivo con patrones a ignorar
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"
DESCARGAS_PERMITIDAS_RECONEXION = 50  # Número máximo de descargas antes de reconectar
MAX_REINTENTOS = 1  # Máximo de reintentos por operación
TIMEOUT_FTP = 180  # Timeout en segundos para conexión FTP
TIEMPO_ESPERA_RECONEXION = 600
UMBRAL_BARRA_PROGRESO = 1024 * 1024  # 1MB - Mostrar barra para archivos mayores a este tamaño
TAMANO_BLOQUE = 8192  # Tamaño de bloque para transferencias

# ==============================================
# CLASES AUXILIARES
# ==============================================
class BarraProgreso:
    """Muestra una barra de progreso simple para transferencias de archivos"""
    
    def __init__(self, nombre_archivo, tamano_total):
        self.nombre = os.path.basename(nombre_archivo)
        self.tamano_total = tamano_total
        self.transferido = 0
        self.ancho = 30
        
    def actualizar(self, bytes_transferidos):
        self.transferido += bytes_transferidos
        porcentaje = min(100, (self.transferido / self.tamano_total) * 100)
        barras = int(self.ancho * porcentaje / 100)
        
        # Formato: [=====>    ] 45% 1.2/2.5MB nombre.txt
        sys.stdout.write(
            f"\r[{'=' * (barras - 1)}>{' ' * (self.ancho - barras)}] "
            f"{porcentaje:.0f}% "
            f"{self._formatear_tamano(self.transferido)}/"
            f"{self._formatear_tamano(self.tamano_total)} "
            f"{self.nombre[:20]}{' ' * 5}"
        )
        sys.stdout.flush()
        
    def completado(self):
        sys.stdout.write("\n")
        sys.stdout.flush()
        
    def _formatear_tamano(self, bytes):
        for unidad in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f}{unidad}"
            bytes /= 1024
        return f"{bytes:.1f}TB"

class Estadisticas:
    def __init__(self):
        self.archivos_descargados = 0
        self.archivos_subidos = 0
        self.carpetas_creadas = 0
        self.tamano_transferido = 0
        self.errores = 0
        
    def mostrar(self):
        print("\n📊 Estadísticas:")
        print(f"  - Archivos descargados: {self.archivos_descargados}")
        print(f"  - Archivos subidos: {self.archivos_subidos}")
        print(f"  - Carpetas creadas: {self.carpetas_creadas}")
        print(f"  - Tamaño total transferido: {self._formatear_tamano(self.tamano_transferido)}")
        print(f"  - Errores encontrados: {self.errores}")
        
    def _formatear_tamano(self, bytes):
        for unidad in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f}{unidad}"
            bytes /= 1024
        return f"{bytes:.1f}TB"

# Variable global para estadísticas
estadisticas = Estadisticas()

# ==============================================
# CONFIGURACIÓN DE LOGGING
# ==============================================
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scb.log', mode='a', encoding='utf-8')]
)

# ==============================================
# FUNCIONES DE CONEXIÓN Y CONFIGURACIÓN
# ==============================================

def conectar_ftp(config):
    """
    Establece conexión con el servidor FTP usando la configuración proporcionada.
    
    Args:
        config (dict): Diccionario con la configuración FTP que debe contener:
                      - ftp_server: Dirección del servidor
                      - ftp_user: Nombre de usuario
                      - ftp_password: Contraseña
    
    Returns:
        FTP: Objeto FTP conectado y autenticado
    
    Raises:
        SocketTimeout: Si se excede el tiempo de conexión
        ftplib.all_errors: Para otros errores relacionados con FTP
    """
    try:
        ftp = FTP(timeout=TIMEOUT_FTP)
        ftp.connect(config['FTP']['ftp_server'], timeout=TIMEOUT_FTP)
        ftp.login(user=config['FTP']['ftp_user'], passwd=config['FTP']['ftp_password'])
        ftp.set_pasv(True)
        return ftp
    except SocketTimeout:
        print("⌛ Timeout al conectar")
        raise
    except ftplib.all_errors as e:
        print(f"❌ Error de conexión: {e}")
        raise

def leer_configuracion(ruta_config):
    """
    Lee y valida el archivo de configuración en formato JSON.
    
    Args:
        ruta_config (str): Ruta completa al archivo de configuración
    
    Returns:
        dict: Diccionario con la configuración cargada
    
    Exits:
        Termina el programa si el archivo no existe o es inválido
    """
    try:
        with open(ruta_config, 'r') as archivo:
            config = json.load(archivo)
            if 'FTP' not in config or not all(k in config['FTP'] for k in ['ftp_server', 'ftp_user', 'ftp_password']):
                raise ValueError("Configuración incompleta o inválida")
            return config
    except Exception as e:
        print(f"❌ Error al leer configuración: {e}")
        sys.exit(1)

def buscar_archivo_ancestro(nombre_archivo, directorio_actual):
    """
    Busca un archivo en el directorio actual y hacia arriba en la jerarquía.
    
    Args:
        nombre_archivo (str): Nombre del archivo a buscar
        directorio_actual (str): Directorio donde comenzar la búsqueda
    
    Returns:
        str: Ruta completa del archivo encontrado o None si no existe
    """
    directorio_actual = os.path.abspath(directorio_actual)
    while True:
        ruta_candidata = os.path.join(directorio_actual, nombre_archivo)
        if os.path.exists(ruta_candidata):
            return ruta_candidata
        padre = os.path.dirname(directorio_actual)
        if padre == directorio_actual:
            return None
        directorio_actual = padre

def leer_ignore_list(ruta_options):
    """
    Lee la lista de patrones de archivos a ignorar durante la sincronización.
    
    Args:
        ruta_options (str): Ruta al archivo de opciones
    
    Returns:
        list: Lista de patrones a ignorar (puede estar vacía)
    """
    if not os.path.exists(ruta_options):
        opciones = {
            "ignore_list": [
                "scb.log",
                "scb.config",
                "scb.options"
                ],
            "_explicacion": "Patrones de archivos/carpetas a ignorar:"
            "archivo.txt - se ignora el archivo por defecto "
            "carpeta* - se ignora carpeta"
            "*.zip - se ignora una terminacion"
        }
        try:
            with open(ruta_options, 'w', encoding='utf-8') as archivo:
                json.dump(opciones, archivo, indent=4, ensure_ascii=False)
            print(f"📄 Archivo de opciones creado: {ruta_options}")
            return opciones['ignore_list']
        except Exception as e:
            print(f"❌ Error al crear {ruta_options}: {e}")
            return []
    else:
        try:
            with open(ruta_options, 'r', encoding='utf-8') as archivo:
                data = json.load(archivo)
                if isinstance(data, dict) and 'ignore_list' in data:
                    return data['ignore_list']
                else:
                    print(f"⚠️ Formato inválido en {ruta_options}")
                    return []
        except json.JSONDecodeError:
            print(f"⚠️ Archivo corrupto: {ruta_options}")
            return []
        except Exception as e:
            print(f"❌ Error leyendo {ruta_options}: {e}")
            return []

def verificar_conexion_internet():
    """Verifica si hay conexión a internet"""
    try:
        import urllib.request
        import socket
        socket.setdefaulttimeout(10)  # Timeout de 10 segundos
        urllib.request.urlopen('http://google.com', timeout=10)
        return True
    except Exception:
        return False

def esperar_reconexion():
    """Espera hasta que se restablezca la conexión a internet"""
    print("🌐 Conexión a internet perdida, esperando reconexión...")
    tiempo_inicio = time.time()
    ultimo_mensaje = 0
    
    while not verificar_conexion_internet():
        tiempo_transcurrido = time.time() - tiempo_inicio
        
        if tiempo_transcurrido > TIEMPO_ESPERA_RECONEXION:
            print("❌ Tiempo de espera agotado, no se pudo reconectar")
            return False
        
        # Mostrar mensaje cada 30 segundos sin saturar
        if time.time() - ultimo_mensaje > 30:
            segundos_restantes = int(TIEMPO_ESPERA_RECONEXION - tiempo_transcurrido)
            print(f"⏳ Esperando reconexión ({segundos_restantes}s restantes)...")
            ultimo_mensaje = time.time()
        
        time.sleep(5)  # Verificar más frecuentemente
    
    print("✅ Conexión a internet restablecida")
    return True


# ==============================================
# FUNCIONES DE REGISTRO Y METADATOS
# ==============================================

def crear_scb_log(ftp, accion, descripcion, tipo="archivo", usuario=None):
    """
    Registra una acción en el archivo de log local y lo sincroniza con el servidor.
    
    Args:
        ftp (FTP): Conexión FTP (puede ser None)
        accion (str): Acción realizada (ej. "descargó", "subió")
        descripcion (str): Descripción del elemento afectado
        tipo (str): Tipo de elemento ("archivo" o "carpeta")
        usuario (str): Nombre de usuario (si no se proporciona, se detecta automáticamente)
    """
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
        with open('scb.log', 'a', encoding='utf-8') as archivo:
            archivo.write(registro + '\n')
        
        if ftp:
            with open('scb.log', 'rb') as archivo:
                ftp.storbinary('STOR scb.log', archivo)
    except Exception as e:
        print(f"⚠️ Error al escribir en log: {e}")

def obtener_timestamp_ftp(ftp, ruta_ftp):
    """
    Obtiene la fecha de modificación de un archivo remoto en formato timestamp.
    
    Args:
        ftp (FTP): Conexión FTP activa
        ruta_ftp (str): Ruta remota del archivo
    
    Returns:
        float: Timestamp en UTC o None si el archivo no existe
    """
    try:
        respuesta = ftp.sendcmd(f"MDTM {ruta_ftp}")
        fecha_str = respuesta[4:].strip()
        fecha_utc = datetime.strptime(fecha_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return fecha_utc.timestamp()
    except ftplib.error_perm as e:
        if "550" in str(e):
            return None
        raise
    except Exception as e:
        print(f"⚠️ Error obteniendo timestamp FTP: {e}")
        return None

def obtener_timestamp_local(ruta_local):
    """
    Obtiene la fecha de modificación de un archivo local en formato timestamp UTC.
    
    Args:
        ruta_local (str): Ruta local del archivo
    
    Returns:
        float: Timestamp en UTC o None si el archivo no existe
    """
    try:
        if not os.path.exists(ruta_local):
            return None
        
        timestamp = os.path.getmtime(ruta_local)
        fecha_local = datetime.fromtimestamp(timestamp).astimezone()
        return fecha_local.timestamp()
    except Exception as e:
        print(f"⚠️ Error obteniendo timestamp local: {e}")
        return None

def necesita_sincronizacion(ts_local, ts_ftp, tolerancia=2):
    """
    Determina si un archivo necesita sincronización comparando sus timestamps.
    
    Args:
        ts_local (float): Timestamp local en UTC
        ts_ftp (float): Timestamp remoto en UTC
        tolerancia (int): Margen de diferencia en segundos
    
    Returns:
        bool: True si los archivos difieren más que la tolerancia
    """
    if ts_local is None or ts_ftp is None:
        return True
    return abs(ts_local - ts_ftp) > tolerancia

def verificar_integridad_archivo(ruta_archivo, tamano_esperado=None):
    """
    Verifica la integridad básica de un archivo descargado.
    
    Args:
        ruta_archivo (str): Ruta al archivo a verificar
        tamano_esperado (int): Tamaño esperado en bytes (opcional)
    
    Returns:
        bool: True si el archivo existe y su tamaño coincide (si se especificó)
    """
    try:
        if not os.path.exists(ruta_archivo):
            return False
        
        if tamano_esperado is not None:
            return os.path.getsize(ruta_archivo) == tamano_esperado
        
        return True
    except Exception as e:
        print(f"⚠️ Error verificando integridad: {e}")
        return False

# ==============================================
# FUNCIONES DE TRANSFERENCIA DE ARCHIVOS
# ==============================================

def descargar_archivo(ftp, ruta_ftp, ruta_local, nombre_archivo, contador):
    """
    Descarga un archivo desde el servidor FTP con verificación de integridad.
    
    Args:
        ftp (FTP): Conexión FTP activa
        ruta_ftp (str): Ruta remota del archivo
        ruta_local (str): Ruta local de destino
        nombre_archivo (str): Nombre del archivo para registro
        contador (list): Contador de descargas (usado para reconexión)
    
    Returns:
        FTP: Objeto FTP (puede ser una nueva conexión)
    
    Raises:
        ConnectionError: Si hay problemas de conexión
        ValueError: Si el archivo descargado no pasa la verificación
        Exception: Para otros errores durante la transferencia
    """
    global estadisticas
    ruta_temp = ruta_local + '.tmp'
    
    try:
        # Verificar conexión antes de comenzar
        try:
            ftp.voidcmd("NOOP")
        except (ftplib.all_errors, gaierror, OSError, SocketTimeout) as e:
            raise ConnectionError(f"Conexión perdida al iniciar descarga: {e}")

        # Forzar modo binario
        ftp.voidcmd('TYPE I')
        
        # Obtener tamaño remoto (si está disponible)
        tamano_remoto = None
        try:
            if 'SIZE' in ftp.voidcmd('FEAT'):
                tamano_remoto = ftp.size(ruta_ftp)
        except ftplib.all_errors:
            pass  # Continuar sin información de tamaño
        
        # Inicializar barra de progreso si el archivo es grande
        barra = None
        if tamano_remoto and tamano_remoto > UMBRAL_BARRA_PROGRESO:
            barra = BarraProgreso(nombre_archivo, tamano_remoto)
        
        # Descargar a archivo temporal primero
        with open(ruta_temp, 'wb') as archivo:
            def callback(data):
                archivo.write(data)
                if barra:
                    barra.actualizar(len(data))
                    
            # Verificar conexión periódicamente durante la descarga
            def verificar_conexion():
                try:
                    ftp.voidcmd("NOOP")
                except (ftplib.all_errors, gaierror, OSError, SocketTimeout) as e:
                    raise ConnectionError(f"Conexión perdida durante descarga: {e}")
            
            # Descargar en bloques con verificación de conexión
            bloque = bytearray()
            ftp.retrbinary(f"RETR {ruta_ftp}", lambda data: bloque.extend(data), blocksize=TAMANO_BLOQUE)
            
            # Verificar conexión después de cada bloque
            if len(bloque) > 0:
                verificar_conexion()
                callback(bloque)
                bloque.clear()
            
        if barra:
            barra.completado()
        
        # Verificar integridad del archivo descargado
        if not verificar_integridad_archivo(ruta_temp, tamano_remoto):
            os.remove(ruta_temp)
            raise ValueError("Archivo descargado corrupto o incompleto")
        
        # Reemplazar archivo existente si es necesario
        if os.path.exists(ruta_local):
            os.remove(ruta_local)
        os.rename(ruta_temp, ruta_local)
        
        # Sincronizar timestamp con el servidor
        ts_ftp = obtener_timestamp_ftp(ftp, ruta_ftp)
        if ts_ftp:
            os.utime(ruta_local, (ts_ftp, ts_ftp))
        
        # Registrar operación y actualizar contador
        crear_scb_log(ftp, "descargó", nombre_archivo)
        contador[0] += 1
        estadisticas.archivos_descargados += 1
        if tamano_remoto:
            estadisticas.tamano_transferido += tamano_remoto
        
        # Reconectar si se alcanza el límite de descargas
        if contador[0] >= DESCARGAS_PERMITIDAS_RECONEXION:
            try:
                ftp.quit()
            except:
                pass
            config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            ftp = conectar_ftp(config)
            contador[0] = 0
        
        return ftp
        
    except ConnectionError as e:
        estadisticas.errores += 1
        # Limpiar archivo temporal en caso de error
        if os.path.exists(ruta_temp):
            try:
                os.remove(ruta_temp)
            except:
                pass
        print(f"❌ Error de conexión al descargar {ruta_ftp}: {e}")
        raise  # Relanzar para manejar reconexión
    except Exception as e:
        estadisticas.errores += 1
        # Limpiar archivo temporal en caso de error
        if os.path.exists(ruta_temp):
            try:
                os.remove(ruta_temp)
            except:
                pass
        print(f"❌ Error al descargar {ruta_ftp}: {e}")
        raise

def subir_archivo(ftp, ruta_local, ruta_ftp, nombre_archivo):
    """
    Sube un archivo local al servidor FTP preservando metadatos.
    
    Args:
        ftp (FTP): Conexión FTP activa
        ruta_local (str): Ruta local del archivo
        ruta_ftp (str): Ruta remota de destino
        nombre_archivo (str): Nombre del archivo para registro
    
    Returns:
        bool: True si la operación fue exitosa
    """
    global estadisticas
    try:
        # Validar que el archivo local existe
        if not os.path.exists(ruta_local):
            print(f"❌ Archivo local no encontrado: {ruta_local}")
            return False

        tamano_local = os.path.getsize(ruta_local)
        barra = None
        if tamano_local > UMBRAL_BARRA_PROGRESO:
            barra = BarraProgreso(nombre_archivo, tamano_local)

        # Obtener metadatos locales
        ts_local = os.path.getmtime(ruta_local)
        fecha_mod = datetime.fromtimestamp(ts_local, timezone.utc)
        fecha_ftp = fecha_mod.strftime('%Y%m%d%H%M%S')

        # Subir primero a archivo temporal remoto
        ruta_temp_ftp = ruta_ftp + '.tmp'
        with open(ruta_local, 'rb') as archivo:
            def callback(data):
                if barra:
                    barra.actualizar(len(data))
                return data
                
            ftp.storbinary(f'STOR {ruta_temp_ftp}', archivo, blocksize=TAMANO_BLOQUE, callback=callback)
            
        if barra:
            barra.completado()

        # Reemplazar archivo remoto existente
        try:
            if ruta_ftp in ftp.nlst(os.path.dirname(ruta_ftp)):
                ftp.delete(ruta_ftp)
            ftp.rename(ruta_temp_ftp, ruta_ftp)
        except:
            print("❌ No se pudo renombrar archivo temporal remoto")
            raise

        # Sincronizar fecha de modificación
        try:
            ftp.sendcmd(f"MFMT {fecha_ftp} {ruta_ftp}")
        except ftplib.all_errors as e:
            print(f"⚠️ No se pudo actualizar fecha remota: {e}")

        # Registrar operación exitosa
        crear_scb_log(ftp, "subió", nombre_archivo)
        estadisticas.archivos_subidos += 1
        estadisticas.tamano_transferido += tamano_local
        return True

    except Exception as e:
        estadisticas.errores += 1
        # Limpiar archivo temporal remoto si existe
        try:
            if 'ruta_temp_ftp' in locals() and ruta_temp_ftp in ftp.nlst(os.path.dirname(ruta_temp_ftp)):
                ftp.delete(ruta_temp_ftp)
        except:
            pass
        
        print(f"❌ Error al subir {ruta_ftp}: {e}")
        return False

# ==============================================
# FUNCIONES DE SINCRONIZACIÓN RECURSIVA
# ==============================================

def descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local, ignore_list, contador=[0], reintentos=0):
    """
    Descarga recursiva de archivos desde servidor FTP con manejo robusto de conexión
    
    Args:
        ftp (FTP): Conexión FTP activa
        ruta_ftp (str): Ruta remota inicial
        ruta_local (str): Ruta local de destino
        ignore_list (list): Patrones de archivos a ignorar
        contador (list): Contador de descargas para reconexión
        reintentos (int): Número de reintentos actuales
        
    Returns:
        FTP: Nueva conexión FTP si hubo reconexión
    """
    if reintentos > MAX_REINTENTOS:
        print("\n❌ Máximo de reintentos alcanzado - Abortando descarga")
        return None

    try:
        # Verificar conexión FTP e internet
        try:
            ftp.voidcmd("NOOP")
        except (ftplib.all_errors, gaierror, OSError, SocketTimeout) as e:
            print(f"\n⚠️ Error de conexión: {str(e)}")
            if not esperar_reconexion():
                return None
            
            print("🔁 Reconectando con servidor FTP...")
            try:
                config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
                ftp = conectar_ftp(config)
                contador[0] = 0
                return descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local, ignore_list, contador, reintentos+1)
            except Exception as e:
                print(f"❌ Error al reconectar: {e}")
                return None

        # Listar contenido remoto
        try:
            elementos = ftp.nlst(ruta_ftp)
        except ftplib.error_perm as e:
            if "550" in str(e):  # No existe el directorio
                return ftp
            raise

        for elemento in elementos:
            ruta_f = os.path.join(ruta_ftp, elemento).replace('\\', '/')
            ruta_l = os.path.join(ruta_local, os.path.basename(elemento))
            nombre = os.path.basename(ruta_f)

            # Filtrar elementos a ignorar
            if any(p in ['.', '..'] for p in ruta_f.split('/')):
                continue
            if nombre == 'scb.log' or any(fnmatch.fnmatch(nombre, patron) for patron in ignore_list):
                continue

            try:
                # Probar si es directorio
                try:
                    ftp.cwd(ruta_f)
                    # Es directorio, procesar recursivamente
                    if not os.path.exists(ruta_l):
                        os.makedirs(ruta_l)
                        crear_scb_log(ftp, "creó", nombre, "carpeta")
                        print(f"📂 Carpeta creada: {ruta_l}")
                    
                    ftp = descargar_archivos_recursivo(ftp, ruta_f, ruta_l, ignore_list, contador)
                    ftp.cwd('..')
                except ftplib.error_perm:
                    # Es archivo, procesar descarga
                    ts_ftp = obtener_timestamp_ftp(ftp, ruta_f)
                    ts_local = obtener_timestamp_local(ruta_l)

                    if necesita_sincronizacion(ts_local, ts_ftp):
                        print(f"🔽 Descargando: {ruta_f}")
                        ftp = descargar_archivo(ftp, ruta_f, ruta_l, nombre, contador)

            except KeyboardInterrupt:
                raise
            except (ftplib.all_errors, gaierror, OSError, SocketTimeout) as e:
                print(f"⚠️ Error de conexión procesando {ruta_f}: {e}")
                if esperar_reconexion():
                    config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
                    ftp = conectar_ftp(config)
                    contador[0] = 0
                    return descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local, ignore_list, contador, reintentos+1)
                else:
                    return None
            except Exception as e:
                print(f"⚠️ Error no relacionado con conexión procesando {ruta_f}: {e}")
                continue

        return ftp

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"\n❌ Error en descarga recursiva: {e}")
        if reintentos < MAX_REINTENTOS:
            print(f"🔄 Reintentando ({reintentos+1}/{MAX_REINTENTOS})...")
            if esperar_reconexion():
                config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
                ftp = conectar_ftp(config)
                contador[0] = 0
                return descargar_archivos_recursivo(ftp, ruta_ftp, ruta_local, ignore_list, contador, reintentos+1)
        return None
    
def subir_archivos_recursivo(ftp, ruta_local, ruta_ftp, ignore_list, reintentos=0):
    """
    Sube recursivamente archivos locales al servidor FTP con manejo robusto de conexión
    
    Args:
        ftp (FTP): Conexión FTP activa
        ruta_local (str): Ruta local inicial
        ruta_ftp (str): Ruta remota destino
        ignore_list (list): Patrones de archivos a ignorar
        reintentos (int): Número de reintentos actuales
    """
    if reintentos > MAX_REINTENTOS:
        print("\n❌ Máximo de reintentos alcanzado - Abortando subida")
        return

    try:
        # Verificar conexión antes de comenzar
        try:
            ftp.voidcmd("NOOP")
        except (ftplib.all_errors, gaierror, OSError, SocketTimeout) as e:
            print(f"\n⚠️ Error de conexión: {str(e)}")
            if not esperar_reconexion():
                return
            
            print("🔁 Reconectando con servidor FTP...")
            config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            ftp = conectar_ftp(config)
            return subir_archivos_recursivo(ftp, ruta_local, ruta_ftp, ignore_list, reintentos+1)

        for nombre in os.listdir(ruta_local):
            ruta_l = os.path.join(ruta_local, nombre)
            ruta_f = os.path.join(ruta_ftp, nombre).replace('\\', '/')

            # Verificar si el archivo debe ser ignorado
            if any(fnmatch.fnmatch(nombre, patron) for patron in ignore_list):
                continue

            if os.path.isfile(ruta_l):
                # Verificar conexión antes de cada subida
                try:
                    ftp.voidcmd("NOOP")
                except (ftplib.all_errors, gaierror, OSError, SocketTimeout) as e:
                    print(f"\n⚠️ Error de conexión: {str(e)}")
                    if not esperar_reconexion():
                        return
                    
                    print("🔁 Reconectando con servidor FTP...")
                    config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
                    ftp = conectar_ftp(config)
                    return subir_archivos_recursivo(ftp, ruta_local, ruta_ftp, ignore_list, reintentos+1)

                ts_local = obtener_timestamp_local(ruta_l)
                ts_ftp = obtener_timestamp_ftp(ftp, ruta_f)

                if necesita_sincronizacion(ts_local, ts_ftp):
                    print(f"🔼 Subiendo: {ruta_f}")
                    if not subir_archivo(ftp, ruta_l, ruta_f, nombre):
                        continue

            elif os.path.isdir(ruta_l):
                try:
                    ftp.cwd(ruta_f)
                except:
                    try:
                        ftp.mkd(ruta_f)
                        print(f"📂 Carpeta creada: {ruta_f}")
                        crear_scb_log(ftp, "creó", nombre, "carpeta")
                        estadisticas.carpetas_creadas += 1
                    except Exception as e:
                        print(f"❌ Error creando carpeta {ruta_f}: {e}")
                        continue

                subir_archivos_recursivo(ftp, ruta_l, ruta_f, ignore_list)
                ftp.cwd('..')

    except KeyboardInterrupt:
        raise  # Solo propagamos la interrupción
    except Exception as e:
        print(f"\n❌ Error en subida recursiva: {e}")
        if reintentos < MAX_REINTENTOS:
            print(f"🔄 Reintentando ({reintentos+1}/{MAX_REINTENTOS})...")
            if esperar_reconexion():
                config = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
                ftp = conectar_ftp(config)
                return subir_archivos_recursivo(ftp, ruta_local, ruta_ftp, ignore_list, reintentos+1)
# ==============================================
# FUNCIONES DE ESTRUCTURA DE CARPETAS
# ==============================================

def crear_estructura_carpetas_ftp(ftp, origen_dir, carpeta_principal, destino_ftp='/'):
    """
    Crea la estructura de carpetas equivalente en el servidor FTP.
    
    Args:
        ftp (FTP): Conexión FTP activa
        origen_dir (str): Ruta local del directorio a replicar
        carpeta_principal (str): Ruta local del directorio base
        destino_ftp (str): Ruta remota base (por defecto '/')
    
    Returns:
        str: Ruta FTP completa creada
    """
    global estadisticas
    ruta_relativa = os.path.relpath(origen_dir, carpeta_principal)
    carpetas = ruta_relativa.split(os.sep)
    ruta_actual_ftp = destino_ftp

    for carpeta in carpetas:
        if carpeta:
            ruta_actual_ftp = os.path.join(ruta_actual_ftp, carpeta).replace("\\", "/")
            try:
                ftp.cwd(ruta_actual_ftp)
                ftp.cwd("..")
            except:
                try:
                    ftp.mkd(ruta_actual_ftp)
                    crear_scb_log(ftp, "creó", carpeta, "carpeta")
                    print(f"📂 Carpeta creada: {ruta_actual_ftp}")
                    estadisticas.carpetas_creadas += 1
                except Exception as e:
                    print(f"❌ Error creando carpeta {ruta_actual_ftp}: {e}")
                    raise

    return ruta_actual_ftp

# ==============================================
# FUNCIONES PRINCIPALES DE OPERACIÓN
# ==============================================

def bajar_archivos():
    """
    Función principal para descargar archivos desde el servidor FTP.
    """
    global estadisticas
    estadisticas = Estadisticas()
    ftp = None  # Inicializar para el bloque finally
    
    try:
        # Buscar archivo de configuración
        ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
        if not ruta_config:
            print("❌ Archivo de configuración no encontrado")
            return

        # Obtener lista de archivos a ignorar
        directorio_base = os.path.dirname(ruta_config)
        ruta_opciones = os.path.join(directorio_base, ARCHIVO_OPTIONS)
        ignore_list = leer_ignore_list(ruta_opciones) if ruta_opciones else []

        # Conectar al servidor FTP
        config = leer_configuracion(ruta_config)
        ftp = conectar_ftp(config)
        if not ftp:
            print("❌ No se pudo conectar al servidor")
            return

        # Determinar ruta remota equivalente
        ruta_relativa = os.path.relpath(os.getcwd(), directorio_base)
        if ruta_relativa == ".":
            ruta_inicial_ftp = ftp.pwd()
        else:
            ruta_inicial_ftp = os.path.join(ftp.pwd(), ruta_relativa).replace('\\', '/')

        print(f"🔽 Iniciando descarga desde: {ruta_inicial_ftp}")
        
        try:
            ftp = descargar_archivos_recursivo(ftp, ruta_inicial_ftp, os.getcwd(), ignore_list)
        except KeyboardInterrupt:
            raise  # Propagamos para manejar en el nivel superior
            
        if ftp:
            print("✅ Descarga completada exitosamente")
        else:
            print("⚠️ Descarga completada con errores")

    except KeyboardInterrupt:
        print("\n🛑 Descarga cancelada por el usuario")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
    finally:
        estadisticas.mostrar()
        if ftp and hasattr(ftp, 'sock') and ftp.sock:
            try:
                ftp.quit()
            except:
                pass
            
def subir_archivos():
    """
    Función principal para subir archivos al servidor FTP.
    """
    global estadisticas
    estadisticas = Estadisticas()
    ftp = None  # Inicializar para el bloque finally
    
    try:
        print("\n🔼 Iniciando proceso de subida")

        # Buscar archivo de configuración
        ruta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
        if not ruta_config:
            print("❌ Archivo de configuración no encontrado")
            return

        # Obtener lista de archivos a ignorar
        directorio_base = os.path.dirname(ruta_config)
        ruta_opciones = os.path.join(directorio_base, ARCHIVO_OPTIONS)
        ignore_list = leer_ignore_list(ruta_opciones) if ruta_opciones else []

        # Conectar al servidor FTP
        config = leer_configuracion(ruta_config)
        ftp = conectar_ftp(config)
        if not ftp:
            print("❌ No se pudo conectar al servidor")
            return

        # Crear estructura de carpetas en FTP
        ruta_final_ftp = crear_estructura_carpetas_ftp(ftp, os.getcwd(), directorio_base)
        print(f"📂 Ruta destino: {ruta_final_ftp}")

        # Subir archivos
        try:
            subir_archivos_recursivo(ftp, os.getcwd(), ruta_final_ftp, ignore_list)
        except KeyboardInterrupt:
            print("\n🛑 Subida cancelada por el usuario")  # Mensaje único aquí
            return
            
        print("✅ Subida completada exitosamente")

    except KeyboardInterrupt:
        print("\n🛑 Subida cancelada por el usuario")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
    finally:
        estadisticas.mostrar()
        if ftp and hasattr(ftp, 'sock') and ftp.sock:
            try:
                ftp.quit()
            except:
                pass

def sincronizar_completo():
    """
    Realiza una sincronización bidireccional completa:
    1. Descarga archivos nuevos/modificados del servidor
    2. Sube archivos nuevos/modificados locales al servidor
    """
    global estadisticas
    estadisticas = Estadisticas()  # Resetear estadísticas
    try:
        print("\n🔄 Iniciando sincronización completa")
        
        # Fase 1: Descargar cambios del servidor
        print("\n🔽 Fase de descarga:")
        bajar_archivos()
        
        # Fase 2: Subir cambios locales
        print("\n🔼 Fase de subida:")
        subir_archivos()
        
        print("\n✅ Sincronización completada exitosamente")
        
    except KeyboardInterrupt:
        print("\n🛑 Sincronización interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ Error durante sincronización: {e}")
    finally:
        estadisticas.mostrar()

# ==============================================
# ENTRADA PRINCIPAL DEL PROGRAMA
# ==============================================

def main():
    """
    Punto de entrada principal del programa.
    """
    if len(sys.argv) != 2:
        print("\nUso: scbox [u|d|s]")
        print("  u: Subir archivos locales al servidor")
        print("  d: Descargar archivos del servidor")
        print("  s: Sincronización completa (descarga + subida)\n")
        sys.exit(1)

    operacion = sys.argv[1].lower()

    try:
        if operacion == "u":
            subir_archivos()
        elif operacion == "d":
            bajar_archivos()
        elif operacion == "s":
            sincronizar_completo()
        else:
            print(f"❌ Operación no válida: {operacion}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Operación cancelada por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Inicializar archivo de log si no existe
    if not os.path.exists('scb.log'):
        with open('scb.log', 'w', encoding='utf-8') as archivo:
            archivo.write(f"Log iniciado - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    main()