"""Application entry point for Browser v1."""

from ui.window import BrowserWindow


def main() -> None:
    """Launch the WebView2-powered browser window."""

    window = BrowserWindow()
    window.run()


if __name__ == "__main__":
    main()
