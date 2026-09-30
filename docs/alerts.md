# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests` (latency ≤ 3000 ms, 99.5% / 28 ngày); ngưỡng alert 2000 ms để cảnh báo sớm trước khi ăn error budget
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 2000 ms` liên tục 5 phút (baseline P95 ≈ 150 ms)
- Ảnh hưởng tới người dùng: câu trả lời đến chậm; nếu vượt 3000 ms thì request đó tiêu hao error budget
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Latency, xác nhận P95/P99/TTFT và thời điểm bắt đầu tăng. TTFT vẫn ~50 ms mà latency tăng nghĩa là chậm ở bước trước LLM (retrieval).
  2. Logs: lọc `data/logs.jsonl` với `event == "response_sent"` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Traces: mở trace Langfuse có cùng `correlation_id`, so sánh thời gian span `retrieval` và `llm-generation`; span nào chiếm phần lớn thời gian là nguyên nhân.
- Mitigation tạm thời: nếu `retrieval` chậm, kiểm tra vector store/cấu hình rồi tắt practice scenario (`python scripts/inject_incident.py --scenario rag_slow --disable`); nếu `llm-generation` chậm sau khi đổi prompt, rollback label `production` về version cũ; giảm tải nếu do traffic.
- Owner: `student-2A202602870`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailure`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `error_rate_pct_max: 2` và `retrieval_success_rate_pct_min: 90` trong `config/slo.yaml`
- Điều kiện và thời gian duy trì: `count(request_failed)/count(request_received)*100 > 2` HOẶC `retrieval_success_rate_pct < 90` (tool_success == true trên mọi event có `tool_success`) liên tục 5 phút
- Ảnh hưởng tới người dùng: request trả HTTP 500, người dùng không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Errors, xem error rate, retrieval success và breakdown theo `error_type`.
  2. Logs: lọc `event == "request_failed"`, đọc `error_type`, `tool_name`, `tool_success` và lấy một `correlation_id`.
  3. Traces: mở trace cùng `correlation_id`; span `retrieval` ở trạng thái ERROR (ví dụ `RuntimeError: Vector store timeout`) xác nhận lỗi nằm ở retrieval, không phải LLM.
- Mitigation tạm thời: khôi phục vector store/retrieval hoặc tắt practice scenario (`--scenario tool_fail --disable`); nếu lỗi bắt đầu ngay sau khi promote prompt/deploy thì rollback; thông báo người dùng qua kênh hỗ trợ nếu kéo dài.
- Owner: `student-2A202602870`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5` trong `config/slo.yaml`
- Điều kiện và thời gian duy trì: `sum(response_sent.cost_usd) / count(response_sent) > 0.005 USD` liên tục 10 phút (baseline ≈ 0.002 USD/request; ngưỡng ≈ 2.5x)
- Ảnh hưởng tới người dùng: người dùng không thấy ngay, nhưng chi phí vận hành tăng nhanh và có thể vượt ngân sách ngày; thường đi kèm câu trả lời dài bất thường
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Cost và Tokens, xem `tokens_out` có tăng đột biến không.
  2. Logs: lọc `response_sent` có `tokens_out`/`cost_usd` cao, lấy một `correlation_id`.
  3. Traces: mở trace cùng `correlation_id`, xem `usage` và `cost` của span `llm-generation`, đối chiếu `prompt_version` trong metadata để biết có phải prompt mới gây ra không.
- Mitigation tạm thời: rollback prompt `production` về version trước nếu spike bắt đầu sau khi promote; giới hạn độ dài output; tắt practice scenario (`--scenario cost_spike --disable`).
- Owner: `student-2A202602870`
