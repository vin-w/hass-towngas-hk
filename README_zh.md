# 香港中華煤氣 for Home Assistant ⛽

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration) [![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/vin_w)

繁體中文 | [English](./README.md)

香港中華煤氣 Home Assistant 自訂整合，用於透過 eService 門戶監控您的煤氣消耗量和帳單。

## 特色 ⭐

- 🔥 現月與次月煤氣消耗量（MJ，實測或估計）
- 💰 帳單歷史（HKD）
- 👥 支援多個中華煤氣帳戶
- 📊 相容 Home Assistant 能源儀表板
- 🧩 UI 設定（無需 YAML）

## 安裝

### HACS（推薦）

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vin-w&repository=hass-towngas-hk&category=integration)

或者在 HACS 中手動新增 `https://github.com/vin-w/hass-towngas-hk` 作為自訂儲存庫。

---

## 設定 ⚙️

[![Add integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=towngas_hk)

1. **設定 → 設備與服務 → 新增整合**
2. 搜尋 **香港中華煤氣**
3. 輸入您的中華煤氣 eService 使用者名稱和密碼
4. 選擇您的帳戶（若有多個帳戶）

## 感測器 🔍

每個已設定的中華煤氣帳戶將以**裝置**形式新增，包含以下實體：

| 實體 | 類型 | 單位 | 描述 |
|------|------|------|------|
| `sensor.current_month_gas_consumption` | 感測器 | MJ | 當月煤氣消耗量（月中為估計值） |
| `sensor.next_month_gas_consumption` | 感測器 | MJ | 下一個月預測用量 |
| `sensor.current_month_gas_consumption_unit` | 感測器 | 度 | 當月消耗量（1 度 = 48 MJ，整數） |
| `sensor.next_month_gas_consumption_unit` | 感測器 | 度 | 下月預測消耗量（1 度 = 48 MJ，整數） |
| `sensor.account_no` | 感測器 | — | 中華煤氣帳戶號碼 |
| `sensor.current_month_code` | 感測器 | — | 機器可讀的本月代碼（`YYYY-MM`） |
| `sensor.next_month_code` | 感測器 | — | 機器可讀的下月代碼（`YYYY-MM`） |
| `binary_sensor.current_consumption_is_estimate` | 二元感測器 | — | 若當月數值為估計則為 `on` |
| `binary_sensor.next_consumption_is_estimate` | 二元感測器 | — | 若下月數值為估計則為 `on` |
| `sensor.current_balance` | 感測器 | HKD | 帳戶結餘 |
| `sensor.bill_amount_due` | 感測器 | HKD | 最近一期賬單金額 |
| `sensor.bill_due_date` | 感測器 | 日期 | 賬單到期日 |
| `binary_sensor.overdue_bill` | 二元感測器 | — | 逾期未繳時顯示為「問題」 |

### 屬性（由兩個消耗量感測器共用）

`sensor.current_month_gas_consumption` 和
`sensor.next_month_gas_consumption` 均提供下列簡潔屬性：

| 屬性 | 描述 |
|------|------|
| `month` | 感測器值所屬之月份字串（例如「Feb 2026」） |
| `is_estimate` | 若該數值為預估（非實際抄表）則為 True |

帳戶號碼現已提供為 `sensor.account_no` 。

### 屬性（`sensor.current_balance`）

| 屬性 | 描述 |
|------|------|
| `updated_date` | 結餘最後更新日期 |
| `auto_pay` | 是否已設定自動轉賬 |
| `ibill` | 是否已登記電子賬單 |
| `account_status` | 帳戶狀態（`A` = 有效） |

## 能源儀表板 ⚡

前往 **設定 → 儀表板 → 能源**，在 **煤氣消耗** 下新增當月感測器。預測感測器亦可用於預覽。

## 需求 📦

- 中華煤氣 eService 帳戶 [https://eservice.towngas.com](https://eservice.towngas.com)
- Home Assistant 2025.1.0 或更新版本

## 支持這個整合 🤝

### 問題與 Pull request

使用中遇到問題或有新功能想法，歡迎開啟新的 [issue](https://github.com/vin-w/hass-towngas-hk/issues/new/choose)。你也可以提交 [pull request](https://github.com/vin-w/hass-towngas-hk/pulls)，無論是程式碼或文件修改都很感謝！

### 其他支援

這是一個業餘時間開發的非官方專案。如果你覺得滿意，可以透過買杯咖啡支持我：

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/vin_w)

---

## 免責聲明 ⚠️

本專案為獨立的非官方整合，與香港中華煤氣有限公司無關亦未經其認可。
