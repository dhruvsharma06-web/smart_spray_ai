from app.config import settings
from app.weather.mock import MockWeatherProvider
class WeatherService:
    def __init__(self):
        providers = {"mock": MockWeatherProvider()}
        self.provider = providers.get(settings.weather_provider, MockWeatherProvider())
    async def get(self, location: dict): return await self.provider.current_and_forecast(location)
