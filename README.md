# Home Credit — Hệ Thống Kho Dữ Liệu & Hỗ Trợ Quyết Định Thẩm Định Tín Dụng (CO4031)

Đồ án môn học **Data Warehouses & Decision Support Systems (CO4031)** — HK261.  
Hệ thống kết hợp ba phân hệ chặt chẽ theo kiến trúc **Star Schema chuẩn Kimball**, suy luận rủi ro giải thích được (**Explainable Machine Learning**), và giao diện vận hành thẩm định doanh nghiệp (**Enterprise Decision Support System — Streamlit Web Application**).

---

## 👥 Phân công Vai trò 3 Phân hệ

- **Thành viên A — Data Warehouse & ETL (Tầng Dữ liệu):**
  - Thiết kế mô hình kho dữ liệu đa chiều Star Schema (Fact, Dims, Staging, Marts) theo phương pháp luận Kimball.
  - Xây dựng pipeline trích xuất - biến đổi - nạp (ETL) dạng streaming qua `COPY`, bảo toàn tính nhất quán transaction, mã băm SHA-256 manifest, khóa chống chạy đồng thời và chống nhân dòng khi nạp lại.
  - Thiết lập rào chắn kiểm soát chất lượng dữ liệu (Data Quality Guardrails): xử lý giá trị dị biệt sentinel `365243` $\rightarrow$ `NULL`, phát hiện 256,513 hồ sơ lịch sử ngoài cohort, chặn rò rỉ thông tin tương lai (`DAYS_DECISION <= 0`).
  - Triển khai kho dữ liệu lên **Neon Cloud DWH (PostgreSQL 18.6 - AWS Singapore)** lưu trữ đầy đủ 307,511 hồ sơ hiện tại và 1,670,214 giao dịch lịch sử.

- **Thành viên B — Machine Learning & Risk Scoring (Tầng Trí tuệ):**
  - Xây dựng pipeline tiền xử lý và huấn luyện mô hình Logistic Regression theo chuẩn Feature Contract v1 (ROC-AUC tập holdout đạt 0.7424).
  - Tách biệt nhãn mục tiêu (`TARGET`) và mã định danh (`SK_ID_CURR` / `application_id`) khỏi tập thuộc tính dự báo nhằm tránh rò rỉ dữ liệu (data leakage).
  - Thiết lập chính sách phân tầng rủi ro tín dụng (`policy_v1_illustrative`): Thấp (`< 0.10`), Trung bình (`0.10 – 0.25`), Cao (`>= 0.25`).
  - Cung cấp cơ chế giải thích mô hình (Explainable AI): phân tích đóng góp log-odds (`model_factors`) cho từng thuộc tính giúp cán bộ thẩm định hiểu rõ căn cứ ra quyết định.
  - Xây dựng gói thư viện `credit_ml` hoàn chỉnh kèm 17 unit test kiểm thử nghiêm ngặt tại `ml/tests/`.

- **Thành viên C — Enterprise Web DSS & Tích hợp Hệ thống (Tầng Ứng dụng & Nghiệp vụ):**
  - Xây dựng ứng dụng Web DSS hoàn chỉnh bằng **Streamlit** module hóa (`app/`), kết nối trực tiếp đến **Neon Cloud DWH** và mô hình ML của Thành viên B.
  - Thiết kế giao diện thẩm định hồ sơ 360 độ (Core DSS) với đồng hồ đo rủi ro chuẩn Basel, phân tích nhân tố log-odds, đòn bẩy tài chính và lịch sử vay quá khứ.
  - Xây dựng công cụ phân tích OLAP đa chiều: hỗ trợ thao tác Roll-up, Slice & Dice trực tiếp trên toàn bộ 307,511 hồ sơ Data Mart theo 4 chiều (Độ tuổi, Hợp đồng, Nguồn thu nhập, Học vấn).
  - Phát triển công cụ mô phỏng kịch bản (What-If Simulation): cho phép cán bộ thẩm định điều chỉnh số tiền vay, thu nhập và khẩu vị rủi ro với tái chấm điểm thời gian thực bằng hàm `assess()` của ML.
  - Thiết lập cơ chế kiểm soát an toàn **Fail-Closed**: tự động chặn quyền phê duyệt nếu xảy ra lỗi mô hình ML, ngăn ngừa việc phê duyệt tự động khi mô hình chưa hoàn tất suy luận hợp lệ.
  - Triển khai bảng nhật ký kiểm toán `app.credit_decisions` trên Neon Cloud, đồng bộ hóa quyết định phê duyệt/từ chối kèm mã lý do chuẩn hóa thời gian thực.
  - Đóng gói bộ 37 automated test cases kiểm thử toàn diện từ logic nghiệp vụ, tính an toàn đến ma trận giao diện người dùng (36 passed, 1 skipped).

---

## ⚡ 0. Hướng dẫn Chạy Nhanh (Dùng sẵn Neon Cloud DWH — Dành cho Giảng viên & Nhóm)

Toàn bộ kho dữ liệu thực tế **Home Credit (307,511 hồ sơ và 1,670,214 giao dịch lịch sử)** đã được nạp hoàn chỉnh lên **Neon Cloud PostgreSQL (AWS Singapore)**, kèm sẵn tệp artifact mô hình máy học (`ml/results/models/logreg_v1_20261106/`).

Do đó, người dùng **không cần** cài đặt PostgreSQL cục bộ trên máy, **không cần** tải 600MB dữ liệu thô từ Kaggle và **không cần** chạy lại pipeline ETL. Quy trình thiết lập gồm 4 bước:

### Bước 1: Tải mã nguồn về máy (Yêu cầu Python 3.12+ hoặc 3.13)
```powershell
git clone https://github.com/hieunguyen2310959-boop/credit-dw-home-credit.git
cd credit-dw-home-credit
```
*(Nếu đã có mã nguồn trong máy, chỉ cần chạy `git pull origin main` để cập nhật mới nhất).*

### Bước 2: Cài đặt các thư viện cần thiết
```powershell
pip install -r requirements.txt
```
*(Khuyến nghị tạo môi trường ảo `.venv` riêng nếu muốn tách biệt môi trường. Nếu muốn chạy thêm bộ kiểm thử `pytest`, cài thêm: `pip install -r requirements-dev.txt`).*

### Bước 3: Cấu hình kết nối Neon Cloud DWH
Sao chép tệp cấu hình mẫu:
- **Trên Windows PowerShell:**
  ```powershell
  Copy-Item .env.example .env
  ```
- **Trên Linux / macOS / Git Bash:**
  ```bash
  cp .env.example .env
  ```
- *Hoặc tạo tệp `.env` tại thư mục gốc dự án rồi dán trực tiếp 2 dòng kết nối Neon Cloud sau:*
  ```env
  DATABASE_URL="postgresql://neondb_owner:npg_VKi3qTN6CZyO@ep-dry-mode-a1eqijxp.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
  DATABASE_URL_POOLED="postgresql://neondb_owner:npg_VKi3qTN6CZyO@ep-dry-mode-a1eqijxp-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
  ```
*(Hệ thống tự động nhận diện kết nối `Neon Cloud` và mở toàn bộ dữ liệu thật. Nếu chưa tạo `.env` hoặc mất mạng, ứng dụng vẫn tự mở ở **Chế độ Offline** với 4 hồ sơ mẫu chuẩn).*

### Bước 4: Khởi chạy Ứng dụng Web DSS
```powershell
python -m streamlit run app/main.py
```
Trình duyệt sẽ tự động mở giao diện tại địa chỉ: **`http://localhost:8501`**.  
Trên thanh tiêu đề sẽ hiển thị huy hiệu: **`🟢 Neon Cloud Live DWH • 307,511 hồ sơ`**.

---

## 🏛️ 1. Kiến trúc Kho Dữ liệu (Star Schema & Neon Cloud DWH)

Kho dữ liệu được thiết kế theo phương pháp luận Kimball gồm 5 schema chuyên biệt:

```mermaid
flowchart TD
    subgraph Staging ["Tầng Staging (Neon Cloud)"]
        S_APP["staging.application<br/>307,511 dòng"]
        S_PREV["staging.previous_application<br/>1,670,214 dòng"]
    end

    subgraph DW ["Tầng Data Warehouse (Star Schema)"]
        DIM_PROF["dw.dim_applicant_profile<br/>(Nhân khẩu học, học vấn, gia đình)"]
        DIM_CONT["dw.dim_contract_type<br/>(Loại hợp đồng tín dụng)"]
        FACT_APP["dw.fact_application<br/>307,511 dòng<br/>(Tiền vay, thu nhập, tổng hợp lịch sử)"]
    end

    subgraph Mart ["Tầng Data Marts"]
        M_FEAT["mart.application_features_v1<br/>(Đặc trưng đầu vào cho ML)"]
        M_OVER["mart.application_overview_v1<br/>(Báo cáo tổng hợp OLAP)"]
        M_ASSESS["mart.latest_assessment_v1<br/>(Kết quả chấm điểm mới nhất)"]
    end

    subgraph App ["Tầng Vận hành & Quyết định (DSS)"]
        APP_DEC["app.credit_decisions<br/>(Nhật ký phê duyệt cán bộ)"]
        ML_ASSESS["ml.assessments<br/>(Lưu vết điểm rủi ro ML)"]
        OPS_RUN["ops.etl_runs<br/>(Nhật ký ETL & SHA-256)"]
    end

    S_APP --> FACT_APP
    S_PREV --> FACT_APP
    DIM_PROF --> FACT_APP
    DIM_CONT --> FACT_APP
    FACT_APP --> M_FEAT
    FACT_APP --> M_OVER
    FACT_APP --> M_ASSESS
    M_FEAT --> App
    App --> APP_DEC
    App --> ML_ASSESS
```

### Các bảng dữ liệu cốt lõi:
1. `staging.application` (307,511 dòng): Lưu trữ dữ liệu thô của đơn xin vay hiện tại.
2. `staging.previous_application` (1,670,214 dòng): Lưu trữ toàn bộ 1,670,214 bản ghi lịch sử các khoản vay trước đó của khách hàng từ tệp `previous_application.csv`.
3. `dw.fact_application` (307,511 dòng): Bảng Fact trung tâm, lưu các số đo tài chính (`amt_credit`, `amt_income_total`, `amt_annuity`, tỷ lệ đòn bẩy) và các thuộc tính tổng hợp từ lịch sử vay (`prev_app_count`, `prev_approved_count`, `prev_refused_count`, `prev_total_credit_approved`...).
4. `dw.dim_applicant_profile` & `dw.dim_contract_type`: Các chiều không gian lưu thông tin khách hàng và hình thức hợp đồng.
5. `ops.etl_runs`: Lưu trữ lịch sử thực thi ETL, mã băm SHA-256 của file nguồn, số dòng nạp và trạng thái thực thi.
6. `app.credit_decisions`: Lưu vết nhật ký kiểm toán (Audit Trail) khi Cán bộ thẩm định ấn lưu quyết định phê duyệt/từ chối trên giao diện Streamlit.
7. `ml.assessments`: Lưu trữ lịch sử các lần suy luận điểm rủi ro của mô hình máy học.

### Rào chắn Kiểm soát Chất lượng Dữ liệu (ETL Quality Guardrails):
- **Xử lý giá trị bất thường (Sentinel Handling):** Trường `DAYS_EMPLOYED = 365243` (giá trị quy ước đại diện cho đối tượng nghỉ hưu hoặc thất nghiệp của Home Credit) được tự động chuyển đổi thành `NULL` trong bảng Fact, ngăn sai lệch khi tính thời gian công tác.
- **Phát hiện đơn mồ côi (Orphan Record Detection):** Pipeline ETL phát hiện và ghi nhận 256,513 bản ghi lịch sử không khớp với tập hồ sơ hiện tại (`cohort`). Những bản ghi này được giữ nguyên ở staging nhưng không đưa vào bảng Fact để tránh dữ liệu rác.
- **Chặn rò rỉ thời gian (Cutoff Leak Prevention):** Toàn bộ giao dịch lịch sử có ngày quyết định phát sinh sau thời điểm nộp đơn hiện tại (`DAYS_DECISION > 0`) đều bị loại bỏ, bảo toàn tính nhân quả của dữ liệu tín dụng.

---

## 🤖 2. Phân hệ Machine Learning & Chính sách Rủi ro (Credit ML Engine)

Mô hình dự báo rủi ro được đóng gói tại thư mục `ml/`, tuân thủ nghiêm ngặt **Feature Contract v1**:

### 1. Thuộc tính & Cơ chế suy luận:
- **Thuộc tính đầu vào:** Thu nhập (`amt_income_total`), Giá trị khoản vay (`amt_credit`), Tiền trả định kỳ (`amt_annuity`), Giá trị hàng hóa (`amt_goods_price`), Tuổi đời (`age_years`), Thời gian công tác (`employment_years`), 3 điểm tín dụng nguồn ngoài (`ext_source_1`, `ext_source_2`, `ext_source_3`), số hợp đồng vay trước đó và tỷ lệ quá hạt quá khứ.
- **Quy tắc phân tách dữ liệu:** Loại trừ cột định danh (`application_id`) và nhãn thực tế (`TARGET`) khỏi danh sách thuộc tính suy luận.
- **Mô hình triển khai:** Logistic Regression được chuẩn hóa qua `StandardScaler` và `SimpleImputer(strategy='median')`. Trọng số mô hình được xuất thành artifact tại `ml/results/models/logreg_v1_20261106/`.

### 2. Phân tầng Rủi ro & Chính sách Phê duyệt (`policy_v1_illustrative`):
Mô hình ước lượng xác suất khó khăn tài chính $p = P(\text{TARGET}=1)$:
- $p < 0.10$ (**Rủi ro THẤP — LOW**): Đề xuất **Phê duyệt tự động** (`APPROVE_SIMULATION`).
- $0.10 \le p < 0.25$ (**Rủi ro TRUNG BÌNH — MEDIUM**): Đề xuất **Xem xét thêm** (`REVIEW`). Cán bộ tín dụng cần thẩm định bổ sung sao kê lương hoặc tài sản bảo đảm.
- $p \ge 0.25$ (**Rủi ro CAO — HIGH**): Đề xuất **Từ chối tín dụng** (`DECLINE_SIMULATION`).

### 3. Quy tắc Đè Chính sách Nghiệp vụ (Policy Override):
- **Cảnh báo thiếu dữ liệu tín dụng ngoài (`ALL_EXTERNAL_SCORES_MISSING`):**  
  Trong thực tế thẩm định, nếu một hồ sơ hoàn toàn không có cả 3 điểm xếp hạng từ trung tâm tín dụng bên ngoài (`EXT_SOURCE_1, 2, 3`), dù mô hình ước lượng xác suất rủi ro thấp ($p < 0.10$, ví dụ hồ sơ `#100402` với $p \approx 0.094$), chính sách rủi ro **bắt buộc ghi đè** khuyến nghị sang **`REVIEW`** (hiển thị banner màu vàng).  
  Điều này ngăn ngừa hiện tượng hồ sơ trắng (clean slate), buộc cán bộ thẩm định phải kiểm tra thực địa trước khi phê duyệt.

### 4. Giải thích Đóng góp Thuộc tính (Explainable Log-Odds):
Xác suất rủi ro được giải thích trực quan bằng tổng logit:
$$\text{logit}(p) = \ln\left(\frac{p}{1-p}\right) = \beta_0 + \sum_{i=1}^{m} \beta_i x_i$$
Giao diện phân tách chi tiết từng nhân tố tác động làm tăng rủi ro (đẩy xác suất lên) hay giảm rủi ro (kéo xác suất xuống), giúp quyết định phê duyệt minh bạch và có căn cứ rõ ràng.

---

## 💻 3. Hệ Hỗ Trợ Quyết Định Doanh Nghiệp (Enterprise Web DSS)

Ứng dụng Web DSS được xây dựng bằng **Streamlit** thuần Python, chia thành 4 Tab nghiệp vụ chuyên biệt:

### Tab 1 — Thẩm định Hồ sơ Chi tiết (Core DSS)
- **Thanh trạng thái KPI Ribbon thời gian thực:** Hiển thị 4 chỉ số cốt lõi từ Neon Cloud: Tổng hồ sơ kho dữ liệu (307,511), Tổng dư nợ đề xuất (`SUM(amt_credit)` chuẩn SI: `K`, `M`, `B`), Tỷ lệ khó khăn tài chính chung (8.1% trên số hồ sơ có nhãn), và Tiến độ ca trực của cán bộ.
- **Hàng đợi hồ sơ (Queue) & Tìm kiếm tức thì:** Hỗ trợ lọc theo trạng thái duyệt (`PENDING / APPROVED / REVIEW / DECLINED`) và mức rủi ro (`LOW / MEDIUM / HIGH / ERROR`). Hộp tìm kiếm cho phép gõ bất kỳ ID nào trong 307,511 hồ sơ (ví dụ: `100009`, `155054`) để truy vấn trực tiếp từ Neon Cloud.
- **Hồ sơ Khách hàng 360 độ:**
  - Đồng hồ đo rủi ro trực quan (Risk Gauge) chia 3 vùng xanh - vàng - đỏ chuẩn Basel.
  - Phân tích log-odds bóc tách nguyên nhân rủi ro hàng đầu.
  - Thông tin nghề nghiệp, học vấn, gia đình, thu nhập và đòn bẩy tài chính `credit_income_ratio`.
  - Lịch sử tín dụng quá khứ (số lần được duyệt, số lần bị từ chối, dư nợ cũ).
- **Khung Quyết định Tín dụng (Decision Panel):**
  - Tự động điền đề xuất dựa theo chính sách rủi ro.
  - 3 nút bấm nghiệp vụ: **Phê duyệt**, **Xem xét thêm**, **Từ chối**.
  - Nút "Điền mẫu nhanh" tự động tổng hợp căn cứ thẩm định.
  - Nút **"LƯU QUYẾT ĐỊNH (SAVE)"** ghi dữ liệu nguyên tử vào bảng `app.credit_decisions` và `ml.assessments` trên Neon Cloud.
- **Cơ chế An toàn Nghiêm ngặt (Fail-Closed Safety):**
  - Nếu mô hình ML gặp sự cố ngoại lệ hoặc dữ liệu đầu vào vi phạm cấu trúc, hệ thống lập tức khóa nút "Phê duyệt" và chuyển sang trạng thái cảnh báo đỏ `ML_ERROR`. Hệ thống vô hiệu hóa chức năng phê duyệt khi chưa có kết quả đánh giá rủi ro hợp lệ từ mô hình.

### Tab 2 — Phân tích Đa chiều (OLAP Analytics)
- Thao tác trực tiếp trên toàn bộ **307,511 hồ sơ Data Mart** của Neon Cloud.
- Hỗ trợ Roll-up, Slice & Dice theo 4 chiều phân tích:
  1. **Nhóm độ tuổi** (Dưới 25, 25-35, 35-50, Trên 50).
  2. **Hình thức hợp đồng tín dụng** (Cash loans, Revolving loans).
  3. **Nguồn thu nhập** (Working, Commercial partner, Pensioner, State servant...).
  4. **Trình độ học vấn** (Higher education, Secondary, Incomplete higher...).
- Ma trận phân bổ chéo (Cross-Tabulation Matrix) kết hợp biểu đồ nhiệt, tính toán tỷ lệ khó khăn tài chính (`TARGET=1`) cho từng phân khúc khách hàng.

### Tab 3 — Mô phỏng Kịch bản Tín dụng (What-If Simulator)
- Cho phép Cán bộ thẩm định thử nghiệm các kịch bản tài chính giả định mà **không ghi đè dữ liệu gốc của kho**:
  - Tinh chỉnh số tiền vay đề xuất (`amt_credit`) theo đơn vị nghìn đồng `K`.
  - Tinh chỉnh thu nhập khách hàng (`amt_income_total`).
  - Tinh chỉnh khẩu vị rủi ro tín dụng (`review_threshold`, `decline_threshold`).
- Tái chấm điểm thời gian thực thông qua hàm `assess()` của gói `credit_ml` (thay vì sử dụng công thức giả định heuristic).
- Ràng buộc an toàn: hệ thống kiểm tra điều kiện logic $\text{review\_threshold} < \text{decline\_threshold}$. Nếu cán bộ kéo sai ngưỡng, hệ thống lập tức vô hiệu hóa nút tính toán và hiển thị thông báo nhắc nhở.
- Nút **"Đẩy kết quả mô phỏng sang Ghi chú Phê duyệt"** tự động chuyển các con số giả định sang biên bản thẩm định ở Tab 1.

### Tab 4 — Nhật ký Kiểm toán & Giám sát Vận hành (Audit Trail & Ops)
- **Nhật ký Kiểm toán (`app.credit_decisions`):** Hiển thị toàn bộ lịch sử các quyết định tín dụng đã được lưu trên Neon Cloud kèm ID hồ sơ, cán bộ ra quyết định, lựa chọn phê duyệt, mã lý do chuẩn hóa và dấu thời gian thực thi (timestamp). Kèm nút **"🔄 Đồng bộ từ Cloud DWH"**.
- **Giám sát Pipeline ETL (`ops.etl_runs`):** Theo dõi lịch sử thực thi nạp dữ liệu từ kho Neon Cloud, đối soát mã băm SHA-256 của file nguồn Kaggle, số lượng dòng nạp thành công và báo cáo kiểm soát chất lượng dữ liệu.

---

## 📁 4. Cấu trúc Thư mục Dự án

```
credit-dw-home-credit/
├── .env.example               # Mẫu cấu hình chuỗi kết nối Neon Cloud DWH
├── README.md                  # Tài liệu hướng dẫn đồ án toàn diện
├── requirements.txt           # Thư viện phục vụ chạy Web DSS & ML inference
├── requirements-dev.txt       # Thư viện bổ sung phục vụ chạy pytest
├── pytest.ini                 # Cấu hình kiểm thử tự động
│
├── app/                       # Mã nguồn Phân hệ Web DSS (Streamlit)
│   ├── main.py                # Điểm khởi động ứng dụng Web
│   ├── data_adapter.py        # Adapter kết nối Neon Cloud DWH & xử lý cache
│   ├── styles.py              # Giao diện CSS doanh nghiệp, Header, KPI Ribbon
│   └── views/                 # 4 Tab nghiệp vụ
│       ├── tab_core.py        # Tab 1: Thẩm định hồ sơ 360 độ & Quyết định
│       ├── tab_olap.py        # Tab 2: Phân tích OLAP đa chiều & Ma trận rủi ro
│       ├── tab_whatif.py      # Tab 3: Mô phỏng kịch bản What-If thời gian thực
│       └── tab_audit.py       # Tab 4: Nhật ký kiểm toán & Giám sát ETL runs
│
├── ml/                        # Mã nguồn Phân hệ Machine Learning (Thành viên B)
│   ├── __init__.py            # Export assess(), what_if(), PolicyConfig
│   ├── config.py              # Feature Contract v1 & ngưỡng rủi ro
│   ├── features.py            # Tiền xử lý dữ liệu và kiểm tra khóa cấm
│   ├── model.py               # Tải mô hình Logistic Regression & tính log-odds
│   ├── policy.py              # Đánh giá chính sách phân tầng & policy override
│   ├── results/models/        # Artifact mô hình huấn luyện sẵn (.joblib)
│   └── tests/
│       └── test_ml.py         # 17 unit tests kiểm thử logic ML & tính toàn vẹn
│
├── sql/                       # Kịch bản DDL Cơ sở dữ liệu (Thành viên A)
│   ├── 001_schema.sql         # Định nghĩa các schema, bảng staging, dw, ops, ml
│   ├── 002_views.sql          # Định nghĩa 3 views Data Mart
│   └── 005_app_decisions.sql  # Định nghĩa bảng tác vụ app.credit_decisions
│
├── scripts/                   # Kịch bản quản trị & ETL
│   ├── database.py            # Quản trị DDL, nạp dữ liệu thật & kiểm tra kho
│   └── download_data.py       # Hỗ trợ tải dữ liệu thô từ nguồn Kaggle
│
├── docs/                      # Tài liệu kỹ thuật chi tiết
│   ├── database.md            # Đặc tả thiết kế kho dữ liệu & Neon Cloud DWH
│   ├── ml_scoring.md          # Đặc tả mô hình máy học & chính sách rủi ro
│   └── web_dss.md             # Đặc tả giao diện & quy trình nghiệp vụ DSS
│
└── tests/                     # Bộ kiểm thử chất lượng tích hợp hệ thống
    ├── test_app_safety.py     # 13 tests an toàn Web DSS (Fail-Closed, Honest DB)
    └── test_ui_matrix.py      # 5 tests giao diện tương tác toàn diện qua AppTest
```

---

## 🧪 5. Kiểm thử Chất lượng Toàn diện (Automated Testing)

Dự án sở hữu bộ kiểm thử tự động gồm **35 test cases** bao phủ toàn bộ các tầng logic từ Machine Learning, Ràng buộc An toàn Nghiệp vụ đến Giao diện Tương tác Streamlit:

### Chạy toàn bộ 35 test cases:
```powershell
pip install -r requirements-dev.txt
python -m pytest ml/tests tests/test_app_safety.py tests/test_ui_matrix.py -v
```

### Chi tiết 3 nhóm kiểm thử:
1. **17 Unit Tests Machine Learning (`ml/tests/test_ml.py`):**
   - Kiểm tra bộ thuộc tính khớp với định nghĩa trong Feature Contract v1.
   - Kiểm tra chống rò rỉ nhãn: từ chối các khóa cấm (`TARGET`, `risk_score`...).
   - Kiểm tra tính bất biến của hàm What-If và sự hội tụ của log-odds.
   - Kiểm tra xử lý an toàn khi thiếu thuộc tính hoặc giá trị bất thường.
2. **13 Tests An toàn Ứng dụng & Nghiệp vụ (`tests/test_app_safety.py`):**
   - Kiểm tra cơ chế Fail-Closed: khóa chức năng phê duyệt khi mô hình ML lỗi.
   - Kiểm tra chính sách Override: bắt buộc chuyển sang `REVIEW` khi thiếu toàn bộ 3 điểm tín dụng ngoài.
   - Kiểm tra tính trung thực của cơ sở dữ liệu: báo lỗi khi kết nối cơ sở dữ liệu gián đoạn, không ghi nhận thành công giả lập khi thao tác ghi thất bại.
   - Kiểm tra giữ nguyên giá trị `NULL` cho dữ liệu tiền tệ bị khuyết (không tự ý ép về 0).
   - Kiểm tra nhận diện chính xác nền tảng `Neon Cloud` từ chuỗi kết nối.
3. **5 Matrix Tests Giao diện Tương tác (`tests/test_ui_matrix.py`):**
   - Kiểm tra tương tác tìm kiếm hồ sơ và bộ lọc rủi ro trên giao diện thật qua `streamlit.testing.v1.AppTest`.
   - Kiểm tra khóa nút What-If khi nhập sai ngưỡng chính sách.
   - Kiểm tra hành vi giao diện khi mô hình ML xảy ra ngoại lệ.
   - Kiểm tra chức năng lưu quyết định thẩm định và giữ lại ghi chú của cán bộ khi có lỗi.
   - Kiểm tra đầy đủ các chiều phân tích OLAP ở cả chế độ Online và Offline.
4. **2 Demo UI & Error Tests (`tests/test_demo_ui.py`):**
   - Kiểm tra luồng thẩm định, chính sách đè khuyến nghị và đường dẫn xử lý lỗi khi DB hoặc mô hình gián đoạn.
   - Kiểm tra tích hợp cơ sở dữ liệu mẫu cục bộ (khi có môi trường kiểm thử).

---

## 📖 6. Hướng dẫn Trải nghiệm & Vận hành Nghiệp vụ Từ Đầu Đến Cuối (End-to-End Walkthrough)

Dành cho Giảng viên và Thành viên nhóm trải nghiệm toàn bộ luồng nghiệp vụ thẩm định tín dụng khép kín trên hệ thống:

```mermaid
flowchart LR
    A["1. Giám sát DWH<br/>(KPI Ribbon)"] --> B["2. Tìm & Lọc Hồ sơ<br/>(Queue & Search)"]
    B --> C["3. Đánh giá 360°<br/>(Gauge & Factors)"]
    C --> D["4. Policy Override<br/>(Kiểm tra #100402)"]
    D --> E["5. Ra Quyết định<br/>(Lưu Neon Cloud)"]
    E --> F["6. Phân tích OLAP<br/>(Roll-up/Slice&Dice)"]
    F --> G["7. Mô phỏng What-If<br/>(Tái cấu trúc khoản vay)"]
    G --> H["8. Kiểm toán Audit<br/>(Đối soát app.decisions)"]
```

### Bước 1: Giám sát Trạng thái Hệ thống (Header & KPI Ribbon)
- Mở ứng dụng tại `http://localhost:8501`.
- Quan sát thanh Sticky Header trên cùng: Huy hiệu màu xanh **`🟢 Neon Cloud Live DWH • 307,511 hồ sơ`** xác nhận kết nối trực tiếp đến kho dữ liệu đám mây.
- Đọc 4 chỉ số tổng quan trên KPI Ribbon:
  - **Tổng hồ sơ:** `307,511` đơn vay thực tế từ cuộc thi Home Credit Default Risk.
  - **Tổng giá trị tín dụng đề xuất:** Chuẩn hóa theo định dạng tài chính quốc tế (hàng tỷ/triệu đồng).
  - **Tỷ lệ khó khăn tài chính trung bình:** `8.1%` (tính trên tập hồ sơ có nhãn `TARGET=1`).
  - **Tiến độ ca trực:** Thống kê số lượng hồ sơ đã xử lý trong phiên làm việc.

### Bước 2: Tìm kiếm & Lọc Hồ sơ Thẩm định (Tab 1 — Core DSS)
- **Lọc theo trạng thái & rủi ro:** Sử dụng bộ lọc tại thanh bên (Sidebar) để lọc hồ sơ theo mức rủi ro (`LOW / MEDIUM / HIGH`).
- **Tìm kiếm hồ sơ cụ thể:** Nhập bất kỳ mã hồ sơ nào vào ô tìm kiếm:
  - Thử hồ sơ rủi ro thấp: Gõ `#100009` $\rightarrow$ Xác suất rủi ro thấp ($p \approx 0.05$), đề xuất phê duyệt.
  - Thử hồ sơ rủi ro cao: Gõ `#100010` hoặc `#155054` $\rightarrow$ Xác suất rủi ro cao ($p > 0.40$), đề xuất từ chối.
- **Nạp thêm dữ liệu:** Nhấn nút **"➕ Nạp thêm 20 hồ sơ"** để phân trang trực tiếp từ kho Neon Cloud DWH.

### Bước 3: Đánh giá Hồ sơ 360 độ & Giải thích Mô hình Máy học (Explainable ML)
- **Đồng hồ đo rủi ro (Risk Gauge):** Quan sát kim chỉ thị nằm trong vùng Xanh (An toàn), Vàng (Cảnh báo) hoặc Đỏ (Nguy hiểm) theo tiêu chuẩn Basel.
- **Đối chiếu nhãn thực tế:** So sánh điểm dự báo của mô hình với nhãn thực tế `TARGET` của Home Credit (`0`: trả nợ đúng hạn; `1`: gặp khó khăn tài chính).
- **Phân tích nhân tố Log-odds (`model_factors`):** Bảng đóng góp bóc tách nguyên nhân cụ thể:
  - Cột màu xanh (kéo giảm rủi ro): Điểm uy tín nguồn ngoài cao (`EXT_SOURCE`), thu nhập cao, việc làm ổn định.
  - Cột màu đỏ (đẩy tăng rủi ro): Đòn bẩy tài chính cao (`credit_income_ratio`), độ tuổi trẻ, có nợ quá hạn trong quá khứ.
- **Lịch sử vay tín dụng:** Xem thông tin tổng hợp từ 1.67 triệu giao dịch lịch sử: số lần vay trước đó, số lần được duyệt, số lần bị từ chối và tổng dư nợ cũ.

### Bước 4: Trải nghiệm Cơ chế Đè Chính sách (Policy Override)
- Tại ô tìm kiếm, gõ mã hồ sơ **`100402`**:
- Hồ sơ này có xác suất rủi ro ước lượng rất thấp ($p \approx 0.094 < 0.10$, mức `LOW`).
- **Quy tắc bảo vệ ngân hàng kích hoạt:** Do hồ sơ này **thiếu toàn bộ 3 điểm tín dụng bên ngoài** (`EXT_SOURCE_1, 2, 3`), chính sách rủi ro `policy_v1_illustrative` tự động đè khuyến nghị sang **`REVIEW`** (hiển thị banner màu vàng với mã lý do `ALL_EXTERNAL_SCORES_MISSING`).
- Cơ chế này kết hợp giữa điểm số mô hình và chính sách quản trị rủi ro để xử lý các hồ sơ thiếu dữ liệu quan trọng, tránh việc phê duyệt tự động khi chưa đủ căn cứ xác minh.

### Bước 5: Thẩm định & Lưu Quyết định vào Kho Dữ liệu Neon Cloud
- Di chuyển xuống khung **Quyết định Tín dụng (Credit Decision Panel)**.
- Chọn 1 trong 3 hành động: **Phê duyệt**, **Xem xét thêm**, hoặc **Từ chối**.
- Bấm nút **"Điền mẫu nhanh"** $\rightarrow$ Hệ thống tự động tổng hợp căn cứ thẩm định vào khung ghi chú.
- Bấm nút **"LƯU QUYẾT ĐỊNH (SAVE)"**:
  - Hệ thống thực hiện ghi dữ liệu nguyên tử (atomic transaction) vào bảng `app.credit_decisions` và `ml.assessments` trên Neon Cloud.
  - Trạng thái hồ sơ trên hàng đợi lập tức chuyển từ `PENDING` sang trạng thái tương ứng.

### Bước 6: Khám phá Dữ liệu Đa chiều (Tab 2 — OLAP Analytics)
- Chuyển sang **Tab 2 (OLAP Analytics)**.
- Chọn chiều phân tích: Ví dụ Hàng = **"Nhóm độ tuổi (Age Band)"**, Cột = **"Trình độ học vấn (Education Level)"**.
- Hệ thống thực hiện thao tác Roll-up / Slice & Dice tức thì trên toàn bộ **307,511 hồ sơ**.
- Quan sát **Ma trận phân bổ chéo (Cross-Tab Matrix)** kết hợp bản đồ nhiệt: Nhận diện rõ phân khúc có tỷ lệ nợ xấu (`TARGET=1`) cao nhất (ví dụ nhóm trẻ tuổi có học vấn phổ thông) để hỗ trợ lãnh đạo điều chỉnh hạn mức tín dụng danh mục.

### Bước 7: Mô phỏng Kịch bản Tài chính (Tab 3 — What-If Simulator)
- Chuyển sang **Tab 3 (What-If Analysis)**.
- Giả định khách hàng có rủi ro cao do đề nghị vay vượt quá khả năng chi trả:
  - Điều chỉnh giảm số tiền vay (`amt_credit`) từ `500,000K` xuống `250,000K`.
  - Tăng thời hạn vay hoặc tăng thu nhập giả định khi có người bảo lãnh.
- Bấm nút **"Chạy mô phỏng kịch bản"**:
  - Mô hình ML lập tức tái chấm điểm thời gian thực thông qua hàm `assess()`.
  - Bảng so sánh Before vs After hiển thị điểm rủi ro giảm xuống và khuyến nghị chuyển từ `DECLINE` sang `APPROVE`.
- Bấm nút **"Đẩy kết quả mô phỏng sang Ghi chú Phê duyệt"** $\rightarrow$ Nội dung đề xuất tái cấu trúc khoản vay được tự động sao chép sang khung ghi chú ở Tab 1.

### Bước 8: Kiểm toán Toàn vẹn & Giám sát Vận hành (Tab 4 — Audit Trail & Ops)
- Chuyển sang **Tab 4 (Audit Trail & ETL Runs)**.
- Bấm nút **"🔄 Đồng bộ từ Cloud DWH"**:
  - Bảng `app.credit_decisions` hiển thị bản ghi quyết định bạn vừa lưu ở Bước 5 với đầy đủ: ID hồ sơ, cán bộ thẩm định, hành động phê duyệt, mã lý do chuẩn hóa và mốc thời gian (timestamp).
- Quan sát bảng giám sát **`ops.etl_runs`**:
  - Kiểm tra tính toàn vẹn dữ liệu: Mã băm SHA-256 của các tệp dữ liệu gốc từ Kaggle.
  - Số lượng dòng thực tế: `307,511` đơn vay hiện tại, `1,670,214` giao dịch lịch sử.
  - Báo cáo kiểm soát chất lượng dữ liệu: `55,374` giá trị dị biệt đã được xử lý về `NULL`, `256,513` đơn mồ côi ngoài cohort được kiểm soát an toàn và `0` lỗi rò rỉ thời gian.
- **Kết luận:** Quy trình hỗ trợ quyết định khép kín từ dữ liệu thô $\rightarrow$ kho đa chiều $\rightarrow$ mô hình AI có thể giải thích $\rightarrow$ thẩm định viên ra quyết định $\rightarrow$ lưu vết kiểm toán vĩnh viễn trên Cloud DWH.
