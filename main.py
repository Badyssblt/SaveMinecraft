import os
import time
import psutil
import subprocess
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import platform
import shutil
import json
import sys

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

drive = None


def log_status(step, status):
    message = json.dumps({"step": step, "status": status})
    print(message)
    sys.stdout.flush()

def authenticate_drive():
    global drive
    gauth = GoogleAuth()
    gauth.settings["host"] = "localhost:9090"
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    return drive


def sync_to_cloud():
    """Sauvegarde des mondes locaux vers le cloud."""
    global drive
    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)
    clear_folder(root_folder_id)

    for world_name in os.listdir(CONFIG["MINECRAFT_SAVES_PATH"]):
        world_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], world_name)
        if os.path.isdir(world_path):
            zip_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], f"{world_name}.zip")
            shutil.make_archive(zip_file_path.replace('.zip', ''), 'zip', world_path)

            world_folder_id = create_or_get_folder(drive, world_name, parent_id=root_folder_id)
            upload_file(drive, zip_file_path, root_folder_id, f"{world_name}.zip")
            os.remove(zip_file_path)


def clear_folder(folder_id):
    global drive

    query = f"'{folder_id}' in parents and trashed = false"

    file_list = drive.ListFile({'q': query}).GetList()

    for file in file_list:
        try:
            file.Delete()
        except Exception as e:
            print(f"Erreur lors de la suppression de {file['title']} : {e}")



def sync_and_restore_from_cloud():
    """Télécharge et restaure les mondes Minecraft depuis Google Drive."""


    if os.listdir(CONFIG["MINECRAFT_SAVES_PATH"]) == 0:
        return False

    global drive
    backup_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], "../backupsSave")
    backup_path = os.path.abspath(backup_path)  # Résolution du chemin absolu
    os.makedirs(backup_path, exist_ok=True)




    # Vider backupsSave
    for root, dirs, files in os.walk(backup_path, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            os.rmdir(dir_path)

    # Déplacer les mondes existants vers backupsSave
    for world_name in os.listdir(CONFIG["MINECRAFT_SAVES_PATH"]):
        world_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], world_name)
        backup_world_path = os.path.join(backup_path, world_name)

        if os.path.isdir(world_path):
            shutil.move(world_path, backup_world_path)

    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)

    for file in drive.ListFile({'q': f"'{root_folder_id}' in parents"}).GetList():
        if file['title'].endswith('.zip'):
            local_zip_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], file['title'])
            file.GetContentFile(local_zip_path)

            extracted_folder_path = local_zip_path.replace('.zip', '')
            shutil.unpack_archive(local_zip_path, extracted_folder_path)

            os.remove(local_zip_path)







def sync_from_cloud():
    """Téléchargement des mondes depuis le cloud après suppression du contenu local."""
    global drive
    
    # Supprimer tout le contenu du dossier des sauvegardes
    for root, dirs, files in os.walk(CONFIG["MINECRAFT_SAVES_PATH"], topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            os.rmdir(dir_path)

    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)

    for world_folder in drive.ListFile({'q': f"'{root_folder_id}' in parents"}).GetList():
        local_world_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], world_folder['title'])
        os.makedirs(local_world_path, exist_ok=True)

        for file in drive.ListFile({'q': f"'{world_folder['id']}' in parents"}).GetList():
            local_file_path = os.path.join(local_world_path, file['title'])
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            file.GetContentFile(local_file_path)
            print(f"Téléchargé : {file['title']} dans {world_folder['title']}")




def upload_file(drive, local_path, folder_id, relative_path):
    """Téléversement d'un fichier vers Google Drive."""
    file = drive.CreateFile({'title': relative_path, 'parents': [{'id': folder_id}]})
    file.SetContentFile(local_path)
    file.Upload()


def create_or_get_folder(drive, folder_name, parent_id=None):
    """Créer ou obtenir un dossier sur Google Drive."""
    query = f"mimeType='application/vnd.google-apps.folder' and title='{folder_name}'"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    folder_list = drive.ListFile({'q': query}).GetList()
    if folder_list:
        return folder_list[0]['id']

    folder_metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        folder_metadata['parents'] = [{'id': parent_id}]

    folder = drive.CreateFile(folder_metadata)
    folder.Upload()
    return folder['id']


def start_minecraft_launcher():
    """Lancer le Minecraft Launcher."""
    if os.path.exists(CONFIG["MINECRAFT_LAUNCHER_PATH"]):
        subprocess.Popen([CONFIG["MINECRAFT_LAUNCHER_PATH"]], shell=True)
        time.sleep(10)
    else:
        print(f"Erreur : Impossible de trouver le Minecraft Launcher : {CONFIG['MINECRAFT_LAUNCHER_PATH']}")


def wait_for_minecraft_to_exit():
    """Surveiller si Minecraft et son launcher sont fermés."""
    while True:
        minecraft_running = any(
            ("java" in proc.info['name'].lower() and "minecraft" in " ".join(proc.info['cmdline']).lower()) or
            ("minecraft" in proc.info['name'].lower() and "launcher" in " ".join(proc.info['cmdline']).lower())
            for proc in psutil.process_iter(['name', 'cmdline'])
            if proc.is_running()
        )
        if not minecraft_running:
            break
        time.sleep(5)


if __name__ == "__main__":
    if not os.path.exists(CONFIG["MINECRAFT_SAVES_PATH"]):
        exit(1)

    log_status("auth", "Authentification Google Drive...")
    drive = authenticate_drive()

    log_status("auth", 'Authentification réussi, chargement des mondes...')
    sync_and_restore_from_cloud()

    log_status("minecraft", "Chargement des mondes terminés, lancement de Minecraft")

    start_minecraft_launcher()

    wait_for_minecraft_to_exit()

    log_status("minecraft", "Minecraft fermé, Upload des mondes sur le cloud...")

    sync_to_cloud()

    log_status("minecraft", 'Upload des mondes terminée')

