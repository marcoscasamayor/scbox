import ftplib
import os
import json
from ftplib import FTP
from datetime import datetime, timezone
import getpass
import fnmatch
import sys
import logging
from socket import timeout as SocketTimeout

# Configuración de constantes
ARCHIVO_CONFIG = 'scb.config'
ARCHIVO_OPTIONS = 'scb.options'
LOG_TEMPLATE = "Log generado el: {fecha}\nCarpeta: {carpeta}\n"
HISTORIAL_TEMPLATE = "{fecha} {hora} el usuario {usuario} {accion} {tipo} {descripcion}"
DESCARGAS_PERMITIDAS_RECONEXION = 50
MAX_REINTENTOS = 3
TIMEOUT_FTP = 60  # segundos

# Configuración básica del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scb.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def conectar_ftp(xConfig):
    """Establece conexión FTP con manejo robusto de errores"""
    try:
        xFtp = FTP(timeout=TIMEOUT_FTP)
        xFtp.connect(xConfig['FTP']['ftp_server'], timeout=TIMEOUT_FTP)
        xFtp.login(user=xConfig['FTP']['ftp_user'], passwd=xConfig['FTP']['ftp_password'])
        xFtp.set_pasv(True)  # Modo pasivo para mejor compatibilidad
        print("Conexión establecida correctamente   [scbox 25.04]")
        return xFtp
    except SocketTimeout:
        logging.error("Timeout al conectar al servidor FTP")
        raise
    except ftplib.all_errors as e:
        logging.error(f"Error de conexión: {e}")
        raise

def leer_configuracion(xRuta_config):
    """Lee y valida el archivo de configuración"""
    try:
        with open(xRuta_config, 'r') as file:
            xConfig = json.load(file)
            # Validar estructura básica
            if 'FTP' not in xConfig or not all(k in xConfig['FTP'] for k in ['ftp_server', 'ftp_user', 'ftp_password']):
                raise ValueError("Configuración incompleta")
            return xConfig
    except Exception as e:
        logging.error(f"Error al leer configuración: {e}")
        sys.exit(1)

def buscar_archivo_ancestro(xNombre_archivo, xDirectorio_actual):
    """Busca recursivamente hacia arriba en la jerarquía de directorios"""
    xDirectorio_actual = os.path.abspath(xDirectorio_actual)
    while True:
        xRuta_candidata = os.path.join(xDirectorio_actual, xNombre_archivo)
        if os.path.exists(xRuta_candidata):
            return xRuta_candidata
        xPadre = os.path.dirname(xDirectorio_actual)
        if xPadre == xDirectorio_actual:  # Llegamos a la raíz
            return None
        xDirectorio_actual = xPadre

def leer_ignore_list(xRuta_options):
    """Lee la lista de archivos a ignorar. Si el archivo no existe, lo crea con ejemplos y explicación detallada."""
    # Asegurarse de que el directorio padre exista
    xDirectorio_padre = os.path.dirname(xRuta_options)
    if xDirectorio_padre and not os.path.exists(xDirectorio_padre):
        os.makedirs(xDirectorio_padre, exist_ok=True)
    
    if not os.path.exists(xRuta_options):
        xOpciones = {
            "ignore_list": [
                "ejemplo213.txt"
            ],
            "_explicacion": {
                "formato": "Los patrones pueden usar comodines y distinguen entre archivos y carpetas:",
                "ejemplos": [
                    "'carpeta*' - Ignora TODAS las carpetas que empiecen con 'carpeta' y su contenido",
                    "'*.ext'    - Ignora todos los archivos que terminen con '.ext'",
                    "'nombre/'  - Ignora específicamente una carpeta (notar la barra al final)",
                    "'archivo'  - Ignora archivos con este nombre exacto (con o sin extensión)",
                    "'ruta/archivo.txt' - Ignora un archivo específico en una ruta específica"
                ],
            }
        }
        try:
            with open(xRuta_options, 'w', encoding='utf-8') as f:
                json.dump(xOpciones, f, indent=4, ensure_ascii=False)
            print(f"📄 Archivo de configuración creado: {xRuta_options}")
            print("   Por favor edítalo para configurar qué archivos/carpetas ignorar durante la sincronización.")
            return xOpciones['ignore_list']
        except Exception as e:
            print(f"❌ Error al crear {xRuta_options}: {e}")
            return []
    else:
        try:
            with open(xRuta_options, 'r', encoding='utf-8') as f:
                xData = json.load(f)
                # Validar que el archivo tenga el formato correcto
                if isinstance(xData, dict) and 'ignore_list' in xData:
                    return xData['ignore_list']
                else:
                    print(f"⚠️ El archivo {xRuta_options} no tiene el formato correcto. Se usará lista vacía.")
                    return []
        except json.JSONDecodeError:
            print(f"⚠️ El archivo {xRuta_options} está corrupto. Se usará lista vacía.")
            return []
        except Exception as e:
            print(f"❌ Error leyendo {xRuta_options}: {e}")
            return []
        

def crear_scb_log(xFtp, xAccion, xDescripcion, xTipo="archivo", xUsuario=None):
    """Registra acciones en el log local y remoto"""
    if xUsuario is None:
        xUsuario = getpass.getuser()
    
    xRegistro = HISTORIAL_TEMPLATE.format(
        fecha=datetime.now().strftime("%d-%m-%Y"),
        hora=datetime.now().strftime("%H:%M"),
        usuario=xUsuario,
        accion=xAccion,
        tipo=xTipo,
        descripcion=xDescripcion
    )
    
    try:
        # Escribir en log local
        with open('scb.log', 'a', encoding='utf-8') as f:
            f.write(xRegistro + '\n')
        
        # Sincronizar log remoto
        if xFtp:
            with open('scb.log', 'rb') as f:
                xFtp.storbinary('STOR scb.log', f)
    except Exception as e:
        logging.error(f"Error al escribir en log: {e}")

def obtener_timestamp_ftp(xFtp, xRuta_ftp):
    """Obtiene timestamp de archivo remoto (asume UTC)"""
    try:
        xRespuesta = xFtp.sendcmd(f"MDTM {xRuta_ftp}")
        xFecha_str = xRespuesta[4:].strip()
        xFecha_utc = datetime.strptime(xFecha_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return xFecha_utc.timestamp()
    except ftplib.error_perm as e:
        if "550" in str(e):
            return None  # Archivo no existe
        raise
    except Exception as e:
        logging.warning(f"Error obteniendo timestamp FTP: {e}")
        return None

def obtener_timestamp_local(xRuta_local):
    """Obtiene timestamp de archivo local convertido a UTC"""
    try:
        if not os.path.exists(xRuta_local):
            return None
        
        # Obtener timestamp local y convertirlo a UTC
        xTimestamp = os.path.getmtime(xRuta_local)
        xFecha_local = datetime.fromtimestamp(xTimestamp).astimezone()
        return xFecha_local.timestamp()
    except Exception as e:
        logging.warning(f"Error obteniendo timestamp local: {e}")
        return None

def necesita_sincronizacion(xTs_local, xTs_ftp, xTolerancia=2):
    """Determina si se necesita sincronización basado en timestamps UTC"""
    if xTs_local is None or xTs_ftp is None:
        return True
    return abs(xTs_local - xTs_ftp) > xTolerancia

def descargar_archivo(xFtp, xRuta_ftp, xRuta_local, xNombre_archivo, xContador):
    """Descarga un archivo individual con manejo robusto"""
    try:
        with open(xRuta_local, 'wb') as f:
            xFtp.retrbinary(f"RETR {xRuta_ftp}", f.write)
        
        # Actualizar timestamp local para coincidir con el remoto
        xTs_ftp = obtener_timestamp_ftp(xFtp, xRuta_ftp)
        if xTs_ftp:
            os.utime(xRuta_local, (xTs_ftp, xTs_ftp))
        
        crear_scb_log(xFtp, "descargó", xNombre_archivo)
        xContador[0] += 1
        
        # Reconectar después de cierto número de descargas
        if xContador[0] >= DESCARGAS_PERMITIDAS_RECONEXION:
            xFtp.quit()
            xConfig = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            xFtp = conectar_ftp(xConfig)
            xContador[0] = 0
        
        return xFtp
    except Exception as e:
        logging.error(f"Error al descargar {xRuta_ftp}: {e}")
        raise

def descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list, aContador=[0], xReintentos=0):
    """Descarga recursiva de archivos con manejo robusto de UTC"""
    if xReintentos > MAX_REINTENTOS:
        logging.error("Máximo de reintentos alcanzado")
        return None

    try:
        # Verificar conexión
        try:
            xFtp.voidcmd("NOOP")
        except:
            logging.warning("Reconectando FTP...")
            xConfig = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            xFtp = conectar_ftp(xConfig)
            aContador[0] = 0

        # Crear directorio local si no existe
        os.makedirs(xRuta_local, exist_ok=True)

        # Listar contenido remoto
        try:
            aElementos = xFtp.nlst(xRuta_ftp)
        except ftplib.error_perm as e:
            if "550" in str(e):  # No existe el directorio
                return xFtp
            raise

        for xElemento in aElementos:
            xRuta_f = os.path.join(xRuta_ftp, xElemento).replace('\\', '/')
            xRuta_l = os.path.join(xRuta_local, os.path.basename(xElemento))
            xNombre = os.path.basename(xRuta_f)

            # Filtrar elementos especiales y archivos ignorados
            if any(p in ['.', '..'] for p in xRuta_f.split('/')):
                continue
            if xNombre == 'scb.log' or any(fnmatch.fnmatch(xNombre, p) for p in xIgnore_list):
                continue

            try:
                # Probar si es directorio
                try:
                    xFtp.cwd(xRuta_f)
                    # Es un directorio, procesar recursivamente
                    if not os.path.exists(xRuta_l):
                        os.makedirs(xRuta_l)
                        crear_scb_log(xFtp, "creó", xNombre, "carpeta")
                    
                    xFtp = descargar_archivos_recursivo(xFtp, xRuta_f, xRuta_l, xIgnore_list, aContador)
                    xFtp.cwd('..')
                except ftplib.error_perm:
                    # No es directorio, procesar como archivo
                    xTs_ftp = obtener_timestamp_ftp(xFtp, xRuta_f)
                    xTs_local = obtener_timestamp_local(xRuta_l)

                    if necesita_sincronizacion(xTs_local, xTs_ftp):
                        print(f"🔽 Descargando: {xRuta_f}")
                        xFtp = descargar_archivo(xFtp, xRuta_f, xRuta_l, xNombre, aContador)

            except Exception as e:
                logging.warning(f"Error procesando {xRuta_f}: {e}")
                continue

        return xFtp

    except Exception as e:
        logging.error(f"Error en descarga recursiva: {e}")
        if xReintentos < MAX_REINTENTOS:
            logging.info(f"Reintentando ({xReintentos+1}/{MAX_REINTENTOS})...")
            xConfig = leer_configuracion(buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd()))
            xFtp = conectar_ftp(xConfig)
            return descargar_archivos_recursivo(xFtp, xRuta_ftp, xRuta_local, xIgnore_list, aContador, xReintentos+1)
        return None

def subir_archivo(xFtp, xRuta_local, xRuta_ftp, xNombre_archivo):
    """Sube un archivo individual con manejo robusto"""
    try:
        with open(xRuta_local, 'rb') as f:
            xFtp.storbinary(f'STOR {xRuta_ftp}', f)
        
        # Sincronizar timestamp remoto
        xTs_local = obtener_timestamp_local(xRuta_local)
        if xTs_local:
            xFecha_mod = datetime.fromtimestamp(xTs_local, timezone.utc)
            xFtp.sendcmd(f"MFMT {xFecha_mod.strftime('%Y%m%d%H%M%S')} {xRuta_ftp}")
        
        crear_scb_log(xFtp, "subió", xNombre_archivo)
        return True
    except Exception as e:
        logging.error(f"Error al subir {xRuta_ftp}: {e}")
        return False

def subir_archivos_recursivo(xFtp, xRuta_local, xRuta_ftp, xIgnore_list):
    """Sube archivos recursivamente al servidor FTP"""
    try:
        for xNombre in os.listdir(xRuta_local):
            xRuta_l = os.path.join(xRuta_local, xNombre)
            xRuta_f = os.path.join(xRuta_ftp, xNombre).replace('\\', '/')

            # Verificar si el archivo debe ser ignorado
            if any(fnmatch.fnmatch(xNombre, xPatron) for xPatron in xIgnore_list):
                continue

            if os.path.isfile(xRuta_l):
                xTs_local = obtener_timestamp_local(xRuta_l)
                xTs_ftp = obtener_timestamp_ftp(xFtp, xRuta_f)

                if necesita_sincronizacion(xTs_local, xTs_ftp):
                    print(f"🔼 Subiendo: {xRuta_f}")
                    if not subir_archivo(xFtp, xRuta_l, xRuta_f, xNombre):
                        continue

            elif os.path.isdir(xRuta_l):
                try:
                    xFtp.cwd(xRuta_f)
                except:
                    try:
                        xFtp.mkd(xRuta_f)
                        logging.info(f"📂 Carpeta creada: {xRuta_f}")
                        crear_scb_log(xFtp, "creó", xNombre, "carpeta")
                    except Exception as e:
                        logging.error(f"Error creando carpeta {xRuta_f}: {e}")
                        continue

                subir_archivos_recursivo(xFtp, xRuta_l, xRuta_f, xIgnore_list)
                xFtp.cwd('..')

    except Exception as e:
        logging.error(f"Error en subida recursiva: {e}")
        raise

def bajar_archivos():
    """Función principal para descargar archivos"""
    try:
        # Buscar configuración
        xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
        if not xRuta_config:
            logging.error("Archivo de configuración no encontrado")
            return

        # Obtener lista de ignorados
        xDirectorio_base = os.path.dirname(xRuta_config)
        xRuta_opciones = xRuta_opciones = os.path.join(xDirectorio_base, ARCHIVO_OPTIONS)
        xIgnore_list = leer_ignore_list(xRuta_opciones) if xRuta_opciones else []

        # Conectar al FTP
        xConfig = leer_configuracion(xRuta_config)
        xFtp = conectar_ftp(xConfig)
        if not xFtp:
            logging.error("No se pudo conectar al servidor")
            return

        # Determinar ruta remota equivalente
        xRuta_relativa = os.path.relpath(os.getcwd(), xDirectorio_base)
        if xRuta_relativa == ".":
            xRuta_inicial_ftp = xFtp.pwd()
        else:
            xRuta_inicial_ftp = os.path.join(xFtp.pwd(), xRuta_relativa).replace('\\', '/')

        print(f"Iniciando proceso de descarga desde: {xRuta_inicial_ftp}")
        xFtp = descargar_archivos_recursivo(xFtp, xRuta_inicial_ftp, os.getcwd(), xIgnore_list)
        
        if xFtp:
            print("✅ Descarga completada exitosamente")
        else:
            logging.warning("⚠️ Descarga completada con errores")

    except KeyboardInterrupt:
        print("\n 🛑 Descarga cancelada por el usuario")
    except Exception as e:
        logging.error(f"❌ Error fatal: {e}")
    finally:
        if 'xFtp' in locals() and xFtp.sock:
            try:
                xFtp.quit()
            except:
                pass

def subir_archivos():
    """Función principal para subir archivos"""
    try:
        print("\nIniciando proceso de subida")

        # Buscar configuración
        xRuta_config = buscar_archivo_ancestro(ARCHIVO_CONFIG, os.getcwd())
        if not xRuta_config:
            logging.error("❌ Archivo de configuración no encontrado")
            return

        # Obtener lista de ignorados
        xDirectorio_base = os.path.dirname(xRuta_config)
        xRuta_opciones = xRuta_opciones = os.path.join(xDirectorio_base, ARCHIVO_OPTIONS)
        xIgnore_list = leer_ignore_list(xRuta_opciones) if xRuta_opciones else []

        # Conectar al FTP
        xConfig = leer_configuracion(xRuta_config)
        xFtp = conectar_ftp(xConfig)
        if not xFtp:
            logging.error("❌ No se pudo conectar al servidor")
            return

        # Crear estructura de carpetas en FTP
        xRuta_final_ftp = crear_estructura_carpetas_ftp(xFtp, os.getcwd(), xDirectorio_base)
        print(f"📂 Ruta destino: {xRuta_final_ftp}")

        # Subir archivos
        subir_archivos_recursivo(xFtp, os.getcwd(), xRuta_final_ftp, xIgnore_list)
        print("✅ Subida completada exitosamente")

    except KeyboardInterrupt:
        print("\n🛑 Subida cancelada por el usuario")
    except Exception as e:
        logging.error(f"❌ Error fatal: {e}")
    finally:
        if 'xFtp' in locals() and xFtp.sock:
            try:
                xFtp.quit()
            except:
                pass

def crear_estructura_carpetas_ftp(xFtp, xOrigen_dir, xCarpeta_principal, xDestino_ftp='/'):
    """Crea la estructura de carpetas en el servidor FTP"""
    xRuta_relativa = os.path.relpath(xOrigen_dir, xCarpeta_principal)
    aCarpetas = xRuta_relativa.split(os.sep)
    xRuta_actual_ftp = xDestino_ftp

    for xCarpeta in aCarpetas:
        if xCarpeta:
            xRuta_actual_ftp = os.path.join(xRuta_actual_ftp, xCarpeta).replace("\\", "/")
            try:
                xFtp.cwd(xRuta_actual_ftp)
                xFtp.cwd("..")
            except:
                try:
                    xFtp.mkd(xRuta_actual_ftp)
                    crear_scb_log(xFtp, "creó", xCarpeta, "carpeta")
                    logging.info(f"📂 Carpeta creada: {xRuta_actual_ftp}")
                except Exception as e:
                    logging.error(f"Error creando carpeta {xRuta_actual_ftp}: {e}")
                    raise

    return xRuta_actual_ftp

def sincronizar_completo():
    """Sincronización bidireccional completa"""
    bajar_archivos()
    subir_archivos()

def main():
    """Función principal"""
    if len(sys.argv) != 2:
        print("Uso: scbox [u|d|s]")
        print("  u: Subir archivos")
        print("  d: Descargar archivos")
        print("  s: Sincronización completa")
        sys.exit(1)

    xOperacion = sys.argv[1].lower()

    try:
        if xOperacion == "u":
            subir_archivos()
        elif xOperacion == "d":
            bajar_archivos()
        elif xOperacion == "s":
            sincronizar_completo()
        else:
            print(f"❌ Operación no válida: {xOperacion}")
            sys.exit(1)
    except KeyboardInterrupt:
        logging.info("\n🛑 Operación cancelada por el usuario")
        sys.exit(0)
    except Exception as e:
        logging.error(f" ❌Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Inicializar archivo de log si no existe
    if not os.path.exists('scb.log'):
        with open('scb.log', 'w', encoding='utf-8') as f:
            f.write(f"Log iniciado - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    main()