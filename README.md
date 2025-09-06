# Trading Bot Dashboard

A Flask-based dashboard for managing Binance futures trading bots. Supports live reporting, bot configuration, and account management.

## Features

- **Account Setup:** Add and verify your Binance API keys (supports testnet).
- **Bot Setup:** Configure bots with custom symbols, timeframes, leverage, margin, and trading logic.
- **Live Dashboard:** Start/stop bots, view status, and see account balance.
- **Reports:** View detailed trade history and statistics for each bot.
- **WebSocket Updates:** Real-time UI updates for bot status and live P&L.

## Folder Structure

```
.gitignore
requirements.txt
run.py
app/
    __init__.py
    bot_logic.py
    models.py
    accounts/
        __init__.py
        routes.py
    bots/
        __init__.py
        routes.py
    templates/
        accounts.html
        base.html
        bot_setup.html
        create_bot.html
        dashboard.html
        report_detail.html
        report_list.html
        reports.html
instance/
    database.db
```

## Getting Started

1. **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

2. **Run the app:**
    ```sh
    python run.py
    ```

3. **Access the dashboard:**
    Open [http://localhost:5000](http://localhost:5000) in your browser.

## Configuration

- The database is stored in `instance/database.db`.
- API keys are managed via the Account page in the dashboard.
- Only one Binance account is supported at a time.

## Notes

- For testnet trading, check "Use Testnet" when adding your account.
- Bots can be configured for multiple symbols and custom trading logic.
- All bot and trade data is stored in the local SQLite database.

## License

MIT