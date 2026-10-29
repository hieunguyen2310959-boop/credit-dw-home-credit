# Kết quả kiểm chứng trước khi push

Môi trường thực thi: Windows, Python 3.13.0, PostgreSQL 16.15 native, psycopg 3.3.6; không Docker. PostgreSQL verification cluster được tách biệt, không sửa database có sẵn của người dùng.

## Kiểm thử

```text
python -m pytest tests -q
22 passed
```

Bộ test đã chạy thật, không dùng SQLite thay PostgreSQL. Bao gồm:
- Khởi tạo đủ 8 bảng/3 view, chạy lại bootstrap an toàn.
- ETL idempotent, surrogate keys ổn định, số hồ sơ/tiền không nhân.
- History cutoff, orphan, sentinel, null/unknown.
- Test không có nhãn không bị coi là TARGET=0.
- Duplicate/rollback và failure log; thay dataset bị từ chối.
- JSON snapshot không label, không NaN/Infinity; FK và score/status constraints.
- Latest success có tie-break ID; lỗi mới hơn không trả score giả.
- Giữ assessment khi rerun; model metadata đã dùng không sửa được.

## Smoke test CLI trên database rỗng khác với DB test

```text
init-db -> Core schema and views initialized (no data deleted).
demo -> etl_run_id: 1, applications: 3, labeled: 3, target_1: 1, total_credit: 1000.0000
demo -> etl_run_id: 2, applications: 3, labeled: 3, target_1: 1, total_credit: 1000.0000
check -> applications: 3, labeled: 3, target_1: 1, total_credit: 1000.0000
```

Tất cả số liệu trên thuộc fixture **SYNTHETIC**, không phải kết quả Home Credit. Không có model train/inference hoặc AUC được công bố.

## SQL và trạng thái CI

Đã thực thi đủ 5 truy vấn trong `sql/004_analytics.sql` trên database demo: lần lượt trả 1, 6, 3, 2 và 0 dòng. Truy vấn cuối latest theo model trả 0 vì database demo không có model/assessment giả (cả hai bảng đều 0 dòng).

Sau push, GitHub Actions có hai run `40794292935` (push) và `40794400870` (workflow_dispatch), đều `startup_failure`, không có job và không có log để đọc. Chưa xác định được nguyên nhân từ API, không khẳng định do billing hay code. Vì vậy **CI chưa được xác nhận**, chỉ bộ kiểm thử PostgreSQL local và CLI/SQL smoke test đã đạt. Không tự thay đổi quyền riêng tư repo hoặc cấu hình thanh toán để xử lý.
