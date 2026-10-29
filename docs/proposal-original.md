# ĐỀ XUẤT CẤU TRÚC DATABASE
## Bài tập lớn Data Warehouse & DSS – Home Credit
Tài liệu thiết kế để nhóm thảo luận và chốt trước khi triển khai
Phiên bản 1.0 • Trạng thái: ĐỀ XUẤT, chưa phải database đã chạy

# 1. Mục tiêu và phạm vi
Nhóm xây dựng kho dữ liệu hồ sơ tín dụng, dashboard phân tích và thành phần ML hỗ trợ xem xét hồ sơ. Database phải vừa dễ hiểu với ba thành viên, vừa phân biệt được dữ liệu nguồn, đặc trưng, nhãn quan sát, kết quả model và gợi ý của hệ thống.
Tài liệu này dành cho bài tập lớn Data Warehouse, không phải đồ án Reputa. Công nghệ đề xuất là PostgreSQL, Python, FastAPI và React; chạy trực tiếp trên Windows, không Docker. Không yêu cầu vận hành ngân hàng thật hay tự động phê duyệt khoản vay thật.
Phạm vi cốt lõi: application_train.csv và previous_application.csv. Có thể thêm application_test.csv để demo hồ sơ không có nhãn. Các nguồn bureau, installments, POS và credit card là mở rộng, không nằm trong cam kết đầu tiên.
Đầu ra nên giữ gọn: một màn hình phân tích tổng quan và một màn hình xem/chấm hồ sơ; ML có baseline, Logistic Regression và đánh giá trên tập giữ riêng. Database không thay thế pipeline ML và không tự chứng minh chất lượng dự báo.

## 1.1. Căn cứ và giới hạn của đề xuất
Nguồn tham khảo nội bộ: báo cáo “[CO4031] DW & DSS Group 1 Submission Report on ETL for Credit Risk”, file người dùng cung cấp tại Downloads. Đã đọc phần Transform, Data Warehouse Schema, Application Review và Limitations; Hình 3.2 ở trang 18 in trên báo cáo, tương ứng trang PDF 19, thể hiện tên trường và PK/FK.
Báo cáo tham khảo có dim_applicant, dim_credit_history, dim_payment_behavior, fact_loan_application và bảng nghiệp vụ credit_decisions. Họ tích hợp dữ liệu và dùng scorecard luật. Tài liệu này không sao chép DDL của họ: mọi kiểu SQL, ràng buộc và bảng mới dưới đây là đề xuất của nhóm, cần hiện thực và kiểm thử.
Chưa khảo sát trực tiếp CSV/dictionary trong lượt soạn này. Danh sách staging là contract tối thiểu dự kiến dựa trên các trường đã trao đổi, không phải tuyên bố đã kiểm tra đầy đủ header của dữ liệu cục bộ. Khi triển khai phải đối chiếu tên cột, ý nghĩa, đơn vị và giá trị đặc biệt với dictionary nguồn.

## 1.2. Những gì giữ và những gì thay đổi
| Thành phần bài tham khảo | Đề xuất áp dụng | Lý do |
| dim_applicant | Giữ ý tưởng thông tin mô tả, đặt tên dim_applicant_profile | Phục vụ lọc và nhóm hồ sơ; không suy diễn thành hệ thống định danh khách hàng xuyên nhiều năm |
| Hai dimension lịch sử | Không sao chép nguyên trong MVP | Chưa dùng đủ các nguồn; nhiều cột là số đo tổng hợp chứ không chỉ là ngữ cảnh mô tả |
| fact_loan_application | Đổi thành fact_application, chỉ giữ dữ liệu hồ sơ và số đếm lịch sử | Một dòng luôn là một hồ sơ, không bị thay đổi khi đổi model |
| Điểm và gợi ý trong fact | Tách sang assessments | Một hồ sơ có thể chấm nhiều lần mà không ghi đè kết quả cũ |
| Chấm điểm trong ETL | Tách huấn luyện và suy luận khỏi ETL | Nạp dữ liệu không kéo theo train; mở dashboard không train lại |
| Ghi quyết định người dùng | Giữ ở mức tùy chọn | Chỉ thêm khi nhóm thực sự có chức năng ghi quyết định |

# 2. Giải thích các khái niệm bằng ví dụ
## 2.1. Grain: một dòng đại diện cho điều gì?
Grain là câu mô tả chính xác ý nghĩa một dòng. Ví dụ minh họa: hồ sơ A có ba hồ sơ vay trước và được hai model chấm. fact_application vẫn có một dòng cho A; bảng hồ sơ trước có ba dòng; assessments có hai dòng. Không nhập cả ba loại sự kiện này vào một bảng rồi cộng chung.
Nếu nối fact hồ sơ với ba dòng lịch sử trước khi tính tổng, giá trị tín dụng của A có thể bị nhân ba. Vì vậy phải tổng hợp lịch sử về một dòng/A trước khi ghép vào feature hoặc tổng hợp dashboard.

## 2.2. Fact, dimension, staging và mart
| Thành phần | Cách hiểu dễ nhớ | Vai trò trong BTL |
| Staging | Bàn nhận dữ liệu từ file | Giữ những trường nguồn cần dùng và thông tin đợt nhập để đối soát |
| Dimension | Các nhãn để chia nhóm | Học vấn, nhóm tuổi, loại thu nhập, loại hợp đồng |
| Fact | Những sự kiện/số đo cần phân tích | Một hồ sơ với giá trị tín dụng, thu nhập, nhãn và số đếm lịch sử |
| Mart/view | Cửa sổ dữ liệu theo mục đích | ML đọc feature; web đọc hồ sơ và kết quả mới nhất |
| Bảng vận hành | Nhật ký hệ thống | Đợt ETL, lần train, lần chấm, quyết định thủ công |
Các schema staging, dw, mart, ml, ops và app chỉ là các ngăn tên trong cùng một PostgreSQL. Chúng không phải sáu database hay sáu service phải chạy riêng.

## 2.3. Phân biệt TARGET, risk_score và recommendation
TARGET là nhãn quan sát theo định nghĩa khó khăn thanh toán của nguồn; không tự thay bằng định nghĩa vỡ nợ 90 ngày hoặc 12 tháng. TARGET=0 không có nghĩa chắc chắn an toàn trong mọi tương lai. TARGET không phải trường đầu vào khi chấm điểm.
risk_score là đầu ra ước lượng của model cho lớp TARGET=1. Trong thiết kế đề xuất, điểm cao hơn biểu thị rủi ro ước lượng cao hơn, ngược chiều với scorecard 0–1000 của bài tham khảo. Không gọi là xác suất thực tế đã được xác nhận nếu chưa kiểm tra hiệu chỉnh và phạm vi áp dụng.
recommendation là gợi ý từ policy mô phỏng của nhóm, dựa trên điểm và tình trạng dữ liệu. Nó không phải nhãn thật, cũng không phải quyết định cấp tín dụng thật.
Ví dụ hoàn toàn minh họa: một nhóm có 20 hồ sơ có nhãn, trong đó 3 hồ sơ TARGET=1. Tỷ lệ ghi nhận của nhóm là 3/20; con số này không phải dự đoán riêng cho hồ sơ A. Model có thể trả score 0,27 cho A và policy chuyển thành “Cần xem xét kỹ”; hai giá trị đó không sửa TARGET của A.

# 3. Kiến trúc database đề xuất
## 3.1. Danh sách thành phần
| Schema | Thành phần | Grain | Mức ưu tiên |
| staging | application | Một dòng/hồ sơ nguồn trong bộ dữ liệu MVP cố định | Cốt lõi |
| staging | previous_application | Một dòng/hồ sơ trước trong nguồn | Cốt lõi |
| ops | etl_runs | Một dòng/đợt ETL | Cốt lõi |
| dw | dim_applicant_profile | Một dòng/thông tin mô tả của hồ sơ hiện tại | Cốt lõi |
| dw | dim_contract_type | Một dòng/loại hợp đồng | Cốt lõi |
| dw | fact_application | Một dòng/hồ sơ hiện tại | Cốt lõi |
| mart | application_features_v1 | Một dòng/hồ sơ; SQL view | Cốt lõi |
| mart | application_overview_v1 | Một dòng/hồ sơ; SQL view | Cốt lõi |
| ml | model_runs | Một dòng/model đã train | Cốt lõi |
| ml | assessments | Một dòng/lần chấm hồ sơ | Cốt lõi |
| mart | latest_assessment_v1 | Tối đa một dòng/hồ sơ; SQL view | Cốt lõi |
| dw | fact_previous_application | Một dòng/hồ sơ trước đã chuẩn hóa | Tùy chọn |
| app | credit_decisions | Một dòng/lần người dùng ghi quyết định | Tùy chọn |
MVP sử dụng dữ liệu cố định. Khóa hồ sơ được giữ duy nhất xuyên các đợt chạy lại; chưa lưu nhiều phiên bản DW đồng thời. Nếu sau này cần lịch sử thay đổi dữ liệu, phải thiết kế thêm dataset_version hoặc snapshot, không chỉ thêm etl_run_id rồi coi như đã có versioning.

## 3.2. Quan hệ và đường đi dữ liệu
```text
CSV → staging → làm sạch/tổng hợp → dw → mart → ML/API/Web

ops.etl_runs             1 ─── N staging.application
ops.etl_runs             1 ─── N staging.previous_application
ops.etl_runs             1 ─── N dw.fact_application

dw.dim_applicant_profile 1 ─── 0..1 dw.fact_application
   (ràng buộc UNIQUE trên FK profile của fact trong MVP)
dw.dim_contract_type     1 ─── N dw.fact_application

dw.fact_application     1 ─── N ml.assessments
ml.model_runs           1 ─── N ml.assessments
ml.assessments          1 ─── N app.credit_decisions [tùy chọn]

dw.fact_application     1 ─── N dw.fact_previous_application [tùy chọn]
```
Trong profile, source_application_id duy nhất; ETL phải kiểm tra nó trùng application_id của fact tham chiếu. MVP không tái sử dụng cùng một dòng profile cho nhiều hồ sơ. Đây là lựa chọn đơn giản cho dữ liệu hiện tại, không phải mô hình customer master doanh nghiệp.

# 4. Quy ước chung khi đọc các bảng dưới đây
PK là khóa chính; FK là khóa ngoại; NN nghĩa là bắt buộc có giá trị; NULL là chưa có hoặc không xác định; UNIQUE nghĩa là không trùng. “Có thể thiếu” không đồng nghĩa giá trị bằng 0.
Các kiểu là đề xuất PostgreSQL: BIGINT cho ID, INTEGER cho số đếm, TEXT cho nhãn, BOOLEAN cho cờ, NUMERIC cho giá trị tài chính, DOUBLE PRECISION cho feature liên tục/điểm, TIMESTAMPTZ cho thời điểm hệ thống, JSONB cho nội dung có cấu trúc.
ID tự sinh nội bộ dùng BIGINT GENERATED BY DEFAULT AS IDENTITY. ID ánh xạ nguồn giữ nguyên giá trị số của nguồn, không tự sinh lại. Dùng NUMERIC(20,4) như lựa chọn lưu giá trị tiền nguồn, nhưng phải kiểm tra miền giá trị/độ chính xác trước khi chốt DDL.
Không mặc định đơn vị tiền là VND/USD. Giữ đơn vị và kỳ đo theo dictionary. Ngày ETL, ngày train và ngày chấm là thời gian hệ thống thật, không phải ngày nộp hồ sơ trong dữ liệu nguồn.

# 5. ops.etl_runs – nhật ký đợt nạp dữ liệu
## 5.1. Chức năng và lý do triển khai
Bảng này trả lời: đã nhập bộ file nào, chạy lúc nào, thành công hay chưa, số dòng ở các bước có khớp không? Khi dashboard thiếu hồ sơ, nhóm nhìn vào nhật ký thay vì đoán. Đây là bảng vận hành, không phải fact kinh doanh.
| Trường | Kiểu và ràng buộc | Chức năng và lý do |
| etl_run_id | BIGINT, PK, tự sinh | Mã đợt chạy để liên kết dữ liệu đã nạp và nhật ký |
| started_at | TIMESTAMPTZ, NN | Thời điểm bắt đầu; hỗ trợ xác định lần chạy và thời gian thực thi |
| finished_at | TIMESTAMPTZ, NULL | Chỉ ghi khi kết thúc; NULL khi đang chạy |
| status | TEXT, NN | running/succeeded/failed; không để web hiểu dữ liệu dở dang là hoàn tất |
| source_manifest | JSONB, NN | Lưu tên file, vai trò nguồn, đường dẫn tương đối và checksum nếu tính thực; giúp nhận biết dữ liệu đầu vào |
| row_counts | JSONB, NN | Lưu input, accepted, rejected, output theo từng bảng; không gộp các grain khác nhau thành một tổng mơ hồ |
| error_message | TEXT, NULL | Ghi lỗi tóm tắt khi thất bại; không ghi mật khẩu/chuỗi kết nối |
Mặc định started_at=now(), status=running, row_counts={} phải được khai báo rõ khi hiện thực. Kiểm tra finished_at không trước started_at; trạng thái kết thúc phải có finished_at. Dữ liệu thiếu/không hợp lệ bị loại cần có lý do và thống kê, không loại im lặng.

# 6. staging.application – dữ liệu hồ sơ nhận từ nguồn
## 6.1. Chức năng và grain
Đây là landing table tối thiểu cho các trường nhóm dùng; không tuyên bố lưu đầy đủ mọi cột CSV. File gốc vẫn giữ nguyên ở thư mục dữ liệu, không commit dữ liệu lớn lên Git. Nếu quyết định giữ toàn bộ CSV trong staging, bổ sung theo header thật và dictionary thay vì tự đoán các cột còn lại.
Một dòng tương ứng một SK_ID_CURR trong bộ dữ liệu cố định. Các cột nguồn dùng chữ hoa để dễ đối chiếu; cột metadata dùng chữ thường. Không fit imputer/scaler ở staging. Giá trị không parse được đưa vào luồng reject hoặc báo lỗi, không âm thầm biến thành 0.
| Trường | Kiểu/ràng buộc đề xuất | Chức năng và lý do |
| SK_ID_CURR | BIGINT, PK | Giữ ID hồ sơ nguồn để nối và đối soát |
| TARGET | SMALLINT, NULL, chỉ 0/1 | Giữ nhãn thật; test không có nhãn để NULL, không điền dự đoán |
| NAME_CONTRACT_TYPE | TEXT, NULL | Nguồn cho chiều hợp đồng |
| AMT_INCOME_TOTAL | NUMERIC(20,4), NULL | Giá trị thu nhập nguồn, dùng tạo fact và feature |
| AMT_CREDIT | NUMERIC(20,4), NULL | Giá trị tín dụng, dùng phân tích số tiền và tỷ số |
| AMT_ANNUITY | NUMERIC(20,4), NULL | Giá trị annuity; không tự đổi kỳ đo |
| AMT_GOODS_PRICE | NUMERIC(20,4), NULL | Giá hàng hóa liên quan tới hồ sơ |
| DAYS_BIRTH | INTEGER, NULL | Giữ độ lệch ngày gốc để tái tạo tuổi |
| DAYS_EMPLOYED | INTEGER, NULL | Giữ giá trị gốc kể cả sentinel để đối soát xử lý |
| NAME_INCOME_TYPE | TEXT, NULL | Nguồn cho nhóm thu nhập |
| NAME_EDUCATION_TYPE | TEXT, NULL | Nguồn cho nhóm học vấn |
| OCCUPATION_TYPE | TEXT, NULL | Nguồn cho nghề nghiệp |
| NAME_FAMILY_STATUS | TEXT, NULL | Nguồn cho tình trạng gia đình |
| CNT_CHILDREN | INTEGER, NULL | Số con theo nguồn |
| CNT_FAM_MEMBERS | NUMERIC, NULL | Giữ khả năng kiểu số nguồn; chỉ đổi sang integer sau kiểm tra |
| FLAG_OWN_CAR | TEXT, NULL | Giữ mã Y/N nguồn; chuyển sang boolean tại bước làm sạch |
| FLAG_OWN_REALTY | TEXT, NULL | Giữ mã sở hữu bất động sản nguồn |
| EXT_SOURCE_1 | DOUBLE PRECISION, NULL | Điểm nguồn thứ nhất; không có dữ liệu thì giữ thiếu |
| EXT_SOURCE_2 | DOUBLE PRECISION, NULL | Điểm nguồn thứ hai |
| EXT_SOURCE_3 | DOUBLE PRECISION, NULL | Điểm nguồn thứ ba |
| data_source | TEXT, NN | application_train/application_test; đây là nguồn file, không phải chia train/holdout của nhóm |
| etl_run_id | BIGINT, FK, NN | Đợt nhập gần nhất của dòng trong staging hiện tại |
| source_file | TEXT, NN | Biết dòng được nhận từ file nào |
Staging giữ giá trị gốc có thể đọc được, không cần áp mọi luật nghiệp vụ như “số ngày làm việc hợp lý” tại đây. Tuy vậy ID trùng, schema sai hoặc TARGET ngoài 0/1 phải dừng/reject có ghi nhận. Không coi một file application_test là tập đánh giá có nhãn.

# 7. staging.previous_application – dữ liệu hồ sơ trước
## 7.1. Chức năng và lý do triển khai
Một hồ sơ hiện tại có thể có nhiều hồ sơ trước. Bảng này giữ chi tiết để tính lịch sử mà không làm nhân bản dòng hồ sơ chính. Chỉ lấy các trường phục vụ contract hiện tại.
| Trường | Kiểu/ràng buộc đề xuất | Chức năng và lý do |
| SK_ID_PREV | BIGINT, PK | Xác định một hồ sơ trước, chống đếm trùng |
| SK_ID_CURR | BIGINT, NN | Nối lịch sử về hồ sơ hiện tại; tạo index cho GROUP BY/join |
| NAME_CONTRACT_STATUS | TEXT, NULL | Dùng đếm Approved, Refused và các trạng thái còn lại |
| NAME_CONTRACT_TYPE | TEXT, NULL | Dùng nếu mở phân tích theo loại hợp đồng trước |
| AMT_APPLICATION | NUMERIC(20,4), NULL | Giá trị đề nghị theo nguồn, không nhầm với giá trị tín dụng |
| AMT_CREDIT | NUMERIC(20,4), NULL | Giá trị tín dụng hồ sơ trước |
| DAYS_DECISION | INTEGER, NULL | Độ lệch thời điểm quyết định để kiểm tra điều kiện lịch sử |
| etl_run_id | BIGINT, FK, NN | Truy vết lần nhập |
| source_file | TEXT, NN | Truy vết file nguồn |
Không bắt FK SK_ID_CURR sang staging.application nếu staging cố ý lưu lịch sử cho cả những hồ sơ chưa nhập trong MVP; thay vào đó đếm bản ghi không khớp và chọn cohort rõ ràng. Nếu chỉ nhập lịch sử của cohort hiện tại, có thể thêm FK sau khi kiểm tra. Không ngầm bỏ bản ghi không khớp rồi gọi dữ liệu đầy đủ.
Điều kiện thời gian phải được xác nhận bằng dictionary trước khi tổng hợp. Chỉ dùng các thông tin đã có tại thời điểm cần đánh giá; không dùng thông tin phát sinh sau cutoff. Không chuyển ngày tương đối thành ngày lịch giả.

# 8. dw.dim_applicant_profile – ngữ cảnh người nộp hồ sơ
## 8.1. Chức năng và lý do tách
Người xem dashboard cần nhóm theo học vấn, loại thu nhập, nhóm tuổi. Tách dimension giúp fact tập trung vào số đo; web/SQL dùng một cách hiểu thống nhất của các nhãn. Một dòng profile gắn với một hồ sơ nguồn trong MVP, chưa quản lý lịch sử thay đổi người dùng theo SCD Type 2.
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| applicant_profile_key | BIGINT, PK, tự sinh | Khóa nội bộ để fact tham chiếu |
| source_application_id | BIGINT, UNIQUE, NN | Ánh xạ SK_ID_CURR, hỗ trợ ETL tìm lại profile khi chạy lại |
| age_years | DOUBLE PRECISION, NULL | Tuổi suy ra từ DAYS_BIRTH, thuận tiện xem chi tiết; công thức phải ghi rõ |
| age_band | TEXT, NN | Nhóm tuổi dùng roll-up; Unknown khi tuổi không xác định, biên nhóm do nhóm chốt |
| education_level | TEXT, NN | Nhãn học vấn phục vụ phân nhóm; Unknown cho thiếu, giữ mapping |
| income_type | TEXT, NN | Nhãn nguồn thu nhập, dùng phân tích phân khúc |
| occupation_type | TEXT, NN | Nhãn nghề nghiệp; thiếu không tự gán nghề có thật |
| family_status | TEXT, NN | Tình trạng gia đình, phục vụ mô tả |
| cnt_children | INTEGER, NULL | Số con; NULL khác không có con |
| cnt_family_members | INTEGER, NULL | Số thành viên, chỉ chuyển khi giá trị nguyên hợp lệ |
| flag_own_car | BOOLEAN, NULL | Có/không sở hữu xe; mã lạ hoặc thiếu không biến thành False |
| flag_own_realty | BOOLEAN, NULL | Có/không sở hữu bất động sản; giữ trạng thái chưa biết |
Tuổi có thể tính bằng -DAYS_BIRTH/365.25 sau kiểm tra miền giá trị; đây là cách quy đổi phục vụ bài tập, không phải ngày sinh thật. Các nhóm tuổi phải có ranh giới không chồng lấn. Không đưa giới tính vào bộ predictor mặc định chỉ vì bài tham khảo có cột đó; trường mô tả và feature dự báo là hai quyết định riêng.
Dùng UNIQUE(source_application_id) để không tạo profile mới mỗi lần chạy lại. Do đây là profile cấp hồ sơ, FK của fact cũng UNIQUE. Hai ID nguồn tương ứng phải được kiểm tra trong ETL; nếu muốn DB cưỡng chế hoàn toàn có thể dùng FK ghép, nhưng MVP chưa cần tăng độ phức tạp đó.

# 9. dw.dim_contract_type – chiều loại hợp đồng
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| contract_type_key | BIGINT, PK, tự sinh | Khóa nội bộ cho loại hợp đồng |
| contract_type_name | TEXT, UNIQUE, NN | Nhãn thống nhất để lọc, nhóm và hiển thị |
Bảng nhỏ này phục vụ so sánh giữa các loại hợp đồng, giảm lỗi viết sai nhãn tại các nơi. Chèn một dòng Unknown và ánh xạ giá trị thiếu tới dòng đó. Nếu xuất hiện loại mới hợp lệ thì thêm dòng mới; không tự gộp thành loại đang có. Không cần thêm product/branch/channel giả khi dữ liệu không có.

# 10. dw.fact_application – fact hồ sơ hiện tại
## 10.1. Chức năng và lý do triển khai
Một dòng là một hồ sơ nguồn. Bảng này là nền tảng cho đếm hồ sơ, phân tích số tiền, tỷ lệ nhãn và đọc feature. Điểm model không thuộc bảng này vì model có thể chạy nhiều lần cho một hồ sơ. Giá trị tài chính giữ tên gần nguồn để tránh mơ hồ.
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| application_id | BIGINT, PK, ánh xạ SK_ID_CURR | ID chung cho DW, ML và web, không dùng làm predictor |
| applicant_profile_key | BIGINT, FK, UNIQUE, NN | Gắn đúng profile và duy trì quan hệ cấp hồ sơ |
| contract_type_key | BIGINT, FK, NN | Gắn loại hợp đồng; thiếu dùng dòng Unknown |
| etl_run_id | BIGINT, FK, NN | Lần ETL đã tạo/cập nhật trạng thái hiện tại; không phải khóa version |
| data_source | TEXT, NN, enum nguồn | Phân biệt train/test nguồn và coverage nhãn |
| amt_income_total | NUMERIC(20,4), NULL | Giá trị thu nhập nguồn để mô tả và tạo tỷ số |
| amt_credit | NUMERIC(20,4), NULL | Giá trị tín dụng để tổng hợp trên cohort và so sánh |
| amt_annuity | NUMERIC(20,4), NULL | Annuity nguồn để xem chi tiết và chọn feature |
| amt_goods_price | NUMERIC(20,4), NULL | Giá hàng hóa; thiếu giữ NULL |
| employment_days | INTEGER, NULL | Số ngày làm việc dạng không âm sau làm sạch; sentinel/không hợp lệ để NULL |
| ext_source_1 | DOUBLE PRECISION, NULL | Điểm nguồn đã kiểm tra kiểu |
| ext_source_2 | DOUBLE PRECISION, NULL | Điểm nguồn thứ hai |
| ext_source_3 | DOUBLE PRECISION, NULL | Điểm nguồn thứ ba |
| previous_application_count | INTEGER, NN, >=0 | Số hồ sơ trước đủ điều kiện; không có lịch sử trong nguồn đã nạp thì 0 |
| previous_approved_count | INTEGER, NN, >=0 | Số hồ sơ trước có status Approved |
| previous_refused_count | INTEGER, NN, >=0 | Số hồ sơ trước có status Refused |
| target | SMALLINT, NULL hoặc 0/1 | Nhãn quan sát, dùng thống kê và train riêng; không phải điểm model |
## 10.2. Quy tắc quan trọng
Approved + Refused không nhất thiết bằng tổng hồ sơ trước, vì còn trạng thái khác. Chỉ yêu cầu mỗi số không vượt tổng và tổng hai nhóm không vượt tổng khi mapping hai nhóm loại trừ nhau.
previous_application_count=0 chỉ mang nghĩa không tìm thấy lịch sử đủ điều kiện trong nguồn đã nạp; không kết luận khách hàng không có lịch sử ở mọi nơi. Nếu nguồn previous chưa nạp hoặc ETL hỏng, không được thay toàn bộ bằng 0 rồi coi hợp lệ.
Không gọi SUM(amt_credit) là tổng dư nợ thực tế hay số tiền giải ngân: đây là tổng giá trị tín dụng của các hồ sơ trong cohort, không chứng minh khoản nào đã giải ngân/còn dư nợ.
Không cộng thu nhập theo hồ sơ để tuyên bố tổng thu nhập khách hàng duy nhất. Tỷ số và tỷ lệ là chỉ số không cộng trực tiếp; cần xác định câu hỏi là trung bình tỷ số hồ sơ hay tỷ số từ các tổng.
Tỷ lệ khó khăn thanh toán ghi nhận = số dòng target=1 / số dòng target có nhãn. Hồ sơ target=NULL không nằm trong mẫu số; mẫu số bằng 0 hiển thị “—”, không phải 0%.

# 11. mart.application_features_v1 – giao diện dữ liệu cho ML
## 11.1. Vì sao là view và vì sao cần có?
View là truy vấn SQL có tên. Nó không tự tạo một bản sao dữ liệu hay giữ lịch sử; khi bảng nguồn thay đổi, view đổi theo. MVP dùng view để tránh chép feature logic ở ETL, notebook và backend. Một dòng luôn phải là một application_id.
View chỉ xuất contract feature đã chốt, không có TARGET hoặc khuyến nghị. Khi train, lấy y riêng từ fact bằng application_id. Người làm ML phải chọn predictor bằng allowlist, loại ID khỏi X. Cột data_source và etl_run_id cũng không tự trở thành predictor.
| Trường xuất ra | Cách lấy/tính | Lý do |
| application_id | Từ fact | Nối nhãn và lưu kết quả, không train bằng ID |
| amt_income_total | Từ fact | Feature tài chính nguồn |
| amt_credit | Từ fact | Feature giá trị tín dụng |
| amt_annuity | Từ fact | Feature annuity |
| credit_income_ratio | amt_credit / amt_income_total khi mẫu số >0 và hai giá trị hợp lệ; khác thì NULL | Một công thức dùng chung, không gọi là DTI |
| age_years | Từ profile | Feature tuổi nếu nhóm thống nhất dùng |
| employment_days | Từ fact | Thời gian làm việc đã làm sạch, NULL được pipeline xử lý |
| income_type | Từ profile | Feature phân loại nguồn thu nhập |
| education_level | Từ profile | Feature học vấn |
| contract_type_name | Từ dimension hợp đồng | Feature loại hợp đồng |
| ext_source_1 | Từ fact | Điểm nguồn thứ nhất |
| ext_source_2 | Từ fact | Điểm nguồn thứ hai |
| ext_source_3 | Từ fact | Điểm nguồn thứ ba |
| previous_application_count | Từ fact | Quy mô lịch sử |
| previous_approved_count | Từ fact | Kết quả chấp thuận trước |
| previous_refused_count | Từ fact | Kết quả từ chối trước |
| previous_approval_rate | approved/count nếu count>0, ngược lại NULL | Không có lịch sử không được tự coi là 0% hay 100% |
Phiên bản v1 là tên contract cột/công thức, không bảo đảm dữ liệu bên dưới bất biến. Để train tái lập, xuất một snapshot feature và nhãn cố định, kèm ID phân chia tập, manifest và pipeline đã lưu. Khi chấm, assessments giữ feature_snapshot thực tế.
Không fit imputer, encoder hoặc scaler bằng toàn bộ view trước khi chia train/holdout. Đọc dữ liệu và tạo tỷ số xác định trước không đồng nghĩa được học preprocessing trên holdout. Nếu cần tuning, tách validation từ train; không dùng holdout để chọn ngưỡng rồi báo như đánh giá độc lập.

# 12. mart.application_overview_v1 – giao diện đọc hồ sơ cho web
## 12.1. Chức năng và thành phần
Đề xuất một view ghép fact + profile + contract, không nối trực tiếp toàn bộ assessments. Web có một cửa đọc ổn định, không cần hiểu mỗi bảng nội bộ. View này có thể có target để phục vụ analytics/đối chiếu, nhưng API scoring không nhận target và không trả nhãn trong nhóm input.
| Nhóm trường | Nội dung | Mục đích và giới hạn |
| Định danh | application_id, data_source | Tra cứu và lọc nguồn |
| Mô tả | Toàn bộ trường profile trừ khóa kỹ thuật, contract_type_name | Hiển thị hồ sơ và filter |
| Số đo | Các trường tài chính, employment_days, ext_source_1/2/3 từ fact | Hiển thị dữ liệu đã chuẩn hóa |
| Lịch sử | Ba số đếm previous và tỷ lệ suy ra theo feature view | Tóm tắt lịch sử |
| Nhãn | target | Chỉ dùng analytics/đối chiếu có chủ đích, không đưa vào scoring form |
Các cột tài chính và lịch sử có cùng định nghĩa với fact/feature view; không tạo công thức khác ở frontend. Bản view cuối cùng phải liệt kê cột tường minh, không dùng SELECT * làm contract lâu dài. Một truy vấn web có thể nối thêm latest_assessment_v1 theo application_id mà vẫn giữ một dòng/hồ sơ.

# 13. ml.model_runs – metadata model đã huấn luyện
## 13.1. Vì sao cần bảng này?
Nếu chỉ lưu điểm 0,27 mà không biết model nào tạo ra, nhóm không giải thích được tại sao hôm sau điểm khác. Bảng này không chứa trọng số model; artifact_path trỏ tới pipeline/model trên đĩa. Nó đủ nhỏ để tự làm, không cần hệ thống registry riêng.
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| model_run_id | BIGINT, PK, tự sinh | ID phiên bản model được assessments tham chiếu |
| model_name | TEXT, NN | Tên thuật toán/baseline, không chỉ đặt “model tốt” |
| feature_version | TEXT, NN | Contract feature dùng khi train, ví dụ application_features_v1 |
| trained_at | TIMESTAMPTZ, NN | Thời điểm hoàn tất huấn luyện |
| artifact_path | TEXT, NN | Đường dẫn tương đối pipeline/model đã lưu; không đưa đường dẫn tùy ý từ người dùng vào loader |
| data_snapshot_ref | TEXT, NN | Manifest/snapshot gồm dữ liệu, nhãn, danh sách ID chia tập; để tái tạo |
| split_seed | INTEGER, NULL | Seed khi dùng chia ngẫu nhiên; seed không thay được danh sách ID đã chia |
| evaluation_metrics | JSONB, NN | Metrics, baseline, cohort đánh giá, số mẫu và ngưỡng phân loại đã dùng |
Đề xuất evaluation_metrics có các khóa mô tả cohort, n_evaluated, roc_auc, pr_auc theo định nghĩa nhóm chọn, threshold và confusion_matrix. Chỉ điền từ thực nghiệm thật; không có metric thì NULL/ghi rõ chưa đo, không tự đặt số đẹp. Metadata nên đi kèm phiên bản thư viện trong manifest artifact để tránh load sai môi trường.
Chỉ đăng ký model khi artifact đã được lưu và thử load/chấm thành công. Chạy model không thành công chưa phải một model sẵn sàng sử dụng. Sau khi có assessments tham chiếu, không sửa artifact bên dưới cùng model_run_id; model mới tạo ID mới.

# 14. ml.assessments – từng lần chấm và policy
## 14.1. Chức năng và lý do tách
Đây là thay đổi quan trọng nhất so với bài tham khảo. Một hồ sơ được chấm lại bằng model mới sẽ sinh dòng mới. Nhờ đó điểm cũ không bị mất, dashboard có thể chọn kết quả đang dùng, và quyết định thủ công tham chiếu đúng lần chấm.
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| assessment_id | BIGINT, PK, tự sinh | Định danh duy nhất lần chấm, xử lý trường hợp trùng thời điểm |
| application_id | BIGINT, FK, NN | Hồ sơ được chấm; phải tồn tại trong DW |
| model_run_id | BIGINT, FK, NN | Model đã chọn, kể cả lần chạy thất bại sau khi chọn model |
| assessed_at | TIMESTAMPTZ, NN | Thời điểm ghi kết quả lần chấm |
| status | TEXT, NN | succeeded/failed/not_ready; phân biệt chưa đủ dữ liệu với điểm thấp |
| feature_snapshot | JSONB, NN | Giá trị feature đầu vào trước preprocessing, không có TARGET; để xem lại lần chấm đã dùng gì |
| risk_score | DOUBLE PRECISION, NULL, miền [0,1] | Đầu ra cho lớp TARGET=1; chỉ có khi thành công và hữu hạn |
| risk_band | TEXT, NULL | Nhãn nhóm theo policy; không phải TARGET |
| recommendation | TEXT, NULL | Gợi ý mô phỏng từ policy, không phải quyết định người dùng |
| policy_version | TEXT, NN | Phiên bản logic kiểm tra sẵn sàng, chia nhóm và khuyến nghị |
| reason_codes | JSONB, NN, mặc định [] | Mã lý do policy/data-quality hoặc lỗi; không giả mạo đóng góp model |
Feature snapshot lưu số thiếu bằng JSON null, không lưu NaN/Infinity và không chứa khóa nhãn. Với MVP ít lượt chấm, lưu JSONB là đủ. Nếu sau này chấm hàng triệu lần, cân nhắc snapshot dùng chung thay vì nhân bản; hiện tại không thêm bảng snapshot riêng để tránh quá tải.
Quy tắc ràng buộc: succeeded bắt buộc risk_score, risk_band và recommendation; failed/not_ready bắt buộc risk_score=NULL, risk_band=NULL, recommendation=NULL và có reason_codes giải thích. Thiếu model/chưa chọn được model thì API trả not_ready, không ép ghi một model_run_id giả vào bảng.
Ví dụ lý do “SCORE_ABOVE_REVIEW_THRESHOLD” là giải thích policy. “INCOME_IS_TOP_CAUSE” chỉ được dùng nếu có phương pháp giải thích model thực sự tạo ra kết quả; không suy đoán từ giá trị đầu vào.
Policy nên có ít trạng thái hỗ trợ xem xét, do nhóm thống nhất trước demo. Ngưỡng là minh họa học thuật hoặc chọn từ train/validation với cách làm công khai, không phải chính sách ngân hàng thật. Không lấy ngưỡng scorecard 750/600/450 áp trực tiếp lên score ML [0,1].

# 15. mart.latest_assessment_v1 – kết quả mới nhất không đếm trùng
Một dòng tối đa cho mỗi application_id. View lọc status=succeeded, sắp assessed_at giảm dần và assessment_id giảm dần, lấy dòng đầu. Các trường xuất: application_id, assessment_id, model_run_id, assessed_at, risk_score, risk_band, recommendation, policy_version, reason_codes.
Nếu chưa có kết quả thành công, view không có dòng cho hồ sơ đó; web LEFT JOIN để vẫn giữ hồ sơ và hiển thị “Chưa có kết quả”. Lần chấm thất bại mới hơn không tự biến score cũ thành kết quả vừa chạy thành công; màn hình phải ghi thời điểm/model của score cũ và báo lỗi của lần yêu cầu hiện tại riêng.
View này có thể trộn model giữa các hồ sơ nếu mỗi hồ sơ được chấm gần nhất bằng model khác nhau. Với biểu đồ so sánh điểm, phải lọc một model_run_id cố định và lấy kết quả mới nhất trong model đó, hoặc hiển thị rõ phân nhóm theo model. Không gộp điểm khác model thành một KPI mơ hồ.
Index đề xuất trên assessments: (application_id, assessed_at DESC, assessment_id DESC) WHERE status='succeeded'. Chỉ thêm index theo model nếu truy vấn thực tế cần. View không bảo đảm hiệu năng nếu không kiểm tra kế hoạch truy vấn.

# 16. Hai bảng tùy chọn: chỉ thêm khi có chức năng
## 16.1. dw.fact_previous_application
Một dòng/hồ sơ trước đã chuẩn hóa. Staging giữ dữ liệu nhận vào; fact này chỉ cần khi muốn drill-down hoặc phân tích lịch sử bằng SQL trên dữ liệu sạch, không chỉ tính vài số đếm cho ML.
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| previous_application_id | BIGINT, PK, ánh xạ SK_ID_PREV | Không đếm trùng một hồ sơ trước |
| application_id | BIGINT, FK, NN | Nối về hồ sơ hiện tại trong cohort DW |
| contract_status | TEXT, NN | Trạng thái đã chuẩn hóa, Unknown nếu thiếu |
| contract_type | TEXT, NN | Loại hợp đồng trước; MVP tùy chọn giữ nhãn để đơn giản |
| amt_application | NUMERIC(20,4), NULL | Giá trị đề nghị theo nguồn |
| amt_credit | NUMERIC(20,4), NULL | Giá trị tín dụng theo nguồn |
| days_decision | INTEGER, NULL | Độ lệch ngày, không phải ngày lịch |
| etl_run_id | BIGINT, FK, NN | Truy vết lần nạp |
Lợi ích: khi thấy previous_refused_count, người dùng truy ra các hồ sơ chi tiết. Chi phí: thêm bảng sạch, kiểm tra và UI nếu hiển thị. Không cộng amt_credit của fact hiện tại với fact trước rồi gọi là cùng một chỉ tiêu. Không nối trực tiếp hai fact để cộng số tiền hồ sơ hiện tại mà chưa xử lý grain.

## 16.2. app.credit_decisions
Một dòng/lần người dùng ghi quyết định mô phỏng. Không sửa TARGET và không sửa recommendation của model. Nếu chỉ demo xem điểm và gợi ý thì chưa cần bảng này.
| Trường | Kiểu/ràng buộc | Chức năng và lý do |
| decision_id | BIGINT, PK, tự sinh | Mã lần ghi quyết định, cho phép lưu lịch sử |
| assessment_id | BIGINT, FK, NN | Biết người dùng đã xem đúng kết quả nào trước khi quyết định |
| reviewer_name | TEXT, NN | Tên hiển thị người xem xét trong demo; không coi là xác thực danh tính |
| decision | TEXT, NN | Giá trị enum mô phỏng do nhóm chốt, ví dụ approve/review/decline |
| notes | TEXT, NULL | Ghi lý do/ghi chú; yêu cầu khi khác gợi ý tương ứng nếu có mapping rõ |
| decided_at | TIMESTAMPTZ, NN | Thời điểm ghi nhận |
Không lặp application_id trong bảng này vì có thể suy ra qua assessment_id; tránh hai khóa chỉ về hai hồ sơ khác nhau. Chỉ chấp nhận assessment thành công và đủ điều kiện theo policy; kiểm tra tại API/transaction vì FK đơn thuần không kiểm tra status của dòng tham chiếu. Tên reviewer tự nhập không phải audit trail bảo mật cho sản phẩm ngân hàng thật.

# 17. Luồng thực hiện đầu-cuối bằng một ví dụ
Ví dụ sau chỉ minh họa cấu trúc, không phải kết quả đã chạy trên Home Credit.
Bước 1: ETL tạo một dòng running trong ops.etl_runs và ghi danh sách file. Nạp hồ sơ A vào staging.application; nạp các hồ sơ trước A1, A2, A3 vào staging.previous_application.
Bước 2: Chuẩn hóa nhãn mô tả, tạo profile và loại hợp đồng. Lọc lịch sử đúng cutoff đã xác minh, đếm ba hồ sơ trước: một Approved, một Refused, một trạng thái khác. Lưu fact_application một dòng/A với count=3, approved=1, refused=1. Tỷ lệ approved sử dụng mẫu số tổng hồ sơ trước theo contract đã chọn, không tự loại trạng thái khác mà không đổi tên định nghĩa.
Bước 3: Feature view tạo một dòng/A. Bộ train lấy X từ view và y riêng, chia tập theo ID; fit pipeline trên train; đánh giá holdout đúng quy trình. Lưu pipeline và manifest, đăng ký model_runs sau khi thử load thành công.
Bước 4: Khi người dùng yêu cầu chấm A, backend đọc feature, kiểm tra sẵn sàng và gọi pipeline đã lưu. Lưu assessments với feature_snapshot, model_run_id, score và policy. Không train tại bước này và không truyền TARGET vào model.
Bước 5: Dashboard đọc overview LEFT JOIN kết quả thành công đã chọn. Chấm lại bằng model khác sinh assessments mới, không thêm dòng fact_application. Nếu có form quyết định, credit_decisions liên kết đúng assessment_id đã hiển thị.
Bước 6: Đợt ETL chỉ chuyển succeeded khi load và kiểm tra hoàn tất. Khi có lỗi, không phát hành một DW nửa cũ nửa mới cho dashboard.

# 18. Triển khai ETL và vòng đời dữ liệu an toàn
## 18.1. Thứ tự nạp
1) Xác minh header/dictionary/file và cohort; tạo nhật ký ETL. 2) Nạp staging với kiểm tra ID trùng và parse. 3) Tổng hợp previous về SK_ID_CURR. 4) Nạp dimension hợp đồng và profile. 5) Nạp/upsert fact theo application_id. 6) Đối soát và commit/phát hành. 7) Hoàn tất nhật ký và cho phép web đọc cohort đã sẵn sàng.
Giữ khóa surrogate ổn định bằng UNIQUE và upsert có kiểm soát; không tái tạo dimension bằng TRUNCATE khiến FK cũ sai. Không chạy song song hai ETL trên cùng bộ bảng MVP; dùng một điều phối hoặc khóa đơn giản. Không chỉ thấy bảng có một dòng rồi kết luận cả lần ETL trước hoàn tất.

## 18.2. Khi chạy lại hoặc đổi dữ liệu
Chạy lại cùng bộ dữ liệu không được thêm bản sao hồ sơ. Upsert dựa trên khóa nguồn; số dòng/kết quả tổng hợp phải khớp. Chạy lại không tự xóa assessments/model metadata.
Nếu thay dataset/công thức làm sạch, không ghi đè âm thầm trong khi vẫn trình bày score cũ như vừa chấm trên dữ liệu mới. Feature_snapshot giữ đầu vào cũ, nhưng dashboard phải ghi rõ score chấm lúc nào; lựa chọn đơn giản nhất cho MVP là khóa bộ dữ liệu cố định sau khi chốt train/demo. Nếu reset DW, phải export/lưu metadata cần giữ và reset các bảng phụ thuộc có chủ đích; không mặc định ON DELETE CASCADE để xóa lịch sử.
Database đề xuất chưa giải quyết version lịch sử doanh nghiệp, CDC hoặc incremental loading phức tạp. Đây là giới hạn có chủ ý, không phải thiếu sót cần thêm trước khi MVP chạy.

# 19. Ràng buộc, index và chất lượng dữ liệu
| Kiểm tra | Mục đích | Ví dụ tiêu chí đạt |
| Khóa nguồn duy nhất | Không đếm trùng hồ sơ | application_id và SK_ID_PREV không trùng trong cohort |
| FK đúng | Không có bản ghi mồ côi | Mọi fact có profile/contract; assessment có application/model |
| Một dòng feature/hồ sơ | Ngăn nhân bản từ join | COUNT(*)=COUNT(DISTINCT application_id) trong feature view |
| Đối soát cohort | Biết hồ sơ nào được giữ/loại | Accepted + rejected giải thích được input; ID nguồn và DW khớp cohort |
| Số đếm lịch sử | Không nhầm các trạng thái | approved/refused không âm, không vượt tổng |
| Kiểm tra NULL | Không biến không biết thành an toàn | Thu nhập thiếu vẫn thiếu, không lịch sử thì tỷ lệ NULL |
| Nhãn | Không nhiễm đầu vào ML | TARGET chỉ 0/1/NULL và không có trong X/snapshot predictor |
| Điểm | Không trả kết quả giả | Succeeded có score hữu hạn [0,1]; failed/not_ready không có score |
| Snapshot | Xem lại được đầu vào | JSON hợp lệ, không TARGET, không NaN/Infinity |
| Coverage dashboard | Mẫu số đúng | Tách có nhãn/không nhãn, đã chấm/chưa chấm |
PK/UNIQUE đã cung cấp index phục vụ tra cứu khóa trong PostgreSQL; không tạo index lặp lại cùng cột. FK phía nhiều có thể cần index riêng: fact.contract_type_key, staging.previous_application.SK_ID_CURR, assessments.model_run_id theo nhu cầu. Không mặc định index mọi cột ít giá trị như target/risk_band sẽ làm truy vấn nhanh; đo trên truy vấn thật trước.
Các kiểm tra chéo bảng, mapping trạng thái và điều kiện cutoff thường cần SQL test/ETL/API ngoài CHECK constraint. Không tuyên bố FK giải quyết được mọi quy tắc nghiệp vụ.

# 20. Hợp đồng DW – ML – Web và quyền sở hữu
| Thành viên | Sở hữu | Bàn giao | Điều kiện nghiệm thu |
| A: DW/ETL | staging, ops, dw, view feature/overview, SQL OLAP | DDL/migration, ETL, data dictionary mapping, SQL test | Chạy lại không trùng, đối soát ID/số đo, view đúng grain |
| B: ML/DSS | Pipeline, split, artifact, model_runs, assessments, policy | Hàm score có schema đầu vào/đầu ra, báo cáo holdout | Không leakage, load artifact được, score không phụ thuộc TARGET |
| C: Web/tích hợp | Một ứng dụng FastAPI, React, truy vấn đọc và ghi | Hai màn hình, API validation, integration test | Không tự tính feature khác A; một hồ sơ không bị đếm nhiều lần |
C là đầu mối tích hợp API và transaction ghi assessments; B cung cấp logic ML/policy và cùng review mapping. A/B bàn giao SQL và hàm xử lý để C không phải viết lại toàn bộ backend. Mọi thay đổi contract feature hoặc tên cột phải được ba người thống nhất trước khi merge.
Hợp đồng tối thiểu gồm application_id, danh sách feature, kiểu/null/đơn vị, quy tắc thiếu và schema response. Response thành công tối thiểu có assessment_id, application_id, model_run_id, status, risk_score, risk_band, recommendation, policy_version. Response lỗi có status và mã lý do, không bịa score.
Form chấm theo ID chỉ cần application_id. Nếu sau này thêm what-if, không ghi đè fact nguồn: ghi nhận scenario riêng hoặc đánh dấu rõ đầu vào giả định. MVP hiện tại chưa có bảng scenario, nên what-if là tùy chọn ngoài cam kết schema này.

# 21. OLAP và nghiệm thu ở mức bài tập lớn
MVP vẫn phải chứng minh vai trò DW, không biến thành notebook ML có web. Đề xuất slice theo loại hợp đồng; dice theo loại thu nhập và học vấn; roll-up tuổi chính xác thành age_band; drill-down từ nhóm hồ sơ tới hồ sơ cụ thể. Nhóm nên đối chiếu rubric môn học để xác nhận cách trình diễn OLAP này, không tự tuyên bố đủ mọi yêu cầu của đề khi chưa kiểm lại đề.
Không tạo dim_date bằng ngày lịch giả cho hồ sơ. Ngày train/chấm cho phép phân tích hoạt động hệ thống, không chứng minh xu hướng tín dụng theo tháng phát sinh nghiệp vụ. Nếu bắt buộc phân tích thời gian kinh doanh, phải bổ sung nguồn có ngày thật hoặc thống nhất giới hạn với giảng viên.
Checklist nghiệm thu: dữ liệu nguồn → staging → DW chạy thật; khóa và grain đúng; SQL/dashboard có mẫu số rõ; feature contract không có nhãn; baseline và model có đánh giá giữ riêng; mở dashboard không train; chấm thành công lưu được assessment rồi đọc lại đúng ID; chấm thất bại không có score giả; lần chấm mới không làm tăng số hồ sơ.
Tài liệu này không thay cho DDL đã kiểm thử hoặc kết quả thực nghiệm. “Đề xuất hoàn tất” không có nghĩa “ETL/model/database đã chạy”.

# 22. Quyết định nhóm cần chốt trước khi code
1. Chỉ dùng application_train + previous hay thêm application_test ngay từ đầu? 2. Bộ feature v1 chính thức và định nghĩa đơn vị/cutoff. 3. Mẫu số previous_approval_rate có dùng mọi trạng thái đủ điều kiện hay một tập con được định nghĩa khác? 4. Nhóm tuổi, mapping Unknown và xử lý sentinel. 5. Chọn model/phiên bản policy nào để dashboard thống nhất. 6. Có cần bảng chi tiết previous hoặc form quyết định thủ công không?
Mặc định khuyến nghị: hoàn thành các thành phần cốt lõi, chưa làm hai bảng tùy chọn; giữ bộ dữ liệu cố định; Logistic Regression và baseline; một API, hai màn hình; không thêm monitoring page, registry riêng, streaming hoặc SCD Type 2 khi chưa có nhu cầu.

# 23. Tóm tắt lý do của thiết kế
Staging để giữ dấu vết nguồn; dimension để nhóm và mô tả; fact để không thay đổi ý nghĩa một dòng; feature view để người làm DW và ML dùng một công thức; model_runs để biết model nào tạo ra điểm; assessments để lưu nhiều lần chấm và đúng đầu vào; latest view để không đếm trùng; etl_runs để biết dữ liệu đã nạp đủ hay chưa. Các bảng tùy chọn chỉ được thêm khi người dùng thực sự cần drill-down hoặc ghi quyết định.
Giá trị của thiết kế không nằm ở nhiều bảng. Nó nằm ở việc ba thành viên trả lời nhất quán: dữ liệu này đến từ đâu, một dòng nghĩa là gì, điểm này được tạo bằng gì và dashboard đang đếm cái gì.

# Phụ lục A. Vị trí tham chiếu trong báo cáo mẫu
| Nội dung tham khảo | Vị trí trong báo cáo | Cách sử dụng trong tài liệu này |
| Tổng hợp lịch sử trước khi ghép | Mục 3.3.2, trang in 13–14 | Học luồng tích hợp, không nối nhiều lịch sử trực tiếp vào fact |
| Scorecard bằng luật | Mục 3.3.3, trang in 15–16 | Phân biệt cách họ làm với ML đề xuất |
| Sơ đồ tên bảng/trường | Hình 3.2, trang in 18, PDF 19 | Đối chiếu bảng gốc; DDL đề xuất không phải DDL sao chép |
| Ghi quyết định người xem xét | Mục 4.2.2, trang in 29–30 | Là cơ sở chức năng cho bảng credit_decisions tùy chọn |
| Chỉ báo không phải xác suất hiệu chỉnh | Mục 5.3, trang in 37 | Không sao chép phép đổi scorecard thành xác suất |
| Không có ngày lịch nộp hồ sơ | Mục 5.3, trang in 37 | Không dựng chiều thời gian nghiệp vụ giả |
Tài liệu được biên soạn từ nội dung trao đổi và PDF người dùng cung cấp. Không có kết quả benchmark, số liệu model hay trạng thái database triển khai nào được khẳng định trong bản đề xuất này.
