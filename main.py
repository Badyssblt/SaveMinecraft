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
import argparse
import uuid


parser = argparse.ArgumentParser(description="Minecraft backup and sync script.")
parser.add_argument('-type', choices=['vanilla', 'curseforge'], default='vanilla',
                    help="Type of Minecraft launcher (vanilla or curseforge). Default is vanilla.")
args = parser.parse_args()

MACHINE_ID = str(uuid.getnode())
MACHINE_ID_FILE = "machine_id.json"

# Détection du système d'exploitation
if platform.system() == 'Windows':
    if args.type == 'vanilla':
        CONFIG = {
            "MINECRAFT_SAVES_PATH": os.path.join(os.getenv("APPDATA"), ".minecraft", "saves"),
            "MINECRAFT_LAUNCHER_PATH": r"C:\\Program Files (x86)\\Minecraft Launcher\\MinecraftLauncher.exe",
        }
    elif args.type == 'curseforge':
        CONFIG = {
            "MINECRAFT_SAVES_PATH": os.path.join(os.getenv("APPDATA"), "CurseForge", "minecraft", "Instances"),
            "MINECRAFT_LAUNCHER_PATH": r"C:\\Program Files (x86)\\Overwolf\\OverwolfLauncher.exe",
        }
elif platform.system() == 'Linux':
    if args.type == 'vanilla':
        CONFIG = {
            "MINECRAFT_SAVES_PATH": os.path.expanduser("~/.minecraft/saves"),
            "MINECRAFT_LAUNCHER_PATH": "/usr/bin/minecraft-launcher",
        }
    elif args.type == 'curseforge':
        CONFIG = {
            "MINECRAFT_SAVES_PATH": os.path.expanduser("~/Documents/curseforge/minecraft/Instances"),
            "MINECRAFT_LAUNCHER_PATH": "/usr/bin/overwolf",
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

    # ATTENTION ! Décommenter lors du build de l'app
    # GoogleAuth.DEFAULT_SETTINGS['client_config_file'] = '/home/badyss/Documents/DevWeb/SaveMinecraft/app/build/linux-unpacked/resources/client_secrets.json'
    gauth = GoogleAuth()

    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    return drive


def sync_to_cloud():
    """Sauvegarde des mondes locaux vers le cloud."""
    global drive

    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)
    # Création des dossiers Vanilla et Modded sur Google Drive
    vanilla_folder_id = create_or_get_folder(drive, 'Vanilla', root_folder_id)
    modded_folder_id = create_or_get_folder(drive, 'Modded', root_folder_id)

    if(args.type == "curseforge"):
        modded_saves_empty = all(len(os.listdir(os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], instance_name, 'saves'))) == 0 
                                    for instance_name in os.listdir(CONFIG["MINECRAFT_SAVES_PATH"])
                                    if os.path.isdir(os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], instance_name)))
        if not modded_saves_empty:
            clear_folder(modded_folder_id)

    if(args.type == "vanilla"):
        vanilla_saves_empty = len(os.listdir(CONFIG["MINECRAFT_SAVES_PATH"])) == 0
        if not vanilla_saves_empty:
            clear_folder(vanilla_folder_id)

    
    # Si nous sommes en mode CurseForge, parcourir les instances (modded)
    if args.type == 'curseforge':
        for instance_name in os.listdir(CONFIG["MINECRAFT_SAVES_PATH"]):
            instance_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], instance_name)
            saves_path = os.path.join(instance_path, 'saves')  # Le chemin vers le dossier saves de chaque modpack

            if os.path.isdir(saves_path):
                modpack_folder_id = create_or_get_folder(drive, instance_name, parent_id=modded_folder_id)

                for world_name in os.listdir(saves_path):
                    world_path = os.path.join(saves_path, world_name)
                    if os.path.isdir(world_path):
                        zip_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], f"{instance_name}_{world_name}.zip")
                        shutil.make_archive(zip_file_path.replace('.zip', ''), 'zip', world_path)

                        # Télécharger les mondes compressés dans le dossier du modpack
                        upload_file(drive, zip_file_path, modpack_folder_id, f"{world_name}.zip")
                        os.remove(zip_file_path)

    else:  # Vanilla
        for world_name in os.listdir(CONFIG["MINECRAFT_SAVES_PATH"]):
            world_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], world_name)
            if os.path.isdir(world_path):
                zip_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], f"{world_name}.zip")
                shutil.make_archive(zip_file_path.replace('.zip', ''), 'zip', world_path)

                # Télécharger les mondes Vanilla dans le dossier Vanilla
                upload_file(drive, zip_file_path, vanilla_folder_id, f"{world_name}.zip")
                os.remove(zip_file_path)


def sync_and_restore_from_cloud():
    """Télécharge et restaure les mondes Minecraft depuis Google Drive, avec des vérifications de sécurité."""
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
    if args.type == 'vanilla':
        vanilla_saves = os.listdir(CONFIG["MINECRAFT_SAVES_PATH"])
        if not vanilla_saves:
            print("Aucun monde Vanilla local à sauvegarder.")
        else:
            for world_name in vanilla_saves:
                world_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], world_name)
                backup_world_path = os.path.join(backup_path, world_name)

                if os.path.isdir(world_path):
                    shutil.move(world_path, backup_world_path)

    elif args.type == 'curseforge':
        modpacks = os.listdir(CONFIG["MINECRAFT_SAVES_PATH"])
        if not modpacks:
            print("Aucun modpack CurseForge local trouvé.")
        else:
            for modpack_name in modpacks:
                modpack_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], modpack_name)
                saves_path = os.path.join(modpack_path, "saves")
                if os.path.isdir(saves_path):
                    modpack_saves = os.listdir(saves_path)
                    if not modpack_saves:
                        print(f"Aucune sauvegarde trouvée dans le modpack {modpack_name}.")
                    else:
                        backup_modpack_path = os.path.join(backup_path, modpack_name, "saves")
                        os.makedirs(backup_modpack_path, exist_ok=True)

                        for save_name in modpack_saves:
                            save_path = os.path.join(saves_path, save_name)
                            backup_save_path = os.path.join(backup_modpack_path, save_name)

                            shutil.move(save_path, backup_save_path)

    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)

    vanilla_folder_id = create_or_get_folder(drive, 'Vanilla', parent_id=root_folder_id)
    modded_folder_id = create_or_get_folder(drive, 'Modded', parent_id=root_folder_id)

    # Restaurer les mondes Vanilla
    if args.type == 'vanilla':
        cloud_vanilla_files = drive.ListFile({'q': f"'{vanilla_folder_id}' in parents"}).GetList()
        if not cloud_vanilla_files:
            print("Aucune sauvegarde Vanilla trouvée sur le cloud.")
        else:
            for file in cloud_vanilla_files:
                if file['title'].endswith('.zip'):
                    local_zip_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], file['title'])
                    file.GetContentFile(local_zip_path)

                    extracted_folder_path = local_zip_path.replace('.zip', '')
                    shutil.unpack_archive(local_zip_path, extracted_folder_path)

                    os.remove(local_zip_path)

    # Restaurer les mondes moddés (CurseForge)
    elif args.type == 'curseforge':
        cloud_modpacks = drive.ListFile({'q': f"'{modded_folder_id}' in parents"}).GetList()
        if not cloud_modpacks:
            print("Aucun modpack trouvé sur le cloud.")
        else:
            for modpack_folder in cloud_modpacks:
                modpack_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], modpack_folder['title'])
                saves_path = os.path.join(modpack_path, 'saves')
                os.makedirs(saves_path, exist_ok=True)

                cloud_saves = drive.ListFile({'q': f"'{modpack_folder['id']}' in parents"}).GetList()
                if not cloud_saves:
                    print(f"Aucune sauvegarde trouvée pour le modpack {modpack_folder['title']} sur le cloud.")
                else:
                    for file in cloud_saves:
                        if file['title'].endswith('.zip'):
                            local_zip_path = os.path.join(saves_path, file['title'])
                            file.GetContentFile(local_zip_path)

                            extracted_folder_path = local_zip_path.replace('.zip', '')
                            shutil.unpack_archive(local_zip_path, extracted_folder_path)

                            os.remove(local_zip_path)

def clear_folder(folder_id):
    global drive

    query = f"'{folder_id}' in parents and trashed = false"

    file_list = drive.ListFile({'q': query}).GetList()

    log_status("delete", "Suppresion des mondes du cloud...")

    for file in file_list:
        try:
            file.Delete()
        except Exception as e:
            print(f"Erreur lors de la suppression de {file['title']} : {e}")



def write_machine_id():
    """Write machine ID to a JSON file in the saves directory."""
    id_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], MACHINE_ID_FILE)
    with open(id_file_path, 'w') as f:
        json.dump({"machine_id": MACHINE_ID}, f)


def check_machine_id():
    """Check if the machine ID matches the ID in the saves directory."""
    id_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], MACHINE_ID_FILE)
    if os.path.exists(id_file_path):
        with open(id_file_path, 'r') as f:
            data = json.load(f)
            return data.get("machine_id") == MACHINE_ID
    return False



def upload_machine_id_to_cloud():
    """Upload the machine ID file to Google Drive."""
    global drive
    id_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], MACHINE_ID_FILE)
    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)
    file = drive.CreateFile({'title': MACHINE_ID_FILE, 'parents': [{'id': root_folder_id}]})
    file.SetContentFile(id_file_path)
    file.Upload()


def download_machine_id_from_cloud():
    """Download the machine ID file from Google Drive."""
    global drive
    root_folder_id = create_or_get_folder(drive, CLOUD_SYNC_PATH)
    query = f"title='{MACHINE_ID_FILE}' and '{root_folder_id}' in parents and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        id_file_path = os.path.join(CONFIG["MINECRAFT_SAVES_PATH"], MACHINE_ID_FILE)
        file_list[0].GetContentFile(id_file_path)


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

    log_status("auth", 'Authentification réussi, Vérification de la machine...')

    download_machine_id_from_cloud()

    if check_machine_id():
        log_status("check", "Pas de changement de machine, les mondes ne se chargeront pas")
    else:
        log_status("check", "Changement de machine, Chargement des mondes...")
        sync_and_restore_from_cloud()
        write_machine_id()
        upload_machine_id_to_cloud()

    log_status("minecraft", "Chargement des mondes terminés, lancement de Minecraft")

    start_minecraft_launcher()

    wait_for_minecraft_to_exit()

    log_status("minecraft", "Minecraft fermé, Upload des mondes sur le cloud...")

    sync_to_cloud()

    log_status("minecraft", 'Upload des mondes terminée')

