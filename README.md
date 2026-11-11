# Home Credit — Hệ Hỗ Trợ Quyết Định Thẩm Định & Phê Duyệt Tín Dụng (CO4031)

Đồ án môn học **Data Warehouses & Decision Support Systems (CO4031)** — HK261.  
Hệ thống kết hợp ba phân hệ chặt chẽ theo kiến trúc Star Schema chuẩn Kimball, suy luận rủi ro giải thích được (Explainable ML), và giao diện vận hành thẩm định doanh nghiệp (Enterprise DSS Dashboard trên Streamlit).

- **Thành viên A (Database & ETL):** Kho dữ liệu PostgreSQL 16+, pipeline ETL streaming COPY, bảo toàn manifest SHA-256, Star Schema và Data Marts.
- **Thành viên B (Machine Learning & Scoring):** Huấn luyện mô hình Logistic Regression (ROC-AUC holdout 0.7424), chính sách phân tầng rủi ro `policy_v1_illustrative`, giải thích log-odds theo Feature Contract v1 (chi tiết tại `ml/README.md`).
- **Thành viên C (Web Dashboard & Tích hợp DSS):** Ứng dụng Streamlit module hóa (`app/`), hỗ trợ cán bộ thẩm định (Officer) đánh giá hồ sơ 360 độ, tìm kiếm trực tiếp 307,511 hồ sơ trên Supabase Cloud, báo cáo phân tích đa chiều OLAP, mô phỏng kịch bản What-If thời gian thực và ghi nhật ký kiểm toán vào `app.credit_decisions`.

---

## ⚡ 0. Hướng dẫn Chạy Nhanh (Kết nối Supabase Cloud — dành cho Thành viên Nhóm / Thầy cô)

Kho dữ liệu đầy đủ **Home Credit (307,511 hồ sơ & 1.67 triệu giao dịch lịch sử)** đã được nhóm nạp hoàn tất lên **Supabase Cloud (PostgreSQL 17)**, kèm sẵn artifact mô hình ML (`ml/results/models/logreg_v1_20261106/`).  
Do đó, bạn **KHÔNG CẦN** cài đặt PostgreSQL local, **KHÔNG CẦN** tải 600MB dữ liệu thô từ Kaggle và **KHÔNG CẦN** chạy lại pipeline ETL. Chỉ cần làm 4 bước sau (mất ~2 phút):

1. **Lấy mã nguồn mới nhất về máy (yêu cầu Python 3.12+ / 3.13):**
   - Nếu mới clone lần đầu:
     ```powershell
     git clone https://github.com/hieunguyen2310959-boop/credit-dw-home-credit.git
     cd credit-dw-home-credit
     ```
   - Nếu đã có repo sẵn trên máy:
     ```powershell
     git pull origin main
     ```
2. **Cài đặt các thư viện cần thiết:**
   ```powershell
   pip install -r requirements.txt
   ```
   *(Khuyến nghị tạo `.venv` riêng trước nếu muốn tách môi trường; nếu cần chạy thêm unit test `pytest`, cài bằng `pip install -r requirements-dev.txt`. Không cần cài gói `credit_ml` rời vì `app/main.py` tự nạp thư mục `ml/`.)*
3. **Cấu hình file kết nối `.env`:**
   ```powershell
   Copy-Item .env.example .env
   ```
   Mở file `.env`, **bỏ dấu `#`** ở dòng `DATABASE_URL=...` rồi thay `YOUR_PASSWORD` bằng mật khẩu Supabase do nhóm trưởng gửi riêng *(file `.env` đã được `.gitignore` ẩn khỏi Git)*.  
   *(Lưu ý: nếu chưa tạo `.env` hoặc mất kết nối mạng, ứng dụng vẫn mở được ở **Chế độ Offline** với bộ 4 hồ sơ mẫu `#1001`–`#1004`.)*
4. **Khởi chạy Ứng dụng Web DSS:**
   ```powershell
   python -m streamlit run app/main.py
   ```
   Trình duyệt sẽ tự động mở tại `http://localhost:8501` với đầy đủ dữ liệu live **307,511 hồ sơ**, mô hình ML, bảng điều khiển OLAP và nhật ký `app.credit_decisions` dùng chung trên Cloud.

---

## Đã có

- **8 bảng cốt lõi**: `ops.etl_runs`; `staging.application`, `staging.previous_application`; `dw.dim_applicant_profile`, `dw.dim_contract_type`, `dw.fact_application`; `ml.model_runs`, `ml.assessments`.
- **3 view**: `mart.application_features_v1`, `mart.application_overview_v1`, `mart.latest_assessment_v1`.
- Nạp CSV theo luồng streaming `COPY`, giữ tiền bằng NUMERIC, xử lý null/sentinel, tổng hợp lịch sử trước khi join, cutoff `DAYS_DECISION <= 0`.
- Manifest SHA-256, nhật ký ETL, khóa chống chạy đồng thời, transaction rollback và nạp lại cùng nguồn không nhân dòng/tiền.
- Ràng buộc PK/FK/UNIQUE/CHECK; snapshot không có nhãn; điểm hợp lệ; chọn kết quả thành công mới nhất, có tie-break theo ID.
- SQL thống kê/OLAP, fixture **SYNTHETIC**, kiểm thử tích hợp trên PostgreSQL thật.

- **Bảng tác vụ nghiệp vụ (trên Supabase Cloud DWH)**: `app.credit_decisions` (lưu vết quyết định phê duyệt/từ chối của Cán bộ kèm mã lý do chuẩn hóa và thời gian thực).
- **Mô hình máy học & Scoring Engine**: Gói `credit_ml` hoàn chỉnh, artifact `logreg_v1_20261106`, API `assess()` và `what_if()` với 17/17 ML tests passing (`ml/tests/`).
- **Giao diện Web DSS (Streamlit)**: 4 Tab nghiệp vụ độc lập (Core DSS, OLAP Analytics, What-If Simulator, Audit Trail), Sticky Header, chuẩn hóa đơn vị tiền tệ SI (`K`, `M`, `B`).

## 1. Cài và tạo database trên Windows

Cài Python 3.12+ (khuyến nghị 3.12 hoặc 3.13) và PostgreSQL 16+ bằng bộ cài Windows. Dùng **pgAdmin** hoặc **SQL Shell (psql)** tạo một database rỗng riêng, ví dụ `credit_dw_demo`, và một database khác cho kiểm thử `credit_dw_test`. Role kết nối phải sở hữu các database này hoặc có quyền tạo schema/bảng trong đó; không cần superuser cho ứng dụng.

Mở PowerShell tại thư mục repo:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Sửa `DATABASE_URL` trong `.env` bằng thông tin kết nối local của bạn. Không commit `.env`. Nếu mật khẩu có ký tự đặc biệt phải URL-encode hoặc dùng biến môi trường PostgreSQL phù hợp.

```powershell
.\.venv\Scripts\python.exe scripts/database.py init-db
.\.venv\Scripts\python.exe scripts/database.py demo
.\.venv\Scripts\python.exe scripts/database.py check
```

`demo` chỉ nạp fixture giả gồm ba hồ sơ hiện tại và năm hồ sơ lịch sử. Một lịch sử thuộc ID ngoài cohort, một ở tương lai, một không rõ cutoff; các trường hợp này được đếm trong log và không đưa vào feature lịch sử. Không dùng demo để báo cáo chất lượng ML.

`init-db` không xóa dữ liệu và có thể chạy lại. Đây là bootstrap v1, không phải công cụ tự nâng cấp DDL cũ: thay schema về sau cần migration mới rõ ràng.

## 2. Nạp dữ liệu Home Credit thật

Lấy dữ liệu từ cuộc thi Home Credit Default Risk trên Kaggle (hoặc tải nhanh qua `python scripts/download_data.py` vào `data/raw/` kèm tự động kiểm tra header ETL) và tuân thủ điều khoản nguồn. Repo không kèm dữ liệu thật. Đặt tệp ở `data/raw/` hoặc ngoài repo. Loader đọc các cột tối thiểu của đề xuất, bỏ qua cột khác. Danh sách chính xác ở `scripts/database.py` (`APP_FIELDS`, `PREV_FIELDS`); thiếu header bắt buộc thì dừng, không tự đoán.

**Dùng database mới**, ví dụ `credit_dw`, với `DATABASE_URL` tương ứng, không dùng DB đã nạp fixture:

```powershell
.\.venv\Scripts\python.exe scripts/database.py init-db
.\.venv\Scripts\python.exe scripts/database.py load --application data/raw/application_train.csv --previous data/raw/previous_application.csv
.\.venv\Scripts\python.exe scripts/database.py check
```

Tùy chọn thêm `--test data/raw/application_test.csv` ngay lần nạp đầu tiên. Bảng test nguồn không được có TARGET; không nhầm với tập holdout có nhãn do người làm ML tự chia.

### Giới hạn vòng đời dữ liệu có chủ đích

- Sau lần thành công đầu, DB chỉ nhận **cùng manifest tệp/role/checksum**. Đổi dữ liệu hoặc thêm nguồn thì dùng database mới; không tự xóa DW/model/assessment cũ.
- Bản MVP chưa có snapshot/version dataset hay incremental load. Rerun giống nguồn giữ surrogate key và kết quả chấm cũ.
- Đọc CSV không tải toàn bộ bảng vào RAM; vẫn COPY theo từng dòng và toàn batch trong một transaction. Thời gian full-data chưa benchmark.
- Parse/khóa trùng/header/nhãn sai làm toàn batch thất bại; không loại im lặng. Lỗi ghi trạng thái failed ngoài transaction dữ liệu. Nếu tệp chưa mở/checksum được hoặc bị khóa bởi một ETL khác, chưa tạo run.
- CSV phải là UTF-8/UTF-8 BOM. Khi dùng cohort nhỏ, tự chuẩn bị CSV hợp lệ và ghi cách chọn; loader giữ/đếm lịch sử ngoài cohort nhưng không gán cho hồ sơ không tồn tại.

## 3. Kiểm thử — chỉ dùng database riêng

> **CẢNH BÁO:** test xóa/tạo lại các schema ops/staging/dw/ml/mart trong `TEST_DATABASE_URL`. Tên database phải chứa `test`. Không trỏ vào dữ liệu cần giữ. Test database không phải database demo hoặc dữ liệu thật.

```powershell
$env:TEST_DATABASE_URL = "postgresql://YOUR_ROLE:YOUR_PASSWORD@127.0.0.1:5432/credit_dw_test"
.\.venv\Scripts\python.exe -m pytest tests -q
```

Các test model/assessment chỉ chèn bản ghi có tên `TEST_ONLY_NO_REAL_MODEL` trong DB test. Đó là kiểm tra constraint, không phải model được train hoặc artifact sử dụng được.

GitHub Actions chạy PostgreSQL native trên Ubuntu, không dùng container. CI phải xanh từ run thật; xem tab Actions để biết trạng thái hiện tại.

## 4. Đọc dữ liệu cho ML và dashboard

```sql
-- ML: lấy X theo allowlist, bỏ application_id khỏi predictor.
SELECT * FROM mart.application_features_v1;
-- Nhãn lấy RIÊNG để chia train/holdout theo application_id.
SELECT application_id, target FROM dw.fact_application WHERE target IS NOT NULL;
-- Web: một dòng mỗi hồ sơ, có thể đọc TARGET cho analytics/đối chiếu.
SELECT * FROM mart.application_overview_v1;
-- Không nhân dòng khi nối kết quả mới nhất.
SELECT o.application_id, o.amt_credit, a.risk_score, a.model_run_id, a.assessed_at
FROM mart.application_overview_v1 o
LEFT JOIN mart.latest_assessment_v1 a USING(application_id);
```

View latest lấy **lần thành công mới nhất**; lỗi mới hơn không làm score cũ thành mới. Khi so sánh điểm, phải chọn một `model_run_id`, không gộp model khác nhau. SQL ví dụ lấy latest trong model và OLAP ở `sql/004_analytics.sql`.

`ml.model_runs` chỉ là metadata, DB không kiểm tra được file model đã tồn tại/load được. Module ML tương lai phải lưu và load thử artifact trước khi đăng ký. Trigger không cho đổi metadata model đã được assessment dùng; nó không ngăn người dùng sửa file artifact ngoài DB.

## 5. Quy ước dữ liệu

- TARGET 0/1/NULL là nhãn, không phải feature; ID cũng không là predictor. JSON snapshot chặn cả nhãn lồng bên trong.
- Tiền theo đơn vị nguồn, không tự gán VND; `SUM(amt_credit)` là tổng giá trị tín dụng hồ sơ, không phải dư nợ.
- Thu nhập/annuity không tự đổi kỳ; `credit_income_ratio` không gọi DTI.
- Thiếu khác 0. Không có lịch sử trong nguồn đã nạp → count=0, approval_rate=NULL; không khẳng định khách hàng không có lịch sử ở mọi nơi.
- `DAYS_EMPLOYED > 0` (gồm sentinel 365243) → NULL; DAYS_BIRTH không âm → tuổi NULL/Unknown. Tuổi = -DAYS_BIRTH/365.25; nhóm `<25`, `25-39`, `40-59`, `60+`, `Unknown`.
- Giá trị tiền âm và external score ngoài [0,1] giữ trong staging, chuyển NULL ở DW và có thống kê cleaning. Cờ Y/N → true/false; mã lạ → NULL.
- Date tương đối không biến thành ngày lịch giả. Với history, ngày quyết định không biết hoặc >0 không vào aggregate.

## 6. ML / DSS

Train trên Colab, kết quả ở `ml/results/`; hướng dẫn chạy, đăng ký model (`ml/scripts/register_model.py`) và hợp đồng API ở `ml/README.md`.

## 7. Cấu trúc repo

```text
sql/                       # Database DDL: 001_schema, 002_views, 003_load_dw, 004_analytics
scripts/
├── database.py            # Bộ công cụ CLI quản trị DB: init-db / load / demo / check
└── download_data.py       # Script tải bộ dữ liệu Home Credit vào data/raw/ & kiểm tra schema
data/fixtures/             # Dữ liệu SYNTHETIC mẫu (không chứa dữ liệu nhạy cảm)
contracts/features-v1.json # Hợp đồng dữ liệu 16 predictors chuẩn giữa DW - ML - Web
ml/                        # Phân hệ ML/DSS: credit_ml, Colab notebook, model artifacts, tests
app/                       # Phân hệ Web & Tích hợp DSS (Streamlit Enterprise)
├── main.py                # File điều phối trung tâm (69 dòng)
├── styles.py              # CSS chuẩn Ngân hàng & Sticky Header ghim cố định
├── data_adapter.py        # Tầng nạp dữ liệu Supabase Live, Contract v1, tải mô hình ML & assess()
└── views/                 # 4 Tab chức năng độc lập
    ├── tab_core.py        # Tab 1: KPI Ribbon, Hàng đợi (Queue + Live Search), Gauge, Drivers, Quyết định
    ├── tab_olap.py        # Tab 2: Phân tích đa chiều OLAP & Ma trận phân bổ chéo từ Supabase DWH
    ├── tab_whatif.py      # Tab 3: Mô phỏng Kịch bản Tín dụng (What-If Simulator)
    └── tab_audit.py       # Tab 4: Nhật ký Kiểm toán (app.credit_decisions) & Giám sát ETL
.streamlit/config.toml     # Cấu hình giao diện Streamlit Enterprise
docs/                      # Tài liệu đặc tả kiến trúc DWH (database.md, verification.md, proposal-original.md)
tests/                     # Kiểm thử tích hợp PostgreSQL thật (Thành viên A)
requirements.txt           # Thư viện chạy Web DSS, DB adapter & ML inference
requirements-dev.txt       # Bổ sung pytest để chạy kiểm thử
.env.example               # Mẫu cấu hình biến môi trường DATABASE_URL (không chứa mật khẩu thật)
```

> Hệ thống hỗ trợ vận hành linh hoạt ở hai chế độ: **Kết nối Live Supabase Cloud** (307,511 hồ sơ thực tế, mặc định khi cấu hình `.env`) hoặc **Local PostgreSQL** (qua `scripts/database.py`), đồng thời có chế độ dự phòng offline với dữ liệu mẫu khi mất kết nối mạng.


## 8. Phân hệ Web & DSS (Streamlit)

Phân hệ Web được xây dựng hoàn toàn bằng **Streamlit** (Python thuần, không phụ thuộc NodeJS hay Docker), kết nối trực tiếp đến Supabase PostgreSQL 17, mô hình ML của Thành viên B (`logreg_v1_20261106`) và tuân thủ tuyệt đối quy ước dữ liệu của Thành viên A.

### 8.1. Tùy chọn khởi chạy nâng cao
*(Các bước cài đặt & chạy chuẩn đã tóm tắt ở **Mục 0** ở đầu trang.)*
* Dùng môi trường ảo `.venv`: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` rồi `.\.venv\Scripts\python.exe -m streamlit run app/main.py`.
* Đổi cổng mặc định (nếu `8501` đang bận): `python -m streamlit run app/main.py --server.port 8502`.
* Chạy không có DB (Offline Mode): bỏ qua bước tạo `.env`, ứng dụng tự dùng 4 hồ sơ mẫu (`#1001`–`#1004`). Lưu ý: nếu tự dựng mới Local PostgreSQL từ `sql/001_schema.sql`, bảng `app.credit_decisions` cần tạo thêm (hiện đã khởi tạo sẵn trên Supabase Cloud).

### 8.2. Các tính năng chính của 4 phân hệ:
1. **Tab 1 — Thẩm định hồ sơ (Core DSS):**
   - **KPI Ribbon 4 chỉ số Live DWH:** Tổng hồ sơ (307,511), tổng giá trị tín dụng đề nghị (`SUM(amt_credit)` chuẩn SI: `K`, `M`, `B`), tỷ lệ khó khăn thanh toán (`TARGET=1` tính trên mẫu số `COUNT(target)` có nhãn = 8.1%), tiến độ ca trực.
   - **Hàng đợi hồ sơ (Queue) & Lọc thông minh:** Lọc kép theo trạng thái xử lý & mức rủi ro (`LOW/MEDIUM/HIGH`), gõ bất kỳ ID nào (VD: `100009`) để truy vấn trực tiếp từ 307,511 hồ sơ trên Supabase, kèm nút **➕ Nạp thêm 20 hồ sơ**.
   - **Hồ sơ 360 độ:** Đồng hồ đo rủi ro Gauge chuẩn Basel, đối chiếu nhãn thực tế (`TARGET=0/1`), phân tích log-odds (`model_factors`), nghề nghiệp/gia đình/3 điểm nguồn ngoài (`EXT_1/2/3`), đòn bẩy `credit_income_ratio`, và lịch sử vay quá khứ (bảo toàn `N/A` cho giá trị `NULL`).
   - **Panel quyết định tín dụng:** Tự động đồng bộ khuyến nghị theo mức rủi ro, 3 nút Segmented Button (`Phê duyệt`, `Xem xét thêm`, `Từ chối`), nút "Điền mẫu nhanh" & "Lưu quyết định" ghi trực tiếp vào `app.credit_decisions` trên Supabase.
2. **Tab 2 — Báo cáo phân tích đa chiều (OLAP Analytics):**
   - Hỗ trợ thao tác Roll-up, Slice & Dice trực tiếp trên toàn bộ 307,511 hồ sơ Data Mart theo 4 chiều Dimension: *Nhóm độ tuổi (Age Band)*, *Loại hợp đồng (Contract Type)*, *Nguồn thu nhập (Income Type)* và *Trình độ học vấn (Education Level)*.
   - Bảng ma trận phân bổ chéo (Cross-Tab Matrix) đồng bộ 100% với Data Mart kèm cột **Tỷ lệ rủi ro (TARGET=1)** theo từng phân khúc và chuẩn hóa nhãn thiếu thành `Unknown`.
3. **Tab 3 — Mô phỏng kịch bản (What-If Analysis):**
   - Cho phép Cán bộ điều chỉnh giả định giá trị tín dụng, thu nhập (theo đơn vị `K` thống nhất và nhân `unit_scale` chuẩn xác khi chấm điểm), cùng ngưỡng khẩu vị rủi ro (`review_threshold`, `decline_threshold` trong `PolicyConfig`).
   - Tái chấm điểm thời gian thực thông qua hàm `assess()` của gói `credit_ml`, đối chiếu trực quan Before vs After mà không ghi đè dữ liệu gốc của kho.
   - Nút "Đẩy kết quả mô phỏng sang Ghi chú Phê duyệt" tự động điền căn cứ sang Tab 1.
4. **Tab 4 — Nhật ký kiểm toán & Giám sát vận hành (Audit Trail & ETL Runs):**
   - Lưu vết toàn bộ quyết định tín dụng vào bảng `app.credit_decisions` trên Supabase kèm nút **🔄 Đồng bộ từ Supabase**.
   - Bảng giám sát tiến trình nạp dữ liệu thực tế từ `ops.etl_runs`, hiển thị thống kê dòng (`app`, `prev`, `dw`), mã băm SHA-256 và **Báo cáo Kiểm soát Chất lượng Dữ liệu ETL** (`55,374` sentinel → `NULL`, lọc đơn mồ côi `orphan`, kiểm tra rò rỉ tương lai).

### 8.3. Kiểm thử chất lượng
Cài thêm công cụ test (nếu chưa cài `requirements-dev.txt`) rồi chạy toàn bộ 17 unit test của phân hệ ML và suy luận:
```powershell
pip install -r requirements-dev.txt
python -m pytest ml/tests/ -q
```
*(Nếu dùng môi trường ảo `.venv`, thay `python` bằng `.\.venv\Scripts\python.exe`.)*
