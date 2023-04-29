import os, shutil, math, sys
from pathlib import Path
import json
from typing import List, Optional
import natsort
import pyminizip
import datetime
from random import randint
from pydantic import BaseModel
from abc import ABC, abstractmethod

MODULE = 25

class EncriptBaseClass(ABC):

    @abstractmethod
    def generate_password(self, key) -> str:
        pass

    @abstractmethod
    def recover_password(self, key) -> str:
        pass

class Vigenre(EncriptBaseClass):

    @classmethod
    def shift_by(cls, char, shift):
        if char.isalpha():
            aux = ord(char) + shift
            z = 'z' if char.islower() else 'Z'
            if aux > ord(z):
                aux -= MODULE
            char = chr(aux)
        return char

    @classmethod
    def vigenere(cls, text, key, decrypt=False):
        shifts = [ord(k) - ord('a') for k in key.lower()]
        i = 0
        def do_shift(char):
            nonlocal i
            if char.isalpha():
                shift = shifts[i] if not decrypt else MODULE - shifts[i]
                i = (i + 1) % len(key)
                return Vigenre.shift_by(char, shift)
            return char
        return ''.join(map(do_shift, text))
    
    @classmethod
    def generate_password(cls, key) -> str:
        password = ''.join([chr(ord("a") + randint(0, 25)) for _ in range(15)])
        return cls.vigenere(password, key)

    @classmethod
    def recover_password(cls, password, key) -> str:
        return cls.vigenere(password, key, decrypt=True)


class Anime(BaseModel):
    name: str
    path: str
    caps: int
    next_cap: int
    last_day: str
    password: str
    max_caps: int
    old_caps: Optional[int]

    def to_representation(self) -> list:
        return [self.name, self.old_caps + self.next_cap, self.old_caps + self.caps, self.last_day]

class AnimeCompressor:
    COMPRESS_DIR = "compress"
    NEW_CAPS_DIR = "new_caps"
    CAPS_DIR = "caps"
    BATCH_MAX_SIZE = 2

    def __init__(self, anime: Anime, password: str) -> None:
        self.anime = anime
        self.password = password
        self.path_to_anime = Path(self.anime.path)
        self.path_to_compress = self.path_to_anime / self.COMPRESS_DIR
        self.path_to_new_caps = self.path_to_anime / self.NEW_CAPS_DIR
        self.batch_size = self.BATCH_MAX_SIZE * self.anime.max_caps

        if not self.path_to_compress.exists():
            os.mkdir(self.path_to_compress)

        if not self.path_to_new_caps.exists():
            os.mkdir(self.path_to_new_caps)

    def delete_old_caps(self):
        """
        Delete caps in the caps directory
        """
        caps_to_delete = [f for f in os.listdir(self.path_to_anime) if os.path.isfile(self.path_to_anime / f)]
        if len(caps_to_delete) > 0:
            aux = min(len(caps_to_delete), self.anime.max_caps)
            self.anime.old_caps += aux
            self.anime.caps -= aux
            self.anime.next_cap -= aux
            for cap in caps_to_delete:
                os.remove(self.path_to_anime / cap)

    def decompress_batch(self, batch_index: int, dest: Path):
        """
        Decompress batch into a desired destination
        """
        compress_files = os.listdir(self.path_to_compress)
        if len(compress_files) > batch_index:
            compress_files = natsort.natsorted(compress_files)
            file_to_decompress = compress_files[batch_index]
            self.decompress(self.path_to_compress / file_to_decompress, dest)
            os.remove(self.path_to_compress / file_to_decompress)

    def compress_caps(self, batch_index: int, new_caps=False):
        """
        Compress caps in batches to the compress directory
        """
        if new_caps:
            caps = os.listdir(self.path_to_new_caps)
        else:
            caps = [f for f in os.listdir(self.path_to_anime) if os.path.isfile(self.path_to_anime / f)]
        if len(caps) > self.anime.max_caps or new_caps:
            if not new_caps:
                caps = natsort.natsorted(caps)
                caps = caps[self.anime.max_caps:]
            for index, cap in enumerate(caps):
                    if new_caps:
                        caps[index] = self.path_to_new_caps / cap
                    else:
                        caps[index] = self.path_to_anime / cap
            
            for i in range(math.ceil(len(caps) / self.batch_size)):
                batch_position = self.batch_size * i
                caps_to_compress = []
                if len(caps[batch_position:]) <= self.batch_size:
                    caps_to_compress = caps[batch_position:]
                else:
                    caps_to_compress = caps[batch_position:batch_position + self.batch_size]
                self.compress(caps_to_compress, batch_index)
                batch_index += 1

            for cap in caps:
                os.remove(cap)

    def compress(self, files: List[Path], name: str):
        """
        Compress files into the compress directory as name.zip
        """
        files = [str(file) for file in files]
        pyminizip.compress_multiple(files, files, str(self.path_to_compress / f"{name}.zip"), self.password, 1)

    def decompress(self, file: Path, dest: Path):
        """
        Decompress file into desired destination
        """
        if file.exists():
            curr_dir = os.getcwd()
            pyminizip.uncompress(str(file), self.password, str(dest), True)
            os.chdir(curr_dir)

    def get_new_caps(self, new_anime = False):
        if not new_anime:
            self.delete_old_caps()
            if self.anime.next_cap + self.anime.max_caps > self.anime.caps:
                self.anime.next_cap += self.anime.caps % self.batch_size
            else:
                self.anime.next_cap += self.anime.max_caps
            self.decompress_batch(0, self.path_to_anime)
        self.compress_caps(0)
        
    def add_new_caps(self):
        caps = os.listdir(self.path_to_new_caps)
        if len(caps) > 0:
            aux = self.anime.caps
            self.anime.caps += len(caps)
            batches = len(os.listdir(self.path_to_compress))
            if aux % self.batch_size > 0 and batches > 0:
                batches -= 1
                self.decompress_batch(batches, self.path_to_new_caps)
                self.compress_caps(batches, True)
            else:
                if self.anime.caps <= self.anime.max_caps:
                    for cap in caps:
                        shutil.move(self.path_to_new_caps / cap, self.path_to_anime / cap)
                else:
                    self.compress_caps(batches, True)
    
class AnimeController:
    if getattr(sys, 'frozen', False):
        current_Path = os.path.dirname(sys.executable)
    else:
        current_Path = str(os.path.dirname(__file__))
    MAIN_DIR = Path(f"{current_Path}/anime_locker")
    STATUS_FILE = Path("anime_status.json")
    KEY_FILE = Path("key.txt")
    COMPRESS_FILE_NAME = "compress.zip"

    def __init__(self):
        self.animes = {}
        self.key = 'desencriptameestaperro'
        self.encript_class = Vigenre

        if not self.MAIN_DIR.exists():
            os.mkdir(self.MAIN_DIR)

        status_path = self.MAIN_DIR / self.STATUS_FILE
        key_path = self.MAIN_DIR / self.KEY_FILE

        if status_path.exists():
            json_animes = {}
            with open(status_path, "r") as f:
                json_animes = json.load(f)
            for anime, data in json_animes.items():
                self.animes[anime] = Anime.parse_obj(data)

        if key_path.exists():
            with open(key_path, "r") as f:
                self.key = json.load(f)


    def add_new_anime(self, name: str, path: str, max_caps: int, old_caps: int):
        if name not in self.animes:
            password = self.encript_class.generate_password(self.key)
            new_anime = Anime(path=str(path),
                  caps=len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]),
                  next_cap=0,
                  last_day=str(datetime.date.today()),
                  password=password,
                  max_caps=max_caps,
                  name=name,
                  old_caps=old_caps)
            self.animes[name] = new_anime
            unencrypted_password = self.encript_class.recover_password(password, self.key)
            AnimeCompressor(new_anime, unencrypted_password).get_new_caps(True)
            self.save_status()
        else:
            raise Exception("This anime is already in the list")
          
    def reload(self):
        animes_to_delete = []
        for anime, data in self.animes.items():
            if not Path(data.path).exists():
                animes_to_delete.append(anime)
            else:
                unencrypted_password = self.encript_class.recover_password(data.password, self.key)
                AnimeCompressor(data, unencrypted_password).add_new_caps()

        for anime in animes_to_delete:
            del self.animes[anime]
        self.save_status()

    def dispense_anime(self, anime) -> bool:
        anime_data = self.animes[anime]
        if anime_data.last_day < str(datetime.date.today()):
            anime_data.last_day = str(datetime.date.today())
            unencrypted_password = self.encript_class.recover_password(anime_data.password, self.key)
            AnimeCompressor(anime_data, unencrypted_password).get_new_caps()
            self.save_status()
            return True
        return False
        
    def save_status(self):
        serialized_animes = {}
        for anime, data in self.animes.items():
            serialized_animes[anime] = data.dict()
        with open(self.MAIN_DIR / self.STATUS_FILE, "w") as f:
            f.write(json.dumps(serialized_animes))
        with open(self.MAIN_DIR / self.KEY_FILE, "w") as f:
            f.write(json.dumps(self.key))

    def delete_anime(self, name):
        if name in self.animes:
            path = self.animes[name].path
            shutil.rmtree(path)
            del self.animes[name]
            self.save_status()

