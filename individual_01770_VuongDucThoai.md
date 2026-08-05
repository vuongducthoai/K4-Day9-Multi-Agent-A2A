# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Vương Đức Thoại |
| MSSV | 2A202601770 |
| Khóa/Lớp | K4 |
| Vai trò chính | Thiết kế và triển khai pipeline điều tra khiếu nại e-commerce theo kiến trúc multi-agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Tầng truy xuất dữ liệu | `src/data_repository.py`, `DataRepository.get_order_bundle` | `claimed_order_id`, các CSV Olist | `OrderBundle` gồm order, customer, item, payment, product, seller và lịch sử đơn | Hoàn thành triển khai |
| Domain agents | `src/agents.py`, `CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent` | `OrderBundle` | Bốn handoff có cấu trúc | Hoàn thành triển khai |
| Quy tắc và điều phối | `src/policy.py`, `src/runner.py` | Handoff từ các agent | `PolicyDecision` và JSON output theo từng case | Hoàn thành triển khai; chờ kiểm thử toàn bộ input |
| Kiểm chứng và audit | `src/verifier.py`, `src/audit.py` | Output trước khi ghi | Kiểm tra schema/evidence/limit, `trace.jsonl`, `metadata.json` | Hoàn thành triển khai; chờ kiểm thử toàn bộ input |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thiết kế tài liệu kiến trúc | Toàn bộ pipeline | Tạo `architecture.md` mô tả vai trò, quyền truy cập và luồng handoff |
| Chuẩn hóa evidence | Policy, Coordinator và Verifier | Thống nhất định dạng `order:`, `item:`, `payment:`, `seller:` và `policy:` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Truy vấn một order và các bảng liên quan | `src/data_repository.py` | `OrderBundle` có dữ liệu nguồn cần thiết cho điều tra | `DataRepository().get_order_bundle(order_id)` |
| Tính đối soát payment và delivery variance | `src/agents.py` | `PaymentHandoff`, `DeliveryHandoff` với tổng tiền, chênh lệch và số giờ | In kết quả các agent trên một `order_id` mẫu |
| Áp dụng chính sách theo thứ tự ưu tiên | `src/policy.py` | Primary/secondary issue, root cause, refund và actions | `PolicyAgent().analyze(...)` |
| Sinh và kiểm tra output | `src/runner.py`, `src/verifier.py` | Một JSON theo schema cho mỗi input hợp lệ | `python -m src.runner` |

Artifact cụ thể của phần việc là pipeline tạo `output/EC_xxx.json` từ `input/EC_xxx.json`, đồng thời ghi các handoff và quyết định vào `logging/trace.jsonl`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mỗi khiếu nại chỉ cung cấp `claimed_order_id`, trong khi kết luận cần đối chiếu nhiều bảng Olist. Pipeline phải xác định đúng trạng thái order, các item/seller, payment, lịch sử khách hàng và thời gian giao hàng; sau đó áp dụng `EC_POLICY_V2` theo thứ tự ưu tiên và tạo JSON không chứa bằng chứng suy diễn.

### Cách triển khai

`DataRepository` đọc các CSV cần thiết một lần, parse timestamp và lấy dữ liệu theo `order_id`. Lịch sử khách hàng dùng `customer_unique_id`, không dùng `customer_id` vì mỗi `customer_id` chỉ đại diện cho một order.

Bốn domain agent nhận cùng `OrderBundle` nhưng trả các handoff độc lập: Customer Agent tìm order liên quan; Order & Product Agent tổng hợp item/seller/product/category; Payment Agent tính `expected_total_brl`, `difference_brl` và `reconciled`; Delivery Agent tính delivery variance và seller handoff variance theo `shipping_limit_date` sớm nhất của từng seller.

Policy Agent dùng các handoff để xét rule theo đúng ưu tiên canceled, unavailable, seller delay, logistics delay, valid split payment và unsupported late claim. Coordinator chuyển kết quả sang schema đầu ra. Verifier kiểm tra key bắt buộc, timestamp, confidence, giới hạn mảng, evidence format và giá trị NaN/Infinity trước khi ghi file.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `input/EC_xxx.json`, trong đó có `case_id`, `customer_request.claimed_order_id` và `policy_version = EC_POLICY_V2` |
| Output | `output/EC_xxx.json` theo schema đề bài; tên file trùng tên input |
| Module phụ thuộc | `data/` CSV Olist, `src/data_repository.py`, `src/models.py` |
| Module sử dụng output | `src/runner.py`, `src/verifier.py`, `logging/trace.jsonl` |
| Điều kiện lỗi cần xử lý | Không tìm thấy order, policy version sai, order không thỏa rule, evidence sai định dạng, timestamp không hợp lệ hoặc vượt giới hạn output |

### Cách xác minh

```powershell
python -m src.runner
```

- **Kết quả mong đợi:** Mỗi input hợp lệ sinh một output cùng tên; output qua verifier và trace có event cho từng handoff.
- **Kết quả thực tế:** Cần xác nhận ở bước chạy toàn bộ 50 case trước khi nộp.
- **Artifact/log:** `output/`, `logging/trace.jsonl`, `logging/metadata.json`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn cách phân loại dispute và tính hoàn tiền từ nhiều bảng dữ liệu.
- **Các phương án đã cân nhắc:** (1) đưa toàn bộ CSV và case vào một prompt LLM; (2) dùng code deterministic để join/tính toán/policy, chia thành các agent có handoff rõ ràng.
- **Phương án đã chọn:** Phương án (2).
- **Lý do:** Các điều kiện `EC_POLICY_V2`, phép tính tiền và evidence ID đều xác định được từ CSV. Code deterministic tái lập được kết quả, giữ đúng thứ tự ưu tiên và tránh LLM suy diễn tracking/refund không tồn tại trong Olist.
- **Bằng chứng quyết định phù hợp:** Các công thức payment reconciliation, delivery variance, evidence format và kiểm tra schema được biểu diễn trực tiếp trong `agents.py`, `policy.py` và `verifier.py`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Mẫu báo cáo ban đầu hỏi về “Crossref”, “vector index” và “retrieval”, không thuộc bài lab Multi-Agent E-commerce Dispute Resolution.
- **Lệnh hoặc bước tái hiện:** Mở file mẫu `individual_01770_VuongDucThoai.md` trong root repository.
- **Nguyên nhân gốc:** Mẫu báo cáo được tái sử dụng từ một lab retrieval khác.
- **Cách xử lý:** Thay phần end-to-end bằng các câu hỏi và câu trả lời về luồng `input → repository → agents → policy → verifier → output` của bài hiện tại.
- **Cách xác minh sau khi sửa:** Đọc lại mục 7 và đối chiếu với `architecture.md` cùng các module trong `src/`.
- **Điều học được:** Báo cáo kỹ thuật phải bám sát artifact và pipeline thực tế; không nên giữ nguyên thuật ngữ của một bài lab khác.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi qua pipeline như thế nào?** `runner.py` đọc một file input, Coordinator lấy `claimed_order_id`, DataRepository truy vấn các CSV và tạo `OrderBundle`. Các domain agent tạo handoff, Policy Agent ra quyết định, Coordinator dựng JSON và Verifier kiểm tra trước khi ghi output.
2. **Bài này đánh giá chất lượng thế nào?** Không có evaluation set hoặc ground-truth document IDs được cung cấp trong repo. Chất lượng kỹ thuật được kiểm tra nội bộ bằng schema, evidence, phép tính và output limit; điểm cuối do hệ thống chấm so sánh 50 output với đáp án của đề.
3. **Quality check khác freshness monitoring ra sao?** Quality check kiểm tra correctness của output hiện tại: schema, timestamp, ID, evidence, NaN và giới hạn mảng. Freshness monitoring theo dõi dữ liệu có mới hay không; bài này dùng CSV tĩnh nên không cần cơ chế freshness.
4. **Vì sao phải dùng cùng 50 input khi chạy lại?** Cùng input giữ phép so sánh tái lập được giữa các lần sửa code, giúp xác định thay đổi policy hoặc verifier có làm thay đổi kết quả hay không.
5. **Khi nào pipeline được xem là hoàn thành?** Khi chạy được toàn bộ 50 case, có đúng 50 JSON output cùng tên input, mọi file qua verifier, trace phản ánh lượt chạy mới nhất, metadata có runtime/model trung thực và output zip chỉ chứa các JSON cần nộp.

## 8. Cam kết của thành viên

Trước khi nộp, tôi sẽ tự kiểm tra và đánh dấu các mục sau:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Vương Đức Thoại  
**Ngày xác nhận:** 2026-08-05
