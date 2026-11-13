# Hướng dẫn hiểu và demo bài tập lớn

Mục tiêu: hiểu được dữ liệu đi đâu, mỗi bước tính gì và vì sao ra khuyến nghị. Đây là mô phỏng học thuật, không phải hệ thống phê duyệt khoản vay thật.

## 1 Luồng chạy cần nhớ

```text
Hai CSV Home Credit
  → scripts/database.py đọc và nạp staging
  → sql/003_load_dw.sql làm sạch, tổng hợp lịch sử, nạp fact/dimension
  → sql/002_views.sql tạo các góc nhìn phục vụ phân tích
  → app/data_adapter.py đọc hồ sơ từ PostgreSQL/Supabase
  → ml/credit_ml/inference.py gọi mô hình đã train
  → ml/credit_ml/policy.py chuyển điểm và cảnh báo thành khuyến nghị
  → app/views/ hiển thị, mô phỏng và lưu quyết định
```

Supabase là PostgreSQL trên cloud. Khi mở web, chương trình đọc DW đã có sẵn; không tải lại CSV hoặc train lại model. Khi không kết nối được DB, web dùng bốn hồ sơ minh họa và model thật. Quyết định offline chỉ nằm trong phiên.

## 2 Thứ tự đọc code

1. `contracts/features-v1.json`: 16 đầu vào của model, ID và TARGET không phải predictor.
2. `sql/001_schema.sql`: staging giữ dữ liệu nguồn; hai dimension mô tả hồ sơ và hợp đồng; fact có grain một dòng/hồ sơ.
3. `scripts/database.py`: các lệnh init-db, load, demo, check; đọc CSV, checksum và transaction.
4. `sql/003_load_dw.sql`: sentinel chuyển NULL; lịch sử chỉ lấy DAYS_DECISION <= 0; gộp lịch sử trước khi join để không nhân dòng.
5. `sql/002_views.sql`: features tách nhãn, overview dành cho web, latest dành cho kết quả đã lưu.
6. `ml/credit_ml/modeling.py` và notebook: train Logistic Regression, tiền xử lý nằm trong pipeline, chia 60/20/20. Chỉ fit train, chọn tham số trên validation, đánh giá holdout.
7. `ml/credit_ml/inference.py`: load artifact và checksum, kiểm tra input, predict_proba, tính đóng góp log-odds, gọi policy.
8. `ml/credit_ml/policy.py`: điểm thấp hơn 0,10 đề xuất duyệt; từ 0,10 đến dưới 0,25 xem xét; từ 0,25 từ chối mô phỏng. Thiếu dữ liệu quan trọng/cảnh báo cao buộc REVIEW bất kể màu điểm.
9. `app/data_adapter.py`: kết nối DB, đọc view, đổi đơn vị hiển thị và đưa 16 feature vào model.
10. `app/main.py` và bốn file trong `app/views/`: điều phối bốn tab, nhận thao tác và hiển thị kết quả.

## 3 Chạy demo

Tại thư mục repo, chạy:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/main.py
```

Để dùng dữ liệu thật, tạo `.env` theo `.env.example` và điền DATABASE_URL của nhóm. Ký tự đặc biệt trong phần mật khẩu của URL phải được URL-encode. Không đưa mật khẩu lên repo hoặc slide.

Nếu máy dùng database local mới, chạy `scripts/database.py init-db` để tạo bảng và view, bao gồm bảng quyết định trong `sql/005_decisions.sql`. Không chạy lệnh nạp fixture demo vào kho dữ liệu thật. Không chạy test database vào Supabase dùng chung.

Kiểm thử không cần DB:

```powershell
.\.venv\Scripts\python.exe -m pytest ml/tests tests/test_demo_ui.py -q
```

## 4 Kịch bản thuyết trình khoảng 10 phút

1. Nói bài toán: phân tích hồ sơ và hỗ trợ người thẩm định lựa chọn, không tự quyết định thật.
2. Vẽ luồng CSV → staging → DW → mart → model → policy → web.
3. Giải thích grain và một ví dụ xử lý sentinel; giải thích vì sao tổng hợp lịch sử trước khi join.
4. Mở OLAP, đổi chiều tuổi/hợp đồng và measure. TARGET=1 là khó khăn thanh toán theo nguồn; tổng amt_credit không phải dư nợ.
5. Mở hồ sơ, chỉ ra 16 feature, điểm model, các yếu tố tăng/giảm điểm và khuyến nghị policy.
6. Chạy what-if: đổi thu nhập, giữ tín dụng; sau đó đổi ngưỡng policy để thấy điểm model không đổi nhưng khuyến nghị có thể đổi. Khi đổi tín dụng, annuity được giả định đổi cùng tỷ lệ; đây là giả định demo.
7. Lưu quyết định: live chỉ báo thành công sau khi DB xác nhận; offline chỉ lưu trong phiên. Quyết định cán bộ là lựa chọn khác với khuyến nghị model.
8. Kết thúc bằng kết quả đã lưu: AUC 0,7424 là kết quả holdout trong artifact báo cáo; không nói vừa train lại khi mở web.

## 5 Câu hỏi dễ gặp

- Vì sao dùng DW? Tập trung dữ liệu nhiều bảng, làm sạch một lần, thống nhất feature và số liệu phân tích.
- Vì sao Logistic Regression? Dễ giải thích, đủ cho BTL, suy luận nhanh; không cần thêm mô hình phức tạp.
- ML khác policy thế nào? ML ước lượng điểm TARGET=1; policy áp ngưỡng và cảnh báo để ra khuyến nghị.
- Vì sao điểm LOW vẫn REVIEW? Điểm và chất lượng dữ liệu là hai yếu tố khác nhau; thiếu dữ liệu quan trọng cần người kiểm tra.
- What-if có chứng minh giảm rủi ro thật không? Không; chỉ cho thấy model phản ứng ra sao khi thay đầu vào giả định.
- Vì sao ml.assessments trống mà web vẫn chạy? Web chấm trực tiếp từ artifact; bản demo không tự lưu mọi lần chấm. Bảng đó là nơi lưu khi sử dụng CLI assess riêng.
- Vì sao lịch sử staging trên cloud có sự khác biệt? Trên tài khoản Supabase 500 MB, bảng staging bị truncate sau khi đã tổng hợp vào DW để tránh quá hạn mức lưu trữ; trên tài khoản Neon Cloud 1 GB, hệ thống lưu trữ nguyên vẹn toàn bộ 1,670,214 dòng staging phục vụ kiểm toán và đối soát dữ liệu.

## 6 Phạm vi vừa đủ cho môn học

Giữ model đã train, bốn tab và kết nối PostgreSQL hiện tại. Chưa thêm đăng nhập, phân quyền ngân hàng, model registry, streaming, tự động retrain hoặc triển khai production. Tập trung hiểu các bước trên và demo đúng kết quả.
