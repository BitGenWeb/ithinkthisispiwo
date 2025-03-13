import os
import hashlib
import logging

logger = logging.getLogger(__name__)

def calculate_folder_hash(folder_path):
    if not os.path.exists(folder_path):
        return None
    sha256 = hashlib.sha256()
    try:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "rb") as f:
                        sha256.update(f.read())
                except (IOError, OSError) as e:
                    logger.error(f"Ошибка чтения файла {file_path}: {e}")
                    continue
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Ошибка вычисления хеша для {folder_path}: {e}")
        return None