import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Telegram Bot Token
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # TMDB API Configuration
    TMDB_API_KEY = os.getenv('TMDB_API_KEY')
    TMDB_BASE_URL = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
    
    # Database configuration
    DATABASE_NAME = 'movie_bot.db'
    
    # Bot settings
    MAX_HISTORY_ENTRIES = 10
    MOVIES_PER_PAGE = 5

# Validate required environment variables
required_vars = ['BOT_TOKEN', 'TMDB_API_KEY']
for var in required_vars:
    if not getattr(Config, var):
        raise ValueError(f"Missing required environment variable: {var}")
