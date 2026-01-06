# Journal Tracker - 期刊清單

## 📊 總覽

- **總計**: 29 個期刊
- **CRC 類別**: 15 個期刊（大腸直腸癌 / 外科）
- **SDS 類別**: 14 個期刊（手術數據科學 / 醫學影像 AI）

---

## 🏥 CRC 類別期刊（Colorectal Cancer / Surgery）

| # | 期刊名稱 | ISSN | 爬蟲類型 |
|---|---------|------|----------|
| 1 | Annals of Coloproctology | 2287-9722 | PubMedScraper |
| 2 | Annals of Surgery | 0003-4932 | RSSScraper |
| 3 | BMC Cancer | 1471-2407 | RSSScraper |
| 4 | British Journal of Surgery | 1365-2168 | RSSScraper |
| 5 | Colorectal Cancer | 1758-194X | RSSScraper |
| 6 | Colorectal Disease | 1462-8910 | RSSScraper |
| 7 | Diseases of the Colon and Rectum | 0012-3706 | RSSScraper |
| 8 | European Journal of Surgical Oncology | 0748-7983 | PubMedScraper |
| 9 | Gastroenterology | 0016-5085 | RSSScraper |
| 10 | International Journal of Colorectal Disease | 0179-1958 | RSSScraper |
| 11 | Journal of Clinical Oncology | 0732-183X | RSSScraper |
| 12 | Journal of Gastrointestinal Surgery | 1091-255X | RSSScraper |
| 13 | Surgical Endoscopy | 0930-2794 | RSSScraper |
| 14 | Techniques in Coloproctology | 1123-6337 | RSSScraper |
| 15 | The Lancet Gastroenterology & Hepatology | 2468-1253 | RSSScraper |

---

## 🔬 SDS 類別期刊（Surgical Data Science / Medical AI）

| # | 期刊名稱 | ISSN | 爬蟲類型 |
|---|---------|------|----------|
| 1 | Annual Review of Biomedical Data Science | 2574-3414 | RSSScraper |
| 2 | Artificial Intelligence in Medicine | 0933-3657 | PubMedScraper |
| 3 | Computer Methods and Programs in Biomedicine | 0169-2607 | PubMedScraper |
| 4 | Computerized Medical Imaging and Graphics (CMIG) | 0895-6111 | PubMedScraper |
| 5 | Computers in Biology and Medicine | 0010-4825 | PubMedScraper |
| 6 | International Journal of Computer Assisted Radiology and Surgery (IJCARS) | 1861-6410 | PubMedScraper |
| 7 | International Journal of Medical Robotics and Computer Assisted Surgery | 1478-596X | PubMedScraper |
| 8 | Journal of Biomedical Informatics | 1532-0464 | PubMedScraper |
| 9 | Journal of the American Medical Informatics Association (JAMIA) | 1067-5027 | RSSScraper |
| 10 | Medical Image Analysis (MedIA) | 1361-8415 | PubMedScraper |
| 11 | Nature Machine Intelligence | 2522-5839 | RSSScraper |
| 12 | npj Computational Materials | 2057-3960 | RSSScraper |
| 13 | npj Digital Medicine | 2398-6352 | RSSScraper |
| 14 | Quantitative Imaging in Medicine and Surgery (QIMS) | 2223-4292 | PubMedScraper |

---

## 📅 更新記錄

- **2026-01-06**: 
  - 移除所有 IEEE 期刊（7 個）
  - 新增 4 個 SDS 期刊：IJCARS, CMIG, Int'l J Medical Robotics, QIMS
  - 將 Surgical Endoscopy 從 SDS 移到 CRC 類別
- **2025-10-01**: 新增 4 個 CRC 類別期刊
- **2025-09-30**: 建立 Journal Tracker 系統

---

## 🔧 爬蟲類型說明

| 爬蟲類型 | 說明 |
|----------|------|
| RSSScraper | 透過期刊官方 RSS feed 抓取 |
| PubMedScraper | 透過 PubMed API 按 ISSN 查詢（適用於無 RSS 的期刊） |

---

## 💡 管理工具

```bash
# 查看雲端資料庫中的期刊清單
python3 list_cloud_journals.py

# 新增期刊（需修改腳本內容）
python3 add_new_journals.py

# 更新期刊設定
python3 update_cloud_journals.py
```

---

最後更新: 2026-01-06
