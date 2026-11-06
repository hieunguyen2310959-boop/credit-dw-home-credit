# ML / DSS — Người 2

Phần **ML + DSS**. Train trên **Google Colab** từ `application_train.csv` + `previous_application.csv`, dùng **đúng feature contract `application_features_v1`** (`contracts/features-v1.json`, `mart.application_features_v1`), rồi bàn giao model và hàm suy luận cho người 3.

```text
ml/
├── credit_ml/            package: features, modeling, policy, inference, whatif, artifacts, training
├── notebooks/ml_dss_colab.ipynb
├── scripts/register_model.py   đăng ký model vào ml.model_runs
├── scripts/assess_cli.py       ví dụ chấm 1 hồ sơ và ghi ml.assessments
├── contracts/assessment-v1.json  hợp đồng API cho người 3
├── results/              kết quả lần chạy thật: models/, reports/, handoff/
├── tests/                17 test (dữ liệu giả lập, không cần PostgreSQL)
└── requirements-ml.txt
```

## Kết quả lần chạy thật (holdout 61.503 hồ sơ, 4.965 TARGET=1)

| | ROC-AUC | PR-AUC |
|---|---|---|
| Baseline hằng số (tỷ lệ nhãn train) | 0,5000 | 0,0807 |
| Baseline luật `1 − mean(EXT_SOURCE)` | 0,7165 | 0,1921 |
| **Logistic Regression** (`C=0,001`) | **0,7424** (CI95 0,7347–0,7494) | **0,2260** |

Số liệu đầy đủ: `results/reports/metrics.json`, `results/handoff/HANDOFF.md`. Model: `results/models/logreg_v1_20261106/` (sha256 artifact và hai CSV nguồn nằm trong `model_manifest.json`).

## 1. Chạy trên Colab

Cấu trúc Drive (tên có thể khác, sửa ô cấu hình mục 1 của notebook):

```text
MyDrive/credit_dw/
├── data/application_train.csv, previous_application.csv
├── ml/                  <- copy thư mục ml/ của repo
└── ml_outputs/          <- notebook tự tạo
```

Mở `ml/notebooks/ml_dss_colab.ipynb` bằng Colab → **Runtime → Run all**. Hai CSV phải **giống hệt** bản đã nạp vào DW (sha256 được ghi vào manifest và `register_model.py` đối chiếu với `ops.etl_runs`).

Sau khi chạy xong, đưa `ml_outputs/models`, `reports`, `handoff` vào `ml/results/` để commit (nhỏ, ~300 KB). `splits/` (4 MB) và `snapshots/` (15 MB) giữ trên Drive, không commit.

## 2. Notebook làm gì

| Bước | Nội dung |
|---|---|
| 2 | Dựng 16 feature theo cùng luật làm sạch của `sql/003_load_dw.sql` + `002_views.sql`; lịch sử gộp về 1 dòng/hồ sơ trước khi ghép |
| 3 | Split 60/20/20 phân tầng theo TARGET, theo `application_id`, seed 42, ba tập không giao nhau |
| 4–5 | Chọn `C` và ngưỡng F1 trên **valid**; pipeline chỉ `fit` trên train; TARGET không nằm trong X |
| 6 | Holdout: ROC-AUC (+CI bootstrap), PR-AUC, Brier, log-loss, confusion matrix, bảng decile, bảng band, 2 baseline |
| 7 | Lưu `pipeline.joblib` + `model_manifest.json`, load lại và chấm 2.000 hồ sơ holdout qua `assess()` phải trùng pipeline gốc |
| 8–9 | Sinh ví dụ response và `HANDOFF.md` |

Mô hình: log1p cho 3 cột tiền → impute trung vị + cờ thiếu → chuẩn hoá; 3 biến phân loại → `Unknown` + one-hot → Logistic Regression không dùng `class_weight`. `risk_score` là ước lượng cho lớp `TARGET=1` (cao = rủi ro cao hơn). Bảng decile cho thấy điểm trung bình sát tỷ lệ quan sát từng nhóm, nhưng chưa kiểm chứng hiệu chỉnh nên không gọi là xác suất thực.

**Policy minh hoạ** `policy_v1_illustrative`: thiếu dữ liệu quan trọng / cảnh báo mức cao → `REVIEW`; nếu không `p ≥ 0,25` → `DECLINE_SIMULATION`; `0,10 ≤ p < 0,25` → `REVIEW`; `p < 0,10` → `APPROVE_SIMULATION`. Trên holdout: LOW 73,7% (tỷ lệ TARGET=1 4,5%), MEDIUM 23,2% (15,7%), HIGH 3,1% (35,0%). `reason_codes` có mã `MODEL_FACTOR_UP|DOWN:<feature>` là đóng góp thật của Logistic Regression vào log-odds so với hồ sơ trung bình của train, không phải quan hệ nhân quả.

## 3. Đăng ký model và dùng trong API (Windows)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r ml/requirements-ml.txt
.\.venv\Scripts\python.exe -m pip install scikit-learn==1.6.1 joblib==1.6.0   # đúng phiên bản trong HANDOFF.md
.\.venv\Scripts\python.exe ml/scripts/register_model.py --models-root ml/results/models --model-dir logreg_v1_20261106
.\.venv\Scripts\python.exe ml/scripts/assess_cli.py --application-id <ID> --models-root ml/results/models
```

`register_model.py` từ chối nếu sha256 artifact sai, model không load được, chấm lại smoke-test lệch điểm đã lưu, hoặc sha256 hai CSV khác lần ETL thành công gần nhất. Chạy lại không tạo bản ghi trùng.

```python
from credit_ml import inference as I, whatif as W      # chạy với PYTHONPATH=ml
bundle = I.load_bundle(MODELS_ROOT, "logreg_v1_20261106", model_run_id)   # lỗi -> ModelNotReady -> 503
result = I.assess(bundle, application_id, feature_row)  # feature_row: dòng của mart.application_features_v1
row    = I.to_db_row(result)                            # INSERT ml.assessments trong transaction của API
what   = W.what_if(bundle, application_id, feature_row, income=..., review_threshold=...)  # không ghi DB
```

Ánh xạ lỗi: 404 hồ sơ không tồn tại (API), 422 `InvalidFeatures` (`.codes`), 503 `ModelNotReady` → `not_ready_result()` và **không** INSERT. Chi tiết: `contracts/assessment-v1.json`, ví dụ response trong `results/handoff/*.json` (tên file ghi rõ REAL / ILLUSTRATIVE / STRUCTURE_ONLY).

## 4. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest ml/tests -q
```

17 test dùng dữ liệu giả lập (`tests/synth.py`): luật feature khớp test của người 1, split, `assess()` khớp pipeline, từ chối khóa nhãn, giá trị NaN/âm/ngoài miền, policy, what-if, tổng đóng góp = logit, artifact bị sửa / đường dẫn `..`, CSV sai. Test PostgreSQL gốc của người 1 vẫn ở `tests/` và không bị ảnh hưởng.

## 5. Giới hạn và việc cần chốt

- Ngưỡng 0,10/0,25 và các cảnh báo là minh hoạ, cần team duyệt (đổi trong `PolicyConfig`).
- Thiếu dữ liệu quan trọng: vẫn chấm điểm nhưng ép `REVIEW` kèm mã lý do. Muốn trả `not_ready` thì thống nhất với người 3 vì khác ràng buộc DB.
- `C` hầu như không ảnh hưởng (ROC-AUC valid 0,7373–0,7375 cho mọi `C` đã thử): mô hình ổn định, không quá nhạy siêu tham số.
- Chỉ dùng `application_train.csv` để train/đánh giá; `application_test.csv` không có nhãn.
- Chưa đối chiếu feature với DW trên dữ liệu thật; việc đảm bảo cùng dữ liệu dựa trên sha256 hai CSV khi đăng ký model.
- `risk_probability` (bản thảo) và `risk_score` (DB/code): chọn một tên khi chốt `openapi.yaml`.
- `TARGET` là định nghĩa khó khăn thanh toán của nguồn; recommendation chỉ là mô phỏng.
