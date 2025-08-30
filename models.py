from peewee import *
from datetime import datetime
import config

# Initialize database
database = SqliteDatabase(config.Config.DATABASE_NAME)

class BaseModel(Model):
    class Meta:
        database = database

class User(BaseModel):
    telegram_id = BigIntegerField(unique=True)
    username = CharField(null=True)
    first_name = CharField()
    last_name = CharField(null=True)
    created_at = DateTimeField(default=datetime.now)

class SearchHistory(BaseModel):
    user = ForeignKeyField(User, backref='searches')
    search_type = CharField()  # 'title', 'rating', 'budget_low', 'budget_high'
    query = TextField()
    result_count = IntegerField()
    created_at = DateTimeField(default=datetime.now)

class MovieResult(BaseModel):
    search = ForeignKeyField(SearchHistory, backref='movies')
    movie_id = IntegerField()
    title = CharField()
    original_title = CharField(null=True)
    overview = TextField(null=True)
    release_date = CharField(null=True)
    vote_average = FloatField(null=True)
    vote_count = IntegerField(null=True)
    genre_names = TextField(null=True)  # Comma-separated genres
    adult = BooleanField(default=False)
    poster_path = CharField(null=True)
    budget = BigIntegerField(null=True)
    revenue = BigIntegerField(null=True)

class UserMovieStatus(BaseModel):
    user = ForeignKeyField(User, backref='movie_statuses')
    movie = ForeignKeyField(MovieResult, backref='user_statuses')
    watched = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

# Create tables
def create_tables():
    with database:
        database.create_tables([
            User, 
            SearchHistory, 
            MovieResult, 
            UserMovieStatus
        ])

# Initialize database
create_tables()
