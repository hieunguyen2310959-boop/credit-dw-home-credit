# Bàn giao ML/DSS — người 2 → người 3 (và người 1)
Sinh tự động lúc 2026-11-06T09:50:37+00:00 từ notebook. Mọi số liệu dưới đây lấy từ lần chạy này trên hai file CSV được chỉ định ở mục 1 (kiểm tra sha256 bên dưới).

## Model
- `logreg_v1_20261106/` trong `ml_outputs/models/` — `pipeline.joblib` + `model_manifest.json`
- model_name `logistic_regression_v1`, feature_version `application_features_v1`, C = 0.001
- sha256 artifact: `ca07840239f53f53638e7265a55e62705b91516ab90987c8c8c93d44a1918362`
- Môi trường train: Python 3.13.18, scikit-learn 1.6.1, pandas 2.2.3, numpy 2.4.6, joblib 1.6.0
  → khi chạy trên Windows: `pip install scikit-learn==1.6.1 joblib==1.6.0`

## Kết quả holdout (61,503 hồ sơ, 4,965 TARGET=1)
| | ROC-AUC | PR-AUC |
|---|---|---|
| Prior baseline | 0.5000 | 0.0807 |
| Luật EXT_SOURCE | 0.7165 | 0.1921 |
| **Logistic Regression** | **0.7424** (CI95 0.7347–0.7494) | **0.2260** |

Ngưỡng phân loại 0.1427 (chọn trên valid): TN=49,981 FP=6,557 FN=2,967 TP=1,998.
Brier = 0.0687; log-loss = 0.2507. Xem bảng hiệu chỉnh trong `reports/` và `model_manifest.json` — chưa nên gọi risk_score là xác suất đã hiệu chỉnh nếu decile lệch.

## Policy (minh hoạ, chờ team duyệt) — `policy_v1_illustrative`
- Thiếu dữ liệu quan trọng / cảnh báo mức cao → `REVIEW`; nếu không: p ≥ 0.25 → `DECLINE_SIMULATION`; 0.1 ≤ p < 0.25 → `REVIEW`; p < 0.1 → `APPROVE_SIMULATION`.
- risk_band: LOW / MEDIUM / HIGH theo cùng hai ngưỡng.

## Parity với DW
{"checked": false}

## Dữ liệu nguồn (sha256 phải khớp ops.etl_runs.source_manifest)
- application_train: `application_train.csv` sha256 `52e96b895b1112e1c853f670e58372719c8441c5ed1c57ac2f7fad559d784f5f`
- previous_application: `previous_application.csv` sha256 `5046cd657ee04df2eaa6dc8308ae86be6b3b1763674a3f63574886a2f2896505`

## Hạn chế
Nhãn TARGET là định nghĩa khó khăn thanh toán của nguồn, không phải vỡ nợ 90 ngày/12 tháng. Recommendation chỉ là mô phỏng, không phải quyết định cấp tín dụng. Số lịch sử previous chỉ mô tả dữ liệu đã nạp.
