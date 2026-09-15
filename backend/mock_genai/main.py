from fastapi import FastAPI
app=FastAPI(title="Mock GenAI Service")
@app.post("/assistant/explain")
async def explain(payload:dict):
    a=payload.get("analysis",{}); d=payload.get("decision",{})
    crop=a.get("crop",{}).get("name","the crop"); disease=a.get("disease",{}).get("name")
    text=f"The system identified {crop}."
    if disease: text+=f" Possible {disease} was detected."
    text+=f" Recommended action: {d.get('primary_decision','MONITOR').replace('_',' ').lower()}."
    return {"text":text,"source":"mock-genai"}
