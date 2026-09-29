"""
Image Module - Управление фоновыми изображениями (JPG, GIF)
"""
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageSequence
from config import RESOURCES_DIR


class BackgroundManager:
    """Менеджер фоновых изображений"""

    def __init__(self):
        self.background_path: Optional[str] = None
        self.is_gif: bool = False
        self.gif_frames: list = []
        self.current_frame: int = 0
        self.frames_dir = RESOURCES_DIR / "backgrounds"
        self.frames_dir.mkdir(parents=True, exist_ok=True)

    def load_background(self, file_path: str) -> Tuple[bool, str]:
        """Загрузка фонового изображения"""
        try:
            if not os.path.exists(file_path):
                return False, "Файл не найден"

            ext = os.path.splitext(file_path)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".gif"]:
                return False, "Поддерживаются только JPG, PNG, GIF"

            img = Image.open(file_path)

            if ext == ".gif":
                self.is_gif = True
                self.gif_frames = []

                MAX_GIF_WIDTH = 1920
                MAX_GIF_HEIGHT = 1080

                for frame in ImageSequence.Iterator(img):
                    if frame.mode != "RGB":
                        frame = frame.convert("RGB")
                    if frame.width > MAX_GIF_WIDTH or frame.height > MAX_GIF_HEIGHT:
                        frame.thumbnail((MAX_GIF_WIDTH, MAX_GIF_HEIGHT), Image.Resampling.LANCZOS)
                    self.gif_frames.append(frame.copy())

                if not self.gif_frames:
                    return False, "GIF не содержит кадров"

                self.background_path = file_path
                self.current_frame = 0
                return True, f"GIF загружен ({len(self.gif_frames)} кадров)"
            else:
                self.is_gif = False
                if img.mode != "RGB":
                    img = img.convert("RGB")
                temp_path = self.frames_dir / "background.jpg"
                img.save(temp_path, quality=95)
                self.background_path = str(temp_path)
                return True, f"Изображение загружено ({img.size[0]}x{img.size[1]})"
        except Exception as e:
            return False, f"Ошибка загрузки: {str(e)}"

    def get_current_frame(self) -> Optional[Image.Image]:
        if not self.is_gif or not self.gif_frames:
            return None
        return self.gif_frames[self.current_frame]

    def next_frame(self) -> bool:
        if not self.is_gif or not self.gif_frames:
            return False
        self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
        return True

    def get_background_path(self) -> Optional[str]:
        return self.background_path

    def clear_background(self):
        self.background_path = None
        self.is_gif = False
        self.gif_frames = []
        self.current_frame = 0

    def save_as_default(self) -> Tuple[bool, str]:
        if not self.background_path:
            return False, "Нет загруженного фона"
        try:
            default_path = self.frames_dir / "default_background.jpg"
            if self.is_gif:
                self.gif_frames[0].save(default_path, quality=95)
            else:
                shutil.copy(self.background_path, default_path)
            return True, "Фон сохранён как дефолтный"
        except Exception as e:
            return False, f"Ошибка сохранения: {str(e)}"

    def load_default(self) -> Tuple[bool, str]:
        default_path = self.frames_dir / "default_background.jpg"
        if not default_path.exists():
            return False, "Дефолтный фон не найден"
        return self.load_background(str(default_path))