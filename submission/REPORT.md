# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Văn Xuân Lộc
- **MSSV:** 2A202602870
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/xuanlocc2/K4-L3-DAY13-NguyenVanXuanLoc-2A202602870-Monitoring-LLMOps
- **Commit SHA cuối:** `cc95997c2ad40e3f90997fdf0796d9f0f735015f` (commit chứa toàn bộ code và evidence; commit sau đó chỉ ghi SHA này vào báo cáo)
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602870`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (21 record, 20 thiếu trường, 0 correlation ID) | 100/100: 107 record, 44 correlation ID, 0 PII leak, 0 thiếu trường | Đủ 4 tiêu chí: schema, correlation ID, enrichment, PII |
| `validate_dashboard.py` | HỢP LỆ 6/6 (contract, chưa có dashboard thật) | HỢP LỆ 6/6 panel | `scripts/dashboard.py` khớp `config/dashboard.yaml` |
| `pytest` | 22 passed | 26 passed (chạy với `--basetemp` vì thư mục temp mặc định của Windows bị từ chối quyền) | Thêm test PII cho CCCD, thẻ, passport, chuỗi sạch |
| Số traces hợp lệ | 0 | ≥ 13 trace `prompt_source=langfuse` (12 baseline v1, 1 candidate v2) | Mỗi trace có 3 observation: agent, retrieval, generation |
| Số PII leak | 0 (validator; load test mẫu không chứa PII, `scrub_event` chưa bật) | 0 | Scrub chạy trước bước ghi file |
| Latency P95 / TTFT P95 | 151 ms / 50 ms (10 response) | 2652 ms / 51 ms (43 response, gồm 5 request incident); trước incident 1387 ms / 51 ms (38 response) | Dưới SLO 3000 ms nhưng vượt ngưỡng cảnh báo 2000 ms trong incident `rag_slow`. P95 trước incident bị kéo lên bởi 1 request 4241 ms lúc server lấy prompt lần đầu |
| Retrieval success rate | 100% | 100% | Trên mọi event có `tool_success` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware (`app/middleware.py`) xóa contextvars, đọc header `x-request-id`; nếu khớp regex `^req-[0-9a-f]{8}$` thì dùng, không thì sinh `req-<8 hex>`. ID được bind vào structlog contextvars nên mọi log line của request đều mang nó, lưu vào `request.state`, truyền vào agent/trace, và trả lại qua header `x-request-id`.
- **Các metadata được ghi vào structured log:** `service`, `event`, `ts` (UTC), `level`, `correlation_id`, `env`, `model`, `feature`, `session_id`, `user_id_hash` (hash, không ghi user_id thô). Event `response_sent` thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` trong `app/logging_config.py` được đặt trước `JsonlFileProcessor` (bước ghi file), nên dữ liệu đã che mới xuống đĩa. Rule trong `app/pii.py` gồm email, điện thoại VN, CCCD, thẻ thanh toán và passport VN.
- **Cách kiểm chứng kết quả:** `pytest` (26 test, gồm các định dạng phone/thẻ), `validate_logs.py` (100/100, 0 PII leak, dùng detector độc lập) và kiểm tra thủ công: gửi email, số điện thoại, CCCD, thẻ giả rồi đọc `data/logs.jsonl` thấy `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`. Bằng chứng nộp: `evidence/log-validator.txt` (0 PII leak) và `evidence/pytest.txt`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Key Langfuse của chính tôi nằm trong `.env` (không commit); trace mang `correlation_id` trùng với log cục bộ và tôi đọc lại được bằng API `v2/observations` với key đó.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` (agent) chứa `retrieval` (retriever) và `llm-generation` (generation, có model, `usage_details` và `cost_details`).
- **Cách nối trace với log:** `correlation_id` được ghi vào metadata của trace và có trong mọi dòng log; lấy ID từ log rồi tìm trong Langfuse Search.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** v1 / `baseline`
- **Version/label candidate:** v2 / `candidate`
- **Trace ID của mỗi version:** (production v2 sau promote: `req-aa21a36d`, ghi `prompt_label=production`, `prompt_version=2`, xem `evidence/02-trace-list.png`.) v1: `fae3e5626a4cf9201702e23c07425a6b` (`req-b36ab629`); v2: `06f2addcd850d19657e4304b315d2d00` (`req-3bbf6148`)
- **Cách promote và rollback `production`:** Trên Langfuse, gán label `production` cho v2 (promote) rồi gán lại cho v1 (rollback); không cần sửa code. App cache prompt khoảng 60 giây nên cần restart API để nhận label mới. Ảnh: `evidence/04-prompt-versioning.png` (trái: `production` ở v2, phải: sau rollback `production` về v1).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `scripts/dashboard.py` (Streamlit, venv riêng) đọc `data/logs.jsonl`, tự refresh, có đường threshold đỏ. Sáu panel: latency (P50/P95/P99 + TTFT), traffic, errors + retrieval success, cost, tokens, quality. Ảnh: `evidence/05-dashboard-incident.png` (P95 2652 ms trong incident).
- **SLO và lý do chọn:** 99.5% request có latency ≤ 3000 ms. Baseline P95 ≈ 150 ms nên có đệm, và kịch bản `rag_slow` (≈2.65 s) vẫn chưa vi phạm SLO nhưng đã vượt ngưỡng cảnh báo 2000 ms.
- **Cách tính error budget:** SLO 99.5% nghĩa là budget 0.5%. Với 10,000 request, tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms; trong 28 ngày tương đương khoảng 201 phút.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (P95 > 2000 ms, 5 phút, warning), `HighErrorRateOrRetrievalFailure` (error rate > 2% hoặc retrieval success < 90%, 5 phút, critical), `CostPerRequestSpike` (cost/request > 0.005 USD, 10 phút, warning). Cả ba gửi Slack `#k4-l3b-alerts`, owner `student-2A202602870`, runbook trong `docs/alerts.md` theo luồng Metrics → Logs → Traces.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (incident `rag_slow`, feature `monitoring`, ngưỡng 2000 ms)
- **Khoảng thời gian điều tra:** 2026-09-30 04:39:45–04:40:00 UTC (5 request, `inject_incident.py` rồi `load_test.py --challenge --concurrency 5`)
- **Triệu chứng từ metrics:** Latency của feature `monitoring` tăng từ khoảng 151 ms (median 34 request `qa` trước đó) lên 2652 ms ở cả 5 request, vượt ngưỡng cảnh báo 2000 ms (và alert `HighLatencyP95`) nhưng chưa vượt SLO 3000 ms. TTFT (50 ms), token và cost không đổi; không có lỗi, retrieval success vẫn 100%. Vì vậy sự cố là chậm chứ không phải hỏng.
- **Log line và correlation ID liên quan:** `response_sent` với `correlation_id=req-c409e920`, `latency_ms=2652`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`, `feature=monitoring`; log cũng có event `incident_enabled`. Bốn request còn lại cùng bất thường: `req-8a5e10a3`, `req-8f6ffc66`, `req-297291b4`, `req-a0f0fb5c`.
- **Trace ID và span gây ảnh hưởng:** Trace `386f3a938c3f09b62ce7ab8fa7749550` (`req-c409e920`): root `lab-agent-run` 2.65 s, trong đó span `retrieval` chiếm 2.50 s còn `llm-generation` chỉ 0.15 s (bình thường).
- **Root cause:** Bước retrieval bị làm chậm khoảng 2.5 s (incident `rag_slow`), chiếm gần như toàn bộ latency. Generation, prompt, token và cost đều bình thường nên không phải lỗi model hay prompt.
- **Fix action:** Tắt incident bằng `python scripts/inject_incident.py --disable`; latency trở về khoảng 150 ms. Với sự cố thật: kiểm tra và khôi phục dependency retrieval, hoặc bật timeout và fallback cho bước đó.
- **Preventive measure:** Alert `HighLatencyP95` (P95 > 2000 ms trong 5 phút) bắt được sự cố trước khi chạm SLO 3000 ms; thêm timeout cho retrieval và giữ span `retrieval` riêng để khoanh vùng nhanh theo runbook trong `docs/alerts.md`.
- **Ghi chú:** Request đầu (`req-8a5e10a3`) ghi `prompt_version=2` do cache prompt 60 giây sau khi tôi rollback `production` về v1; các request sau đã dùng v1. Điều này không liên quan đến độ trễ.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Đặt `scrub_event` trước `JsonlFileProcessor` trong chuỗi processor của structlog. Nếu scrub chạy sau bước ghi file thì PII đã nằm trên đĩa; đặt trước bảo đảm không dòng log nào chứa PII thô, kể cả khi sau này thêm processor khác.
- **Một lỗi/blocker đã gặp:** Server đang chạy không gửi trace nào lên Langfuse, và sau khi đổi `LANGFUSE_PROMPT_LABEL` trace vẫn ghi label cũ; ngoài ra `curl.exe` trên PowerShell 5.1 làm hỏng JSON (lỗi 422 `json_invalid`).
- **Cách tìm nguyên nhân và xử lý:** Đọc lại trace qua API `v2/observations` để so `prompt_label`/`prompt_version`/`prompt_source` với kỳ vọng, phát hiện server chỉ đọc `.env` một lần lúc khởi động (và prompt được cache 60 giây), nên phải restart sau mỗi lần đổi key hoặc label. Với curl, chuyển sang `Invoke-RestMethod` để gửi JSON đúng.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metric (dashboard) cho biết có vấn đề gì và khi nào (P95 tăng lên 2652 ms). Log lọc ra request cụ thể qua `correlation_id` (`req-c409e920`). Trace cùng `correlation_id` chỉ ra bước gây ra (span `retrieval` 2.50 s trong 2.65 s). Ba tín hiệu cùng chỉ về một nguyên nhân mới là kết luận hợp lệ.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version cho phép so v1/v2 theo trace và rollback `production` chỉ bằng đổi label, không cần deploy code. Token và cost trên từng generation giúp thấy prompt mới có đắt hơn không. SLO và error budget cho ngưỡng rõ ràng để quyết định khi nào cảnh báo hoặc rollback.
- **Điều quan trọng nhất đã học:** Quan sát được hệ thống phải có ID chung nối log và trace; không có `correlation_id` thì không lần được từ metric đến nguyên nhân.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Ảnh 04 minh họa promote và rollback bằng trang versions ở hai trạng thái, không phải một trace `production` v2 đặt cạnh trang versions; trace production v2 được ghi ở mục 5. Load test challenge chỉ có 5 request nên đỉnh latency trên dashboard nhỏ. Dashboard đọc log file, chưa dùng Prometheus/Grafana.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
