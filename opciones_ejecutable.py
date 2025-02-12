import subprocess
import os

def buscar_y_ejecutar_archivo():
    # Rutas en las que buscar los archivos (puedes agregar más directorios si lo deseas)
    rutas_posibles = [
        os.getcwd(),  # Directorio desde el cual se ejecuta el script
        os.path.expanduser("~"),  # Directorio del usuario, en Windows sería algo como C:\Users\TuUsuario
        os.path.expanduser("~\\Documents"),  # Documento del usuario en Windows
        os.path.expanduser("~\\Downloads"),  # Descargas del usuario en Windows
        "C:/",  
        ]

    # Nombres de los archivos que estamos buscando
    archivos_a_buscar = ["upload_archivos.py", "download_archivos.py"]

    # Lista de archivos encontrados
    archivos_encontrados = []

    # Buscar los archivos en las rutas posibles
    for ruta in rutas_posibles:
        print(f"Buscando en: {ruta}")
        for root, dirs, files in os.walk(ruta):  # Recorre todas las subcarpetas
            for archivo in archivos_a_buscar:
                if archivo in files:
                    archivos_encontrados.append(os.path.join(root, archivo))

    # Verificar si se encontraron archivos
    if not archivos_encontrados:
        print("No se encontraron los archivos 'upload_archivos.py' ni 'download_archivos.py' en las rutas especificadas.")
        return

    # Mostrar los archivos encontrados
    print("Archivos encontrados:")
    for i, archivo in enumerate(archivos_encontrados, start=1):
        print(f"{i}: {archivo}")

    # Solicitar al usuario que elija qué archivo ejecutar
    try:
        opcion = int(input("Introduce el número del archivo que deseas ejecutar: "))
        if opcion < 1 or opcion > len(archivos_encontrados):
            print("Opción inválida.")
            return

        archivo_elegido = archivos_encontrados[opcion - 1]
        
        # Ejecutar el archivo seleccionado
        try:
            subprocess.run(["python", archivo_elegido], check=True)
            print(f"Ejecutando {archivo_elegido}")
        except Exception as e:
            print(f"Error al ejecutar el archivo: {e}")
    except ValueError:
        print("Por favor, ingresa un número válido.")

if __name__ == "__main__":
    buscar_y_ejecutar_archivo()
