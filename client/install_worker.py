import logging
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

class InstallWorker(QThread):
    progress = Signal(str)  # Передаем строку с прогрессом
    finished = Signal(bool, str)

    def __init__(self, install_func, *args):
        super().__init__()
        self.install_func = install_func
        self.args = args
        self.max_files = 0  # Общее количество файлов
        self.current_file = 0  # Текущий файл

    def run(self):
        try:
            # Callback-словарь для minecraft_launcher_lib
            def set_status(status):
                logger.info(f"Статус: {status}")

            def set_max(max_value):
                self.max_files = max_value
                message = f"Скачано {self.current_file} из {self.max_files} файлов"
                logger.info(message)
                self.progress.emit(message)

            def set_progress(current):
                self.current_file = current
                if self.max_files > 0:
                    message = f"Скачано {self.current_file} из {self.max_files} файлов"
                    logger.info(message)
                    self.progress.emit(message)

            callback_dict = {
                "setStatus": set_status,
                "setMax": set_max,
                "setProgress": set_progress
            }

            logger.info(f"Вызов функции: {self.install_func.__name__} с аргументами: {self.args}")
            self.install_func(*self.args, callback=callback_dict)
            logger.info(f"Установка {self.args[0]} завершена успешно")
            self.finished.emit(True, "Установка завершена успешно")
        except Exception as e:
            logger.error(f"Ошибка в InstallWorker: {str(e)}", exc_info=True)
            self.finished.emit(False, f"Ошибка установки: {str(e)}")