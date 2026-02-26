# Hong Kong Towngas for Home Assistant 🔥

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration) [![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/vin_w)

English | [繁體中文](./README_zh.md)

A Home Assistant custom integration for monitoring your [Hong Kong Towngas](https://eservice.towngas.com) gas consumption and billing via the eService portal.

![Towngas card example](docs/images/towngas-card.png)

## Features ⭐

- 🔥 Current and Next Month gas consumption in MJ (actual or estimated)
- 💰 Billing history with amounts in HKD
- 👥 Supports multiple Towngas accounts
- 📊 Compatible with the Home Assistant Energy Dashboard
- 🧩 Setup via UI (no YAML required)

## Installation

### HACS (Recommended)

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vin-w&repository=hass-towngas-hk&category=integration)

Or manually add `https://github.com/vin-w/hass-towngas-hk` as a Custom Repository in HACS.

---

## Configuration ⚙️

[![Add integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=towngas_hk)

1. **Settings → Devices & Services → Add Integration**
2. Search **Hong Kong Towngas**
3. Enter your Towngas eService username and password
2. Select your account (if multiple accounts exist). Each entry will be titled `Towngas HK <account_number>`.

## Sensors 🔍

Each configured Towngas account is added as a **device** (named `Towngas HK Account <number>`) with the following entities:

| Entity | Type | Unit | Description |
|--------|------|------|-------------|
| `sensor.current_month_gas_consumption` | Sensor | MJ | Current month gas consumption (actual or estimated) |
| `sensor.next_month_gas_consumption` | Sensor | MJ | Next‑month gas consumption (estimated) |
| `sensor.current_month_gas_consumption_unit` | Sensor | Unit | Current month consumption in units (1 unit = 48 MJ, integer) |
| `sensor.next_month_gas_consumption_unit` | Sensor | Unit | Predicted next‑month consumption in units (1 unit = 48 MJ, integer) |
| `sensor.account_no` | Sensor | — | Towngas account number |
| `sensor.current_month_code` | Sensor | — | Machine-friendly month code for current month (`YYYY-MM`) |
| `sensor.next_month_code` | Sensor | — | Machine-friendly month code for next month (`YYYY-MM`) |
| `binary_sensor.current_consumption_is_estimate` | Binary Sensor | — | `on` if the current month value is estimated |
| `binary_sensor.next_consumption_is_estimate` | Binary Sensor | — | `on` if the next month value is estimated |
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

## Dashboard example 🖥️

You can add a simple Towngas card stack to any dashboard:

```yaml
type: vertical-stack
cards:
  - type: history-graph
    title: Towngas Usage (Monthly)
    entities:
      - entity: sensor.towngas_current_month_gas_consumption
        name: Current month
      - entity: sensor.towngas_next_month_gas_consumption
        name: Next month
    hours_to_show: 720
  - type: entities
    state_color: true
    entities:
      - entity: binary_sensor.towngas_overdue_bill
        name: Overdue bill
      - entity: sensor.towngas_bill_due_date
      - entity: sensor.towngas_bill_amount_due
```

## Energy Dashboard ⚡

Go to **Settings → Dashboards → Energy** and add the sensor.current_month_gas_consumption (in MJ) under **Gas consumption**.

![Towngas Energy Dashboard example](docs/images/gas_consumption.png)

## Automation Blueprint 🔁

A convenient automation blueprint is included to alert you when your
Towngas bill becomes overdue. You can import it directly using the
button below or by using the URL:

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?url=https://github.com/vin-w/hass-towngas-hk/blob/master/blueprints/overdue_bill_alert_en.yaml)

[https://github.com/vin-w/hass-towngas-hk/blob/master/blueprints/overdue_bill_alert_en.yaml](https://github.com/vin-w/hass-towngas-hk/blob/master/blueprints/overdue_bill_alert_en.yaml)

Once imported, create an automation from the blueprint and configure the
inputs:

1. **Overdue Bill Sensor** – select `binary_sensor.overdue_bill` for your
   Towngas account.
2. **Notification Service** – choose a notify service (e.g.
   `notify.mobile_app_yourphone`).

The built automation will fire when the sensor turns **on**, sending a
title/message to the chosen notify target.


## Requirements 📦

- Towngas eService account at https://eservice.towngas.com
- Home Assistant 2025.1.0 or newer

## Support the integration 🤝

### Issues and pull requests

If you run into any problems or have ideas for improvements, feel free to open a new [issue](https://github.com/vin-w/hass-towngas-hk/issues/new/choose). You're also very welcome to send a [pull request](https://github.com/vin-w/hass-towngas-hk/pulls) if you'd like to contribute code or documentation!

### Other support

This is a free‑time, unofficial project. If you find it useful, you can buy me a coffee to show your appreciation:

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/vin_w)

---

## Disclaimer ⚠️

This project is an independent, unofficial integration and is not affiliated with The Hong Kong and China Gas Company Limited.
