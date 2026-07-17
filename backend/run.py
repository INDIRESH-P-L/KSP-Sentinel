import os
import uvicorn

if __name__ == "__main__":
    # Get the port assigned by Zoho Catalyst AppSail (defaulting to 9000)
    port = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", 9000))
    print(f"Starting KSP-Sentinel backend on port {port}...")
    # Run the FastAPI app
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
