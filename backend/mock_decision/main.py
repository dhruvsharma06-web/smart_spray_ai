from fastapi import FastAPI
app=FastAPI(title="Mock Decision Engine")
@app.post("/decision")
async def decide(payload:dict):
    weather=payload.get("weather_data",{}); risk=payload.get("analysis",{}).get("climate_risk",{})
    rain=weather.get("rain_probability",0)
    if rain>=70: return {"primary_decision":"DELAY_SPRAY","risk_level":"HIGH","actions":[{"type":"DELAY_SPRAY","priority":"HIGH"}],"warnings":["Heavy rainfall expected. Delay spraying."],"requires_confirmation":False}
    if risk.get("drought",0)>=.8: return {"primary_decision":"IRRIGATE","risk_level":"HIGH","actions":[{"type":"IRRIGATION","priority":"HIGH"}],"warnings":["Low moisture / high drought risk."],"requires_confirmation":False}
    return {"primary_decision":"SPRAY","risk_level":"MEDIUM","actions":[{"type":"SPRAY","priority":"MEDIUM"}],"warnings":[],"requires_confirmation":False}
