# Mac Mini Local RAG API

A fully local, Apple Silicon-optimized Retrieval-Augmented Generation (RAG) server. It uses Qdrant for hybrid vector search, Docling for intelligent PDF parsing, and FastEmbed (ONNX) for CPU-accelerated embedding inference.

## Prerequisites
1. **Docker Desktop** or **OrbStack** (recommended for Mac) installed.
2. **Python 3.9+** installed.

## 1. Installation

Clone or download this repository, navigate to the root folder (`mac-rag-api`), and install it into a virtual environment.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package and its dependencies
pip install -e .

```

## 2. Start the Vector Database

The application requires Qdrant to be running. We use Docker to host it and save the data locally to a `qdrant_storage` folder.

```bash
# Start Qdrant in the background
docker-compose up -d
```

## 3. Running Manually

To test the server manually, you can use the command-line shortcut created by our `pyproject.toml`:

```bash
mac-rag-server
```

You should see Uvicorn start on `http://0.0.0.0:8000`. Test the API by going to `http://localhost:8000/docs` in your browser to see the interactive Swagger UI. Press `Ctrl+C` to stop it.

---

## 4. Running as a macOS Background Service

To make the server run continuously in the background (and restart automatically if it crashes or if the Mac restarts), we will use macOS's native `launchd` system.

### Step A: Create the Launch Agent `plist` file

Create a file at `~/Library/LaunchAgents/com.local.mac-rag.plist`.

*Note: You MUST replace `/Users/YOUR_USERNAME/path/to/...` with the actual absolute paths to your project directory.*

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "[http://www.apple.com/DTDs/PropertyList-1.0.dtd](http://www.apple.com/DTDs/PropertyList-1.0.dtd)">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.mac-rag</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/path/to/mac-rag-api/.venv/bin/mac-rag-server</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/path/to/mac-rag-api</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>QDRANT_HOST</key>
        <string>localhost</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/path/to/mac-rag-api/server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/path/to/mac-rag-api/server_error.log</string>
</dict>
</plist>
```

### Step B: Load and Start the Service

Open your terminal and run the following commands to tell macOS to load and run your new service:

```bash
# Load the service into launchd
launchctl load ~/Library/LaunchAgents/com.local.mac-rag.plist

# Start the service
launchctl start com.local.mac-rag

```

### Managing the Service

* **Check Logs:** `tail -f ~/path/to/mac-rag-api/server.log`
* **Stop the Service:** `launchctl stop com.local.mac-rag`
* **Disable the Service:** `launchctl unload ~/Library/LaunchAgents/com.local.mac-rag.plist`

*Note: Make sure Docker is set to start on login/boot in its application settings, so Qdrant is available when the Python service starts.*
