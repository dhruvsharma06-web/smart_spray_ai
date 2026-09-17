import os
import uvicorn
try:
    from .api import app
except ImportError:
    from api import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
