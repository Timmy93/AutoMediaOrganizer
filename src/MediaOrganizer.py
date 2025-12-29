import hashlib
import json
import logging
import os
import re
import shutil
import tomllib
from pathlib import Path
from typing import Optional, Dict
from pymysql import OperationalError
from src.Database import Database
from src.TMDBClient import TMDBClient

# Configurazioni di default
config_dir = "Config"
config_file_name = 'config.toml'
sys_config_file_name = 'software_config.toml'
allowed_media_types = ['movie', 'tv']
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def print_errors(file_processing: dict):
    preprocessing_successful = file_processing['processing_outcome'].get('outcome', False)
    processing_successful = file_processing['processing_outcome'].get('outcome', False)
    if not processing_successful:
        print(f"Analizzato: {file_processing['name'].name}")
        print(f">>> Preprocessing applicati: {len(file_processing['preprocessing_outcome'])}")
        out = []
        for result in file_processing['preprocessing_outcome']:
            if err := result.get('error'):
                out.append("❌" + result['pattern'] + f" (Errore: {err})")
            else:
                out.append("✅" + result['pattern'])
        print(f">>> Patterns: {'|'.join(out)}")
        print(f">>> Esito processamento: {'Successo' if preprocessing_successful else 'Saltato'}")


class MediaOrganizer:
    """Classe principale per organizzare i file multimediali"""

    def __init__(self, config: dict):
        self.config = config
        self.scan_config = {}
        self.logger = logging.getLogger(__name__)
        self.tmdb_client = TMDBClient(
            self.config['tmdb']['api_key'],
            self.config['tmdb']['language']
        )
        self.db = Database(
            host=self.config['db'].get('host'),
            user=self.config['db'].get('user'),
            password=self.config['db'].get('password'),
            database=self.config['db'].get('database'),
            port=self.config['db'].get('port', 3306)
        )
        # Regex per tv
        self.tv_regex = re.compile(
            self.config['regex']['tv_pattern'],
            re.IGNORECASE
        )
        # Regex per film
        self.movie_regex = re.compile(
            self.config['regex']['movie_pattern'],
            re.IGNORECASE
        )

        self.stats = {
            'movies_processed': 0,
            'tv_processed': 0,
            'skipped': 0,
            'errors': 0,
            'files': []
        }

    def reset_stats(self):
        self.stats['movies_processed'] = 0
        self.stats['tv_processed'] = 0
        self.stats['skipped'] = 0
        self.stats['errors'] = 0
        self.stats['files'] = []

    def _get_media_info(self, file_path: Path) -> dict:
        """Determina se un file è un film o una serie TV in base alla sua posizione"""
        file_info = {
            'original_path': file_path,
            'path': file_path,
            'destination_subfolder': None,
            'processing_patterns': ['generic'],
            'media_type': '',
            'year': None
        }
        self.get_info_from_path(file_info)
        if file_info.get('ignore', False):
            self.logger.debug(f"File ignorato in base alla configurazione: {file_path}")
        elif file_info.get('media_type', ''):
            self.logger.debug(f"Tipo di media determinato dalla cartella: {file_info.get('scanned_dir')} -> {file_info.get('media_type')}")
        elif self.tv_regex.search(file_path.stem):
            self.logger.debug("Tipo di media determinato dal nome del file: tv")
            file_info['media_type'] = 'tv'
        else:
            self.logger.debug(f"Tipo di media non determinato. Default: movie")
            file_info['media_type'] = 'movie'
        return file_info

    def get_info_from_path(self, file_info: dict):
        """
        Analizza il percorso del file ed estrae informazioni sul file in base alla configurazione di scansione
        :param file_info:
        :return:
        """
        base_path = self.config['paths']['source_folder']
        relative_path = file_info['path'].relative_to(base_path)
        for scanned_dir in self.scan_config.get('directories', []):
            dir_path = Path(scanned_dir.get('path', ''))
            # Controlla se il file si trova in questa directory
            if dir_path in relative_path.parents or dir_path == relative_path.parent:
                file_info['scanned_dir'] = dir_path
                file_info['processing_patterns'] = scanned_dir.get('pattern_list', ['generic'])
                file_info['ignore'] = scanned_dir.get('ignore', False)
                file_info['destination_subfolder'] = scanned_dir.get('destination_subfolder', '')
                media_type = scanned_dir.get('media_type', '').lower()
                if media_type in allowed_media_types:
                    file_info['media_type'] = media_type
                elif media_type:
                    self.logger.warning(f"Tipo di media non valido nella configurazione: {media_type}")
                return
        return

    @staticmethod
    def _clean_title(title: str) -> str:
        """Pulisce il titolo sostituendo punti e underscore con spazi"""
        title = title.replace('.', ' ').replace('_', ' ')
        # Rimuove spazi multipli
        title = ' '.join(title.split())
        return title.strip()

    def _parse_movie_filename(self, file_info: dict):
        """Estrae informazioni da un nome di file film"""
        match = self.movie_regex.search(file_info['path'].stem)
        if match:
            info = match.groupdict()
            file_info['title'] = self._clean_title(info['title'])
            file_info['year'] = int(info['year'])
            # Gestione di film senza anno
            if 'year' not in info or not info['year']:
                file_info['year'] = None

    def _generate_movie_path(self, movie_info: Dict, file_info: dict) -> Path:
        """Genera il percorso di destinazione per un film"""
        pattern = self.config['naming'].get('movie_pattern')
        if not pattern:
            self.logger.warning("Nessun pattern di naming per film definito nella configurazione.")
            raise ValueError("Nessun pattern di naming per film definito nella configurazione.")

        folder_name = pattern.format(
            title=movie_info['title'],
            year=movie_info.get('release_date', '')[:4]
        )
        # Sanitizza il nome
        folder_name = self._sanitize_filename(folder_name)
        dest_folder = os.path.join(
            Path(self.config['paths']['destination_folder']),
            file_info.get('destination_subfolder'),
            Path(self.config['paths']['movie_folder']),
            folder_name
        )
        return Path(os.path.join(dest_folder, file_info['path'].name))

    def _parse_tv_filename(self, filename: str) -> Optional[Dict]:
        """Estrae informazioni da un nome di file serie TV"""
        match = self.tv_regex.search(filename)
        if match:
            info = match.groupdict()
            info['title'] = self._clean_title(info['title'])
            info['season'] = int(info['season'])
            info['episode'] = int(info['episode'])
            return info
        return None

    def _generate_tv_path(self, tv_info: Dict, episode_info: Dict, season: int, episode: int, file_info: dict) -> Path:
        """Genera il percorso di destinazione per un episodio di serie TV"""
        show_pattern = self.config['naming']['tv_show_pattern']

        # Nome cartella serie
        show_folder = show_pattern.format(
            title=tv_info['name'],
            season=season
        )
        if ("/" in show_folder) or ("\\" in show_folder):
            # Splitta in sottocartelle
            parts = re.split(r'[\\/]', show_folder)
            # Join con Path per gestire le sottocartelle
            show_folder = Path(*[self._sanitize_filename(part) for part in parts])
        # Rinomina l'episodio se il pattern è definito, altrimenti mantiene il nome originale
        if ep_pattern := self.config['naming'].get('episode_pattern'):
            episode_name = ep_pattern.format(
                title=tv_info['name'],
                season=season,
                episode=episode,
                episode_title=episode_info.get('name', 'Episode') if episode_info else 'Episode'
            )
            episode_name = self._sanitize_filename(episode_name)
            episode_name += file_info["original_path"].suffix
        else:
            episode_name = file_info['path'].name

        # Percorso finale
        dest_folder = os.path.join(
            Path(self.config['paths']['destination_folder']),
            file_info.get('destination_subfolder'),
            Path(self.config['paths']['tv_show_folder']),
            show_folder
        )
        return Path(os.path.join(dest_folder, episode_name))

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Rimuove caratteri non validi dai nomi di file"""
        # Caratteri non permessi in Windows/Unix
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        return filename

    def _is_video_file(self, file_path: Path) -> bool:
        """Verifica se un file è un file video"""
        return file_path.suffix.lower() in self.config['options']['video_extensions']

    def _link_or_copy_file(self, file_info: dict, destination: Path) -> dict:
        """Sposta o copia un file dalla sorgente alla destinazione"""
        try:
            # Crea la directory di destinazione se necessario
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Controlla se il file esiste già
            if destination.exists() and self.config['options'].get('skip_existing', True):
                self.logger.info(f"File già esistente, saltato: {destination}")
                return {'outcome': True, 'error': 'File già esistente, saltato'}

            # Copia o sposta
            if self.config['options'].get('copy_instead_of_link', False):
                shutil.copy2(file_info.get('original_path'), destination)
                self.logger.info(f"Copiato: {file_info.get('original_path').name} -> {destination}")
            else:
                os.link(file_info.get('original_path'), destination)
                self.logger.info(f"Linkato: {file_info.get('original_path').name} -> {destination}")
            return {'outcome': True, 'error': None}

        except Exception as e:
            self.logger.exception(f"Errore nello spostamento/copia di {file_info.get('original_path').name}: {e}")
            return {'outcome': False, 'error': str(e)}

    def pre_process_file(self, file_info: dict, file_processing: dict) -> dict:
        """Applica le regole di pre-processamento al file"""
        for pattern_name in file_info.get('processing_patterns', []):
            pattern_rules = self.scan_config.get('patterns', {}).get(pattern_name, {})
            self.check_skip(file_info, file_processing)
            for pattern in pattern_rules:
                pattern_result = self.apply_pattern_rule(file_info, pattern)
                # Salva solo i pattern applicati o con errori
                if pattern_result.get('applied', False) or pattern_result.get('error'):
                    file_processing['preprocessing_outcome'].append(pattern_result)
                # Se il file è stato marcato come ignorato, esce dal ciclo
                self.check_skip(file_info, file_processing)
                if file_info.get('ignore', False):
                    break
        return file_info

    def check_skip(self, file_info: dict, file_processing: dict):
        """Controlla se il file deve essere ignorato"""
        if file_info.get('ignore', False):
            self.logger.info(f"File ignorato in base alla configurazione: {file_info['path'].name}")
            self.stats['skipped'] += 1
            file_processing['skipped'] = True
            file_processing['processing_outcome'] = {'outcome': True, 'error': 'File ignorato durante pre-processing'}

    def process_movie(self, file_info: dict) -> dict:
        """Processa un file film"""
        self.logger.info(f"Processando film: {file_info['path'].name}")

        # Estrae informazioni dal nome del file
        self._parse_movie_filename(file_info)
        if not file_info.get('title') or not file_info.get('year'):
            self.logger.warning(f"Film - Impossibile estrarre informazioni da: {file_info['path'].name}")
            return {'outcome': False, 'error': 'Parsing fallito'}
        # Cerca su TMDB
        movie_info = self.tmdb_client.search_movie(
            file_info['title'],
            file_info.get('year')
        )
        if not movie_info:
            self.logger.info(f"Film non trovato su TMDB: {file_info['path'].name}")
            movie_info = self.tmdb_client.search_movie(
                self.guess_correct_title(file_info['original_path'].stem)
            )
            if not movie_info:
                self.logger.warning(f"Film non trovato su TMDB (guessing): {file_info['path'].name}")
                return {'outcome': False, 'error': f'Media non disponibile su TMDB [{file_info['path'].name}]'}
        # Genera percorso di destinazione
        dest_path = self._generate_movie_path(movie_info, file_info)
        # Sposta/copia il file
        return self._link_or_copy_file(file_info, dest_path)

    def guess_correct_title(self, title: str) -> str:
        """Prova a indovinare il titolo corretto rimuovendo blocchi di testo non necessari"""
        # Rimuove contenuti tra parentesi tonde o quadre
        title = re.sub(r'\[.*?]|\(.*?\)', '', title)
        # Rimuove parole comuni non necessarie
        common_words = ['HD', '1080p', '720p', 'BluRay', 'WEBRip', 'x264', 'YIFY', 'DVDRip']
        for word in common_words:
            title = re.sub(r'\b' + re.escape(word) + r'\b', '', title, flags=re.IGNORECASE)
        # Pulisce spazi multipli
        title = ' '.join(title.split())
        return title.strip()

    def process_tv_show(self, file_info: dict) -> dict:
        """Processa un file serie TV"""
        file_path = file_info['path']
        self.logger.info(f"Processando serie TV: {file_path.name}")

        # Estrae informazioni dal nome del file
        parsed_info = self._parse_tv_filename(file_path.stem)
        if not parsed_info:
            self.logger.warning(f"Serie TV - Impossibile estrarre informazioni da: {file_path.name}")
            return {'outcome': False, 'error': 'Parsing fallito'}

        # Cerca la serie su TMDB
        tv_info = self.tmdb_client.search_tv_show(parsed_info['title'], file_info)
        if not tv_info:
            self.logger.warning(f"Serie TV non trovata su TMDB: {file_path.name}")
            return {'outcome': False, 'error': f'Media non disponibile su TMDB [{parsed_info['title']}]'}

        # Ottiene dettagli dell'episodio
        episode_info = self.tmdb_client.get_episode_details(
            tv_info['id'],
            parsed_info['season'],
            parsed_info['episode']
        )

        # Genera percorso di destinazione
        dest_path = self._generate_tv_path(
            tv_info,
            episode_info,
            parsed_info['season'],
            parsed_info['episode'],
            file_info
        )
        # Sposta/copia il file
        return self._link_or_copy_file(file_info, dest_path)

    def apply_pattern_rule(self, file_info: dict, pattern: dict) -> dict:
        result = {
            'pattern': pattern.get('name') or pattern.get('regex') or 'unnamed',
            'id': hashlib.sha256(json.dumps(pattern, sort_keys=True).encode('utf-8')).hexdigest(),
            'applied': False,
            'error': None
        }
        try:
            if pattern.get('regex') and pattern.get('ignore'):
                if re.search(pattern.get('regex'), file_info['path'].stem):
                    file_info['ignore'] = True
                    result['applied'] = True
            if pattern.get('regex') and pattern.get('substitution'):
                result['applied'] = self.regex_rename(file_info, pattern)
            if pattern.get('regex') and pattern.get('year'):
                if re.search(pattern.get('regex'), file_info['path'].stem):
                    # Aggiunge o modifica l'anno nel file_info
                    file_info['year'] = pattern.get('year')
                    result['applied'] = True
        except re.error as e:
            self.logger.error(f"Errore nell'applicare la regola di rinomina: {e}")
            result['error'] = str(e)
        except Exception as e:
            self.logger.exception(f"Errore inatteso nell'applicare la regola di rinomina: {e}")
            result['error'] = str(e)
        return result

    def regex_rename(self, file_info: dict, rename_rule) -> bool:
        def repl(m):
            d = m.groupdict() | folder_info
            if episode_padding := rename_rule.get("episode_padding") is None:
                episode_padding = self.config.get('options', {}).get('episode_padding', 0)
            if season_padding := rename_rule.get("season_padding") is None:
                season_padding = self.config.get('options', {}).get('season_padding', 0)
            # Normalizzazione valori
            if d.get("episode"):
                if ep_offset := rename_rule.get("episode_offset", 0):
                    d["episode"] = int(d["episode"]) + ep_offset
                    d["episode"] = str(d["episode"]).zfill(episode_padding)
            if (season_number := rename_rule.get("season_number")) is not None:
                d["season"] = season_number
            if d.get("season"):
                if season_offset := rename_rule.get("season_offset", 0):
                    d["season"] = int(d["season"]) + season_offset
                d["season"] = str(d["season"]).zfill(season_padding)
            return rename_rule.get('substitution').format(**d)
        match = re.search(rename_rule.get('regex'), file_info['path'].stem)
        if not match:
            self.logger.debug("Nessuna corrispondenza trovata per la regola di rinomina.")
            return False
        else:
            folder_info = {}
            if "folder_regex" in rename_rule:
                # Estrae informazioni dalla cartella padre
                folder_match = re.match(rename_rule.get('folder_regex'), os.path.basename(os.path.dirname(file_info['path'])))
                if folder_match:
                    folder_info = folder_match.groupdict()
            self.logger.debug(f"Applicando regola di rinomina: {rename_rule.get('regex')} -> {rename_rule.get('substitution')}")
            try:
                rename_rule = re.sub(rename_rule.get('regex'), repl, file_info['path'].stem)
            except re.error as e:
                self.logger.error(f"Errore nella sostituzione della regola di rinomina: {e}")
                return False
            except KeyError as e:
                self.logger.error(f"Valori mancanti per la rinomina [{', '.join(e.args)}]")
                return False
            file_info['path'] = Path(str(os.path.join(file_info['path'].parent, rename_rule + file_info['path'].suffix)))
            return True

    def scan_and_organize(self)-> None:
        """
        Scansiona la cartella sorgente e organizza tutti i file
          1. Seleziona le cartelle da scansionare
          2. Per ogni file, determina se è un film o una serie TV in base a:
            2.1. Cartella, se definito nelle config
            2.2. Nome del file, (serie tv se identifica pattern SxxExx)
          3. Pre-processa in base ai patterns applicati
          4. Processa i file con TMDB
          5. Esporta il file nel catalogo
        :return: None
        """
        print("Starting scan and organize process...")
        self.reload_all_config()
        self.reset_stats()
        already_processed_files = self.load_info()
        self.logger.info(f"Caricati {len(already_processed_files)} file già processati con successo in precedenza.")


        # Itera ricorsivamente attraverso tutti i file
        for main_dir in self.config['paths']['selected_dir']:
            self.config['paths']['source_folder'] = main_dir.get('source_folder')
            self.config['paths']['destination_folder'] = main_dir.get('destination_folder')
            self.scan_config = main_dir.get('scan_config')

            try:
                source_folder = Path(self.config['paths']['source_folder'])
                if not source_folder.exists():
                    self.logger.error(f"La cartella sorgente non esiste: {source_folder}")
                    print(f"La cartella sorgente non esiste: {source_folder}")
                    continue
            except TypeError as e:
                self.logger.error(f"Percorso sorgente non valido: {self.config['paths']['source_folder']} -> {e}")
                print(f"Percorso sorgente non valido: {self.config['paths']['source_folder']}")
                continue

            selected_dirs = self.get_dir_to_scan()
            print(f"Scanning directory: {source_folder} - Found {len(selected_dirs)} subdirectories to scan.")

            for selected_dir in selected_dirs:
                for file_path in selected_dir.rglob('*'):
                    file_processing = {
                        'name': file_path,
                        'preprocessing_outcome': [],
                        'processing_outcome': {'outcome': False, 'error': 'Not processed'},
                        'skipped': False,
                    }
                    try:
                        if self.skip_this_file(file_path, already_processed_files):
                            continue
                        # Determina il tipo di media
                        file_info = self._get_media_info(file_path)
                        # Pre-processa il file in base alle regole definite
                        self.pre_process_file(file_info, file_processing)
                        # Processa in base al tipo di media
                        self.process_file(file_info, file_processing)
                        self.stats['files'].append(file_processing)

                        print_errors(file_processing)

                    except Exception as e:
                        self.logger.exception(f"Errore nella gestione di {file_path}: {e}")
                        self.stats['errors'] += 1

        # Salva lo stato del processamento
        self.store_info()
        print("Scan and organize process completed.")

        # Stampa statistiche
        self.logger.info("=" * 60)
        self.logger.info("STATISTICHE FINALI")
        self.logger.info("=" * 60)
        self.logger.info(f"Film processati: {self.stats['movies_processed']}")
        self.logger.info(f"Episodi TV processati: {self.stats['tv_processed']}")
        self.logger.info(f"File saltati: {self.stats['skipped']}")
        self.logger.info(f"Errori: {self.stats['errors']}")
        self.logger.info("=" * 60)

    def skip_this_file(self, file_path, already_processed_files: list) -> bool:
        if str(file_path) in already_processed_files:
            self.logger.debug(f"File già processato in precedenza, saltato: {file_path}")
            media_to_skip = True
        elif not file_path.is_file():
            media_to_skip = True
        elif not self._is_video_file(file_path):
            self.logger.debug(f"File non video, saltato: {file_path}")
            media_to_skip = True
        else:
            media_to_skip = False
        return media_to_skip

    def store_info(self):
        payload = []
        for file_stat in self.stats['files']:
            payload.append({
                'name': str(file_stat['name']),
                'preprocessing_outcome': file_stat['preprocessing_outcome'],
                'processing_outcome': file_stat['processing_outcome'],
                'skipped': file_stat['skipped'],
            })
        self.store_in_db(payload)

    def store_in_db(self, files_stats: list):
        for file_stat in files_stats:
            try:
                self.db.insert_media_entry(file_stat)
            except OperationalError as e:
                self.logger.error(f"Errore di connessione al database durante il salvataggio dei dati {file_stat['name']} - Errore: {e}")
            except Exception as e:
                self.logger.error(f"Errore inatteso durante il salvataggio dei dati nel database {file_stat['name']} - Errore: {e}")

    def load_info(self) -> list:
        try:
            return self.db.load_processed_files()
        except OperationalError as e:
            self.logger.error(f"Errore di connessione al database: {e}")
            print("Impossibile connettersi al database. Proseguo senza dati pregressi.")
            return []
        except Exception as e:
            self.logger.error(f"Errore nel caricare lo stato del processamento: {e}")
            print("Errore inatteso durante il caricamento da database. Proseguo senza dati pregressi.")
            return []

    def process_file(self, file_info: dict, file_processing: dict):
        try:
            if file_info.get('ignore', False):
                self.logger.info(f"File saltato durante il pre-processamento: {file_info['path'].name}")
                self.stats['skipped'] += 1
                return
            elif file_info.get('media_type') == 'movie':
                result = self.process_movie(file_info)
                if result['outcome']:
                    self.stats['movies_processed'] += 1
                    file_processing['processing_outcome'] = result
                else:
                    self.stats['skipped'] += 1
            elif file_info.get('media_type') == 'tv':
                result = self.process_tv_show(file_info)
                if result['outcome']:
                    self.stats['tv_processed'] += 1
                    file_processing['processing_outcome'] = result
                else:
                    self.stats['skipped'] += 1
            else:
                self.logger.warning(f"Tipo di media non supportato per il file: {file_info['name']}")
                self.stats['skipped'] += 1
                file_processing['processing_outcome'] = {'outcome': False, 'error': 'Tipo di media non supportato'}
        except Exception as e:
            self.logger.exception(f"Errore nel processare [{file_info.get('media_type')}] {file_info['name']}: {e}")
            self.stats['errors'] += 1
            file_processing['processing_outcome'] = {'outcome': False, 'error': str(e)}

    def get_dir_to_scan(self) -> list:
        """Restituisce la lista delle directory da scansionare"""
        base_path = Path(self.config['paths']['source_folder'])
        if not self.config['paths'].get('scan_only_selected_subdir', True):
            self.logger.info(f"SCAN - Scansione di tutta la cartella sorgente: {base_path}")
            return [base_path]
        else:
            dirs_to_scan = []
            for scanned_dir in self.scan_config.get('directories', []):
                if scanned_dir.get('ignore', False):
                    self.logger.info(f"SKIP - Directory ignorata: {scanned_dir.get('path', '')}")
                    continue
                # Gestisce i "/" nel path e crea un percorso completo
                full_path = base_path.joinpath(*scanned_dir.get('path').split('/'))
                if full_path.exists() and full_path.is_dir():
                    dirs_to_scan.append(full_path)
                    self.logger.info(f"SCAN - Directory scansionata {scanned_dir.get('path', '')}")
                else:
                    self.logger.warning(f"Directory di scansione non valida o inesistente: {full_path}")
            return dirs_to_scan

    def reload_all_config(self):
        """Ricarica la configurazione da file"""
        self.config = reload_generic_config()
        # TODO - Sostituire e permettere configurazioni multiple
        selected_dir_to_scan = self.config.get("paths", {}).get("selected_dir", [])
        for i, scan_info in enumerate(selected_dir_to_scan):
            try:
                self.config['paths']['selected_dir'][i]['scan_config'] = load_config(scan_info.get('scan_config_file', 'scan_config_not_defined'))
            except MissingConfigException as e:
                self.logger.error(f"Errore nel caricare la configurazione della directory #{i+1}: {e}")
                print(f"Errore inatteso nel caricare la configurazione della directory #{i+1}.")
            except Exception as e:
                self.logger.exception(f"Errore inatteso nel caricare la configurazione della directory #{i+1}: {e}")
                print(f"Errore inatteso nel caricare la configurazione della directory #{i+1}.")

class MissingConfigException(Exception):
    pass

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

def reload_scan_config() -> dict:
    scanConfigFile = os.path.join(root_dir, config_dir, scan_config_file)
    return load_config(scanConfigFile)

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