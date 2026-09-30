"""Dashboard 6 panel đọc data/logs.jsonl, khớp config/dashboard.yaml.

Chạy (venv riêng, không cài chung với API):
    .\\.venv-dashboard\\Scripts\\streamlit run scripts/dashboard.py
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
CFG = yaml.safe_load((ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
PANELS = {p["id"]: p for p in CFG["panels"]}
RETRIEVAL_SUCCESS_MIN = 90  # config/slo.yaml guardrails.retrieval_success_rate_pct_min

st.set_page_config(page_title=CFG["title"], layout="wide")


def load_logs() -> pd.DataFrame:
    rows = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def line(df: pd.DataFrame, cols: list[str], title: str, unit: str, threshold: float, mark: str = "line"):
    """Biểu đồ theo phút + đường threshold (st.line_chart không vẽ được threshold)."""
    long = df[["minute", *cols]].melt("minute", var_name="series", value_name="value")
    base = alt.Chart(long).encode(
        x=alt.X("minute:T", title="UTC"),
        y=alt.Y("value:Q", title=unit),
        color=alt.Color("series:N", title=None),
        tooltip=["minute:T", "series:N", "value:Q"],
    )
    layer = base.mark_line(point=True) if mark == "line" else base.mark_bar()
    rule = alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(color="red", strokeDash=[6, 4]).encode(y="y:Q")
    st.altair_chart((layer + rule).properties(height=240), width="stretch")
    st.caption(f"Đường đỏ = threshold {threshold:g} {unit} · {title}")


def header(panel_id: str) -> dict:
    p = PANELS[panel_id]
    th = p["threshold"]
    st.subheader(p["title"])
    st.caption(f"Đơn vị: {p['unit']} · SLO: {th['aggregation']} {th['operator']} {th['value']:g} · {CFG['time_range_minutes']} phút gần nhất")
    return th


@st.fragment(run_every=CFG["refresh_seconds"])
def render() -> None:
    df = load_logs()
    if df.empty:
        st.warning("Chưa có log. Chạy API rồi `python scripts/load_test.py`.")
        return

    anchor_latest = st.sidebar.checkbox("Neo cửa sổ vào log mới nhất (thay vì 'bây giờ')", value=False)
    end = df["ts"].max() if anchor_latest else pd.Timestamp.now(tz="UTC")
    start = end - timedelta(minutes=CFG["time_range_minutes"])
    df = df[(df["ts"] >= start) & (df["ts"] <= end)].copy()
    st.sidebar.write(f"Cửa sổ UTC: {start:%H:%M:%S} → {end:%H:%M:%S}")
    st.sidebar.write(f"Refresh: {CFG['refresh_seconds']}s · {len(df)} dòng log")
    if df.empty:
        st.warning("Không có log trong 60 phút gần nhất. Bật checkbox bên trái hoặc chạy load test.")
        return
    df["minute"] = df["ts"].dt.floor("min")

    sent = df[df["event"] == "response_sent"]
    received = df[df["event"] == "request_received"]
    failed = df[df["event"] == "request_failed"]

    st.title(CFG["title"])
    left, right = st.columns(2)

    with left:  # 1. Latency
        th = header("latency")
        if sent.empty:
            st.info("Chưa có response_sent")
        else:
            lat, ttft = sent["latency_ms"], sent["ttft_ms"]
            k = st.columns(4)
            k[0].metric("P50", f"{lat.quantile(.5):.0f} ms")
            k[1].metric("P95", f"{lat.quantile(.95):.0f} ms", delta="OK" if lat.quantile(.95) <= th["value"] else "VƯỢT SLO", delta_color="normal" if lat.quantile(.95) <= th["value"] else "inverse")
            k[2].metric("P99", f"{lat.quantile(.99):.0f} ms")
            k[3].metric("TTFT P95", f"{ttft.quantile(.95):.0f} ms")
            g = sent.groupby("minute")
            per_min = pd.DataFrame({
                "P50": g["latency_ms"].quantile(.5),
                "P95": g["latency_ms"].quantile(.95),
                "P99": g["latency_ms"].quantile(.99),
                "TTFT P95": g["ttft_ms"].quantile(.95),
            }).reset_index()
            line(per_min, ["P50", "P95", "P99", "TTFT P95"], "latency", "ms", th["value"])

    with right:  # 2. Traffic
        th = header("traffic")
        per_min = received.groupby("minute").size().rename("requests/phút").reset_index()
        st.metric("Tổng request", len(received), help=f"Trung bình {len(received) / CFG['time_range_minutes']:.2f} req/phút trong cửa sổ")
        if not per_min.empty:
            line(per_min, ["requests/phút"], "traffic", "requests_per_minute", th["value"], mark="bar")

    left, right = st.columns(2)
    with left:  # 3. Errors + retrieval success
        th = header("errors")
        err_rate = len(failed) / len(received) * 100 if len(received) else 0.0
        checked = df[df["tool_success"].notna()] if "tool_success" in df else df.iloc[0:0]
        retr = (checked["tool_success"] == True).mean() * 100 if len(checked) else float("nan")  # noqa: E712
        k = st.columns(3)
        k[0].metric("Error rate", f"{err_rate:.2f} %", delta="OK" if err_rate <= th["value"] else "VƯỢT SLO", delta_color="normal" if err_rate <= th["value"] else "inverse")
        k[1].metric("Retrieval success", f"{retr:.1f} %", help=f"tool_success==true / mọi event có tool_success (guardrail ≥ {RETRIEVAL_SUCCESS_MIN}%)")
        k[2].metric("Số lỗi", len(failed))
        rec = pd.DataFrame({"minute": sorted(df["minute"].unique())})
        rec["Error rate %"] = rec["minute"].map(failed.groupby("minute").size() / received.groupby("minute").size() * 100).fillna(0)
        if len(checked):
            rec["Retrieval success %"] = rec["minute"].map(checked.groupby("minute")["tool_success"].apply(lambda s: (s == True).mean() * 100))  # noqa: E712
            rec["Retrieval success %"] = rec["Retrieval success %"].ffill().fillna(100)
        line(rec, [c for c in rec.columns if c != "minute"], "errors", "percent", th["value"])
        if "error_type" in failed and failed["error_type"].notna().any():
            st.write("Lỗi theo `error_type`:", failed["error_type"].value_counts().to_dict())

    with right:  # 4. Cost
        th = header("cost")
        cost = sent.groupby("minute")["cost_usd"].sum().rename("Cost/phút").reset_index()
        total = sent["cost_usd"].sum()
        st.metric("Tổng cost", f"${total:.4f}", delta="OK" if total <= th["value"] else "VƯỢT SLO", delta_color="normal" if total <= th["value"] else "inverse")
        if not cost.empty:
            cost["Cost tích lũy"] = cost["Cost/phút"].cumsum()
            line(cost, ["Cost/phút", "Cost tích lũy"], "cost", "usd", th["value"])

    left, right = st.columns(2)
    with left:  # 5. Tokens
        th = header("tokens")
        tin, tout = int(sent["tokens_in"].sum()), int(sent["tokens_out"].sum())
        k = st.columns(2)
        k[0].metric("Tokens in", f"{tin:,}")
        k[1].metric("Tokens out", f"{tout:,}")
        tok = sent.groupby("minute")[["tokens_in", "tokens_out"]].sum().reset_index()
        if not tok.empty:
            tok[["tokens_in", "tokens_out"]] = tok[["tokens_in", "tokens_out"]].cumsum()
            line(tok, ["tokens_in", "tokens_out"], "tokens (tích lũy)", "tokens", th["value"])

    with right:  # 6. Quality
        th = header("quality")
        if sent.empty:
            st.info("Chưa có response_sent")
        else:
            q = sent["quality_score"].mean()
            st.metric("Quality trung bình", f"{q:.2f}", delta="OK" if q >= th["value"] else "DƯỚI SLO", delta_color="normal" if q >= th["value"] else "inverse")
            qm = sent.groupby("minute")["quality_score"].mean().rename("quality (mean)").reset_index()
            line(qm, ["quality (mean)"], "quality", "score_0_to_1", th["value"])


render()
