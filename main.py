import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

if __name__ == "__main__":
    import uvicorn
    # Import the FastAPI app from the new modular structure
    from yumi.api.server import app

    print("Starting Yumi server from backward-compatibility wrapper...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
