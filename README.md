# Hong Kong Towngas for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

[![Add integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=towngas_hk)

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/vin_w)

English | [繁體中文](./README_zh.md)

A Home Assistant custom integration for monitoring your [Hong Kong Towngas](https://eservice.towngas.com) gas consumption and billing via the eService portal.

## Features

- Monthly gas consumption in MJ (current + historical)
- Estimated consumption for the current month
- Billing history with amounts in HKD
- Supports multiple Towngas accounts
- Compatible with the Home Assistant Energy Dashboard
- Setup via UI (no YAML required)

## Installation

### HACS (Recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/vin-w/hass-towngas-hk` as an **Integration**
3. Search for **Hong Kong Towngas** and install
4. Restart Home Assistant

### Manual

Copy `custom_components/towngas_hk/` to your HA `config/custom_components/` folder, then restart.

## Configuration

1. **Settings → Devices & Services → Add Integration**
2. Search **Hong Kong Towngas**
3. Enter your Towngas eService username and password
4. Select your account (if multiple accounts exist)

## Sensors

Each configured Towngas account is added as a **device** with the following entities:

| Entity | Type | Unit | Description |
|--------|------|------|-------------|
| `sensor.gas_consumption` | Sensor | MJ | Current month gas consumption (estimated if mid-cycle) |
| `sensor.current_balance` | Sensor | HKD | Current account balance |
| `sensor.bill_amount_due` | Sensor | HKD | Latest bill amount due |
| `sensor.bill_due_date` | Sensor | Date | Bill payment due date |
| `binary_sensor.overdue_bill` | Binary Sensor | — | `on` if bill is overdue (shows as Problem in HA) |

### Attributes (`sensor.gas_consumption`)

| Attribute | Description |
|-----------|-------------|
| `account_no` | Towngas account number |
| `readings` | Last 8 months of consumption history |
| `bills` | Last 4 bills with date and HKD amount |

### Attributes (`sensor.current_balance`)

| Attribute | Description |
|-----------|-------------|
| `updated_date` | Date balance was last updated |
| `auto_pay` | Whether auto-pay is enabled |
| `ibill` | Whether iBill (e-statement) is enrolled |
| `account_status` | Account status (`A` = Active) |

## Energy Dashboard

Go to **Settings → Dashboards → Energy** and add the sensor under **Gas consumption**.

## Requirements

- Towngas eService account at https://eservice.towngas.com
- Home Assistant 2023.1.0 or newer

## Disclaimer

Not affiliated with or endorsed by The Hong Kong and China Gas Company Limited.

<a href="https://www.flaticon.com/free-icons/gas" title="gas icons">Gas icons created by Freepik - Flaticon</a>

<a href="https://www.flaticon.com/free-icons/gas" title="gas icons">Gas icons created by Freepik - Flaticon</a>

<a href="https://www.flaticon.com/free-icons/gas" title="gas icons">Gas icons created by Freepik - Flaticon</a>
