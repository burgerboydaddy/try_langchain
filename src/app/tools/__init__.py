from .calculator import calculator
from .current_weather import current_weather
from .stock_data import get_stock_data
from .transcribe_audio import transcribe_audio
from .utc_time import utc_time
from .weather_forecast import weather_forecast

TOOLS = [utc_time, calculator, current_weather, weather_forecast, get_stock_data, transcribe_audio]
