import uvicorn
import streaming_server
from control_api import app
import os

if __name__ == "__main__":
    # 1. Start the Stream Server thread (Port 5555)
    streaming_server.start_stream_server_thread()

    # 2. Run the FastAPI Control Plane (Port 8000)
    # We use 0.0.0.0 to be accessible from outside the container
    port = int(os.environ.get("CONTROL_PORT", "8000"))
    print(f"[MAIN] Starting Control API on 0.0.0.0:{port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
