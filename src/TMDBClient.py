import logging
from typing import Dict, Optional
import requests


class TMDBClient:
    """Client per interagire con l'API di TMDB"""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, language: str = "it-IT"):
        self.api_key = api_key
        self.language = language
        self.logging = logging.getLogger(__name__)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Effettua una richiesta all'API TMDB"""
        if params is None:
            params = {}

        params.update({
            'api_key': self.api_key,
            'language': self.language
        })

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logging.warning(f"Errore nella richiesta TMDB: {e}")
            return None

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Cerca un film su TMDB"""
        params = {'query': title}
        if year:
            params['year'] = str(year)
        data = self._make_request('search/movie', params)
        if data and data.get('results'):
            # Restituisce il primo risultato
            result = self.get_best_movie_candidate(params, data)
            self.logging.info(f"Film trovato: {result['title']} ({result.get('release_date', '')[:4]})")
            return result
        self.logging.warning(f"Nessun film trovato per: {title} ({year})")
        return None

    def search_tv_show(self, title: str, file_info: dict) -> Optional[Dict]:
        """Cerca una serie TV su TMDB"""
        params = {'query': title}
        if 'year' in file_info and file_info['year']:
            params['first_air_date_year'] = str(file_info['year'])
        data = self._make_request('search/tv', params)

        if data and data.get('results'):
            result = self.get_best_tv_show_candidate(params, data)
            self.logging.info(f"Serie TV trovata: {result['name']} ({result.get('first_air_date', '')[:4]})")
            return result

        self.logging.warning(f"Nessuna serie TV trovata per: {title}")
        return None

    def get_best_tv_show_candidate(self, search_params: dict, tmdb_data: dict) -> Optional[Dict]:
        # Get first result as best candidate - It's based on tmdb popularity can be not accurate
        # The tmdb name can be different from the original title searched
        return tmdb_data['results'][0]
    def get_best_movie_candidate(self, search_params: dict, tmdb_data: dict) -> Optional[Dict]:
        return tmdb_data['results'][0]

    def get_episode_details(self, tv_id: int, season: int, episode: int) -> Optional[Dict]:
        """Ottiene i dettagli di un episodio"""
        endpoint = f"tv/{tv_id}/season/{season}/episode/{episode}"
        data = self._make_request(endpoint)
        if data:
            self.logging.info(f"Episodio trovato: S{season:02d}E{episode:02d} - {data.get('name', '')}")
        return data