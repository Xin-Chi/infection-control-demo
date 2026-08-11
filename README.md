# 感染管控收案系統 — 示範版

臨床資料檢閱與收案標註平台的**可展示版本**，由原大學專題（`djangoProject`，
實驗室內部稱為 AI Center）重寫而來。

原專案包含醫學影像分析（DICOM 檢視、影像分割模型）等模組，本示範版**不含這些功能**，
聚焦在感染管控的病患篩選與報告判讀流程。

> **站內所有資料皆為虛構。** 病患姓名、病歷號、病房、菌種、檢驗報告與檢查紀錄
> 都是由 `seed_demo` 指令以固定字庫產生，與任何真實醫院或病患無關。
> 本專案不連線任何醫院資料庫。

---

## 快速開始

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env          # 開發用預設值即可

python manage.py migrate
python manage.py seed_demo      # 產生虛構資料
python manage.py createsuperuser

python manage.py runserver
```

開啟 <http://127.0.0.1:8000/>，**不需要登入**即可瀏覽。

部署到公開網址的完整步驟見 **[DEPLOY.md](DEPLOY.md)**。

### 兩種執行模式

由 `DJANGO_DEMO_MODE` 環境變數切換（預設開啟）。

| | `DJANGO_DEMO_MODE=1`（預設） | `DJANGO_DEMO_MODE=0` |
| --- | --- | --- |
| 對象 | 公開展示 | 完整應用程式 |
| 未登入可見 | 只有「查詢」 | 無（一律導向登入） |
| 登入後可見 | 全部頁面，但**唯讀** | 全部（依權限） |
| 資料修改 | 一律拒絕（HTTP 403） | 依權限開放 |
| 導覽列 | 只列出「查詢」 | 依權限列出所有區塊 |

**為什麼示範版不設登入**：站內每一筆資料都是程式產生的虛構資料，沒有任何東西需要保護；
而要讓人點進來看，示範帳密本來就得公開，那道門等於沒鎖，只是多一個步驟。
權限系統本身並沒有被拿掉——`accounts/permissions.py`、`SectionPermission`、
`TopicPermission` 都仍在，關閉示範模式就會生效。

三個存取層級由 `accounts/permissions.py` 的裝飾器表達，同一份 view 同時服務兩種模式：

| 裝飾器 | 用途 |
| --- | --- |
| `demo_readable(section)` | 示範模式公開；否則等同 `gated` |
| `gated(section)` | 一律需登入且具該區塊權限 |
| `blocked_in_demo(section)` | 會寫入資料；示範模式一律 403 |

### 帳號

`seed_demo` 會建立三個帳號，密碼皆為 `demo-pass-2026`：

| 帳號 | 權限 |
| --- | --- |
| `demo` | 感染管控 + 癌症研究 |
| `infection` | 僅感染管控 |
| `research` | 僅癌症研究 |

管理員功能（權限控管、`/admin/`）需要 superuser 帳號。

即使在示範模式下，登入後仍可檢視其餘頁面（唯讀）——這是刻意的，讓有興趣的人能看到
完整系統的樣子。這些頁面頂端會顯示「唯讀模式」提示，且編輯控制項會被停用，
而不是留著可點但一按就失敗。

> 開發時若修改模板沒有生效，請重啟 `runserver`。Django 4.1 起即使
> `DEBUG=True` 也會啟用樣板快取，靠開發伺服器自動重啟來更新；若以
> `--noreload` 啟動就不會自動重載。

---

## 功能範圍

| 區塊 | 頁面 | 未登入可見 |
| --- | --- | --- |
| 感染管控 | 查詢（病患時間軸） | ✅ |
| 感染管控 | 歸類（字詞詞庫）、管路確認、管路歸類 | 需登入・唯讀 |
| 癌症研究 | 入庫清單、研究主題、確認病患階段 | 需登入・唯讀 |
| 管理員專區 | 權限控管、Django admin 資料維護 | 需 superuser・唯讀 |

### 查詢頁

進入時會先顯示一次「示範資料聲明」，需按下確認才能繼續；
點背景或 Esc 不會關閉，且**不記住確認狀態**，每次進入都會再次顯示。

版面分三欄：**病患清單 → 時間軸 → 整理後報告**，
另有兩個側邊抽屜：左側「篩選」、右側「原始報告」。

#### 時間軸

採垂直事件流呈現，而非寬表格：

* 事件類別以左緣細色條標示（住院／護理／導管／生理評值各一色），
  強烈色彩只保留給臨床上需要注意的項目——目前是發燒。
* 生命徵象以 BT／BP／PULSE／SPO2 四欄一列內嵌顯示，
  不會像多欄表格那樣被擠出畫面。
* 培養出菌種的事件標有細菌圖示（常在菌以灰色與標籤區別）；
  體溫 ≥ 38.0°C 標有發燒圖示，該筆整體轉為警示配色。

#### 原始報告（右側抽屜）

來源系統輸出的**純文字報告全文**，以等寬字型呈現、保留原始欄位對齊，
包含表頭（病歷號、報告編號、採檢／簽收／報告時間）與完整敘述。
護理紀錄的敘述長度約 400–570 字，與實際病房紀錄的密度相當。

#### 整理後報告（右側面板）

同一份資料經系統解析後的結構化結果，可與原文對照。分兩個頁籤：

* **生命徵象** — 該病患**跨所有紀錄統整**的時間序列表格
  （Time／脈搏／呼吸／血氧／體溫／收縮壓／舒張壓）。
  未量測的欄位留白；超出參考範圍的數值以整格反色標示
  （偏高紅底、偏低藍底），並附 `title` 說明方向，不單靠顏色辨識。
  參考範圍集中定義於 `clinical/vitals.py`，與時間軸的發燒標記共用同一組閾值。
* **檢驗／護理報告** — 點選時間軸事件後切換至此。
  * **微生物培養報告**：檢驗報告【日期】、檢驗項目、檢驗來源的表頭，
    接著**每一株分離菌各一個面板**（同一檢體常培養出多株菌），
    面板內為該菌株的抗生素敏感性測試，欄位順序為
    判讀（S／I／R）→ MIC → 抗生素名稱。
  * **護理紀錄／生理評值紀錄**：病程敘述，其中的生命徵象數值會 highlight。

#### 護理紀錄與異常生理評值的區別

兩者是**產生原因**不同，而非資料多寡：

| | 護理紀錄／交班紀錄 | 異常生理評值 |
| --- | --- | --- |
| 觸發 | 例行排程，每班固定記錄 | 生命徵象超出範圍才開立 |
| 內容 | 照護過程、管路、進食、排泄、衛教 | 發現異常 → 通報醫師 → 處置 → 複測 |
| 數值 | 通常正常（約 9% 會測到異常） | **必定**至少一項超出參考範圍 |

種子資料以 `_abnormal_reading()` 保證後者一定含異常值——否則那筆紀錄就沒有存在的理由。

原專案的**醫學影像相關功能已全部移除**（DICOM 檢視、影像上傳、MRI/RT 工具、
影像切片標註）。入庫清單保留檢查紀錄的**中繼資料**（檢查編號、序列、張數），
但不含任何影像像素資料。自然語言分析（字詞生成、詞語歸類）與 MEWS 亦不在此版本範圍。

---

## 專案結構

```
config/      設定、URL、WSGI/ASGI
accounts/    帳號、個人設定、區塊與主題權限、管理員控制台
clinical/    病患、病房、科別、事件類別、臨床事件、生命徵象、報告、導管
             ├ vitals.py                          生命徵象參考範圍與判讀
             └ management/commands/seed_demo.py   虛構資料產生器
infection/   感染管控：字詞、分類、詞庫歸類
research/    癌症研究：研究主題、疾病分組、檢查紀錄、階段確認
templates/   頁面模板
static/      CSS、JS、圖片、vendored Bootstrap
```

---

## 相較原專案的改動

### 資安

| 原本 | 現在 |
| --- | --- |
| SQL 以 f-string 拼接使用者輸入（`where ChartNo={ChartNo}`），可注入 | 全面改用 ORM，所有值皆參數化 |
| 幾乎每個 view 都掛 `@csrf_exempt`，CSRF 防護等同關閉 | 移除；前端由 cookie 讀取 token 隨請求送出 |
| 以黑名單過濾 `select`/`drop` 等關鍵字擋注入 | 移除；參數化本身即可根治，黑名單可被繞過 |
| 權限存在 session 的 `au` 字元陣列，可竄改且撤銷後仍有效 | 每次請求由資料庫讀取權限（`SectionPermission`） |
| 多數 view 沒有 `login_required` | 全面加上 `login_required` 與 `section_required` |
| `SECRET_KEY`、資料庫密碼明碼寫在 `settings.py` | 改由環境變數提供，`.env` 已列入 `.gitignore` |
| `DEBUG = True` 寫死 | 由環境變數控制；關閉時自動啟用 HTTPS/HSTS 相關設定 |
| 註冊表單自訂、未套用密碼強度驗證 | 改用 `UserCreationForm`，套用 Django 密碼驗證器 |
| 登出是 GET 連結，可被第三方頁面觸發 | 改為 POST 表單 |
| Bootstrap 由公開 CDN 載入 | 改為本地 vendored |
| `X_FRAME_OPTIONS = 'SAMEORIGIN'`、上傳上限 5 GB | 改為 `DENY`、上傳上限 5 MB |
| 權限查詢用 `username like 'name%'`，會誤中其他帳號 | 改為外鍵關聯精確比對 |
| 使用者名稱等資料以 `innerHTML` 寫入 | 一律 `textContent`，避免 XSS |

### 程式寫法

- `models.py` 原本全空、全靠手寫 SQL；現在有完整 ORM 模型、外鍵、唯一性約束與 migration。
- 魔術數字改為具名選項：`checked = -1/0/1` → `Status.ABANDONED/PENDING/CONFIRMED`；
  導管 `Category=2/3` → `VARIANT_A/VARIANT_B`。
- `tube` 與 `tube2` 兩個幾乎相同的 app 合併成一個帶參數的頁面；`warehousing` 與 `pool` 的
  重複清單邏輯同樣合併。
- 計數更新原本先讀值、在 Python 加一再寫回（併發會漏更新），改為資料庫端 `F()` 運算。
- API 回傳由多個平行陣列（`{'TokenID': [...], 'Token': [...]}`）改為物件陣列。
- 移除散落各處的 `print(query)`，改用 logging 設定。

### 版面（RWD）

原本每個面板都以 `position: absolute` 搭配手調的固定值定位
（`top: 65px; left: calc(22% + 20px); width: 30%`），且全站**沒有任何 `@media` 斷點**，
`body` 還設了 `position: fixed` 讓頁面無法捲動——換一台螢幕就會錯位。

現在：

- 版面改用 **CSS Grid + Flexbox**，欄數隨視窗寬度收合（三欄 → 二欄 → 單欄）。
- 面板各自內部捲動，頁面不會橫向捲動；寬表格在自己的容器內捲動。
- 篩選與報告面板改為抽屜（drawer），窄螢幕不會壓到內容。
- 尺寸改用相對單位與 `clamp()`；斷點定義於 `static/css/app.css`。
- 移除 `maximum-scale=1, user-scalable=0`，恢復雙指縮放。
- 切換鈕改為「選中＝深色填滿」，並加上 `aria-pressed`；
  原本是選中反而顯示白底，狀態也只靠顏色表達。
- CSS／JS 網址以檔案 mtime 加上版本參數（`{% static_v %}`，見
  `accounts/templatetags/assets.py`）。開發伺服器只送 `Last-Modified`，
  瀏覽器可能沿用舊快取，導致新版 HTML 套到舊版樣式而整個版面崩掉。

---

## 資料模型概覽

```
Patient ──< ClinicalEvent >── MedType
   │             │  │  └──< ExamReport ──< CultureIsolate ──< SusceptibilityResult
   │             │  │            │             └── Bacteria    （藥敏測試）
   │             │  │            └ raw_text    （來源系統原文，結構化欄位由此解析而來）
   │             │  └───── VitalSign          （時間軸上的單筆摘要）
   │             └──< ExamStudy               （檢查中繼資料，無影像）
   └──< VitalMeasurement                      （統整生命徵象表，跨紀錄依時間排序）
Ward ── Division
Tube ──> Tube (canonical)                     （原始名稱對應標準名稱）

Token ──< CategoryPoolEntry >── InfectionCategory      （待審字詞）
Token ──< ConversionEntry   >── ConversionCategory     （已歸類詞庫）

Patient ──< PatientDisease >── DiseaseGroup
ResearchTopic ──< StageDefinition ──< StageConfirmation >── User
User ──< SectionPermission / TopicPermission / Profile
```

---

## 重新產生資料

```bash
python manage.py seed_demo --reset            # 清除後重建
python manage.py seed_demo --reset --patients 100
```

`--reset` 會刪除示範資料與所有非 superuser 帳號。
