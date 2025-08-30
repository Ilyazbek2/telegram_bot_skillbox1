import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from datetime import datetime, timedelta
import config
from models import User, SearchHistory, MovieResult, UserMovieStatus, database

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MovieBot:
    def __init__(self):
        self.config = config.Config
        self.app = Application.builder().token(self.config.BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("history", self.history))
        self.app.add_handler(CommandHandler("movie_search", self.movie_search_command))
        self.app.add_handler(CommandHandler("movie_by_rating", self.movie_by_rating_command))
        self.app.add_handler(CommandHandler("low_budget_movie", self.low_budget_movie_command))
        self.app.add_handler(CommandHandler("high_budget_movie", self.high_budget_movie_command))
        
        # Callback query handlers
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def get_or_create_user(self, update: Update):
        user_data = update.effective_user
        user, created = User.get_or_create(
            telegram_id=user_data.id,
            defaults={
                'username': user_data.username,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name
            }
        )
        return user

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when the command /start is issued."""
        user = await self.get_or_create_user(update)
        
        welcome_text = (
            "🎬 Добро пожаловать в Movie Search Bot! 🎬\n\n"
            "Я помогу вам найти информацию о фильмах и сериалах.\n\n"
            "Доступные команды:\n"
            "/movie_search - Поиск фильма по названию\n"
            "/movie_by_rating - Поиск фильмов по рейтингу\n"
            "/low_budget_movie - Фильмы с низким бюджетом\n"
            "/high_budget_movie - Фильмы с высоким бюджетом\n"
            "/history - История поиска\n"
            "/help - Справка по командам\n\n"
            "Просто отправьте мне название фильма для быстрого поиска!"
        )
        
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message."""
        help_text = (
            "📖 Справка по командам:\n\n"
            "🔍 /movie_search [название] - Поиск фильма по названию\n"
            "⭐ /movie_by_rating [мин.рейтинг] [жанр] - Фильмы по рейтингу\n"
            "💸 /low_budget_movie [жанр] - Фильмы с низким бюджетом\n"
            "💰 /high_budget_movie [жанр] - Фильмы с высоким бюджетом\n"
            "📋 /history - Показать историю поиска\n\n"
            "Примеры:\n"
            "/movie_search Матрица\n"
            "/movie_by_rating 8.0 фантастика\n"
            "/low_budget_movie комедия\n"
            "/high_budget_movie фантастика"
        )
        await update.message.reply_text(help_text)

    async def search_movies_by_title(self, query: str, page: int = 1):
        """Search movies by title using TMDB API."""
        url = f"{self.config.TMDB_BASE_URL}/search/movie"
        params = {
            'api_key': self.config.TMDB_API_KEY,
            'query': query,
            'page': page,
            'language': 'ru-RU'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error searching movies: {e}")
            return None

    async def search_movies_by_rating(self, min_rating: float, genre: str = None, page: int = 1):
        """Search movies by rating with optional genre filter."""
        url = f"{self.config.TMDB_BASE_URL}/discover/movie"
        params = {
            'api_key': self.config.TMDB_API_KEY,
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 100,  # Minimum votes to avoid low-rated movies
            'vote_average.gte': min_rating,
            'page': page,
            'language': 'ru-RU'
        }
        
        if genre:
            # Get genre ID from name
            genre_id = await self.get_genre_id(genre)
            if genre_id:
                params['with_genres'] = genre_id
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error searching movies by rating: {e}")
            return None

    async def search_movies_by_budget(self, budget_type: str, genre: str = None, page: int = 1):
        """Search movies by budget (low or high)."""
        url = f"{self.config.TMDB_BASE_URL}/discover/movie"
        
        if budget_type == 'low':
            sort_by = 'budget.asc'
        else:  # high
            sort_by = 'budget.desc'
        
        params = {
            'api_key': self.config.TMDB_API_KEY,
            'sort_by': sort_by,
            'budget.gte': 1000,  # Minimum budget to avoid invalid data
            'page': page,
            'language': 'ru-RU'
        }
        
        if genre:
            genre_id = await self.get_genre_id(genre)
            if genre_id:
                params['with_genres'] = genre_id
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error searching movies by budget: {e}")
            return None

    async def get_genre_id(self, genre_name: str):
        """Get genre ID from genre name."""
        url = f"{self.config.TMDB_BASE_URL}/genre/movie/list"
        params = {
            'api_key': self.config.TMDB_API_KEY,
            'language': 'ru-RU'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            genres = response.json().get('genres', [])
            
            for genre in genres:
                if genre_name.lower() in genre['name'].lower():
                    return genre['id']
            return None
        except requests.RequestException:
            return None

    async def get_movie_details(self, movie_id: int):
        """Get detailed information about a movie."""
        url = f"{self.config.TMDB_BASE_URL}/movie/{movie_id}"
        params = {
            'api_key': self.config.TMDB_API_KEY,
            'language': 'ru-RU'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error getting movie details: {e}")
            return None

    async def format_movie_message(self, movie_data: dict):
        """Format movie information into a readable message."""
        title = movie_data.get('title', 'Неизвестно')
        original_title = movie_data.get('original_title', '')
        release_date = movie_data.get('release_date', 'Неизвестно')
        vote_average = movie_data.get('vote_average', 0)
        overview = movie_data.get('overview', 'Описание отсутствует.')
        genres = ', '.join([genre['name'] for genre in movie_data.get('genres', [])])
        adult = "🔞 18+" if movie_data.get('adult') else "👨‍👩‍👧‍👦 Для всех"
        budget = movie_data.get('budget', 0)
        revenue = movie_data.get('revenue', 0)
        
        message = (
            f"🎬 <b>{title}</b>\n"
            f"📝 Оригинальное название: {original_title}\n"
            f"📅 Год: {release_date[:4] if release_date else 'Неизвестно'}\n"
            f"⭐ Рейтинг: {vote_average}/10\n"
            f"🎭 Жанр: {genres or 'Неизвестно'}\n"
            f"🔞 Возрастной рейтинг: {adult}\n"
        )
        
        if budget > 0:
            message += f"💰 Бюджет: ${budget:,}\n"
        if revenue > 0:
            message += f"💵 Сборы: ${revenue:,}\n"
        
        message += f"\n📖 Описание:\n{overview}\n\n"
        
        return message

    async def save_search_history(self, user: User, search_type: str, query: str, results: list):
        """Save search results to database."""
        with database.atomic():
            search = SearchHistory.create(
                user=user,
                search_type=search_type,
                query=query,
                result_count=len(results)
            )
            
            for movie_data in results:
                MovieResult.create(
                    search=search,
                    movie_id=movie_data.get('id'),
                    title=movie_data.get('title', ''),
                    original_title=movie_data.get('original_title', ''),
                    overview=movie_data.get('overview', ''),
                    release_date=movie_data.get('release_date', ''),
                    vote_average=movie_data.get('vote_average', 0),
                    vote_count=movie_data.get('vote_count', 0),
                    genre_names=', '.join([genre['name'] for genre in movie_data.get('genres', [])]),
                    adult=movie_data.get('adult', False),
                    poster_path=movie_data.get('poster_path', ''),
                    budget=movie_data.get('budget', 0),
                    revenue=movie_data.get('revenue', 0)
                )

    async def movie_search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle movie search command."""
        user = await self.get_or_create_user(update)
        
        if not context.args:
            await update.message.reply_text(
                "Пожалуйста, укажите название фильма для поиска.\n"
                "Пример: /movie_search Матрица"
            )
            return
        
        query = ' '.join(context.args)
        await update.message.reply_text(f"🔍 Ищу фильмы по запросу: {query}...")
        
        results = await self.search_movies_by_title(query)
        
        if not results or not results.get('results'):
            await update.message.reply_text("❌ Фильмы не найдены. Попробуйте другой запрос.")
            return
        
        movies = results['results'][:self.config.MOVIES_PER_PAGE]
        
        # Get detailed information for each movie
        detailed_movies = []
        for movie in movies:
            details = await self.get_movie_details(movie['id'])
            if details:
                detailed_movies.append(details)
        
        # Save to history
        await self.save_search_history(user, 'title', query, detailed_movies)
        
        # Send results
        for movie in detailed_movies:
            message = await self.format_movie_message(movie)
            poster_path = movie.get('poster_path')
            
            if poster_path:
                poster_url = f"{self.config.TMDB_IMAGE_BASE_URL}{poster_path}"
                await update.message.reply_photo(
                    photo=poster_url,
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(message, parse_mode='HTML')

    async def movie_by_rating_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle movie search by rating command."""
        user = await self.get_or_create_user(update)
        
        if not context.args:
            await update.message.reply_text(
                "Пожалуйста, укажите минимальный рейтинг.\n"
                "Пример: /movie_by_rating 8.0 фантастика"
            )
            return
        
        try:
            min_rating = float(context.args[0])
            genre = context.args[1] if len(context.args) > 1 else None
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, укажите числовой рейтинг.")
            return
        
        await update.message.reply_text(
            f"⭐ Ищу фильмы с рейтингом от {min_rating}..."
            f"{f' в жанре {genre}' if genre else ''}"
        )
        
        results = await self.search_movies_by_rating(min_rating, genre)
        
        if not results or not results.get('results'):
            await update.message.reply_text("❌ Фильмы не найдены. Попробуйте другие параметры.")
            return
        
        movies = results['results'][:self.config.MOVIES_PER_PAGE]
        
        # Get detailed information
        detailed_movies = []
        for movie in movies:
            details = await self.get_movie_details(movie['id'])
            if details:
                detailed_movies.append(details)
        
        await self.save_search_history(user, 'rating', f"rating>{min_rating}{f' genre:{genre}' if genre else ''}", detailed_movies)
        
        for movie in detailed_movies:
            message = await self.format_movie_message(movie)
            poster_path = movie.get('poster_path')
            
            if poster_path:
                poster_url = f"{self.config.TMDB_IMAGE_BASE_URL}{poster_path}"
                await update.message.reply_photo(
                    photo=poster_url,
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(message, parse_mode='HTML')

    async def low_budget_movie_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle low budget movie search command."""
        await self.handle_budget_search(update, context, 'low')

    async def high_budget_movie_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle high budget movie search command."""
        await self.handle_budget_search(update, context, 'high')

    async def handle_budget_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, budget_type: str):
        """Common handler for budget searches."""
        user = await self.get_or_create_user(update)
        
        genre = ' '.join(context.args) if context.args else None
        budget_text = "низкобюджетные" if budget_type == 'low' else "высокобюджетные"
        
        await update.message.reply_text(
            f"💸 Ищу {budget_text} фильмы..."
            f"{f' в жанре {genre}' if genre else ''}"
        )
        
        results = await self.search_movies_by_budget(budget_type, genre)
        
        if not results or not results.get('results'):
            await update.message.reply_text("❌ Фильмы не найдены. Попробуйте другие параметры.")
            return
        
        movies = results['results'][:self.config.MOVIES_PER_PAGE]
        
        # Get detailed information
        detailed_movies = []
        for movie in movies:
            details = await self.get_movie_details(movie['id'])
            if details:
                detailed_movies.append(details)
        
        search_query = f"budget:{budget_type}{f' genre:{genre}' if genre else ''}"
        await self.save_search_history(user, f'budget_{budget_type}', search_query, detailed_movies)
        
        for movie in detailed_movies:
            message = await self.format_movie_message(movie)
            poster_path = movie.get('poster_path')
            
            if poster_path:
                poster_url = f"{self.config.TMDB_IMAGE_BASE_URL}{poster_path}"
                await update.message.reply_photo(
                    photo=poster_url,
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(message, parse_mode='HTML')

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show search history."""
        user = await self.get_or_create_user(update)
        
        # Get last 10 searches
        searches = (SearchHistory
                   .select()
                   .where(SearchHistory.user == user)
                   .order_by(SearchHistory.created_at.desc())
                   .limit(self.config.MAX_HISTORY_ENTRIES))
        
        if not searches:
            await update.message.reply_text("📋 История поиска пуста.")
            return
        
        message = "📋 <b>История поиска:</b>\n\n"
        
        for i, search in enumerate(searches, 1):
            message += (
                f"{i}. <b>Тип:</b> {self.get_search_type_name(search.search_type)}\n"
                f"   <b>Запрос:</b> {search.query}\n"
                f"   <b>Дата:</b> {search.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   <b>Найдено:</b> {search.result_count} фильмов\n\n"
            )
        
        # Add inline keyboard for detailed history view
        keyboard = [
            [InlineKeyboardButton("📅 Показать за последние 7 дней", callback_data="history_7")],
            [InlineKeyboardButton("📅 Показать за последние 30 дней", callback_data="history_30")],
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)

    def get_search_type_name(self, search_type: str) -> str:
        """Get Russian name for search type."""
        types = {
            'title': 'По названию',
            'rating': 'По рейтингу',
            'budget_low': 'Низкобюджетные',
            'budget_high': 'Высокобюджетные'
        }
        return types.get(search_type, search_type)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('history_'):
            days = int(query.data.split('_')[1])
            await self.show_detailed_history(query, days)
        elif query.data == 'clear_history':
            await self.clear_history(query)

    async def show_detailed_history(self, query, days: int):
        """Show detailed history for specific period."""
        user = User.get(telegram_id=query.from_user.id)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        searches = (SearchHistory
                   .select()
                   .where((SearchHistory.user == user) & 
                          (SearchHistory.created_at >= cutoff_date))
                   .order_by(SearchHistory.created_at.desc()))
        
        if not searches:
            await query.edit_message_text("📋 История поиска за выбранный период пуста.")
            return
        
        message = f"📋 <b>История поиска за последние {days} дней:</b>\n\n"
        
        for search in searches:
            message += (
                f"📅 <b>{search.created_at.strftime('%d.%m.%Y %H:%M')}</b>\n"
                f"   <b>Тип:</b> {self.get_search_type_name(search.search_type)}\n"
                f"   <b>Запрос:</b> {search.query}\n"
                f"   <b>Результатов:</b> {search.result_count}\n\n"
            )
        
        await query.edit_message_text(message, parse_mode='HTML')

    async def clear_history(self, query):
        """Clear user's search history."""
        user = User.get(telegram_id=query.from_user.id)
        
        # Delete all user's search history
        deleted_count = (SearchHistory
                        .delete()
                        .where(SearchHistory.user == user)
                        .execute())
        
        await query.edit_message_text(f"🗑️ Удалено записей истории: {deleted_count}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages for quick movie search."""
        user = await self.get_or_create_user(update)
        query = update.message.text
        
        # Quick search if message looks like a movie title
        if len(query) > 2:  # Minimum length for meaningful search
            await update.message.reply_text(f"🔍 Ищу фильм: {query}...")
            
            results = await self.search_movies_by_title(query)
            
            if not results or not results.get('results'):
                await update.message.reply_text("❌ Фильм не найден. Попробуйте другой запрос.")
                return
            
            # Get the first result
            movie_data = results['results'][0]
            details = await self.get_movie_details(movie_data['id'])
            
            if details:
                message = await self.format_movie_message(details)
                poster_path = details.get('poster_path')
                
                # Save to history
                await self.save_search_history(user, 'title', query, [details])
                
                if poster_path:
                    poster_url = f"{self.config.TMDB_IMAGE_BASE_URL}{poster_path}"
                    await update.message.reply_photo(
                        photo=poster_url,
                        caption=message,
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text(message, parse_mode='HTML')
            else:
                await update.message.reply_text("❌ Не удалось получить информацию о фильме.")

    def run(self):
        """Start the bot."""
        logger.info("Starting Movie Search Bot...")
        self.app.run_polling()

if __name__ == '__main__':
    bot = MovieBot()
    bot.run()
