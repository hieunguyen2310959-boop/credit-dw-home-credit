# Home Credit — Database cho BTL CO4031

Phần **database + ETL** theo bản đề xuất của nhóm. PostgreSQL, chạy trực tiếp Windows, **không Docker**. Chưa có frontend/API hoặc mô hình ML đã train.

## Đã có

- **8 bảng cốt lõi**: `ops.etl_runs`; `staging.application`, `staging.previous_application`; `dw.dim_applicant_profile`, `dw.dim_contract_type`, `dw.fact_application`; `ml.model_runs`, `ml.assessments`.
- **3 view**: `mart.application_features_v1`, `mart.application_overview_v1`, `mart.latest_assessment_v1`.
- Nạp CSV theo luồng streaming `COPY`, giữ tiền bằng NUMERIC, xử lý null/sentinel, tổng hợp lịch sử trước khi join, cutoff `DAYS_DECISION <= 0`.
- Manifest SHA-256, nhật ký ETL, khóa chống chạy đồng thời, transaction rollback và nạp lại cùng nguồn không nhân dòng/tiền.
- Ràng buộc PK/FK/UNIQUE/CHECK; snapshot không có nhãn; điểm hợp lệ; chọn kết quả thành công mới nhất, có tie-break theo ID.
- SQL thống kê/OLAP, fixture **SYNTHETIC**, kiểm thử tích hợp trên PostgreSQL thật.

**Chưa làm:** train/baseline/inference ML, API/React, `dw.fact_previous_application`, `app.credit_decisions`. Hai bảng cuối là tùy chọn trong đề xuất. Không đăng ký model hoặc sinh assessment giả trong lệnh demo.

## 1. Cài và tạo database trên Windows

Cài Python 3.13 và PostgreSQL 16+ bằng bộ cài Windows. Dùng **pgAdmin** hoặc **SQL Shell (psql)** tạo một database rỗng riêng, ví dụ `credit_dw_demo`, và một database khác cho kiểm thử `credit_dw_test`. Role kết nối phải sở hữu các database này hoặc có quyền tạo schema/bảng trong đó; không cần superuser cho ứng dụng.

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

Lấy dữ liệu từ cuộc thi Home Credit Default Risk trên Kaggle và tuân thủ điều khoản nguồn. Repo không kèm dữ liệu thật. Đặt tệp ở `data/raw/` hoặc ngoài repo. Loader đọc các cột tối thiểu của đề xuất, bỏ qua cột khác. Danh sách chính xác ở `scripts/database.py` (`APP_FIELDS`, `PREV_FIELDS`); thiếu header bắt buộc thì dừng, không tự đoán.

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

## 6. Cấu trúc repo

```text
sql/001_schema.sql        # bảng, constraint, index, guard model
sql/002_views.sql         # 3 giao diện đọc
sql/003_load_dw.sql       # transform/upsert từ staging
sql/004_analytics.sql     # SQL dashboard/OLAP và latest theo model
scripts/database.py      # init-db / load / demo / check
data/fixtures/           # chỉ dữ liệu SYNTHETIC
contracts/features-v1.json # allowlist feature, tách nhãn và metadata
docs/database.md         # mapping thiết kế → hiện thực + ERD
docs/proposal-original.md # nội dung đề xuất khôi phục, giữ làm căn cứ
tests/                  # kiểm thử PostgreSQL thật
```

Tài liệu thiết kế gốc có một số nội dung ngoài phạm vi database lần này; `docs/database.md` ghi phần đã hiện thực và giới hạn. Nguồn dữ liệu/dictionary phải được nhóm kiểm tra lại khi tải CSV thật; lần triển khai này mới chạy fixture synthetic, chưa tuyên bố kết quả full Home Credit.
