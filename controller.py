import os, shutil
import stat
from pathlib import Path
import json
import threading
from typing import List
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
    last_cap: int
    last_day: str
    password: str
    max_caps: int
    old_caps = 10

    def to_representation(self) -> list:
        return [self.name, self.last_cap, self.caps, self.last_day]


class AnimeController:
    MAIN_DIR = Path("./anime_locker")
    STATUS_FILE = Path("anime_status.json")
    KEY_FILE = Path("key.txt")
    COMPRESS_FILE_NAME = "compress.zip"

    def __init__(self):
        self.animes = {}
        self.key = 'desencriptameestaperro'
        self.encript_class = Vigenre()
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


    def add_new_anime(self, name: str, path: str, max_caps: int):
        if name not in self.animes:
            path = self.MAIN_DIR / path 
            password = self.encript_class.generate_password(self.key)
            new_anime = Anime(path=str(path),
                  caps=len(os.listdir(path)),
                  last_cap=0,
                  last_day=str(datetime.date.today()),
                  password=password,
                  max_caps=max_caps,
                  name=name)
            self.animes[name] = new_anime
            self.set_up_anime(name)
            self.save_status()
        else:
            raise Exception("This anime is already in the list")
    
    def set_up_anime(self, name):
        self.decompress(name)
        path = Path(self.animes[name].path)
        max_caps = self.animes[name].max_caps
        password = self.encript_class.recover_password(self.animes[name].password, self.key)
        last_cap = self.animes[name].last_cap
        caps = os.listdir(path)
        caps = natsort.natsorted(caps)
        for index, cap in enumerate(caps):
            caps[index] = path / cap
        if len(caps) > max_caps:
            caps_to_compress = []
            if self.animes[name].last_day <= str(datetime.date.today()):
                caps_to_compress = caps[:last_cap] + caps[last_cap + max_caps:]
                self.unhid_files(caps[last_cap:last_cap + max_caps])
                self.hid_files(caps_to_compress)
                self.compress_files(caps_to_compress, path, password)
            for cap in caps_to_compress:
                os.remove(cap)

    def unhid_files(self, files):
        for file in files:
            st = os.stat(file)
            os.chflags(file, st.st_flags & (not stat.UF_HIDDEN))

    def hid_files(self, files):
        for file in files:
            st = os.stat(file)
            os.chflags(file, st.st_flags | stat.UF_HIDDEN)
    
    def compress_files(self, files: List[Path], dir: Path, password: str):
        files = [str(file) for file in files]
        pyminizip.compress_multiple(files, files, str(dir / self.COMPRESS_FILE_NAME), password, 1)
          
    def reload(self):
        animes_to_delete = []
        for anime, data in self.animes.items():
            if not Path(data.path).exists():
                animes_to_delete.append(anime)
            else:
                caps = os.listdir(data.path)
                if len(caps) > data.max_caps + 1:
                    self.set_up_anime(anime)

        for anime in animes_to_delete:
            del self.animes[anime]
        self.save_status()

    def check_anime_status(self, anime) -> bool:
        return self.animes[anime].last_day < str(datetime.date.today())

    def dispense_anime(self, anime) -> bool:
        anime_data = self.animes[anime]
        if anime_data.last_day < str(datetime.date.today()):
            anime_data.last_day = str(datetime.date.today())
            anime_data.last_cap = anime_data.last_cap + anime_data.max_caps
            self.set_up_anime(anime)
            self.save_status()
            return True
        return False
    
    def fall_back_anime(self, anime):
        anime_data = self.animes[anime]
        anime_data.last_day = str(datetime.date.today())
        if anime_data.last_cap >= anime_data.max_caps:
            anime_data.last_cap = anime_data.last_cap - anime_data.max_caps
            self.set_up_anime(anime)
        self.save_status()

    def decompress(self, name):
        password = self.encript_class.recover_password(self.animes[name].password, self.key)
        dir = self.animes[name].path
        if Path(f"{dir}/{self.COMPRESS_FILE_NAME}").exists():
            pyminizip.uncompress(f"{dir}/{self.COMPRESS_FILE_NAME}", password, dir, True)
            os.chdir("../..")
            os.remove(f"{dir}/{self.COMPRESS_FILE_NAME}")
        

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

