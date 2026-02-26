# Hong Kong Towngas for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration) [![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/vin_w)

[![Add integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=towngas_hk)

English | [繁體中文](./README_zh.md)

A Home Assistant custom integration for monitoring your [Hong Kong Towngas](https://eservice.towngas.com) gas consumption and billing via the eService portal.

## Features

- Current and Next Month gas consumption in MJ (actual or estimated)
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
| `sensor.current_month_gas_consumption` | Sensor | MJ | Current month gas consumption (actual or estimated) |
| `sensor.next_month_gas_consumption` | Sensor | MJ | Predicted next‑month gas consumption (actual or estimated) |
| `sensor.current_month_gas_consumption_unit` | Sensor | Unit | Current month consumption in units (1 unit = 48 MJ, integer) |
| `sensor.next_month_gas_consumption_unit` | Sensor | Unit | Predicted next‑month consumption in units (1 unit = 48 MJ, integer) |
| `sensor.account_no` | Sensor | — | Towngas account number |
| `sensor.consumption_month` | Sensor | — | Month label for the current consumption |
| `sensor.current_month_code` | Sensor | — | Machine-friendly month code for current month (`YYYY-MM`) |
| `sensor.next_month_code` | Sensor | — | Machine-friendly month code for next month (`YYYY-MM`) |
| `binary_sensor.current_is_estimate` | Binary Sensor | — | `on` if the current month value is estimated |
| `binary_sensor.next_is_estimate` | Binary Sensor | — | `on` if the next month value is estimated |
| `sensor.current_balance` | Sensor | HKD | Current account balance |
| `sensor.bill_amount_due` | Sensor | HKD | Latest bill amount due |
| `sensor.bill_due_date` | Sensor | Date | Bill payment due date |
| `binary_sensor.overdue_bill` | Binary Sensor | — | `on` if bill is overdue (shows as Problem in HA) |

### Attributes (shared by both consumption sensors)

Both `sensor.current_month_gas_consumption` and
`sensor.next_month_gas_consumption` expose the same, minimal attribute
set used for templates and the Energy dashboard:

| Attribute | Description |
|-----------|-------------|
| `month` | Month string the sensor value applies to (e.g. "Feb 2026") |
| `is_estimate` | True if the reported value is an estimated (forecast) value |

Account number is available as `sensor.account_no`.

### Attributes (`sensor.current_balance`)

| Attribute | Description |
|-----------|-------------|
| `updated_date` | Date balance was last updated |
| `auto_pay` | Whether auto-pay is enabled |
| `ibill` | Whether iBill (e-statement) is enrolled |
| `account_status` | Account status (`A` = Active) |

## Energy Dashboard

Go to **Settings → Dashboards → Energy** and add the current-month sensor under **Gas consumption**.  The next-month sensor can also be used for forecasts.

## Requirements

- Towngas eService account at https://eservice.towngas.com
- Home Assistant 2023.1.0 or newer

## Disclaimer

This project is an independent, unofficial integration and is not affiliated with The Hong Kong and China Gas Company Limited.
