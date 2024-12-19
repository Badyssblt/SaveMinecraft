import os
import time
import psutil
import subprocess  # Ajout de subprocess pour lancer des applications externes
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

MINECRAFT_SAVES_PATH = os.path.join(os.getenv("APPDATA"), ".minecraft", "saves")
CLOUD_SYNC_PATH = "MinecraftBackups"
MINECRAFT_LAUNCHER_PATH = r"C:\Program Files (x86)\Minecraft Launcher\MinecraftLauncher.exe"

def authenticate_drive():
    """Authenticate with Google Drive using PyDrive."""
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    return drive

def sync_to_cloud(drive):
    """Sync Minecraft saves to Google Drive cloud."""
    print("Synchronisation des sauvegardes vers le cloud...")
    folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)

    for root, dirs, files in os.walk(MINECRAFT_SAVES_PATH):
        for file_name in files:
            local_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(local_path, MINECRAFT_SAVES_PATH)

            query = f"title='{relative_path}' and '{folder_id}' in parents"
            file_list = drive.ListFile({'q': query}).GetList()

            if file_list:
                print(f"Fichier déjà synchronisé : {relative_path}")
            else:
                upload_file(drive, local_path, folder_id, relative_path)
    print("Synchronisation vers le cloud terminée.")

def sync_from_cloud(drive):
    """Download Minecraft saves from Google Drive cloud."""
    print("Téléchargement des sauvegardes depuis le cloud...")
    folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)
    file_list = drive.ListFile({'q': f"'{folder_id}' in parents"}).GetList()

    for file in file_list:
        local_path = os.path.join(MINECRAFT_SAVES_PATH, file['title'])
        if not os.path.exists(local_path):
            file.GetContentFile(local_path)
            print(f"Téléchargé : {file['title']}")
    print("Téléchargement terminé.")

def create_or_get_folder(drive, folder_name):
    """Create or get the folder ID from Google Drive."""
    folder_list = drive.ListFile({'q': f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder'"}).GetList()
    if folder_list:
        folder_id = folder_list[0]['id']
    else:
        folder = drive.CreateFile({'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'})
        folder.Upload()
        folder_id = folder['id']
    return folder_id

def upload_file(drive, local_path, folder_id, relative_path):
    """Upload a file to Google Drive."""
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
    if os.path.exists(MINECRAFT_LAUNCHER_PATH):
        print("Démarrage du Minecraft Launcher...")
        subprocess.Popen([MINECRAFT_LAUNCHER_PATH], shell=True)
    else:
        print(f"Erreur : Impossible de trouver le Minecraft Launcher à l'emplacement spécifié : {MINECRAFT_LAUNCHER_PATH}")

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
    if not os.path.exists(MINECRAFT_SAVES_PATH):
        print(f"Erreur : le dossier {MINECRAFT_SAVES_PATH} n'existe pas.")
        exit(1)
    
    monitor_minecraft()
    
    # Attendre que Minecraft soit lancé
    wait_for_minecraft_to_start()
    
    # Authentification avec Google Drive
    print("Authentification Google Drive...")
    drive = authenticate_drive()
    
    # Synchronisation des sauvegardes vers le cloud
    sync_to_cloud(drive)
