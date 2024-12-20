import os
import time
import psutil
import subprocess
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import platform


# Détection du système d'exploitation
if platform.system() == 'Windows':
    CONFIG = {
    "MINECRAFT_SAVES_PATH": os.path.join(os.getenv("APPDATA"), ".minecraft", "saves"),
    "MINECRAFT_LAUNCHER_PATH": r"C:\\Program Files (x86)\\Minecraft Launcher\\MinecraftLauncher.exe",
}
elif platform.system() == 'Linux':
    CONFIG = {
    "MINECRAFT_SAVES_PATH": os.path.expanduser("~/.minecraft/saves"),
    "MINECRAFT_LAUNCHER_PATH": "/usr/bin/minecraft-launcher",
}
    
else:
    print("Erreur : système d'exploitation non supporté.")
    exit(1)

CLOUD_SYNC_PATH = "MinecraftBackups"


def authenticate_drive():
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    return drive


def sync_to_cloud(drive):
    print("Synchronisation des sauvegardes vers le cloud...")
    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)

    # Parcourir les dossiers de mondes dans le répertoire de sauvegarde
    for world_name in os.listdir(CONFIG["MINECRAFT_SAVES_PATH"]):
        world_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], world_name)

        if os.path.isdir(world_path):  # Vérifier que c'est un dossier (un monde)
            print(f"Traitement du monde : {world_name}")
            world_folder_id = create_or_get_folder(drive, world_name, parent_id=root_folder_id)

            for root, dirs, files in os.walk(world_path):
                for file_name in files:
                    local_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(local_path, world_path)

                    query = f"title='{relative_path}' and '{world_folder_id}' in parents"
                    file_list = drive.ListFile({'q': query}).GetList()
                    
                    upload_file(drive, local_path, world_folder_id, relative_path)
    print("Synchronisation vers le cloud terminée.")


def create_or_get_folder(drive, folder_name, parent_id=None):
    query = f"mimeType='application/vnd.google-apps.folder' and title='{folder_name}'"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    folder_list = drive.ListFile({'q': query}).GetList()
    if folder_list:
        folder_id = folder_list[0]['id']
    else:
        metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id:
            metadata['parents'] = [{'id': parent_id}]
        folder = drive.CreateFile(metadata)
        folder.Upload()
        folder_id = folder['id']
    return folder_id



def sync_from_cloud(drive):
    print("Téléchargement des sauvegardes depuis le cloud...")
    folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)
    file_list = drive.ListFile({'q': f"'{folder_id}' in parents"}).GetList()

    for file in file_list:
        local_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], file['title'])
        if not os.path.exists(local_path):
            file.GetContentFile(local_path)
            print(f"Téléchargé : {file['title']}")
    print("Téléchargement terminé.")


def upload_file(drive, local_path, folder_id, relative_path):
    query = f"title='{relative_path}' and '{folder_id}' in parents"
    file_list = drive.ListFile({'q': query}).GetList()

    if file_list:
        # Comparer les dates de modification
        cloud_file = file_list[0]
        local_mtime = os.path.getmtime(local_path)
        cloud_mtime = time.mktime(time.strptime(cloud_file['modifiedDate'], "%Y-%m-%dT%H:%M:%S.%fZ"))

        if local_mtime <= cloud_mtime:
            print(f"Le fichier est déjà à jour : {relative_path}")
            return
        else:
            print(f"Le fichier a été modifié localement : {relative_path}")
            # Supprimer le fichier existant pour éviter les conflits
            cloud_file.Delete()

    # Téléverser le fichier local
    file = drive.CreateFile({
        'title': relative_path,
        'parents': [{'id': folder_id}]
    })
    file.SetContentFile(local_path)
    file.Upload()
    print(f"Téléversé : {relative_path}")



def monitor_minecraft():
    """Monitor if Minecraft is running."""
    process_found = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.is_running():
            try:
                if "java" in proc.info['name'].lower() and "minecraft" in " ".join(proc.info['cmdline']).lower():
                    process_found = True
                    break
            except psutil.NoSuchProcess:
                continue

    if process_found:
        print("Minecraft est en cours d'exécution.")
    else:
        print("Minecraft n'est pas en cours d'exécution.")
        start_minecraft_launcher()


def start_minecraft_launcher():
    """Launch Minecraft Launcher if it's not running."""
    if os.path.exists(CONFIG["MINECRAFT_LAUNCHER_PATH"]):
        print("Démarrage du Minecraft Launcher...")
        subprocess.Popen([CONFIG["MINECRAFT_LAUNCHER_PATH"]], shell=True)
    else:
        print(f"Erreur : Impossible de trouver le Minecraft Launcher à l'emplacement spécifié : {CONFIG['MINECRAFT_LAUNCHER_PATH']}")


def wait_for_minecraft_to_start():
    """Wait for Minecraft to start running."""
    print("En attente de Minecraft...")
    while True:
        process_found = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.is_running():
                try:
                    if "java" in proc.info['name'].lower() and "minecraft" in " ".join(proc.info['cmdline']).lower():
                        process_found = True
                        break
                except psutil.NoSuchProcess:
                    continue

        if process_found:
            print("Minecraft est maintenant lancé.")
            break
        time.sleep(5)  # Vérifier toutes les 5 secondes


if __name__ == "__main__":
    if not os.path.exists(CONFIG["MINECRAFT_SAVES_PATH"]):
        print(f"Erreur : le dossier {CONFIG['MINECRAFT_SAVES_PATH']} n'existe pas.")
        exit(1)

    monitor_minecraft()

    # Attendre que Minecraft soit lancé
    wait_for_minecraft_to_start()

    # Authentification avec Google Drive
    print("Authentification Google Drive...")
    drive = authenticate_drive()

    # Synchronisation des sauvegardes vers le cloud
    sync_to_cloud(drive)
