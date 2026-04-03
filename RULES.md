# FlowForge Development Rules

**⚠️ IMPORTANT:** The AI agent MUST strictly follow all development rules below. These are mandatory requirements, not suggestions.

## Rules

1. **Run Tests After Backend Implementation** — After writing backend functionality and tests, always run `pytest` to verify correctness

2. **Update PROGRESS.md** — After completing each major task block, update `PROGRESS.md` with progress and changes

3. **Run Ruff Formatter** — After writing backend code, run `ruff format backend/` to ensure consistent code style

4. **Explain Before Changing on User Questions** — When the user asks a clarifying question about implementation decisions, first explain the reasoning behind the original implementation, then ask if they want it changed before making modifications

5. **Test Strategy** — Use testcontainers for integration tests that require any external connections (database, Redis, S3, etc.). Unit tests should only test pure functions without any external dependencies or mocking

6. **Verify Docker Builds** — After modifying Dockerfile or docker-compose.yaml, always attempt to build the image with `docker build` or `docker-compose build` before committing changes

7. **Build Frontend in Docker Only** — NEVER run `npm run build` or `npm install` locally. Always build the frontend inside Docker using `docker build -f frontend/Dockerfile frontend/` or `docker-compose build frontend`

8. **Clean Before Session End** — Before offering to end or continue a session, clean `__pycache__` directories: `find . -type d -name "__pycache__" -exec rm -rf {} +`

9. **End of Session Protocol** — At the end of a session, make a git commit with all changes. Do not start tasks from the next session; instead, offer to complete or compact the current session

10. **Verify Frontend Changes** — Before committing frontend changes, ask the user to verify the fix works in their browser

11. **Ask on Architectural Decisions** — When facing important architectural or implementation decisions (e.g., API design, technology choices, complex patterns), the agent MUST ask the user for preference before implementing. Do not assume — explain options and wait for confirmation.

12. **Use Project Root venv** — Always use the virtual environment from the project root directory (`.venv/` in `bachelor_thesis/`). Run commands with `.venv/bin/python` or `.venv/bin/pytest` instead of system Python.
