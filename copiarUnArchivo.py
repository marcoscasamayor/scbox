import shutil
import os


origen_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosOrigen'
destino_dir = r'C:\Users\SC3 Sistemas\Desktop\Ruben\ArchivosDestino'


if not os.path.exists(origen_dir):
    print(f"El directorio de origen no existe: {origen_dir}")
elif not os.path.exists(destino_dir):
    print(f"El directorio de destino no existe: {destino_dir}")
else:
    # Lista los archivos que hay en origen
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
                dst = os.path.join(destino_dir, archivo_seleccionado)

             
                if os.path.exists(dst):
                    print(f"El archivo ya existe en el destino: {dst}")
                else:
                    shutil.copy2(src, dst)  # Copiar archivo con metadatos
                    print(f"Archivo copiado con éxito: {src} -> {dst}")
        except ValueError:
            print("Debe ingresar un número válido.")
