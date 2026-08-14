# Feishu Driver

Python CLI tool for sending notifications to Feishu (Lark).

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-WEBHOOK-KEY"
export FEISHU_WEBHOOK_TRADING="..."  # Optional: for trading channel
export FEISHU_WEBHOOK_ALERTS="..."   # Optional: for alerts channel
```

## Usage

### Send notification to user

```bash
python main.py send --user yunpeng --title "Test" --message "Hello World"
```

### Send notification to channel

```bash
python main.py send --channel general --title "Alert" --message "System status"
```

### Markdown support

```bash
python main.py send --user yunpeng --title "Markdown Test" \
  --message "**Bold** *Italic* \`code\`"
```

### Custom color

```bash
python main.py send --user yunpeng --title "Error" --message "Something failed" \
  --color red
```

Available colors: `blue`, `green`, `red`, `orange`, `purple`, `grey`

### Test notification

```bash
python main.py test --title "Test Notification"
```

## Exit Codes

- `0`: Success
- `1`: Invalid arguments
- `2`: Business error (e.g., user not found, API error)
- `3`: System error (e.g., network failure, unexpected exception)

## Features

- **Retry mechanism**: 3 retries with exponential backoff
- **Markdown support**: Rich text formatting in notifications
- **User/Channel routing**: Map users and channels to different webhooks
- **Error handling**: Comprehensive error handling with proper exit codes
- **Timeout**: 10-second timeout for API requests

## Architecture

```
feishu-driver/
├── main.py                          # CLI entry point
├── api/
│   ├── __init__.py
│   └── feishu_api.py               # Feishu Webhook API client
├── manager/
│   ├── __init__.py
│   └── notification_manager.py     # User/channel routing logic
└── requirements.txt
```
