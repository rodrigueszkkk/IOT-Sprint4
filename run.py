"""Sobe a API + painel web da CLYVO VET em http://localhost:8000 (Swagger em /docs)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:create_app", factory=True, host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "8000")), reload=False)
