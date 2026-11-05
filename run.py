#!/usr/bin/env python3
"""Entry point for running Muse Analyse."""

import uvicorn

from app.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
