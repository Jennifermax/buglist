from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import config, testcases, generate, execute

app = FastAPI(title="Buglist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(testcases.router)
app.include_router(generate.router)
app.include_router(execute.router)

@app.get("/")
async def root():
    return {"message": "Buglist API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
