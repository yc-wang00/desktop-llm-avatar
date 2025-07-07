# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a desktop pet/avatar application that monitors screen activity and provides contextual animations and comments based on what the user is doing. The pet uses OpenAI's GPT-4 Vision to analyze screenshots and responds with appropriate animations (idle vs engage) and comments.

## Architecture

- **main.py**: Simple entry point with "Hello World" functionality
- **run.py**: Main application containing:
  - `PetWindow`: Main PyQt5 widget that creates the desktop overlay pet
  - `AnalysisThread`: Background thread for non-blocking LLM analysis of screenshots
  - Screen capture using `mss` library
  - Multi-monitor support with configurable monitor selection
  - Draggable pet window that stays on top

## Key Components

### PetWindow Class
- Creates a transparent, always-on-top desktop overlay
- Handles GIF animations (idle.gif, engage.gif from assets/)
- Manages chat bubble with pet comments
- Implements screen capture and analysis every 5 seconds
- Supports dragging the pet around the screen

### AnalysisThread Class
- Performs OpenAI API calls in background to avoid UI blocking
- Analyzes screenshots to determine pet behavior (idle vs engage)
- Returns JSON with comment and action recommendations

## Dependencies

The project uses:
- **PyQt5**: GUI framework for desktop overlay
- **mss**: Cross-platform screen capture
- **OpenAI**: GPT-4 Vision API for image analysis
- **OpenCV**: Image processing and encoding
- **numpy**: Array operations for image data

## Environment Setup

Requires `OPENAI_API_KEY` environment variable (loaded via python-dotenv).

## Common Commands

```bash
# Run the application
python run.py

# Run basic entry point
python main.py

# Install dependencies
pip install -e .
```

## Assets

The `assets/` directory contains:
- `idle.gif`: Default/calm animation
- `engage.gif`: Excited/gaming animation 
- `f-idle.gif`, `f-engage.gif`: Alternative animations

## Multi-Monitor Support

The application supports multi-monitor setups via the `monitor_index` parameter:
- `monitor_index=1`: Primary monitor (default)
- `monitor_index=2`: Secondary monitor
- `monitor_index=0`: All monitors combined

## Development Notes

- Screenshots are saved to `debug_screenshots/` directory for debugging
- The pet analyzes screen content every 5 seconds
- Window visibility is checked every 2 seconds to ensure it stays on top
- macOS-specific code exists for proper window layering