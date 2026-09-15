from app.weather.base import WeatherProvider
class MockWeatherProvider(WeatherProvider):
    async def current_and_forecast(self, location: dict) -> dict:
        return {"temperature": 35, "humidity": 76, "rainfall": 0, "rain_probability": 15, "forecast": [{"hours": 24, "rain_probability": 15}], "extreme_weather": []}
