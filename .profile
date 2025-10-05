# Install Playwright browsers on first run
if [ ! -f ~/.playwright_installed ]; then
    echo "Installing Playwright browsers..."
    playwright install chromium
    playwright install-deps chromium
    touch ~/.playwright_installed
fi
