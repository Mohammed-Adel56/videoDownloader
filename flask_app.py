from flask import Flask, render_template, request, jsonify
import yt_dlp
import logging
from flask_cors import CORS
import random
import time
from functools import lru_cache
import requests
from settings import FEATURES
import json
from bs4 import BeautifulSoup
import pickle
from datetime import datetime, timedelta
import base64
import isodate
import urllib.parse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote
from requests.adapters import HTTPAdapter  
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import functools
from requests.adapters import Retry
from requests.sessions import Session





app = Flask(__name__, static_url_path='/static')
CORS(app,resources={r"/*": {"origins": "*"}})
# Enhanced logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = app.logger
API_KEY = 'AIzaSyDD2lvW5RRswUJOLpyE-6l5wZdjkmhmT6Y'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
RATE_LIMIT_REQUESTS = 100  # Quota units per user
RATE_LIMIT_WINDOW = 3600   # 1 hour window
MAX_RETRIES = 3

executor = ThreadPoolExecutor(max_workers=3)
def timeout_handler(timeout):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            future = executor.submit(func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout)
                return result
            except TimeoutError:
                future.cancel()
                raise TimeoutError("Operation timed out")
        return wrapper
    return decorator

@app.route('/')
def home():
    return render_template('index.html', features=FEATURES)
# class YouTubeAPI:
#     def __init__(self, api_key):
#         self.youtube = build(
#             YOUTUBE_API_SERVICE_NAME,
#             YOUTUBE_API_VERSION,
#             developerKey=api_key
#         )
#         self.session = requests.Session()
#         self.session.headers.update({
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#         })
    
#     def extract_video_id(self, url):
#         """Extract video ID from various YouTube URL formats"""
#         import re
#         patterns = [
#             r'(?:v=|\/videos\/|embed\/|youtu.be\/|\/v\/|\/e\/|watch\?v%3D|watch\?feature=player_embedded&v=|%2Fvideos%2F|embed%\u200C\u200B2F|youtu.be%2F|%2Fv%2F)([^#\&\?\n]*)',
#             r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)',
#         ]
        
#         for pattern in patterns:
#             match = re.search(pattern, url)
#             if match:
#                 return match.group(1)
#         return None
#     def get_video_info(self, video_id):
#         """Get video info using a lightweight approach"""
#         try:
#             url = f"https://www.youtube.com/watch?v={video_id}"
#             headers = {
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#             }
#             response = requests.get(url, headers=headers)
            
#             # Extract player_response from page
#             player_response_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', response.text)
#             if not player_response_match:
#                 return None
                
#             return player_response_match.group(1)
#         except Exception as e:
#             logger.error(f"Error getting video info: {str(e)}")
#             return None

#     def get_download_url(self, video_id, itag):
#         """Generate a download URL for the video"""
#         try:
#             video_url = f"https://www.youtube.com/watch?v={video_id}"
#             # Get video webpage
#             headers = {
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#             }
#             response = requests.get(video_url, headers=headers)
            
#             # Find the streaming data
#             streams_match = re.search(r'"streamingData":({.+?}),"playbackTracking"', response.text)
#             if not streams_match:
#                 return None

#             # Extract and decode the URL map
#             streams_data = streams_match.group(1)
#             formats_match = re.findall(r'"formats":(\[.+?\])', streams_data)
#             if not formats_match:
#                 return None

#             # Find the matching format
#             for format_str in formats_match:
#                 if f'"itag":{itag}' in format_str:
#                     url_match = re.search(r'"url":"([^"]+)"', format_str)
#                     if url_match:
#                         url = url_match.group(1)
#                         return urllib.parse.unquote(url.encode('utf-8').decode('unicode-escape'))
            
#             return None
#         except Exception as e:
#             logger.error(f"Error generating download URL: {str(e)}")
#             return None

#     def get_video_details(self, video_id):
#         """Get comprehensive video details using YouTube Data API"""
       
#             # Get video details
#         video_response = self.youtube.videos().list(
#                 part='snippet,contentDetails,statistics,status',
#                 id=video_id
#             ).execute()

#         if not video_response.get('items'):
#                 raise ValueError('Video not found')

#         video = video_response['items'][0]
            
#             # Get available video formats
#         formats = []
            
#         # Define common formats
#         formats = [
#             {
#                 'format_id': '137',
#                 'ext': 'mp4',
#                 'height': 1080,
#                 'quality': '1080p',
#                 'vcodec': 'avc1',
#                 'acodec': 'none'
#             },
#             {
#                 'format_id': '136',
#                 'ext': 'mp4',
#                 'height': 720,
#                 'quality': '720p',
#                 'vcodec': 'avc1',
#                 'acodec': 'none'
#             },
#             {
#                 'format_id': '135',
#                 'ext': 'mp4',
#                 'height': 480,
#                 'quality': '480p',
#                 'vcodec': 'avc1',
#                 'acodec': 'none'
#             },
#             {
#                 'format_id': '134',
#                 'ext': 'mp4',
#                 'height': 360,
#                 'quality': '360p',
#                 'vcodec': 'avc1',
#                 'acodec': 'none'
#             }
#         ]

#         # Check format availability
#         available_formats = []
#         for format_info in formats:
#             test_url = self.get_download_url(video_id, format_info['format_id'])
#             if test_url:
#                 available_formats.append(format_info)

#             # Parse duration
#         duration = isodate.parse_duration(video['contentDetails']['duration'])
#         duration_seconds = int(duration.total_seconds())

#         return {
#                 'title': video['snippet']['title'],
#                 'formats': available_formats,
#                 'duration': duration_seconds,
#                 'thumbnail': video['snippet']['thumbnails']['maxres']['url'] 
#                            if 'maxres' in video['snippet']['thumbnails'] 
#                            else video['snippet']['thumbnails']['high']['url'],
#             }
    
# class YouTubeExtractor:
#     def __init__(self, api_key):
#         self.api_key = api_key
#         self.youtube = build('youtube', 'v3', developerKey=api_key)
#         self.session = requests.Session()
#         self.session.headers.update({
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#             'Accept-Language': 'en-US,en;q=0.9',
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#             'Content-type': 'application/json',
#             'Origin': 'https://www.youtube.com',
#             'Referer': 'https://www.youtube.com/',
#              'Cookie': 'CONSENT=YES+1'  # Add consent cookie by default
#         })




    



#     def login(self, cookies):
#         """
#         Set authentication cookies for YouTube
        
#         Args:
#             cookies: Dictionary containing authentication cookies
#                     (Usually needs 'SAPISID', 'HSID', 'SSID', 'APISID', 'SID')
#         """
#         try:
#             for name, value in cookies.items():
#                 self.session.cookies.set(name, value, domain='.youtube.com')
#             return True
#         except Exception as e:
#             logger.error(f"Failed to set authentication cookies: {str(e)}")
#             return False

#     def _get_consent_cookie(self) :
#         """Get initial consent cookie if needed"""
#         try:
#             response = self.session.get('https://www.youtube.com/')
#             if 'CONSENT' not in self.session.cookies:
#                 self.session.cookies.set('CONSENT', 'YES+1', domain='.youtube.com')
#         except Exception as e:
#             logger.error(f"Failed to get consent cookie: {str(e)}")


    
#     def _extract_player_config(self, video_id: str, attempt_bypass: bool = True) -> Optional[Dict[str, Any]]:
#         """
#         Extract player configuration data from YouTube page
        
#         Args:
#             video_id: YouTube video ID
#             attempt_bypass: Whether to attempt bypassing login requirement
#         """
#         try:
#             if self.use_cookies:
#                 self._get_consent_cookie()

#             url = f"https://www.youtube.com/watch?v={video_id}"
            
#             # Try different request configurations
#             headers_variations = [
#                 {'Cookie': 'CONSENT=YES+1'},
#                 {'Cookie': 'CONSENT=YES+1; VISITOR_INFO1_LIVE=yes'},
#                 {'Cookie': ''},
#             ]

#             for headers in headers_variations:
#                 try:
#                     response = self.session.get(url, headers=headers)
#                     response.raise_for_status()
                    
#                     html = response.text
#                     config = self._parse_player_config(html)
                    
#                     if config:
#                         # Check if login is required
#                         playability_status = config.get('playabilityStatus', {})
#                         if playability_status.get('status') == 'LOGIN_REQUIRED':
#                             if attempt_bypass:
#                                 bypass_config = self._attempt_bypass(video_id)
#                                 if bypass_config:
#                                     return bypass_config
                            
#                             # If bypass failed or wasn't attempted, return the login required config
#                             return config
#                         return config
#                 except requests.RequestException:
#                     continue

#             raise ValueError("Could not extract player config after all attempts")
#         except Exception as e:
#             logger.error(f"Error extracting player config for video {video_id}: {str(e)}")
#             return None

#     def _parse_player_config(self, html: str) -> Optional[Dict[str, Any]]:
#         """Parse the player configuration from HTML"""
#         try:
#             soup = BeautifulSoup(html, 'html.parser')

#             # Try multiple patterns to find the config
#             patterns = [
#                 r'ytInitialPlayerResponse\s*=\s*({.+?});',
#                 r'ytplayer\.config\s*=\s*({.+?});',
#                 r'ytcfg\.set\(({.+?})\);'
#             ]

#             # First try in script tags
#             for script in soup.find_all('script'):
#                 if not script.string:
#                     continue
                
#                 for pattern in patterns:
#                     match = re.search(pattern, script.string)
#                     if match:
#                         return json.loads(match.group(1))

#             # Then try in the whole HTML
#             for pattern in patterns:
#                 match = re.search(pattern, html)
#                 if match:
#                     return json.loads(match.group(1))

#             return None
#         except Exception as e:
#             logger.error(f"Error parsing player config: {str(e)}")
#             return None

#     def _attempt_bypass(self, video_id: str) -> Optional[Dict[str, Any]]:
#         """Attempt to bypass login requirement using alternative methods"""
#         try:
#             # Try embedding endpoint
#             embed_url = f"https://www.youtube.com/embed/{video_id}"
#             response = self.session.get(embed_url)
#             response.raise_for_status()
            
#             config = self._parse_player_config(response.text)
#             if config and config.get('playabilityStatus', {}).get('status') != 'LOGIN_REQUIRED':
#                 return config

#             # Try mobile endpoint
#             mobile_url = f"https://m.youtube.com/watch?v={video_id}"
#             response = self.session.get(mobile_url, 
#                                      headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'})
#             response.raise_for_status()
            
#             return self._parse_player_config(response.text)
#         except Exception as e:
#             logger.error(f"Bypass attempt failed: {str(e)}")
#             return None

#     def extract_video_id(self, url):
#         """Extract video ID from various YouTube URL formats"""
#         logger.debug(f"Extracting video ID from URL: {url}")
        
#         patterns = [
#             r'(?:v=|\/videos\/|embed\/|youtu.be\/|\/v\/|\/e\/|watch\?v%3D|watch\?feature=player_embedded&v=|%2Fvideos%2F|embed%\u200C\u200B2F|youtu.be%2F|%2Fv%2F)([^#\&\?\n]*)',
#             r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?([^#\&\?\n]*)'
#         ]
        
#         for pattern in patterns:
#             match = re.search(pattern, url)
#             if match:
#                 video_id = match.group(1)
#                 logger.debug(f"Successfully extracted video ID: {video_id}")
#                 return video_id
                
#         logger.error(f"Failed to extract video ID from URL: {url}")
#         return None
        
#     def _extract_player_config(self, video_id):
#         """Extract player configuration data from page HTML"""
#         try:
#             url = f"https://www.youtube.com/watch?v={video_id}"
#             response = self.session .get(url)
#             response.raise_for_status()
#             html = response.text

#             soup = BeautifulSoup(html, 'html.parser')

#             # Try to find the config in a script tag
#             for script in soup.find_all('script'):
#                 if 'ytInitialPlayerResponse' in script.text:
#                     match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', script.string)
#                     if match:
#                         return json.loads(match.group(1))

#             # Fallback to searching in the entire HTML
#             player_response_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
#             if player_response_match:
#                 return json.loads(player_response_match.group(1))

#             # Second fallback to ytplayer.config
#             player_config_match = re.search(r'ytplayer\.config\s*=\s*({.+?});', html)
#             if player_config_match:
#                 return json.loads(player_config_match.group(1))

#             raise ValueError("Could not find player config")
#         except Exception as e:
#             logger.error(f"Error extracting player config: {str(e)}")
#             return None
#     def get_stream_data(self, video_id):
#         """Get stream data including download URLs"""
#         config = self._extract_player_config(video_id)

#         return config
        
#         # if not config:
#         #     raise ValueError("Failed to extract player config")

#         # # Handle login required case
#         # if config.get('playabilityStatus', {}).get('status') == 'LOGIN_REQUIRED':
#         #     raise ValueError("Video requires login to access")

#         # # Extract streaming data
#         # streaming_data = {}
        
#         # if 'streamingData' in config:
#         #     streaming_data['formats'] = config['streamingData'].get('formats', [])
#         #     streaming_data['adaptiveFormats'] = config['streamingData'].get('adaptiveFormats', [])
        
#         # # Extract video details
#         # if 'videoDetails' in config:
#         #     streaming_data['videoDetails'] = {
#         #         'title': config['videoDetails'].get('title'),
#         #         'lengthSeconds': config['videoDetails'].get('lengthSeconds'),
#         #         'channelId': config['videoDetails'].get('channelId'),
#         #         'viewCount': config['videoDetails'].get('viewCount')
#         #     }

#         # # Extract player config
#         # streaming_data['playabilityStatus'] = config.get('playabilityStatus', {})
        
#         # return streaming_data
#     def get_video_info(self, url):
#         """Main method to get all video information"""
#         try:
#             video_id = self.extract_video_id(url)
#             if not video_id:
#                 logger.error("Invalid video ID")
#                 return None

#             # Get video metadata from API
#             logger.debug(f"Fetching metadata for video ID: {video_id}")
#             video_response = self.youtube.videos().list(
#                 part='snippet,contentDetails,statistics,status',
#                 id=video_id
#             ).execute()

#             if not video_response.get('items'):
#                 logger.error("No video items found in API response")
#                 return None

#             video = video_response['items'][0]
#             duration = isodate.parse_duration(video['contentDetails']['duration'])

#             # logger.debug(video)
#             # Get video page
#             logger.debug("Fetching video page")
#             # page_response = self.session.get(f"https://www.youtube.com/watch?v={video_id}")
#             # if not page_response.ok:
#             #     logger.error(f"Failed to fetch video page. Status: {page_response.status_code}")
#             #     return None

#             # Extract player config
#             player_config = self.get_stream_data(video_id)
#             if not player_config:
#                 logger.error("Failed to extract player config")
#                 return None
#             # # Get available video formats
#             # formats = []
            
#             # # Standard quality options
#             # quality_options = [
#             #     {'quality': '1080p', 'itag': '137', 'format': 'mp4'},
#             #     {'quality': '720p', 'itag': '22', 'format': 'mp4'},
#             #     {'quality': '480p', 'itag': '135', 'format': 'mp4'},
#             #     {'quality': '360p', 'itag': '18', 'format': 'mp4'},
#             #     {'quality': '240p', 'itag': '133', 'format': 'mp4'}
#             # ]
           
#             # Check video availability and restrictions
#             # if video['status']['embeddable']:
#             #     print("************************")
#             #     logger.debug(video["status"]["embeddable"])
#             #     formats.extend([
#             #         {
#             #             'format_id': opt['itag'],
#             #             'ext': opt['format'],
#             #             'height': int(opt['quality'].replace('p', '')),
#             #             'quality': opt['quality'],
#             #             'vcodec': 'avc1',
#             #             'acodec': 'mp4a.40.2',

#             #         }
#             #         for opt in quality_options
#             #     ])

#             # Extract formats
#              # Generate download links for different qualities
#             # formats = [
#             #     {"format_id": "18", "ext": "mp4", "height": 360, "quality": "360p"},
#             #     {"format_id": "22", "ext": "mp4", "height": 720, "quality": "720p"},
#             #     {"format_id": "137", "ext": "mp4", "height": 1080, "quality": "1080p"},
#             # ]

#             # for format in formats:
#             #     format['url'] = f"https://www.youtube.com/watch?v={video_id}&format={format['format_id']}"
#             formats = []
#             streaming_data = player_config
            
#             logger.debug("Processing formats")
#             return {
                
#                 "title": video['snippet']['title'],
#                 "duration": int(duration.total_seconds()),
#                 "thumbnail": video['snippet']['thumbnails']['maxres']['url'] 
#                            if 'maxres' in video['snippet']['thumbnails'] 
#                            else video['snippet']['thumbnails']['high']['url'],
#                 "formats":streaming_data
#             }
            
#             # Process adaptive formats
#             # for format_data in streaming_data.get('adaptiveFormats', []):
#             #     try:
#             #         if format_data.get('mimeType', '').startswith('video/mp4'):
#             #             height = format_data.get('height', 0)
#             #             url = format_data.get('url')
                        
#             #             if not url and 'signatureCipher' in format_data:
#             #                 cipher_data = dict(urllib.parse.parse_qs(format_data['signatureCipher']))
#             #                 url = cipher_data.get('url', [''])[0]
                        
#             #             if url and height:
#             #                 formats.append({
#             #                     'format_id': format_data.get('itag'),
#             #                     'ext': 'mp4',
#             #                     'height': height,
#             #                     'quality': f'{height}p',
#             #                     'url': url,
#             #                     'vcodec': 'avc1',
#             #                     'acodec': 'none'
#             #                 })
#             #     except Exception as e:
#             #         logger.error(f"Error processing format: {str(e)}")
#             #         continue

#             # # Process formats
#             # for format_data in streaming_data.get('formats', []):
#             #     try:
#             #         if format_data.get('mimeType', '').startswith('video/mp4'):
#             #             height = format_data.get('height', 0)
#             #             url = format_data.get('url')
                        
#             #             if not url and 'signatureCipher' in format_data:
#             #                 cipher_data = dict(urllib.parse.parse_qs(format_data['signatureCipher']))
#             #                 url = cipher_data.get('url', [''])[0]
                        
#             #             if url and height:
#             #                 formats.append({
#             #                     'format_id': format_data.get('itag'),
#             #                     'ext': 'mp4',
#             #                     'height': height,
#             #                     'quality': f'{height}p',
#             #                     'url': url,
#             #                     'vcodec': 'avc1',
#             #                     'acodec': 'mp4a.40.2'
#             #                 })
#             #     except Exception as e:
#             #         logger.error(f"Error processing format: {str(e)}")
#             #         continue
#             # return {
                
#             #     "title": video['snippet']['title'],
#             #     "duration": int(duration.total_seconds()),
#             #     "thumbnail": video['snippet']['thumbnails']['maxres']['url'] 
#             #                if 'maxres' in video['snippet']['thumbnails'] 
#             #                else video['snippet']['thumbnails']['high']['url'],
#             #     "formats":formats
#             # }

#             # Remove duplicates and sort
#             # seen = set()
#             # unique_formats = []
#             # for f in formats:
#             #     quality = f['quality']
#             #     if quality not in seen:
#             #         seen.add(quality)
#             #         unique_formats.append(f)

#             # unique_formats.sort(key=lambda x: x['height'], reverse=True)
            
#             # logger.debug(f"Successfully extracted {len(unique_formats)} formats")

#             # return {
#             #     'title': video['snippet']['title'],
#             #     'duration': int(duration.total_seconds()),
#             #     'thumbnail': video['snippet']['thumbnails']['maxres']['url'] 
#             #                if 'maxres' in video['snippet']['thumbnails'] 
#             #                else video['snippet']['thumbnails']['high']['url'],
#             #     'formats': unique_formats
#             # }

#         except Exception as e:
#             logger.error(f"Error in get_video_info: {str(e)}", exc_info=True)
#             return None
class YouTubeExtractor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.session = requests.Session()
        self.timeout = 15  # Increased timeout
        self._setup_session()
        
        # Setup detailed logging
        # self.logger = logging.getLogger(__name__)
        # self.logger.setLevel(logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def _get_rotating_headers(self):
        """Generate different header combinations to avoid detection"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Origin': 'https://www.youtube.com',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
            'DNT': '1'
        }
        
        # self.logger.debug(f"Generated headers: {headers}")
        return headers

    def _setup_session(self):
        """Setup session with retry mechanism"""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update(self._get_rotating_headers())
        
        # Set required cookies with longer expiry
        cookies = {
            'CONSENT': 'YES+1',
            'VISITOR_INFO1_LIVE': str(random.randint(100000, 999999)),
            'PREF': f'f4={random.randint(4000, 8000)}&hl=en',
            'GPS': '1'
        }
        
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.youtube.com')

    def safe_request(self, url, method='get', **kwargs):
        """Make a safe request with retries and error handling"""
        try:
            kwargs['timeout'] = kwargs.get('timeout', self.timeout)
            response = getattr(self.session, method)(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.Timeout:
            self.logger.error(f"Timeout occurred while requesting {url}")
            raise
        except requests.RequestException as e:
            self.logger.error(f"Request failed for {url}: {str(e)}")
            raise
    def _parse_player_config(self, html):
        """Parse the player configuration from HTML with improved patterns"""
        try:
            # self.logger.debug("Starting player config extraction")
            
            # Method 1: Direct ytInitialPlayerResponse
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
            if match:
                # self.logger.debug("Found ytInitialPlayerResponse")
                return json.loads(match.group(1))
                

            # Method 2: From ytInitialData
            match = re.search(r'ytInitialData\s*=\s*({.+?});', html)
            if match:
                # self.logger.debug("Found ytInitialData")
                    data = json.loads(match.group(1))
                    if 'playerResponse' in data:
                        return data['playerResponse']
                

            # Method 3: From script tags
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script'):
                if script.string and 'ytInitialPlayerResponse' in script.string:
                    match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', script.string)
                    if match:
                        # self.logger.debug("Found ytInitialPlayerResponse in script tag")
                        return json.loads(match.group(1))
                        

            # self.logger.warning("No valid player config found")

            
        except Exception as e:
            # self.logger.error(f"Error in _parse_player_config: {str(e)}")
            return None

    def _extract_formats_from_config(self, config):
        """Safer format extraction with validation"""
        if not config or not isinstance(config, dict):
            return []

        formats = []
        try:
            streaming_data = config.get('streamingData', {})
            if not streaming_data:
                return formats

            for format_list_name in ['adaptiveFormats', 'formats']:
                format_list = streaming_data.get(format_list_name, [])
                
                for format_data in format_list:
                    try:
                        if not isinstance(format_data, dict):
                            continue

                        # Validate required fields
                        mime_type = format_data.get('mimeType', '')
                        if not mime_type.startswith('video/'):
                            continue

                        format_info = {
                            'format_id': format_data.get('itag'),
                            'ext': mime_type.split('/')[-1].split(';')[0],
                            'height': format_data.get('height', 0),
                            'quality': format_data.get('qualityLabel', f"{format_data.get('height', 0)}p"),
                            'vcodec': format_data.get('codecs', '').split('.')[0],
                            'acodec': 'mp4a.40.2' if format_list_name == 'formats' else 'none',
                            'url': None
                        }

                        # Safe URL extraction
                        if 'url' in format_data:
                            format_info['url'] = format_data['url']
                        elif 'signatureCipher' in format_data:
                            cipher_data = parse_qs(format_data['signatureCipher'])
                            if cipher_data.get('url'):
                                base_url = unquote(cipher_data['url'][0])
                                signature = unquote(cipher_data.get('s', [''])[0])
                                sp = cipher_data.get('sp', ['signature'])[0]
                                
                                format_info['url'] = f"{base_url}&{sp}={signature}" if signature else base_url

                        # Validate format_info before adding
                        if format_info['url'] and all(k in format_info for k in [
                            'format_id', 'ext', 'height', 'quality', 'vcodec', 'acodec'
                        ]):
                            formats.append(format_info)

                    except Exception as e:
                        self.logger.warning(f"Error processing format: {str(e)}")
                        continue

            return formats

        except Exception as e:
            self.logger.error(f"Error extracting formats: {str(e)}")
            return formats

    def extract_video_id(self, url):
        """Extract video ID from various YouTube URL formats"""
        import re
        patterns = [
            r'(?:v=|\/videos\/|embed\/|youtu.be\/|\/v\/|\/e\/|watch\?v%3D|watch\?feature=player_embedded&v=|%2Fvideos%2F|embed%\u200C\u200B2F|youtu.be%2F|%2Fv%2F)([^#\&\?\n]*)',
            r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_video_info(self, url, max_retries=3):
        """Enhanced video info extraction with better error handling"""
        start_time = time.time()
        self.logger.info(f"Starting video extraction for URL: {url}")
        
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                raise ValueError("Could not extract video ID")

            # First try to get video metadata from API
            for attempt in range(max_retries):
                try:
                    # API request with timeout
                    video_response = self.youtube.videos().list(
                        part='snippet,contentDetails',
                        id=video_id
                    ).execute()

                    if not video_response.get('items'):
                        raise ValueError("No video found in API response")

                    video = video_response['items'][0]
                    snippet = video.get('snippet', {})
                    content_details = video.get('contentDetails', {})

                    # Validate required fields
                    if not snippet or not content_details:
                        raise ValueError("Missing required video metadata")

                    # Get thumbnail with validation
                    thumbnails = snippet.get('thumbnails', {})
                    thumbnail_url = None
                    for quality in ['maxres', 'high', 'medium', 'default']:
                        thumb = thumbnails.get(quality, {})
                        if thumb and thumb.get('url'):
                            thumbnail_url = thumb['url']
                            break
                    
                    if not thumbnail_url:
                        raise ValueError("No thumbnail URL found")

                    # Try different URL patterns with timeouts
                    formats = None
                    urls_to_try = [
                        f"https://www.youtube.com/watch?v={video_id}",
                        f"https://www.youtube.com/embed/{video_id}"
                    ]

                    for url_to_try in urls_to_try:
                        try:
                            response = self.safe_request(
                                url_to_try,
                                headers=self._get_rotating_headers()
                            )
                            
                            config = self._parse_player_config(response.text)
                            if config:
                                formats = self._extract_formats_from_config(config)
                                if formats:
                                    break
                                
                        except Exception as e:
                            self.logger.warning(f"Failed to extract from {url_to_try}: {str(e)}")
                            continue

                    if not formats:
                        raise ValueError("Could not extract video formats")

                    # Create result with validation
                    try:
                        duration = isodate.parse_duration(content_details.get('duration', 'PT0S'))
                        result = {
                            'title': snippet.get('title', 'Untitled'),
                            'duration': int(duration.total_seconds()),
                            'thumbnail': thumbnail_url,
                            'formats': formats
                        }
                        
                        # Validate result
                        if not all(k in result for k in ['title', 'duration', 'thumbnail', 'formats']):
                            raise ValueError("Missing required fields in result")
                            
                        self.logger.info(f"Successfully extracted video info in {time.time() - start_time:.2f}s")
                        return result

                    except (ValueError, AttributeError) as e:
                        raise ValueError(f"Error creating result: {str(e)}")

                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(min(2 ** attempt, 8))  # Cap maximum sleep time
                    else:
                        raise

        except Exception as e:
            self.logger.error(f"Failed to extract video info: {str(e)}")
            return None

class CustomYTDLP(yt_dlp.YoutubeDL):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.success_count = 0
        self.last_request_time = 0
        
    def _download_webpage(self, *args, **kwargs):
        # Add delay between requests
        current_time = time.time()
        if self.last_request_time:
            time_diff = current_time - self.last_request_time
            if time_diff < 2:  # Minimum 2 second delay between requests
                time.sleep(2 - time_diff)
        
        self.last_request_time = time.time()
        return super()._download_webpage(*args, **kwargs)

# youtube_api = YouTubeAPI(API_KEY)

def check_rate_limit(request):
    """Rate limiting with IP-based quota tracking"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    client_ip = base64.b64encode(client_ip.encode()).decode()
    
    current_time = time.time()
    
    if not hasattr(app, 'rate_limit_cache'):
        app.rate_limit_cache = {}
        
    # Clean up old entries
    app.rate_limit_cache = {
        k: v for k, v in app.rate_limit_cache.items() 
        if current_time - v['timestamp'] < RATE_LIMIT_WINDOW
    }
    
    if client_ip not in app.rate_limit_cache:
        app.rate_limit_cache[client_ip] = {
            'quota': RATE_LIMIT_REQUESTS - 1,
            'timestamp': current_time
        }
        return True
        
    if current_time - app.rate_limit_cache[client_ip]['timestamp'] < RATE_LIMIT_WINDOW:
        if app.rate_limit_cache[client_ip]['quota'] <= 0:
            return False
        app.rate_limit_cache[client_ip]['quota'] -= 1
    else:
        app.rate_limit_cache[client_ip] = {
            'quota': RATE_LIMIT_REQUESTS - 1,
            'timestamp': current_time
        }
    
    return True

def get_rotating_user_agent():
    """Rotate between different user agents to avoid detection."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    return random.choice(user_agents)

@lru_cache(maxsize=100)
def get_video_info(url):
    """Extract video metadata with enhanced error handling and anti-bot measures."""
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'format': 'best',
                'http_headers': {
                    'User-Agent': get_rotating_user_agent(),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Sec-Fetch-Dest': 'document',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'config', 'js'],
                        'skip': ['hls', 'dash']
                    }
                },
                'socket_timeout': 30,
                'retries': 5,
                'nocheckcertificate': True,
                'ignoreerrors': False
            }

            with CustomYTDLP(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    if "Sign in to confirm you're not a bot" in str(e):
                        # Try alternative extraction method
                        ydl_opts.update({
                            'extractor_args': {
                                'youtube': {
                                    'player_client': ['tv_embedded', 'android'],
                                    'player_skip': ['webpage'],
                                    'skip': ['hls']
                                }
                            }
                        })
                        # Add delay before retry
                        time.sleep(random.uniform(2, 4))
                        with CustomYTDLP(ydl_opts) as ydl_retry:
                            info = ydl_retry.extract_info(url, download=False)
                    else:
                        raise

                if info is None:
                    return None

                # Process formats with validation
                formats = []
                seen_qualities = set()
                
                for f in info.get('formats', []):
                    if not isinstance(f, dict):
                        continue
                        
                    if f.get('vcodec') == 'none':
                        continue
                        
                    height = f.get('height', 0)
                    if not isinstance(height, (int, float)) or height <= 0:
                        continue
                        
                    quality = f"{height}p"
                    if quality in seen_qualities:
                        continue
                        
                    seen_qualities.add(quality)
                    
                    formats.append({
                        'format_id': f['format_id'],
                        'ext': f.get('ext', 'mp4'),
                        'height': height,
                        'filesize': f.get('filesize', 0),
                        'tbr': f.get('tbr', 0),
                        'quality': quality,
                        'vcodec': f.get('vcodec', ''),
                        'acodec': f.get('acodec', '')
                    })

                formats.sort(key=lambda x: x['height'], reverse=True)
                
                # Validate required fields
                title = info.get('title')
                if not title or not isinstance(title, str):
                    title = 'Untitled'
                
                thumbnail = info.get('thumbnail', '')
                if not isinstance(thumbnail, str):
                    thumbnail = ''
                
                duration = info.get('duration', 0)
                if not isinstance(duration, (int, float)):
                    duration = 0
                
                return {
                    'title': title,
                    'formats': formats,
                    'duration': duration,
                    'thumbnail': thumbnail
                }

        except Exception as e:
            retry_count += 1
            error_message = str(e)
            
            if retry_count >= max_retries:
                if "Sign in to confirm you're not a bot" in error_message:
                   return None
                elif "This video is private" in error_message:
                   return None
                elif "Video unavailable" in error_message:
                    return None
                else:
                    logger.error(f"Error extracting info: {error_message}")
                    return None
            
            # Add exponential backoff delay before retry
            time.sleep(2 ** retry_count)


@app.route("/download", methods=["POST"])
def download():
    """Enhanced download endpoint using YouTube Data API"""

    video_url = request.form.get("video_url")
    if not video_url:
        return jsonify({"error": "No video URL provided"}), 400
        
    try:
        @timeout_handler(timeout=25)  # 25 second timeout
        def extract_info(url):
            extractor = YouTubeExtractor(API_KEY)
            return extractor.get_video_info(url)    
        # if not check_rate_limit(request):
        #     return jsonify({
        #         "error": "Rate limit exceeded",
        #         "retry_after": RATE_LIMIT_WINDOW,
        #         "message": "Please try again later"
        #     }), 429
        video_data = get_video_info(video_url)
        if video_data:
            # return jsonify(video_data)
            return render_template(
            "download.html",
            title=video_data["title"],
            thumbnail=video_data["thumbnail"],
            quality_options=video_data["formats"],
            features=FEATURES,
            video_url=video_url
            )
        else :
            logger.info(f"Processing download request for URL: {video_url}")
            video_data = extract_info(video_url)

        # if not video_data:
        #     return jsonify({
        #         "error": "Video processing failed",
        #         "message": "Unable to extract video information. Please check the URL and try again."
        #     }), 400

        # if not video_data.get('formats'):
        #     return jsonify({
        #         "error": "No formats available",
        #         "message": "No downloadable formats found for this video."
        #     }), 400

            logger.info(f"Successfully processed video: {video_data['title']}")
            logger.debug(f"Available formats: {json.dumps(video_data['formats'], indent=2)}")
            return jsonify(video_data)
        # return render_template(
        #     "download.html",
        #     title=video_data["title"],
        #     thumbnail=video_data["thumbnail"],
        #     quality_options=video_data["formats"],
        #     features=FEATURES,
        #     video_url=video_url
        #  )
            # if not video_data:
            #     return jsonify({
            #         "error": "Invalid YouTube URL",
            #         "message": "Please provide a valid YouTube video URL"
            #     }), 400
            
            # video_data = youtube_api.get_video_details(video_id)
            
            # if not video_data.get('formats'):
            #     return jsonify({
            #         "error": "No downloadable formats",
            #         "message": "This video might be restricted or unavailable"
            #     }), 400
                
            # return jsonify(video_data)
            # return render_template(
            # "download.html",
            # title=video_data["title"],
            # thumbnail=video_data["thumbnail"],
            # quality_options=video_data["formats"],
            # features=FEATURES,
            # video_url=video_url
            # )
        
    except HttpError as e:
        error_message = str(e)
        logger.error(f"YouTube API error: {error_message}")
        
        if e.resp.status == 403:
            return jsonify({
                "error": "API quota exceeded",
                "message": "Please try again later"
            }), 429
        elif e.resp.status == 404:
            return jsonify({
                "error": "Video not found",
                "message": "The requested video does not exist or is private"
            }), 404
        else:
            return jsonify({
                "error": "YouTube API error",
                "message": "Please try again later"
            }), 500
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Download error: {error_message}")
        return jsonify({
            "error": "Failed to process video",
            "message": "Please try again later"
        }), 500

if __name__ == '__main__':
    app.run(debug=False)    