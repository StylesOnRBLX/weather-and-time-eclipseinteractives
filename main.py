from fastapi import FastAPI, HTTPException
from datetime import datetime
import pytz
import httpx

app = FastAPI(title="Eclipse Interactives - Time & Weather API")

# --- Time Endpoint ---
@app.get("/time")
def get_time(timezone: str = "UTC"):
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return {
            "timezone": timezone,
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "day_of_week": now.strftime("%A"),
            "utc_offset": now.strftime("%z")
        }
    except pytz.UnknownTimeZoneError:
        raise HTTPException(status_code=400, detail=f"Unknown timezone '{timezone}'. Use format like 'America/Chicago'")

# --- Weather Endpoint ---
@app.get("/weather")
async def get_weather(city: str):
    async with httpx.AsyncClient() as client:
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1}
        )
        results = geo.json().get("results")
        if not results:
            raise HTTPException(status_code=404, detail=f"City '{city}' not found")

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        city_name = results[0]["name"]
        country = results[0].get("country", "")
        timezone = results[0].get("timezone", "UTC")

        weather = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "hourly": "relative_humidity_2m,apparent_temperature",
                "timezone": timezone,
                "forecast_days": 1
            }
        )
        data = weather.json()
        w = data["current_weather"]

        current_hour = w["time"][:13]
        hourly_times = [t[:13] for t in data["hourly"]["time"]]
        idx = hourly_times.index(current_hour) if current_hour in hourly_times else 0
        humidity = data["hourly"]["relative_humidity_2m"][idx]
        feels_like = data["hourly"]["apparent_temperature"][idx]

        weather_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle",
            55: "Heavy drizzle", 61: "Slight rain", 63: "Rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
            95: "Thunderstorm", 99: "Thunderstorm with hail"
        }
        condition = weather_codes.get(w["weathercode"], f"Code {w['weathercode']}")

        return {
            "city": city_name,
            "country": country,
            "temperature_c": w["temperature"],
            "temperature_f": round(w["temperature"] * 9/5 + 32, 1),
            "feels_like_c": feels_like,
            "feels_like_f": round(feels_like * 9/5 + 32, 1),
            "humidity_percent": humidity,
            "wind_speed_kmh": w["windspeed"],
            "condition": condition,
        }

# --- Combined Endpoint ---
@app.get("/time-and-weather")
async def get_time_and_weather(city: str, timezone: str = None):
    weather = await get_weather(city)
    tz_to_use = timezone or weather["city"]
    time = get_time(tz_to_use)
    return {
        "time": time,
        "weather": weather
    }

# --- Health Check ---
@app.get("/")
def root():
    return {"status": "ok", "message": "Eclipse Interactives API is running"}
