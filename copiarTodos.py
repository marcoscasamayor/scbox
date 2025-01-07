import shutil
import os

origen_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosOrigen'
destino_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosDestino'

# Verificar si los directorios existen
if not os.path.exists(origen_dir):
    print(f"El directorio de origen no existe: {origen_dir}")
elif not os.path.exists(destino_dir):
    print(f"El directorio de destino no existe: {destino_dir}")
else:
    # Obtener archivos del directorio de origen
    archivos = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]

    if not archivos:
        print("No se encontraron archivos en el directorio de origen.")
    else:
        print("Elija una opción:")
        print("1. Copiar archivos al directorio de destino.")
        print("2. Borrar archivos del directorio de destino.")
        
        opcion = input("Ingrese el número de la opción que desea: ").strip()
        
        if opcion == '1':
            print("Copiando archivos desde el directorio de origen al destino...")
            for archivo in archivos:
                src = os.path.join(origen_dir, archivo)
                dst = os.path.join(destino_dir, archivo)
                
                if os.path.exists(dst):
                    print(f"El archivo ya existe en el destino: {archivo}")
                else:
                    try:
                        shutil.copy2(src, dst)  # Copiar archivo con metadatos
                        print(f"Archivo copiado con éxito: {archivo}")
                    except Exception as e:
                        print(f"Ocurrió un error al copiar {archivo}: {e}")
        
        elif opcion == '2':
            print("Borrando archivos del directorio de destino...")
            for archivo in archivos:
                src = os.path.join(origen_dir, archivo)
                dst = os.path.join(destino_dir, archivo)
                try:
                    os.remove(dst)  # Borrar archivo del destino
                    print(f"Archivo eliminado del destino: {archivo}")  # Corregido: Se cierra el f-string correctamente.
                except Exception as e:
                    print(f"Ocurrió un error al eliminar {archivo} del destino: {e}")

        
                else:
                    print("Opción no válida.")
        
                    print("Proceso completado.")
