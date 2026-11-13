# Kết quả kiểm thử BTL ngày 12 tháng 11 năm 2026

Nhánh: `lytrunghoa`. Phạm vi là bản demo môn học, không đánh giá khả năng vận hành ngân hàng thực tế.

## Đã kiểm tra thành công

| Phần | Kết quả |
| --- | --- |
| Toàn bộ pytest | 41 passed, 1 warning; bằng chứng docs/evidence/tests.xml |
| PostgreSQL riêng | Portable 16.6, host 127.0.0.1 cổng 55439; database credit_dw_review_test, tách hoàn toàn database cloud |
| DW và ETL | Grain, PK/FK/CHECK, cutoff, null/sentinel, rollback, idempotency và latest assessment |
| Giao diện local có DB | Bốn tab mở được, đổi bốn chiều OLAP, chạy what-if, lưu quyết định rồi mở phiên mới đọc lại |
| Giao diện khi lỗi | Model chưa sẵn sàng, policy REVIEW thắng band LOW, DB lưu thất bại, offline lưu trong phiên, what-if suy luận lỗi |
| Parity trên fixture | 16 feature dựng bằng pandas khớp feature view SQL |
| CLI demo | init-db; demo chạy hai lần vẫn 3 hồ sơ, 3 nhãn, 1 TARGET=1, tổng credit 1000,0000; check đạt |
| SQL OLAP | Năm truy vấn trong sql/004_analytics.sql lần lượt trả 1, 6, 3, 2, 0 dòng trên fixture |
| Python và diff | compileall đạt; git diff --check không có lỗi khoảng trắng |
| Neon Cloud DWH chỉ đọc | 307.511 hồ sơ duy nhất, 24.825 TARGET=1, không orphan dimension, 1.670.214 dòng staging.previous_application, tổng credit 184.207.084.195,5 |
| Suy luận live | 100 hồ sơ từ mart được chấm thành công, cấu trúc feature khớp contract |

Fixture là SYNTHETIC, chỉ chứng minh chương trình xử lý đúng các tình huống kiểm thử, không chứng minh chất lượng mô hình trên dữ liệu thực. AppTest thực thi các callback và cây giao diện Streamlit, không thay cho kiểm tra bố cục trực quan trên trình duyệt.

Lần kiểm tra live mới nhất có 1 bản ghi ml.model_runs, 0 ml.assessments và 0 app.credit_decisions. Các số này chỉ là ảnh chụp trạng thái lúc kiểm tra và có thể thay đổi khi thành viên nhóm làm việc. Bằng chứng tổng hợp nằm ở docs/evidence/live_verification.json, không chứa thông tin đăng nhập hoặc dữ liệu từng hồ sơ.

## Cách chạy lại

Chuẩn bị database test riêng, tên có chữ test. Tuyệt đối không dùng database Neon Cloud của nhóm vì các test DB xóa/tạo lại schema.

```powershell
$env:TEST_DATABASE_URL = 'postgresql://credit_test@127.0.0.1:55439/credit_dw_review_test'
.\.venv\Scripts\python.exe -m pytest tests ml/tests -q
```

Kiểm tra live chỉ đọc khi đã có DATABASE_URL trong môi trường hoặc .env:

```powershell
.\.venv\Scripts\python.exe scripts/verify_live.py
```

Script live chỉ đọc số tổng hợp và tối đa 100 hồ sơ để suy luận, không train và không lưu hồ sơ ra tệp.

## Các sửa đổi đủ cho demo môn học

- Không trả điểm/khuyến nghị giả khi model lỗi; what-if không dùng công thức thay thế.
- Hiển thị banner theo recommendation của policy, không suy từ band.
- Chỉ đổi trạng thái sau khi ghi DB thành công; offline thông báo đúng phạm vi session.
- Hồ sơ thật thiếu lịch sử quá hạn được ghi là chưa có dữ liệu.
- Thêm sql/005_decisions.sql vào init-db để dựng local đủ bảng quyết định.
- Sửa tên feature học vấn trong OLAP offline, không vẽ 0 thành 0,5, bỏ nhãn An toàn suy từ tỷ lệ 0.
- Ghim scikit-learn 1.6.1 và joblib 1.6.0 theo artifact để máy khác load cùng phiên bản.
- Giữ Streamlit, model hiện có, cách đọc artifact và schema lõi; không thêm kiến trúc mới.

## Chưa xác nhận

- Chưa retrain hoặc tái tính AUC holdout gốc. Metrics được đối chiếu artifact; kiểm thử parity chỉ thực hiện trên fixture.
- Chưa ghi/đọc thử trên database production khác. Đường ghi/đọc và lưu bền vững đã chạy trên PostgreSQL local riêng và đã xác thực kiểm thử mô phỏng.
- Tái tính AUC từ toàn bộ dữ liệu live và thử INSERT dù rollback bị bộ xét duyệt tự động chặn vì phạm vi dữ liệu tài chính và ghi từ xa; cần xác nhận riêng của người dùng trước khi thử tiếp.
- Trạng thái lưu trữ staging: Hệ thống triển khai trên Neon Cloud DWH (1 GB), `staging.previous_application` lưu trữ đầy đủ 1,670,214 dòng và đã được xác thực qua `scripts/verify_live.py` (kết quả tại `docs/evidence/live_verification.json`).
- Compiler báo cáo timeout do môi trường; ba ảnh tab 2/3/4 còn thiếu. Chưa kiểm tra PDF cuối hoặc bố cục in.
- Chưa có slide PDF, video/hình thức thuyết trình được xác nhận và bộ ZIP cuối trong phạm vi tệp đã cung cấp.

Cảnh báo còn lại từ sklearn/SciPy: Unknown solver options iprint khi train test synthetic. Không làm test thất bại, không dùng để kết luận artifact bị hỏng. Chưa thay thư viện tối ưu vì model demo đã load và chấm được.

Đối chiếu chi tiết đề bài và nhận xét báo cáo: docs/DOI_CHIEU_DE_BAI_VA_BAO_CAO.md. Hướng dẫn đọc code và kịch bản trình bày: docs/DEMO_VA_LUONG_CODE.md.
