# 部署到 PythonAnywhere（免費方案）

免費方案給一個 `<帳號>.pythonanywhere.com` 網址、一個 web app，不需信用卡，
檔案系統是持久的（SQLite 不會被清掉）。這個專案不呼叫任何外部 API，
所以免費方案的對外連線限制不影響它。

以下 `<user>` 請替換成你的 PythonAnywhere 帳號名稱。

---

## 1. 取得程式碼

在 PythonAnywhere 開一個 **Bash console**：

```bash
git clone https://github.com/<你的帳號>/<repo名>.git ~/aicenter_demo
cd ~/aicenter_demo
```

## 2. 建立虛擬環境

PythonAnywhere 的 `mkvirtualenv` 會把環境放在 `~/.virtualenvs/`，
Web 分頁需要填這個路徑。

```bash
mkvirtualenv --python=/usr/bin/python3.10 aicenter
pip install -r requirements.txt
```

（Python 版本可挑 PythonAnywhere 當下支援的任一 3.10+ 版本。）

## 3. 設定環境變數

專案的 `settings.py` 會自動讀取專案根目錄的 `.env`：

```bash
cd ~/aicenter_demo
python -c "from django.core.management.utils import get_random_secret_key as k; print('DJANGO_SECRET_KEY=' + k())" > .env
cat >> .env <<'EOF'
DJANGO_DEBUG=0
DJANGO_DEMO_MODE=1
DJANGO_ALLOWED_HOSTS=<user>.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://<user>.pythonanywhere.com
EOF
```

> `DJANGO_DEBUG=0` 時若沒有 `DJANGO_SECRET_KEY`，程式會直接拒絕啟動——
> 這是刻意的，避免拿預設金鑰上線。

**`DJANGO_DEMO_MODE=1` 一定要保留**，否則整站會變成需要登入才能看。

## 4. 建立資料庫與靜態檔

```bash
python manage.py migrate
python manage.py seed_demo          # 產生虛構資料
python manage.py collectstatic --noinput
```

要建管理員帳號（可看權限控管頁）再執行：

```bash
python manage.py createsuperuser
```

## 5. 設定 Web 分頁

到 **Web** 分頁 → **Add a new web app** → **Manual configuration**
（不要選 Django，那會另外幫你建一個新專案）→ 選對應的 Python 版本。

接著填三個欄位：

| 欄位 | 值 |
| --- | --- |
| Source code | `/home/<user>/aicenter_demo` |
| Working directory | `/home/<user>/aicenter_demo` |
| Virtualenv | `/home/<user>/.virtualenvs/aicenter` |

### WSGI 設定檔

點 **WSGI configuration file** 的連結，把內容整個換成：

```python
import os
import sys

path = '/home/<user>/aicenter_demo'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 靜態檔

WhiteNoise 已內建在 middleware 中，會直接送出 `staticfiles/` 的內容，
所以 **Static files 那一區可以留空不設定**。

（若想讓 PythonAnywhere 直接送靜態檔以減少 Python 負載，
可加一組對應 `/static/` → `/home/<user>/aicenter_demo/staticfiles`，
兩者並存也不會衝突。）

## 6. 重新載入

回到 Web 分頁按綠色的 **Reload** 按鈕，然後開
`https://<user>.pythonanywhere.com`。

---

## 更新已部署的版本

```bash
cd ~/aicenter_demo
git pull
workon aicenter
pip install -r requirements.txt      # 依賴有變才需要
python manage.py migrate
python manage.py collectstatic --noinput
```

最後回 Web 分頁按 **Reload**。

要把示範資料重置成乾淨狀態：

```bash
python manage.py seed_demo --reset
```

---

## 疑難排解

**整站沒有樣式（純文字裸頁）**
`collectstatic` 沒跑，或跑完後沒有 Reload。先確認
`~/aicenter_demo/staticfiles/` 底下有檔案。

**DisallowedHost 錯誤**
`.env` 的 `DJANGO_ALLOWED_HOSTS` 沒有包含你的網域。

**表單送出出現 CSRF 錯誤**
`.env` 的 `DJANGO_CSRF_TRUSTED_ORIGINS` 要填含 `https://` 的完整網址。

**改了程式但網站沒變**
PythonAnywhere 不會自動重載，每次都要按 Web 分頁的 **Reload**。

**看錯誤訊息**
Web 分頁下方有 Error log 與 Server log 連結，Django 的例外會出現在
Error log 裡。

---

## 為什麼不用 Render

Render 免費方案是**所有服務共用每月 750 小時**。若已有其他服務靠定時 ping
維持不休眠，額度基本上已被用盡，再開一個服務就會超額。
PythonAnywhere 的免費 web app 額度獨立，且不會因閒置而休眠，
面試官點進來不需要等待喚醒。
