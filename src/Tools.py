import hashlib
import logging
import os
import re
import tomllib
from pathlib import Path


config_dir = "Config"
config_file_name = 'config.toml'
sys_config_file_name = 'software_config.toml'
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

common_words = ['HD', '1080p', '720p', 'BluRay', 'WEBRip', 'x264', 'YIFY', 'DVDRip']


def hash_this_file(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def get_relative_path(entry) -> str:
    root_dir = Path(entry.get("source_folder", ""))  # cartella radice
    original_path = Path(entry["original_path"])  # path assoluto del file
    # Calcolo del path relativo
    try:
        relative_path = str(original_path.parent.relative_to(root_dir))
    except ValueError:
        # Se original_path NON è sotto root_dir, fallback
        relative_path = str(original_path.parent)
    return relative_path

def reload_generic_config() -> dict:
    """Ricarica la configurazione generica unendo system_config.toml e config.toml"""
    systemConfigFile = os.path.join(root_dir, config_dir, sys_config_file_name)
    configFile = os.path.join(root_dir, config_dir, config_file_name)
    sys_conf = load_config(systemConfigFile)
    user_conf = load_config(configFile)
    return join_configs(sys_conf, user_conf)

def join_configs(base: dict, override: dict) -> dict:
    """Unisce due configurazioni, elemento per elemento, con override che sovrascrive base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = join_configs(result[key], value)
        else:
            result[key] = value
    return result

def load_config(path: str) -> dict:
    log = logging.getLogger(__name__)
    if not os.path.exists(path):
        log.error("load_config - Missing config file: " + str(path))
        raise MissingConfigException("load_config - Missing config file: " + str(path))
    try:
        with open(path, 'rb') as stream:
            config = tomllib.load(stream)
    except FileNotFoundError:
        log.error(f"Cannot find the config file: [{path}]")
        raise MissingConfigException("File di configurazione mancante")
    except tomllib.TOMLDecodeError as e:
        log.error(f"Cannot parse the configuration: [{e}]")
        raise MissingConfigException(str(e))
    except PermissionError as e:
        log.error(f"Insufficient permissions to read configuration: [{path}]")
        raise MissingConfigException(str(e))
    return config

def guess_correct_title(title: str) -> str:
    """Prova a indovinare il titolo corretto rimuovendo blocchi di testo non necessari"""
    # Rimuove contenuti tra parentesi tonde o quadre
    title = re.sub(r'\[.*?]|\(.*?\)', '', title)
    # Rimuove parole comuni non necessarie
    for word in common_words:
        title = re.sub(r'\b' + re.escape(word) + r'\b', '', title, flags=re.IGNORECASE)
    # Pulisce spazi multipli
    title = ' '.join(title.split())
    return title.strip()

def _clean_title(title: str) -> str:
    """Pulisce il titolo sostituendo punti e underscore con spazi"""
    title = title.replace('.', ' ').replace('_', ' ')
    # Rimuove spazi multipli
    title = ' '.join(title.split())
    return title.strip()

def _sanitize_filename(filename: str) -> str:
    """Rimuove caratteri non validi dai nomi di file"""
    # Caratteri non permessi in Windows/Unix
    replace_patterns = [
        {'from': '/\\', 'to': '-'},
        {'from': '<>:"|?*', 'to': ''}
    ]
    for pattern in replace_patterns:
        for invalid_char in pattern['from']:
            filename = filename.replace(invalid_char, pattern['to'])
    return filename
class MissingConfigException(Exception):
    pass
