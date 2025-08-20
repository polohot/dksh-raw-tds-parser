# main.py
from fastapi import FastAPI, File, Form, UploadFile
from typing import List, Annotated
import asyncio
import random

app = FastAPI()

##########
# HELPER #
##########

async def func1() -> int:
    delay = random.randint(1, 5)
    await asyncio.sleep(delay)
    return delay

async def func2() -> int:
    delay = random.randint(1, 4)
    await asyncio.sleep(delay)
    return delay

async def func3() -> int:
    delay = random.randint(1, 3)
    await asyncio.sleep(delay)
    return delay

#############
# END POINT #
#############

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/process")
async def process(
    string1: Annotated[str, Form(...)],
    string2: Annotated[str, Form(...)],
    listOfFiles: Annotated[List[UploadFile], File(...)]):
    
    # (Optional) touch files so FastAPI reads the uploads (not required for timing)
    # for f in listOfFiles:
    #     await f.read()  # avoid in-memory bloat on large files in real apps

    time1 = await func1()
    time2 = await func2()
    time3 = await func3()

    return {"time1": time1, "time2": time2, "time3": time3}