import hashlib
import json
import logging
import os
import re
from pathlib import Path


class Preparser:

    def __init__(self, config: dict, scan_config: dict, file_info: dict, file_processing: dict):
        self.file_info = file_info
        self.config = config
        self.scan_config = scan_config
        self.file_processing = file_processing
        self.logger = logging.getLogger(__name__)

    def preparse(self):
            """
            Preparse file information to standardize titles and years
            :return: Updated file_info dictionary
            """
            for pattern_name in self.file_info.get('processing_patterns', []):
                pattern_rules = self.scan_config.get('patterns', {}).get(pattern_name, {})
                self.check_skip()
                for pattern in pattern_rules:
                    pattern_result = self.apply_pattern_rule(pattern)
                    # Salva solo i pattern applicati o con errori
                    if pattern_result.get('applied', False) or pattern_result.get('error'):
                        self.file_processing['preprocessing_outcome'].append(pattern_result)
                    # Se il file è stato marcato come ignorato, esce dal ciclo
                    self.check_skip()
                    if self.file_info.get('ignore', False):
                        break


    def check_skip(self):
        """Controlla se il file deve essere ignorato"""
        if self.file_info.get('ignore', False):
            self.logger.info(f"File ignorato in base alla configurazione: {self.file_info['path'].name}")
            self.file_processing['skipped'] = True
            self.file_processing['processing_outcome'] = {'outcome': True, 'error': 'File ignorato durante pre-processing'}

    def apply_pattern_rule(self, pattern: dict) -> dict:
        result = {
            'pattern': pattern.get('name') or pattern.get('regex') or 'unnamed',
            'id': hashlib.sha256(json.dumps(pattern, sort_keys=True).encode('utf-8')).hexdigest(),
            'applied': False,
            'error': None
        }
        try:
            if not self.in_episode_range(pattern):
                return result
            if pattern.get('regex') and pattern.get('ignore'):
                if re.search(pattern.get('regex'), self.file_info['path'].stem):
                    self.file_info['ignore'] = True
                    result['applied'] = True
            if pattern.get('regex') and pattern.get('substitution'):
                result['applied'] = self.regex_rename(pattern)
            if pattern.get('regex') and pattern.get('year'):
                if re.search(pattern.get('regex'), self.file_info['path'].stem):
                    # Aggiunge o modifica l'anno nel file_info
                    self.file_info['year'] = pattern.get('year')
                    result['applied'] = True
        except re.error as e:
            self.logger.error(f"Errore nell'applicare la regola di rinomina: {e}")
            result['error'] = str(e)
        except Exception as e:
            self.logger.exception(f"Errore inatteso nell'applicare la regola di rinomina: {e}")
            result['error'] = str(e)
        return result

    def in_episode_range(self, pattern) -> bool:
        """Verifica se un file è nell'intervallo di episodi specificato nella regola"""
        if 'from_episode' not in pattern and 'to_episode' not in pattern:
            # No episode selection required
            return True
        else:
            # Compare episode number if available
            if 'regex' in pattern:
                episode = None
                match = re.search(pattern.get('regex'), self.file_info['path'].stem)
                if not match:
                    # This pattern does not match the file
                    return False
                elif 'episode' in match.groupdict():
                    episode = self.file_info.get('episode') or int(match.group('episode'))
                else:
                    self.logger.warning("No <episode> group found in regex for episode range check.")
                    return False
            else:
                self.logger.warning("No regex defined to identify episode.")
                return False

            # Check episode range
            if episode is not None:
                from_ep = pattern.get('from_episode', 1)
                to_ep = pattern.get('to_episode', float('inf'))
                if from_ep <= episode <= to_ep:
                    return True
                else:
                    return False
            self.logger.warning(f"Impossibile estrarre il numero dell'episodio per la regola: {pattern.get('name') or pattern.get('regex')}")
            return False

    def regex_rename(self, rename_rule) -> bool:
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
        match = re.search(rename_rule.get('regex'), self.file_info['path'].stem)
        if not match:
            self.logger.debug("Nessuna corrispondenza trovata per la regola di rinomina.")
            return False
        else:
            folder_info = {}
            if "folder_regex" in rename_rule:
                # Estrae informazioni dalla cartella padre
                folder_match = re.match(rename_rule.get('folder_regex'), os.path.basename(os.path.dirname(self.file_info['path'])))
                if folder_match:
                    folder_info = folder_match.groupdict()
            self.logger.debug(f"Applicando regola di rinomina: {rename_rule.get('regex')} -> {rename_rule.get('substitution')}")
            try:
                rename_rule = re.sub(rename_rule.get('regex'), repl, self.file_info['path'].stem)
            except re.error as e:
                self.logger.error(f"Errore nella sostituzione della regola di rinomina: {e}")
                return False
            except KeyError as e:
                self.logger.error(f"Valori mancanti per la rinomina [{', '.join(e.args)}]")
                return False
            self.file_info['path'] = Path(str(os.path.join(self.file_info['path'].parent, rename_rule + self.file_info['path'].suffix)))
            return True