# AceCoder (Open-sourced)

Inspired by [Interview Coder](https://github.com/ibttf/interview-coder) by @ibttf

An app that does this shouldn't be locked behind a $60/mo paywall.

AceCoder is a **Windows desktop AI assistant** designed to help you with a wide range of questions and tasks presented visually (e.g., in screenshots). It captures screen areas, sends them to an AI model via OpenRouter for analysis, and displays the results in a convenient, minimal overlay window.

This project is licensed under the **GNU General Public License v3.0**. See the `LICENSE` file for details.

**Note:** This application is currently designed specifically for **Windows**.

## Key Features

*   **Screenshot Capture:** Capture one or more screenshots of coding problems or code snippets using a hotkey.
*   **AI Analysis:** Sends captured images to a powerful AI model (configurable, defaults to a Gemini model via OpenRouter) for explanation and solution generation.
*   **Overlay Interface:** Displays the AI's response in a persistent, always-on-top overlay window.
*   **Markdown Rendering:** Formats the AI's response using Markdown, including syntax highlighting for code blocks.
*   **Follow-up Questions:** Ask follow-up questions about the provided solution directly within the overlay (uses the previous analysis as context).
*   **Configurable Hotkeys:** Control capture, processing, overlay visibility, and movement with global hotkeys.
*   **Capture Exclusion (Windows):** The overlay window attempts to exclude itself from screen captures.

## Planned Features

*   **Click-through Overlay:** Allow mouse interactions with windows underneath the overlay.
*   **Optional Follow-up Suppression:** Ability to type in follow-up window without losing focus of current window.

## Keybindings

*   **`Ctrl + Shift + H`**: Capture a screenshot. Press multiple times to capture multiple images for a single analysis.
*   **`Ctrl + Shift + Enter`**: Process the captured screenshot(s) and send for AI analysis.
*   **`Ctrl + B`**: Toggle the visibility of the overlay window.
*   **`Ctrl + Alt + Arrow Keys` (Left/Right/Up/Down)**: Move the overlay window around the screen.
*   **`Ctrl + Shift + V`**: Toggle whether the overlay window itself appears in screen captures. 
*   **`Ctrl + Shift + R`**: Reset (clear) the currently captured screenshots.
*   **`Ctrl + L`**: Open the follow-up input area at the bottom of the overlay (only works after an initial analysis).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/safzanpirani/acecoder-open.git
    cd acecoder-open
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

AceCoder requires an API key from **OpenRouter.ai** to function. OpenRouter provides access to various AI models, including free ones (rate limits apply).

1.  **Get an OpenRouter API Key:** Sign up at [https://openrouter.ai/](https://openrouter.ai/) and generate an API key.
2.  **Set the Environment Variable:** You **must** set the `OPENROUTER_API_KEY` environment variable before running the application.

    *   **Temporary (Command Prompt):** Open Command Prompt and run:
        ```cmd
        set OPENROUTER_API_KEY=your_actual_api_key_here
        python main.py
        ```
    *   **Temporary (PowerShell):** Open PowerShell and run:
        ```powershell
        $env:OPENROUTER_API_KEY="your_actual_api_key_here"
        python main.py
        ```
    *   **Permanent:** Search for "Edit the system environment variables" in the Start menu, click "Environment Variables...", and add `OPENROUTER_API_KEY` with your key as the value under "User variables". You may need to restart your terminal or PC for the change to take effect.

    **Important:** Keep your API key secure and do not commit it directly into the code or share it publicly.

3.  **(Optional) Configure OpenRouter Referrer/Title:** You can optionally set `OPENROUTER_REFERRER_URL` and `OPENROUTER_SITE_TITLE` environment variables if you want to identify traffic from your app in OpenRouter analytics (use the same methods as above to set them).

### Changing the AI Model

AceCoder uses OpenRouter, giving you access to a variety of AI models. To change the model used for analysis:

1.  Open the `api_client.py` file.
2.  Locate the `__init__` method within the `ApiClient` class.
3.  Find the line `self.model_name = "google/gemini-2.0-flash-thinking-exp:free"` (or similar).
4.  Replace the model string (e.g., `"google/gemini-2.0-flash-thinking-exp:free"`) with the desired model identifier from [OpenRouter Models](https://openrouter.ai/models). Ensure you choose a model compatible with multimodal inputs (image and text).
5.  You might also want to adjust `self.max_tokens` depending on the chosen model's limits.

## Usage

1.  Ensure the `OPENROUTER_API_KEY` environment variable is set (see Configuration).
2.  Activate your virtual environment (`.\venv\Scripts\activate`).
3.  Run the main script from the project directory:
    ```bash
    python main.py
    ```
4.  Use the hotkeys (listed above) to capture screenshots and trigger analysis. The overlay window will appear and update with status messages and results.

## License

This project is licensed under the **GNU General Public License v3.0**. A copy of the license should be included in the file `LICENSE`.

Under the GPLv3, you are free to use, modify, and distribute this software, provided that you also distribute the source code of any derivative works under the same GPLv3 license.

## Contributing

Contributions are welcome! Please feel free to open issues for bugs or feature requests, or submit pull requests.