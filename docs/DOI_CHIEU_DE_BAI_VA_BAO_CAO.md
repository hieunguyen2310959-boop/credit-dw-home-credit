# Đối chiếu đề bài và rà soát báo cáo

Ngày kiểm tra: 12/11/2026. Nhánh làm việc: `fix/coursework-demo-verification`.

Nguồn: đề CO4031_Assignment_HK261 (1).pdf trong thư mục cha và bản LaTeX tại `C:/Users/admin/Downloads/BTL_DataWarehouse`. Bản LaTeX gốc được giữ nguyên. Tài liệu này là nhận xét cần dùng để cập nhật báo cáo trước khi xuất PDF nộp.

## 1 Kết luận theo phạm vi môn học

Hệ thống có đủ các thành phần kỹ thuật chính để trình diễn BTL: DW theo star schema, ETL, SQL OLAP, dashboard, mô hình và chính sách DSS, what-if và lưu quyết định. Streamlit phù hợp yêu cầu dashboard/giao diện truy vấn của đề; đề không bắt buộc frontend React hoặc API FastAPI riêng.

Không cần bổ sung Kafka, nhiều mô hình ML, đăng nhập ngân hàng hoặc quy trình vận hành production. Cần chỉnh báo cáo khớp code, hoàn thiện hình/PDF và bộ nộp. Chưa đủ cơ sở khẳng định mọi yêu cầu nộp bài đã hoàn tất.

## 2 Bảng đối chiếu yêu cầu đề bài

| Yêu cầu | Bằng chứng trong chương trình và báo cáo | Kết luận |
| --- | --- | --- |
| Phân tích nghiệp vụ và bài toán thực tế | Chương 1; phân tích rủi ro hồ sơ, hỗ trợ cán bộ chọn quyết định | Có nội dung; cần giảm các cam kết pháp lý/hiệu quả chưa đo |
| Thiết kế đa chiều star/snowflake và ETL | Chương 2–3; sql/001_schema.sql, sql/003_load_dw.sql, scripts/database.py | Đã hiện thực; sửa mô tả khóa nguồn và khóa thay thế |
| Backend cơ sở dữ liệu, ETL, OLAP | PostgreSQL, mart views, sql/004_analytics.sql, adapter | Đã kiểm thử local; live kiểm tra chỉ đọc có giới hạn |
| Frontend dashboard/giao diện truy vấn | app/main.py và bốn tab Streamlit; chương 3–4 | Chạy được bằng AppTest; không bắt buộc stack trong kế hoạch cũ |
| DSS dựa trên DW | 16 features, Logistic Regression, PolicyConfig, what-if | Đã kiểm thử; phân biệt score, policy và quyết định người dùng |
| Đánh giá kết quả, hạn chế, hướng phát triển | Chương 4–5; metrics.json; tests và docs/evidence | Có nội dung; số AUC lấy từ artifact, chưa tái tính trên holdout gốc |
| Nhóm 2–3 người, vai trò rõ ràng | assignment.tex: 3 thành viên với công việc và tỷ lệ | Đã trình bày; sự tham gia thực tế do nhóm xác nhận |
| Báo cáo PDF | Hiện cung cấp dự án LaTeX, chưa có PDF cuối được kiểm chứng | Cần biên dịch và kiểm tra bố cục |
| Mã nguồn, SQL, ETL, frontend | Đủ trong repo; README có cách chạy | Khi đóng ZIP đặt repo trong src/ theo đề, không cần đổi cấu trúc code |
| Dữ liệu mẫu | data/fixtures gồm CSV synthetic có mô tả | Có mẫu chạy; thêm hướng dẫn tải dữ liệu thật và tuân thủ điều khoản |
| Slide PDF | Chưa có trong các tệp được cung cấp | Cần chuẩn bị trước nộp |
| Trình bày trực tiếp hoặc video | Chưa có bằng chứng đăng ký/hình thức hoặc video | Nhóm chốt hình thức, mọi thành viên đều tham gia |
| Video nếu không trình bày trực tiếp | Chưa có đường dẫn trong bìa | Nếu thuộc diện này: video 10–15 phút, cấp quyền xem, thêm link vào bìa |
| Nộp LMS | Deadline đề: 23:59 ngày 15/11/2026 | Tự kiểm tra ZIP và lưu bằng chứng nộp |

Trình bày trực tiếp: 15 phút thuyết trình và 5 phút hỏi đáp. Không dùng thời lượng video thay cho thời lượng trực tiếp.

## 3 Các điểm báo cáo cần sửa

### 3.1 Lỗi kỹ thuật cần sửa trước

1. **Khóa thay thế ở chương 2.** Báo cáo gọi `application_id` là BIGINT IDENTITY tự sinh. Code giữ nguyên `SK_ID_CURR` vào `application_id`; IDENTITY nằm ở `applicant_profile_key` và `contract_type_key`. Sửa đoạn này, không sửa database để chạy theo mô tả sai.
2. **Nguồn huấn luyện ở chương 3.** Notebook đọc hai CSV, dựng feature bằng pandas. Không trích trực tiếp view DB để train. Web mới đọc feature từ Data Mart để inference. Cùng tên feature/checksum nguồn chưa đủ để khẳng định parity trên toàn bộ dữ liệu thật.
3. **Danh mục 16 feature.** Nghề nghiệp hiển thị trong hồ sơ nhưng không phải predictor trong contract v1. Bỏ nghề nghiệp khỏi danh sách đầu vào model. View features vẫn có `application_id` làm khóa join; chỉ loại nó khi lấy X, không nói view không có ID.
4. **Staging không phải toàn bộ chuỗi gốc.** SQL đã dùng BIGINT, NUMERIC, INTEGER và DOUBLE PRECISION cho nhiều cột staging. Sửa bảng mô tả chương 3.
5. **Idempotency không phải bỏ qua checksum trùng.** Loader cùng nguồn sẽ nạp lại trong transaction và upsert DW, giữ grain/khóa/kết quả cũ. Thay nguồn bị từ chối và yêu cầu DB mới. Sửa đoạn nói tự bỏ qua nguồn giống nhau nếu đang có.
6. **Không khẳng định view giảm tải tự động.** SQL view thông thường không lưu kết quả tính sẵn; database vẫn thực thi truy vấn bảng nền. Phân biệt view với materialized view/cache giao diện.
7. **Trạng thái cloud phải nói đúng.** Khi triển khai trên Supabase (hạn mức 500 MB), bảng `staging.previous_application` từng được truncate để tiết kiệm bộ nhớ; khi triển khai trên Neon Cloud DWH (hạn mức 1 GB), toàn bộ 1,670,214 dòng staging được lưu trữ đầy đủ và đối soát thành công (kết quả tại `docs/evidence/live_verification.json`). Báo cáo cần ghi rõ cấu hình kho dữ liệu tương ứng.
8. **Artifact path.** Đường dẫn trong repo là `ml/results/models/logreg_v1_20261106/`, không phải `ml/artifacts/...`.

### 3.2 Điều chỉnh cách diễn giải kết quả

9. `TARGET=1` là khó khăn thanh toán theo định nghĩa nguồn. Không tự gọi thành nợ xấu 90 ngày hoặc PD 12 tháng.
10. `SUM(amt_credit)` là tổng giá trị tín dụng hồ sơ, không phải dư nợ hiện tại. Goods price là giá trị hàng hóa theo nguồn, không mặc nhiên là tài sản thế chấp.
11. `credit_income_ratio` là credit amount / thu nhập, không phải DTI theo nghĩa tổng nghĩa vụ trả nợ tháng / thu nhập tháng.
12. EXT_SOURCE là các điểm nguồn ngoài đã chuẩn hóa; không xác nhận đó là điểm CIC Việt Nam. Trong code đã đổi nhãn EXT_3 chính cho đúng.
13. Không dùng Brier = 0,0687 để khẳng định PD đã hiệu chuẩn hoặc được ngân hàng công nhận. Nêu metrics và calibration plot như đánh giá trên holdout đã lưu, kèm giới hạn dữ liệu.
14. 17 test ML kiểm tra logic code và bất biến; không chứng minh hiệu chuẩn xác suất trên dân số thực. Bộ test mới bổ sung kiểm tra tích hợp, xem docs/evidence/tests.xml.
15. Không khẳng định model tốt hơn baseline ở mọi ngưỡng, không quá khớp tuyệt đối, hoặc đã triệt tiêu gian lận chỉ dựa trên AUC. AUC chỉ mô tả khả năng xếp hạng tổng quát trên tập đánh giá.
16. Các số latency 18,4 / 22,1 / 12,6 / 34,8 ms và thời gian thẩm định dưới 3 phút cần log đo, câu SQL, cấu hình máy, số lần chạy. Nếu không có, bỏ bảng cam kết SLA và ghi đây là mục tiêu chưa đo lại.
17. Bỏ tuyên bố đã đáp ứng hoàn hảo Basel II/Thông tư, đã giải quyết công bằng hay kiểm toán tuân thủ toàn diện. BTL chỉ minh họa giải thích điểm và ghi nhật ký; chưa xác minh tuân thủ pháp lý.
18. Hướng phát triển có thể đề xuất so sánh thêm mô hình; không hứa AUC sẽ vượt 0,78 hoặc Kafka chắc chắn đạt dưới 1 giây khi chưa thực nghiệm.

### 3.3 Đồng bộ với bản code đã sửa

19. Model lỗi: báo lỗi và dừng chấm, không có điểm thay thế. What-if lỗi: không tạo kết quả giả. Cảnh báo dữ liệu có thể buộc REVIEW dù band LOW/HIGH.
20. Live ghi DB thành công mới xác nhận quyết định; ghi lỗi không thay đổi trạng thái. Offline chỉ lưu trong session, không bền vững khi mở lại.
21. Web chấm trực tiếp từ artifact. Việc có bảng ml.model_runs/ml.assessments không có nghĩa mỗi lần web chấm đều ghi vào đó. Không mô tả đường ghi mà giao diện chưa thực hiện.
22. What-if đổi tín dụng kéo annuity cùng tỷ lệ là giả định demo với các điều kiện khác cố định; không phải phép tối ưu khoản vay hoặc kết luận nhân quả.
23. OLAP hiện chọn chiều/measure và có bảng chéo cố định. Không mô tả như giao diện hỗ trợ mọi phép slice/dice/drill-down tự do; các ví dụ SQL và thao tác UI phải được phân biệt.

## 4 Các đoạn có thể thay trực tiếp trong báo cáo

**Khóa và grain:** Bảng fact giữ application_id bằng SK_ID_CURR của nguồn, mỗi dòng là một hồ sơ. Các dimension sử dụng applicant_profile_key và contract_type_key tự sinh. Lịch sử được tổng hợp theo SK_ID_CURR trước khi join để bảo toàn số hồ sơ và các tổng tiền.

**Huấn luyện và suy luận:** Notebook dựng 16 feature từ hai CSV theo các quy tắc tương ứng với SQL Data Mart. Pipeline tiền xử lý và Logistic Regression được fit trên train; validation dùng chọn tham số, holdout dùng báo cáo kết quả. Khi demo, web đọc DW và chấm bằng artifact đã lưu, không huấn luyện lại.

**Kết quả:** Artifact lần chạy ngày 06/11/2026 ghi ROC-AUC 0,7424, average precision 0,2260 và Brier 0,0687 trên 61.503 hồ sơ holdout. Lần rà soát hiện tại đã kiểm tra artifact và suy luận với 100 hồ sơ live, nhưng chưa tái tính các chỉ số holdout hoặc retrain từ toàn bộ nguồn. Không xem risk_score là xác suất vỡ nợ đã được hiệu chuẩn cho sử dụng thực tế.

**Giới hạn:** Hệ thống dùng hai bảng nguồn và ngưỡng policy minh họa. Chưa có nhãn gian lận xác nhận, chưa xác minh tuân thủ quy định ngân hàng, chưa đo lại SLA nêu trong bản thảo. Model chạy từ artifact tĩnh; kết quả what-if là độ nhạy theo đầu vào giả định. Mục tiêu là minh họa luồng DW–OLAP–DSS trong phạm vi môn học.

## 5 Tệp báo cáo hiện chưa đầy đủ để xuất PDF

Các tệp ảnh được chapter4.tex gọi nhưng không có trong thư mục figures được cung cấp:

- `fig_dss_tab2_olap.png`
- `fig_dss_tab3_whatif.png`
- `fig_dss_tab4_audit.png`

Không thay bằng hình giả hoặc ảnh minh họa được gắn nhãn như kết quả thật. Chụp lại ba tab sau khi chạy demo, hoặc bỏ figure/tham chiếu tương ứng nếu không dùng.

Đã gọi compiler tích hợp cho main.tex: timeout; log báo lỗi quyền MiKTeX và tải bộ định dạng Tectonic chưa hoàn tất. Đây là lỗi môi trường biên dịch, không phải xác nhận LaTeX nguồn đúng/sai. Chưa có PDF cuối được render và kiểm tra bố cục. Cần biên dịch bản đầy đủ hình trước nộp.

## 6 Phần cần hoàn thành trước khi nộp

- Sửa các mô tả sai và giảm các kết luận quá mức ở trên; giữ báo cáo vừa sức BTL.
- Bổ sung ba ảnh hoặc bỏ tham chiếu, xuất báo cáo PDF và kiểm tra bảng/hình/chữ tràn.
- Chuẩn bị slide PDF và phân công thuyết trình đủ ba người.
- Nếu nộp video: 10–15 phút, đủ thành viên, link xem được và nằm trên bìa báo cáo.
- ZIP gồm báo cáo PDF, mã nguồn trong src/, data mẫu, slide PDF và link video nếu áp dụng; không chứa mật khẩu, .venv, .local-postgres.
- Không tuyên bố đã chạy kiểm thử live ghi DB hoặc tái lập AUC nếu hai bước đó chưa được cấp quyền và chạy thành công.
