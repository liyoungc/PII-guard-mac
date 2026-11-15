# PII Guard for Mac

[English](README.md) ｜ **繁體中文**

在 Mac 上完全離線，把文件裡的人名去識別化的選單列（menu bar）小工具。
原始用途是醫院病人安全通報文件：把「王小明」換成「王○○」，其餘內容與版面一個字都不動。

- **完全在本機執行**：用 [Rapid-MLX](https://github.com/raullenchai/Rapid-MLX) 在 Apple Silicon 上跑開源模型，文件內容不會離開這台 Mac。
- **模型只負責「找」，不負責「改」**：模型列出原文中的人名，取代由程式做。模型無法改寫你的文件。
- **只換文字**：直接改寫 `.docx`／`.xlsx`／`.pptx` 內的文字節點，字型、框線、圖片、公式、版面都維持原樣。
- **寫檔前人工確認**：先看清單、可取消、可手動補漏，也可以一鍵全部接受。
- **寫完自動複查**：重新開啟輸出檔，確認找不到任何已確認的原文。
- **原檔永不更動**：輸出寫在原檔旁的新檔（`檔名_去識別.xlsx`）。

> ⚠️ 模型不保證抓到每一個姓名，較小的模型更容易漏。這是輔助工具，重要文件請務必人工確認。

## 系統需求

- Apple Silicon Mac（M1 以後），macOS 14 以上，記憶體 8 GB 以上
- Xcode Command Line Tools（`xcode-select --install`）
- [uv](https://docs.astral.sh/uv/)（`brew install uv`）

## 安裝（從原始碼）

```bash
git clone https://github.com/liyoungc/PII-guard-mac.git
cd PII-guard-mac
scripts/install.sh
open "$HOME/Applications/PII Guard.app"
```

安裝腳本會做兩件事：把 Python 引擎與 Rapid-MLX 裝進獨立環境
（`~/Library/Application Support/PII-guard-mac/venv`，不影響你既有的任何 Rapid-MLX 安裝），
並用 Swift 建置 App、複製到 `~/Applications`。可重複執行。

### 給 AI agent 的安裝說明

想讓 agent 一步一步帶你安裝並教你使用，把 [AGENT_PROMPT.zh-TW.md](AGENT_PROMPT.zh-TW.md) 的內容貼給它即可。

請依序執行，每一步都有可檢查的結果：

```bash
# 1. 前置條件（任何一項失敗就停下來回報，不要繞過）
[ "$(uname -m)" = "arm64" ] && sw_vers -productVersion     # 需為 arm64 且 14 以上
command -v swift && command -v uv                          # 兩者都要有；缺 uv：brew install uv

# 2. 安裝
git clone https://github.com/liyoungc/PII-guard-mac.git && cd PII-guard-mac
scripts/install.sh                                         # 結尾應印出 "==> Done."

# 3. 驗證引擎（應輸出含 "formats" 的 JSON）
PG="$HOME/Library/Application Support/PII-guard-mac/venv/bin/piiguard"
"$PG" info

# 4. 看這台 Mac 的建議模型並載入（第一次會下載模型，數 GB，請耐心等）
"$PG" models                                               # 讀 "recommended"
"$PG" server start --wait                                  # 結果應為 "state": "ready"

# 5. 端到端自我測試（合成資料）
printf '通報人：王小明，由護理師林美玲協助。\n' > /tmp/piiguard-demo.txt
"$PG" run /tmp/piiguard-demo.txt                           # "verified": true，輸出檔內為 王○○、林○○

# 6. 啟動選單列 App
open "$HOME/Applications/PII Guard.app"
```

注意：不要把使用者的真實文件貼進對話或上傳到任何服務；本工具的目的就是讓文件留在本機。

## 使用方式

1. 點選單列的眼睛圖示 →「選擇檔案去識別化…」。
2. 第一次會自動載入模型（需下載）。之後可在選單「載入模型／卸載模型」；卸載會把記憶體完全還給系統。
3. 確認清單出現後：取消勾選不該遮的、手動補上漏掉的，或直接按「全部接受並寫出」。
4. 輸出檔寫在原檔旁邊。

### 設定

| 分頁 | 內容 |
|---|---|
| 模型 | 各記憶體級距的實測數字與建議；選擇、載入、卸載模型 |
| 遮蔽 | 遮蔽模式、遮蔽字元、要遮蔽的類別、自訂樣式、是否顯示確認清單、是否輸出對照表 |
| 白名單 | 不需遮蔽的詞（內建醫療常用詞，可增修）、一定要遮蔽的詞 |

### 遮蔽模式

| 模式 | 王小明 | 王明 | 歐陽大華 |
|---|---|---|---|
| 留姓（預設） | 王○○ | 王○ | 歐陽○○ |
| 留姓＋編號 | 同姓的不同人會變成 王○○(1)、王○○(2) | | |
| 全遮 | ○○○ | ○○ | ○○○○ |
| 代號 | 人員A | 人員B | 人員C |

遮蔽字元預設為全形「○」，可自訂。除人名外，可另外開啟：身分證／居留證字號、電話、Email、病歷號，或自訂正規表示式。

### 對照表

預設只輸出去識別（去連結）版本。若在設定開啟「同時輸出對照表」，會另存一份
`檔名_去識別_對照表.csv`（原文 → 取代文字）。對照表含原始姓名，請與去識別檔分開保管。

### 命令列

```bash
PG="$HOME/Library/Application Support/PII-guard-mac/venv/bin/piiguard"
"$PG" scan  報告.docx > found.json        # 只偵測，不寫檔；可編輯 found.json
"$PG" apply 報告.docx --decisions found.json
"$PG" run   報告.docx --mode full --mapping   # 全部接受直接寫檔
"$PG" server stop                          # 卸載模型
```

## 該用哪個模型

下表是在合成的病安通報語料上實測的結果，不是憑印象的推薦。**召回率**（人名被找到的比例）最重要：
漏掉一個名字是隱私事故，多抓一個只是確認清單上多取消一個勾。

<!-- BENCH -->
| 最低記憶體 | 模型 | 召回率 | 精確率 | 速度（字／秒） | 記憶體 | 下載大小 | 建議用於 |
|---|---|---|---|---|---|---|---|
| 8 GB | `mlx-community/Qwen3.5-2B-MLX-4bit` | 79.6% | 92.9% | 197 | 3.2 GB | 1.8 GB |  |
| 8 GB | `mlx-community/gemma-4-e2b-it-4bit` | 100.0% | 98.0% | 204 | 4.93 GB | 3.6 GB | ✅ 8、16 GB |
| 16 GB | `mlx-community/Qwen3.5-4B-MLX-4bit` | 98.0% | 98.0% | 46 | 7.78 GB | 3.1 GB |  |
| 16 GB | `mlx-community/gemma-4-e4b-it-4bit` | 98.0% | 100.0% | 117 | 6.54 GB | 5.2 GB |  |
| 24 GB | `mlx-community/Qwen3.5-9B-6bit` | 98.0% | 98.0% | 33 | 13.0 GB | 8.2 GB |  |
| 24 GB | `mlx-community/gemma-4-12B-it-4bit` | 100.0% | 100.0% | 34 | 8.36 GB | 6.8 GB | ✅ 24、32 GB |
| 32 GB | `rapid-mlx/Qwen3.8-27B-4bit-MTP-MLX` | — | — | — | — | 16.3 GB |  |
| 32 GB | `mlx-community/gemma-4-26b-a4b-it-4bit` | — | — | — | — | 15.4 GB |  |

量測環境：Apple M4 Pro, 24 GB, rapid-mlx 1.0.3, 2026-11-15。語料：`bench/corpus.jsonl`（20 篇合成文件、49 個人名）。
<!-- /BENCH -->

各級距的建議怎麼選的：先看召回率，再看記憶體佔用是否留得出空間給系統，最後看速度。

- 語料只有 49 個人名，相差一兩個名字不具統計意義；偵測提示詞也曾依這份語料的失敗案例調整過，所以數字偏樂觀。
- 8 GB 的建議（約 4.9 GB）未在真正的 8 GB 機器上驗證，使用時請關閉其他大型 App；若記憶體不足，改用 `Qwen3.5-2B`（約 3.2 GB，但漏抓較多）。
- 32 GB 級距的兩個大模型無法在量測用的 24 GB 機器上實測（它們需要約 18 GB 的 GPU 記憶體，Rapid-MLX 的載入前檢查會擋下），暫以 24 GB 的建議代替。有 32 GB 以上機器的人歡迎補測。
- 在這個任務上，模型越大不代表越準。

數字是「模型原始輸出」的成績，未計入白名單與人工確認。自己重測：
`.venv/bin/python bench/run_bench.py <模型 id>`。

## 支援格式

| 格式 | 說明 |
|---|---|
| `.docx` `.xlsx` `.pptx`（含 `.docm` `.xlsm` `.pptm`） | 內文、表格、頁首頁尾、註解、備忘稿、追蹤修訂中的文字；並清除作者等檔案屬性 |
| `.txt` `.md` `.csv` `.tsv` `.json` `.xml` `.html` `.yaml` `.log` | UTF-8、UTF-16、Big5 |
| `.doc` `.xls` `.ppt` | **不支援**。請先用 Office 或 LibreOffice「另存新檔」成新版格式 |
| `.pdf` | **不支援**：PDF 無法原樣取代文字 |

## 已知限制

- 模型可能漏抓，尤其是兩個字的姓名、姓名中間有空白、以及較小的模型。
- 只有姓氏加稱謂（「王醫師」）不會被遮蔽。
- 同一個姓名被拆在兩個段落或兩個儲存格時不會被認出。
- 工作表名稱、圖表內的文字、圖片中的文字不會處理。
- 白名單為完全相符比對。

## 姓氏規則

`engine/src/piiguard/surname.py` 決定「留姓」時留下哪幾個字：已知複姓（歐陽、司馬、范姜、張簡…）留兩個字，
其餘留第一個字；冠夫姓（王林美玉）目前只留第一個字。規則很短，歡迎依需要修改。

## 解除安裝

把 `~/Applications/PII Guard.app` 與 `~/Library/Application Support/PII-guard-mac` 丟進垃圾桶。
模型檔在 `~/.cache/huggingface/hub/`（資料夾名稱以 `models--` 開頭）。

## 致謝與授權

設計原則（模型只回報原文字串、由程式取代並複查）參考自 [danyuchn/pii-guard](https://github.com/danyuchn/pii-guard)（MIT）。
推論後端為 [Rapid-MLX](https://github.com/raullenchai/Rapid-MLX)（Apache-2.0）。各模型的授權請見其模型頁。

本專案以 MIT 授權釋出。測試與評測只使用合成資料，repo 內不含任何真實文件。
