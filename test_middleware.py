import asyncio
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

app = FastAPI()

class Outer(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print("Middle 1 entered")
        res = await call_next(request)
        print("Middle 1 exited")
        return res

class Inner(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print("Middle 2 entered")
        res = await call_next(request)
        print("Middle 2 exited")
        return res

app.add_middleware(Outer)
app.add_middleware(Inner)

@app.get("/")
def read_root():
    print("Handler")
    return {"Hello": "World"}

if __name__ == "__main__":
    client = TestClient(app)
    client.get("/")
