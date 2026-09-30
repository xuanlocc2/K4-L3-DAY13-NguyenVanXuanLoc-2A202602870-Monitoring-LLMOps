# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Văn Xuân Lộc
- **MSSV:** 2A202602870
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/xuanlocc2/K4-L3-DAY13-NguyenVanXuanLoc-2A202602870-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602870`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (21 record, 20 thiếu trường, 0 correlation ID) | 100/100: 95 record, 38 correlation ID, 0 PII leak, 0 thiếu trường | Đủ 4 tiêu chí: schema, correlation ID, enrichment, PII |
| `validate_dashboard.py` | HỢP LỆ 6/6 (contract, chưa có dashboard thật) | HỢP LỆ 6/6 panel | `scripts/dashboard.py` khớp `config/dashboard.yaml` |
| `pytest` | 22 passed | 26 passed | Thêm test PII cho CCCD, thẻ, passport, chuỗi sạch |
| Số traces hợp lệ | 0 | ≥ 13 trace `prompt_source=langfuse` (12 baseline v1, 1 candidate v2) | Mỗi trace có 3 observation: agent, retrieval, generation |
| Số PII leak | 0 (validator; load test mẫu không chứa PII, `scrub_event` chưa bật) | 0 | Scrub chạy trước bước ghi file |
| Latency P95 / TTFT P95 | 151 ms / 50 ms (10 response) | 1387 ms / 51 ms (38 response) | Dưới SLO 3000 ms; P95 bị kéo lên bởi 1 request 4241 ms lúc server lấy prompt lần đầu |
| Retrieval success rate | 100% | 100% | Trên mọi event có `tool_success` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware (`app/middleware.py`) xóa contextvars, đọc header `x-request-id`; nếu khớp regex `^req-[0-9a-f]{8}$` thì dùng, không thì sinh `req-<8 hex>`. ID được bind vào structlog contextvars nên mọi log line của request đều mang nó, lưu vào `request.state`, truyền vào agent/trace, và trả lại qua header `x-request-id`.
- **Các metadata được ghi vào structured log:** `service`, `event`, `ts` (UTC), `level`, `correlation_id`, `env`, `model`, `feature`, `session_id`, `user_id_hash` (hash, không ghi user_id thô). Event `response_sent` thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` trong `app/logging_config.py` được đặt trước `JsonlFileProcessor` (bước ghi file), nên dữ liệu đã che mới xuống đĩa. Rule trong `app/pii.py` gồm email, điện thoại VN, CCCD, thẻ thanh toán và passport VN.
- **Cách kiểm chứng kết quả:** `pytest` (26 test, gồm các định dạng phone/thẻ), `validate_logs.py` (100/100, 0 PII leak, dùng detector độc lập) và ảnh `05-pii-redaction.png`: gửi email, số điện thoại, CCCD, thẻ giả rồi kiểm tra dòng log có `[REDACTED_*]`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Key Langfuse của chính tôi nằm trong `.env` (không commit); trace mang `correlation_id` trùng với log cục bộ và tôi đọc lại được bằng API `v2/observations` với key đó.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` (agent) chứa `retrieval` (retriever) và `llm-generation` (generation, có model, `usage_details` và `cost_details`).
- **Cách nối trace với log:** `correlation_id` được ghi vào metadata của trace và có trong mọi dòng log; lấy ID từ log rồi tìm trong Langfuse Search.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** v1 / `baseline`
- **Version/label candidate:** v2 / `candidate`
- **Trace ID của mỗi version:** v1: `fae3e5626a4cf9201702e23c07425a6b` (`req-b36ab629`); v2: `06f2addcd850d19657e4304b315d2d00` (`req-3bbf6148`)
- **Cách promote và rollback `production`:** Trên Langfuse, gán label `production` cho v2 (promote) rồi gán lại cho v1 (rollback); không cần sửa code. App cache prompt khoảng 60 giây nên cần restart API để nhận label mới. Ảnh: `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `scripts/dashboard.py` (Streamlit, venv riêng) đọc `data/logs.jsonl`, tự refresh, có đường threshold đỏ. Sáu panel: latency (P50/P95/P99 + TTFT), traffic, errors + retrieval success, cost, tokens, quality. Ảnh: `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** 99.5% request có latency ≤ 3000 ms. Baseline P95 ≈ 150 ms nên có đệm, và kịch bản `rag_slow` (≈2.65 s) vẫn chưa vi phạm SLO nhưng đã vượt ngưỡng cảnh báo 2000 ms.
- **Cách tính error budget:** SLO 99.5% nghĩa là budget 0.5%. Với 10,000 request, tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms; trong 28 ngày tương đương khoảng 201 phút.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (P95 > 2000 ms, 5 phút, warning), `HighErrorRateOrRetrievalFailure` (error rate > 2% hoặc retrieval success < 90%, 5 phút, critical), `CostPerRequestSpike` (cost/request > 0.005 USD, 10 phút, warning). Cả ba gửi Slack `#k4-l3b-alerts`, owner `student-2A202602870`, runbook trong `docs/alerts.md` theo luồng Metrics → Logs → Traces.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
