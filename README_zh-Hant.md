# 香港中華煤氣 for Home Assistant 🔥

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration) [![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/vin_w)

繁體中文 | [English](./README.md)

香港中華煤氣 Home Assistant 自訂整合，用於透過 eService 門戶監控您的煤氣用量和帳單。

<!-- TODO: 請重新截圖 -->
![卡片範例](docs/images/towngas-card.png)

<!-- TODO: 請重新截圖 -->
![提醒範例](docs/images/notification_zh-Hant.jpeg)

## 特色 ⭐

- 🔥 每月煤氣用量（MJ 及度數）
- 📊 累計煤氣錶讀數
- 💰 根據實際用量及當前燃料調整費率計算估計煤氣費
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

| 實體 | 單位 | 描述 |
|------|------|------|
| `sensor.towngas_hk_{account}_consumption` | MJ | 本月煤氣用量 |
| `sensor.towngas_hk_{account}_consumption_units` | 度數 | 本月用量（度數） |
| `sensor.towngas_hk_{account}_meter_reading` | 度數 | 累計煤氣錶讀數 |
| `sensor.towngas_hk_{account}_reading_type` | — | 讀數類型：Remote / Actual / Estimate |
| `sensor.towngas_hk_{account}_reading_date` | 日期 | 最新讀數日期 |
| `sensor.towngas_hk_{account}_latest_reading_text` | — | 預先格式化的最新讀數資訊（如有） |
| `sensor.towngas_hk_{account}_tariff_estimate` | HKD | 根據最新用量計算的估計煤氣費 |
| `sensor.towngas_hk_{account}_account_no` | — | 中華煤氣帳戶號碼 |
| `sensor.towngas_hk_{account}_balance` | HKD | 帳戶結餘 |
| `sensor.towngas_hk_{account}_bill_amount` | HKD | 最近一期賬單金額 |
| `sensor.towngas_hk_{account}_bill_due_date` | 日期 | 賬單到期日 |

### `consumption` 感測器屬性

| 屬性 | 描述 |
|------|------|
| `reading_type` | Remote / Actual / Estimate |
| `reading_date` | 讀數的 ISO 日期 |
| `meter_reading` | 累計錶讀數（度數） |
| `consumption_units` | 原始用量（度數） |
| `has_prediction` | 中華煤氣是否顯示預測用量 |
| `latest_reading_text` | API 提供的預先格式化文字 |

### `tariff_estimate` 感測器屬性

| 屬性 | 描述 |
|------|------|
| `consumption_mj` | 用於計算的用量（MJ） |
| `fuel_rate_cents` | 當前燃料調整費率（仙/MJ） |
| `tariff_source` | 官方收費標準頁面 URL |
| `tariff_effective_date` | 收費標準最後更新日期 |

### `balance` 感測器屬性

| 屬性 | 描述 |
|------|------|
| `updated_date` | 結餘最後更新日期 |
| `auto_pay` | 是否已設定自動轉賬 |
| `ibill` | 是否已登記電子賬單 |
| `account_status` | 帳戶狀態（`A` = 有效） |

### 燃料調整費率輔助輸入

安裝整合時會自動建立一個名為 `Towngas <帳戶> Fuel Adjust Rate` 的
`input_number` 輔助實體。預設值為 **4.52 仙/MJ**，可至「設定 → 設備與
服務 → 輔助實體」修改。費率變更後，估計煤氣費感測器會使用該值計算；
如果輔助實體不存在，則採用預設費率。

## 用量與度數說明

- **用量 (MJ)** 指的是每次抄表時顯示的煤氣熱能消耗，以兆焦為單位，
  亦即賬單上的實際耗用數值。
- **度數** 是按每 48 MJ 計算的傳統電錶式顯示單位，也是中華煤氣
  在網站與紙本賬單上使用的標準。

轉換公式：`度數 × 48 = MJ`

### 帳單周期說明

當月用量感測器代表**最後完成的抄表周期**。中華煤氣通常在當月初進行抄表。
整合使用 API 的 `historyList` 作為主要數據來源，該列表始終包含最新數據
（包括在 chartBarList 更新前的手動抄表）。

官方資源：
- 收費標準：https://www.towngas.com/en/Household/Customer-Services/Tariff
- 如何閱讀煤氣單：https://www.towngas.com/media/getmedia/2f4237d6-bd4c-4f13-9b7c-50b009183468/how-to-read-bill_chi.pdf

## 儀表板範例 🖥️

<!-- TODO: 請重新截圖 -->

您可以在任何儀表板中新增簡單的中華煤氣卡片堆疊：

```yaml
type: vertical-stack
cards:
  - type: history-graph
    title: 煤氣使用量（月度）
    entities:
      - entity: sensor.towngas_hk_{account}_consumption
        name: 本月用量 (MJ)
    hours_to_show: 720
  - type: entities
    state_color: true
    entities:
      - entity: sensor.towngas_hk_{account}_consumption
      - entity: sensor.towngas_hk_{account}_consumption_units
      - entity: sensor.towngas_hk_{account}_meter_reading
      - entity: sensor.towngas_hk_{account}_reading_type
      - entity: sensor.towngas_hk_{account}_reading_date
      - entity: sensor.towngas_hk_{account}_tariff_estimate
```

## 能源儀表板 ⚡

前往 **設定 → 儀表板 → 能源**，在 **煤氣消耗** 下新增 `sensor.towngas_hk_{account}_consumption`。

<!-- TODO: 請重新截圖 -->
![Towngas Energy Dashboard example](docs/images/gas_consumption.png)

## 自動化藍圖 🔁

已內置一個方便使用的自動化藍圖，當你的
煤氣賬單逾期時會發出提醒。你可以使用下面的按鈕
或以下網址直接匯入藍圖：

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fvin-w%2Fhass-towngas-hk%2Fblob%2Fmaster%2Fblueprints%2Foverdue_bill_alert_zh-Hant.yaml)

[https://github.com/vin-w/hass-towngas-hk/blob/master/blueprints/overdue_bill_alert_zh-Hant.yaml](https://github.com/vin-w/hass-towngas-hk/blob/master/blueprints/overdue_bill_alert_zh-Hant.yaml)

匯入後，請根據此藍圖建立一個自動化，並設定以下輸入：

1. **逾期賬單感測器** – 為你的煤氣賬戶選擇 `binary_sensor.overdue_bill`。
2. **通知服務** – 選擇一個通知服務（例如
   `notify.mobile_app_yourphone`）。

當感測器狀態變為 **on** 時，建立好的自動化會被觸發，
向所選的通知目標發送標題及訊息。

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
