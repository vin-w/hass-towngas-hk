# 香港中華煤氣 for Home Assistant 🔥

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration) [![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/vin_w)

繁體中文 | [English](./README.md)

香港中華煤氣 Home Assistant 自訂整合，用於透過 eService 門戶監控您的煤氣用量和帳單。

![卡片範例](docs/images/towngas-card.png)

## 特色 ⭐

- 🔥 每月煤氣用量（MJ 及度數）
- 📊 累計煤氣錶讀數
- 💰 根據實際用量及當前燃料調整費率計算估計煤氣費
- 👥 支援多個中華煤氣帳戶
- 📊 相容 Home Assistant 能源儀表板
- 🧩 UI 設定（無需 YAML）
- 🔄 智能快取自動更新（每月帳單週期）
- 🔔 透過自動化藍圖接收賬單逾期提醒

## 安裝

### HACS（推薦）

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vin-w&repository=hass-towngas-hk&category=integration)

或者在 HACS 中手動新增 `https://github.com/vin-w/hass-towngas-hk` 作為自訂儲存庫。

---

## 設定 ⚙️

[![Add integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=towngas_hk)

1. **設定 → 裝置與服務 → 新增整合**
2. 搜尋 **Hong Kong Towngas**
3. 輸入您的中華煤氣 eService 使用者名稱和密碼
4. ☐ **儲存密碼以自動重新整理** — 如需自動更新資料，請勾選此選項
5. 您將收到一封 **6位數驗證碼** 電郵 — 輸入驗證碼以確認身份
6. 選擇您的帳戶（如有多个帳戶）

---

## 認證與資料更新 🔐

中華煤氣要求每次登入都需要 **OTP（一次性密碼）驗證**。這是中華煤氣的安全措施，無法繞過。

### 資料更新方式

| 情況 | 處理方式 |
|------|---------|
| **已儲存密碼** | 協調器在重啟時自動登入。資料每 30 天自動更新（對應每月帳單週期）。 |
| **未儲存密碼** | 顯示上次成功擷取的快取資料，直到 30 天更新間隔到期。之後需重新驗證。 |

### 何時需要重新驗證

- **連線逾時** — HA 在「設定 → 整合」中顯示「重新驗證」通知
- **強制重新整理** — 按裝置上的「強制重新整理」按鈕手動取得最新資料
- **30 天後** — 自動更新需要有效的登入憑證

### 重新驗證流程

1. 在修復通知中點擊**重新驗證**
2. 輸入密碼（已儲存則自動填入）
3. ☐ 如需自動更新，勾選**儲存密碼以自動重新整理**
4. 輸入寄送到您電郵的 **6位數驗證碼**
5. 完成 — 已載入最新資料

### 未儲存密碼的情況

如果您在設定時選擇不儲存密碼：
- 感測器顯示上次成功擷取的**快取資料**
- 30 天後仍顯示快取資料，但不會擷取新資料
- 點擊**強制重新整理** → 輸入密碼 → 輸入驗證碼 → 載入最新資料
- 您可在重新驗證時啟用「儲存密碼」以避免日後重複輸入

---

## 感測器 🔍

每個已設定的中華煤氣帳戶會新增為一個**裝置**（命名為 `Towngas HK Account <號碼>`），包含以下實體：

| 實體 ID | 單位 | 描述 |
|---------|------|------|
| `sensor.towngas_hk_{account}_consumption` | MJ | 每月煤氣用量 |
| `sensor.towngas_hk_{account}_consumption_units` | 度數 | 每月用量（度數） |
| `sensor.towngas_hk_{account}_meter_reading` | 度數 | 累計煤氣錶讀數 |
| `sensor.towngas_hk_{account}_reading_type` | — | 讀數方式：遙讀 / 實讀 / 估算 |
| `sensor.towngas_hk_{account}_reading_date` | 日期 | 最新讀數日期 |
| `sensor.towngas_hk_{account}_latest_reading_text` | — | 最新讀數預先格式化文字 |
| `sensor.towngas_hk_{account}_tariff_estimate` | HKD | 根據最新用量估算的煤氣費 |
| `sensor.towngas_hk_{account}_account_no` | — | 中華煤氣帳戶號碼 |
| `sensor.towngas_hk_{account}_balance` | HKD | 最新賬單結餘（超過 $0 即逾期） |
| `sensor.towngas_hk_{account}_bill_amount` | HKD | 最新賬單金額 |
| `sensor.towngas_hk_{account}_bill_due_date` | 日期 | 賬單到期日 |

### 按鈕實體

| 實體 ID | 描述 |
|---------|------|
| `button.towngas_hk_{account}_force_refresh` | 強制重新擷取資料（清除快取並重新驗證） |

### 感測器屬性

**consumption** 感測器：
| 屬性 | 描述 |
|------|------|
| `reading_type` | 遙讀 / 實讀 / 估算 |
| `reading_date` | 讀數日期 (ISO) |
| `meter_reading` | 累計錶讀總數（度數） |
| `consumption_units` | 原始用量（度數） |
| `has_prediction` | 中華煤氣是否顯示預測 |
| `latest_reading_text` | API 預先格式化文字 |

**tariff_estimate** 感測器：
| 屬性 | 描述 |
|------|------|
| `consumption_mj` | 計算所用 MJ |
| `fuel_rate_cents` | 當前燃料調整費率（¢/MJ） |
| `tariff_source` | 官方收費頁面 URL |
| `tariff_effective_date` | 費率最後更新日期 |

**balance** 感測器：
| 屬性 | 描述 |
|------|------|
| `updated_date` | 餘額最後更新日期 |
| `auto_pay` | 是否啟用自動繳費 |
| `ibill` | 是否訂閱電子賬單 |
| `account_status` | 帳戶狀態（`A` = 活躍） |

---

## 收費與帳單 💰

### 估計收費方式

估計收費基於：
1. **階梯煤氣收費** — 按用量區間的每 MJ 收費
2. **燃料調整費** — 浮動費率（預設：4.52 ¢/MJ，可透過輔助工具調整）
3. **每月保養費** — HK$10
4. **每月基本費** — HK$20（僅在煤氣費 < $20 時收取）

來源：[中華煤氣收費](https://www.towngas.com/en/Household/Customer-Services/Tariff)

### 燃料調整輔助工具

整合使用燃料調整費率（預設：**4.52 ¢/MJ**）來估算煤氣費。此費率每月變更。您可透過**設定 → 裝置與服務 → 輔助工具**進行調整 — 尋找 `Towngas <帳戶> Fuel Adjust Rate`。

### 用量與度數

- **用量（MJ）** — 煤氣熱能消耗，以百萬焦耳計。這是實際計費數值。
- **度數** — 傳統煤氣錶顯示方式，1 度 = 48 MJ。

換算：`度數 × 48 = MJ`

### 帳單週期

每月用量感測器顯示**最近完成的讀數週期**。中華煤氣通常在每月月初讀錶。

---

## 儀表板範例 🖥️

### Lovelace 卡片

```yaml
type: vertical-stack
cards:
  - type: history-graph
    title: Towngas Usage (Monthly)
    entities:
      - entity: sensor.towngas_hk_{account}_consumption
        name: Consumption (MJ)
    hours_to_show: 720
  - type: entities
    state_color: true
    entities:
      - entity: sensor.towngas_hk_{account}_consumption
      - entity: sensor.towngas_hk_{account}_consumption_units
      - entity: sensor.towngas_hk_{account}_meter_reading
      - entity: sensor.towngas_hk_{account}_tariff_estimate
      - entity: sensor.towngas_hk_{account}_balance
      - entity: sensor.towngas_hk_{account}_bill_amount
      - entity: sensor.towngas_hk_{account}_bill_due_date
      - entity: button.towngas_hk_{account}_force_refresh
```

### 能源儀表板

前往**設定 → 儀表板 → 能源**，在**煤氣用量**下新增 `sensor.towngas_hk_{account}_consumption`（單位 MJ）。

---

## 自動化藍圖 🔁

藍圖可用於在帳戶餘額超過 $0（賬單逾期）時發送提醒。

[![匯入藍圖](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fvin-w%2Fhass-towngas-hk%2Fblob%2Fmaster%2Fblueprints%2Foverdue_bill_alert_zh-Hant.yaml)

### 設定

1. 從上方連結匯入藍圖
2. 從藍圖建立自動化
3. 設定：
   - **餘額感測器** — 選擇 `sensor.towngas_hk_{account}_balance`
   - **通知服務** — 選擇您的通知服務（例如 `notify.mobile_app_yourphone`）
4. 當餘額超過 $0 時，自動化將觸發通知

---

## 需求 📦

- 中華煤氣 eService 帳戶 https://eservice.towngas.com
- Home Assistant 2026.1.0 或更新版本

---

## 支援整合 🤝

### 問題與 Pull Request

如果您遇到任何問題或有改進建議，歡迎開新 [Issue](https://github.com/vin-w/hass-towngas-hk/issues/new/choose)。如果您想貢獻程式碼或文件，也非常歡迎提交 [Pull Request](https://github.com/vin-w/hass-towngas-hk/pulls)！

### 其他支援

這是一個業餘時間的非官方項目。如果您覺得有用，歡迎請我喝杯咖啡以表支持：

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/vin_w)

---

## 免責聲明 ⚠️

本項目是一個獨立的非官方整合，與香港中華煤氣有限公司無關。
