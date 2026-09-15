from fastapi import FastAPI, UploadFile, File, Form
import json
app=FastAPI(title="Mock AI Service")
@app.post("/ai/analyze")
async def analyze(image:UploadFile=File(...), sensor_data:str=Form("{}"), weather_data:str=Form("{}"), crop_stage:str=Form("")):
    return {"crop":{"name":"tomato","confidence":0.96},"disease":{"name":"early_blight","confidence":0.94},"pests":[],"nutrient_deficiency":None,"severity":{"level":"moderate","affected_area_percent":18},"climate_risk":{"drought":0.78,"heat":0.84,"flood":0.12,"waterlogging":0.25},"requires_confirmation":False}
