**Язык / Language:** [Русский](../README.md) **|** <ins>English</ins>

<div id="header" align="center"><h1>XRay VPN Bot [Telegram]</h1></div>

<div id="header" align="center"><img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/QueenDekim/XRay-bot"> <img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/QueenDekim/XRay-bot"><br><img alt="GitHub top language" src="https://img.shields.io/github/languages/top/QueenDekim/XRay-bot"> <a href="./LICENSE" target="_blank"><img alt="GitHub License" src="https://img.shields.io/github/license/QueenDekim/XRay-bot"></a></div>

## Project Description

This project is a Telegram bot for selling and managing VPN subscriptions via the 3X-UI control panel. The bot allows users to purchase VPN subscriptions, create and manage their profiles, and enables administrators to manage users and track statistics.

Key Features:

- User registration with a trial period
- Subscription renewal via Telegram's built-in payment system
- Creation and deletion of VPN profiles (VLESS) in the 3X-UI panel
- Subscription expiration notifications
- Administrative menu for user management and broadcast messages
- Traffic usage statistics

## Installation and Setup

### Prerequisites

- Python 3.10+
- 3X-UI control panel
   - An inbound created with the security setting set to `Reality`
- A Telegram bot (created via `@BotFather`)

### Installation Steps

1. Clone the repository:

```bash
git clone https://github.com/QueenDekim/XRay-bot
cd XRay-bot
```

2. Install dependencies:

```bash
python -m venv .venv # use python3 on Linux
.venv\Scripts\activate
# source .venv/bin/activate on Linux
pip install -r requirements.txt
```

3. Configure environment variables:

```bash
cp src/.env.example src/.env # use "/" instead of "\" on Linux
# Edit the .env file with your values
```

4. Run the bot:

```bash
python src/app.py # use python3 and "/" instead of "\" on Linux
```

### Environment Variables Configuration

Mandatory parameters in `.env`:

- `BOT_TOKEN` - Your Telegram bot token from @BotFather
- `PAYMENT_TOKEN` - Payment token from @BotFather
- `ADMINS` - Administrator IDs, comma-separated
- `XUI_API_URL` - 3X-UI panel URL (e.g., http://ip:54321)
- `XUI_USERNAME` and `XUI_PASSWORD` - Panel credentials
- `INBOUND_ID` - Inbound ID in the 3X-UI panel
- Reality parameters (public key, fingerprint, SNI, etc.)

## Technical Architecture

### File Structure

```
./
├── src
│   ├── .env.example        # Example configuration file
│   ├── app.py              # Main application file
│   ├── config.py           # Application configuration
│   ├── database.py         # Database models and functions
│   ├── functions.py        # Functions for 3X-UI API interaction
│   └── handlers.py         # Command and callback handlers
├── docs                    # Documentation in other languages
│   └── README.en_US        # Documentation in English
├── users.db                # SQLite database file. Created on first bot run
├── README.md               # Documentation in Russian
└── requirements.txt        # Project dependencies
```

### Database

The project uses `SQLite` with `SQLAlchemy ORM`. Main tables:

1.  **`users`** - User information:
    - `telegram_id` - User's Telegram ID
    - `subscription_end` - Subscription end date
    - `vless_profile_data` - VPN profile data in JSON
    - `is_admin` - Administrator flag
2.  **`static_profiles`** - Static VPN profiles:
    - `name` - Profile name
    - `vless_url` - VLESS URL

### Core Components

#### 1. `app.py`

The main application file that:

- Initializes the database
- Starts the background task for subscription checks
- Handles payment pre-checkout and successful payment queries
- Starts the bot's polling

#### 2. `config.py`

Loads and validates configuration using `Pydantic`. Contains:

- 3X-UI panel connection settings
- Reality protocol parameters
- Subscription prices and discounts
- Functions for cost calculation

#### 3. `database.py`

Models and functions for database interaction:

- `User` model for storing users
- `StaticProfile` model for static profiles
- Functions for managing subscriptions and profiles

#### 4. `functions.py`

The `XUIAPI` class for interacting with the **3X-UI** panel:

- Panel authentication
- Creating and deleting clients
- Retrieving usage statistics
- Generating VLESS URLs

#### 5. `handlers.py`

Command and callback handlers:

- `/start` and `/menu` commands
- Payment processing
- Administrative functions
- Profile management

## Payment Processing

The bot uses Telegram's built-in payment system. When a subscription is selected:

1.  The user selects a subscription period
2.  The bot creates an invoice via `bot.send_invoice()`
3.  After successful payment, it is processed by `process_successful_payment()`
4.  The user's subscription is extended

## Administrative Functions

Administrators have access to a special menu with functions:

- Adding/removing subscription time
- Viewing the user list
- Network usage statistics
- Broadcasting messages to users
- Managing static profiles

## Integration with **3X-UI**

The bot interacts with the **3X-UI** panel via its API:

1.  Authentication via login/password
2.  Retrieving inbound data
3.  Adding clients to the inbound settings
4.  Updating the inbound configuration

## VLESS URL Generation

VLESS URL format for Reality:

```
vless://{client_id}@{host}:{port}?type=tcp&security=reality&pbk={public_key}&fp={fingerprint}&sni={sni}&sid={short_id}&spx={spider_x}#{remark}
```

## Monitoring and Notifications

The bot automatically checks subscriptions every hour and:

- Notifies users 24 hours before expiration
- Deletes profiles with expired subscriptions
- Sends payment notifications to administrators

## Security

- All sensitive data is stored in environment variables
- Configuration validation is done via Pydantic
- Restricted access to administrative functions
- Secure storage of payment information through Telegram

## Potential Issues and Solutions

1.  **3X-UI Connection Errors** - Check the URL and credentials
2.  **Payment Issues** - Ensure the payment token is correct
3.  **Database Errors** - Check write permissions in the directory
4.  **Notifications Not Working** - Check time and timezone settings

---

*For additional information, refer to the [aiogram](https://docs.aiogram.dev/en/latest/) and [3X-UI](https://github.com/MHSanaei/3x-ui/wiki) documentation.*

---

| Demo - Fully functional bot                            | Communication with the developer                 |
| ------------------------------------------------------ | ------------------------------------------------ |
| Telegram: [@Dekim_vpn_bot](https://t.me/Dekim_vpn_bot) | Telegram: [@QueenDek1m](https://t.me/QueenDek1m) |
|                                                        | Discord: `from_russia_with_love`                 |
