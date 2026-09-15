from abc import ABC, abstractmethod
class WeatherProvider(ABC):
    @abstractmethod
    async def current_and_forecast(self, location: dict) -> dict: ...
