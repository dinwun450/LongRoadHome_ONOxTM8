# LongRoadHome_ONOxTM8

This is the prototype is what will happen. Stay tuned.

## Overview

A Next.js React application with an AI-powered chatbot assistant built using [CopilotKit](https://copilotkit.ai/) and Google ADK. The app features:

- **AI Chatbot Sidebar** – Conversational assistant powered by Google's Gemini model
- **3D Graph Visualization** – Interactive survivor network visualization using react-force-graph-3d
- **Proverbs Management** – Shared state management between frontend and agent
- **Weather Widget** – Generative UI example for displaying weather information
- **Theme Customization** – Dynamic theme color changes via chat commands

## Prerequisites

- **Node.js** v18 or higher
- **Python** 3.12 or higher
- **uv** (Python package manager) – Install via `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Google API Key** – Required for the AI agent ([Get one here](https://makersuite.google.com/app/apikey))

### Optional (for full functionality)

- **Neo4j** database credentials (for graph data)
- **Snowflake** credentials (for data queries)

## Environment Variables

Create a `.env` file in the root directory (and/or in the `agent/` folder) with the following variables:

```env
# Required
GOOGLE_API_KEY=your-google-api-key

# Optional - Neo4j (for graph visualization)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password

# Optional - Snowflake (for data queries)
SNOWFLAKE_USER=your-user
SNOWFLAKE_PASSWORD=your-password
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_WAREHOUSE=your-warehouse
SNOWFLAKE_DATABASE=your-database
SNOWFLAKE_SCHEMA=your-schema
```

## Installation

### 1. Install Node.js dependencies

```bash
npm install
```

This will also automatically install the Python agent dependencies via the `postinstall` script.

### 2. Manual agent setup (if needed)

If the automatic setup didn't work, you can manually set up the agent:

**Linux/macOS:**
```bash
cd agent
python -m uv sync
```

**Windows:**
```bash
cd agent
python -m uv sync
```

Or use the provided scripts:
```bash
# Linux/macOS
./scripts/setup-agent.sh

# Windows
scripts\setup-agent.bat
```

## Running the Application

### Development Mode (Recommended)

Run both the Next.js frontend and Python agent concurrently:

```bash
npm run dev
```

This command:
- Starts the Next.js frontend on `http://localhost:3000`
- Starts the Python agent on `http://localhost:8000`

### Debug Mode

For verbose logging:

```bash
npm run dev:debug
```

### Running Components Separately

**Frontend only:**
```bash
npm run dev:ui
```

**Agent only:**
```bash
npm run dev:agent
```

Or manually:
```bash
cd agent
uv run main.py
```

## Production Build

```bash
# Build the Next.js app
npm run build

# Start the production server
npm start
```

> **Note:** For production, you'll need to run the Python agent separately.

## Usage

1. Open `http://localhost:3000` in your browser
2. The chatbot sidebar will open automatically on the right side
3. Try these example interactions:
   - **"Get the weather in San Francisco"** – Displays a weather card (Generative UI)
   - **"Set the theme to green"** – Changes the app's theme color
   - **"Add a proverb about AI"** – Adds a proverb to the shared state
   - **"What are the proverbs?"** – Lists all proverbs in the shared state
   - **"Find all survivors"** – Queries the survivor network (requires Neo4j)

## Project Structure

```
├── agent/                  # Python backend agent
│   ├── main.py             # FastAPI app with ADK agent
│   ├── pyproject.toml      # Python dependencies
│   └── services/           # Agent services
├── scripts/                # Setup and run scripts
├── src/
│   ├── app/                # Next.js app router
│   │   ├── api/copilotkit/ # CopilotKit API route
│   │   ├── layout.tsx      # Root layout with CopilotKit provider
│   │   └── page.tsx        # Main page component
│   ├── components/         # React components
│   │   ├── graph3DCanvas.tsx
│   │   ├── proverbs.tsx
│   │   └── weather.tsx
│   └── lib/                # Utilities and types
├── package.json
└── README.md
```

## Troubleshooting

### "GOOGLE_API_KEY environment variable not set"

Make sure you've created a `.env` file with your Google API key:
```env
GOOGLE_API_KEY=your-api-key-here
```

### Agent not starting

1. Ensure Python 3.12+ is installed: `python --version`
2. Ensure uv is installed: `uv --version`
3. Try reinstalling dependencies:
   ```bash
   cd agent
   uv sync --reinstall
   ```

### Neo4j connection issues

- The graph visualization will show empty if Neo4j is not configured
- Ensure your Neo4j instance is running and credentials are correct in `.env`

### Port conflicts

- Frontend runs on port 3000
- Agent runs on port 8000

If these ports are in use, you can modify them in:
- `next.config.ts` for the frontend
- `agent/main.py` (change the `PORT` environment variable)

## License

See [LICENSE](./LICENSE) for details. It's coming soon.
