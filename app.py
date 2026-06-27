import io
import re
import math
import base64
from html import escape
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Optional PDF export. The app still works if reportlab is not installed.
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

st.set_page_config(
    page_title="Universal Data Analyzer Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
<style>
:root {
  --bg-card: #ffffff;
  --border: #e5e7eb;
  --text-muted: #475467;
  --accent: #0ea5e9;
  --accent-dark: #0369a1;
  --dark: #111827;
  --title-safe: #0ea5e9;
}
/* Extra top padding prevents the title from being clipped by Streamlit header */
.block-container {
  padding-top: 3.8rem !important;
  padding-bottom: 2rem !important;
  overflow: visible !important;
}
.main-title {
  display: block;
  font-size: 2.05rem;
  line-height: 1.28;
  font-weight: 900;
  color: var(--title-safe) !important;
  margin-top: 0.35rem;
  margin-bottom: 0.35rem;
  padding-top: 0.25rem;
  letter-spacing: -0.02em;
  overflow: visible !important;
  text-shadow: 0 1px 2px rgba(0,0,0,0.35), 0 0 1px rgba(255,255,255,0.55);
}
.subtitle {
  font-size: 1.02rem;
  color: #38bdf8 !important;
  margin-bottom: 1rem;
  font-weight: 600;
  text-shadow: 0 1px 2px rgba(0,0,0,0.28);
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
  color: var(--title-safe) !important;
  font-weight: 800 !important;
}
.kpi-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 18px 18px;
  box-shadow: 0 4px 14px rgba(16, 24, 40, 0.05);
  min-height: 118px;
}
.kpi-label {font-size: .84rem; color: #475467; font-weight: 700; margin-bottom: 8px;}
.kpi-value {font-size: 1.62rem; color: #111827; font-weight: 900; line-height: 1.1;}
.kpi-note {font-size: .78rem; color: #475467; margin-top: 8px;}
.insight-card {
  border-left: 5px solid #0ea5e9;
  background: #f8fafc;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
  color: #111827;
}
.warning-card {
  border-left: 5px solid #d92d20;
  background: #fff7f7;
  color: #111827;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
}
.ok-card {
  border-left: 5px solid #16a34a;
  background: #f0fdf4;
  color: #111827;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
}
.small-muted {color: #475467; font-size: .86rem;}
.section-header {
  font-size: 1.2rem;
  font-weight: 900;
  color: var(--title-safe) !important;
  margin-top: .4rem;
  margin-bottom: .6rem;
  text-shadow: 0 1px 2px rgba(0,0,0,0.25);
}
.codebox {background:#111827;color:#f9fafb;padding:12px;border-radius:10px; font-family:monospace;}
.filter-note {font-size: .82rem; color: #38bdf8; font-weight: 600;}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Security and secrets
# -----------------------------
def get_secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def password_gate() -> bool:
    app_password = str(get_secret("APP_PASSWORD", "") or "").strip()
    if not app_password:
        return True
    if st.session_state.get("auth_ok"):
        return True

    st.markdown('<div class="main-title">Universal Data Analyzer Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Secure access is enabled for this app.</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Open app")
        if submitted:
            if password == app_password:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
    st.info("Set APP_PASSWORD inside Streamlit Secrets. Do not store passwords in source code.")
    return False


if not password_gate():
    st.stop()

# -----------------------------
# Helper functions
# -----------------------------
def safe_number(x: Any) -> Optional[float]:
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)
    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "null", "-"}:
        return np.nan
    pct = False
    if s.endswith("%"):
        pct = True
        s = s[:-1]
    s = re.sub(r"[,$€£EGPج.م\s]", "", s, flags=re.IGNORECASE)
    s = s.replace("،", "").replace(",", "")
    try:
        value = float(s)
        return value / 100 if pct else value
    except Exception:
        return np.nan


def normalize_col_name(name: Any) -> str:
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z_\u0600-\u06FF-]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "Column"


def make_unique_columns(cols: List[Any]) -> Tuple[List[str], Dict[str, str]]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    mapping: Dict[str, str] = {}
    for c in cols:
        base = normalize_col_name(c)
        n = seen.get(base, 0)
        new = base if n == 0 else f"{base}_{n+1}"
        seen[base] = n + 1
        out.append(new)
        mapping[str(c)] = new
    return out, mapping


def looks_like_metadata_sheet(name: str, df: pd.DataFrame) -> bool:
    name_l = str(name).lower()
    meta_terms = [
        "log", "note", "notes", "readme", "metadata", "dictionary", "empname_removal", "removal", "instruction",
        "cover", "mapping", "audit"
    ]
    if any(t in name_l for t in meta_terms):
        return True
    if df.empty:
        return True
    non_empty_rows = df.dropna(how="all").shape[0]
    non_empty_cols = df.dropna(axis=1, how="all").shape[1]
    if non_empty_rows <= 1 or non_empty_cols <= 1:
        return True
    # Tiny text-only notes sheets are usually not analytical data.
    if non_empty_rows <= 3 and non_empty_cols <= 3:
        numeric_cells = df.applymap(lambda x: pd.notna(safe_number(x))).sum().sum()
        if numeric_cells == 0:
            return True
    return False


def maybe_promote_header(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = [str(c) for c in df.columns]
    unnamed_ratio = sum(c.lower().startswith("unnamed") or c.isdigit() for c in cols) / max(len(cols), 1)
    first = df.iloc[0]
    first_non_null = first.dropna()
    if first_non_null.empty:
        return df
    first_strings = sum(isinstance(x, str) and len(str(x).strip()) > 0 for x in first_non_null)
    row_is_header = first_strings >= max(2, len(first_non_null) * 0.6)
    if unnamed_ratio > 0.4 and row_is_header:
        new_cols = [x if pd.notna(x) and str(x).strip() else f"Column_{i+1}" for i, x in enumerate(first.tolist())]
        df = df.iloc[1:].copy()
        df.columns = new_cols
    return df


def parse_month_column(series: pd.Series) -> pd.Series:
    month_map = {
        "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
        "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
        "august": 8, "aug": 8, "september": 9, "sep": 9, "october": 10, "oct": 10,
        "november": 11, "nov": 11, "december": 12, "dec": 12,
    }
    s = series.astype(str).str.strip().str.lower()
    nums = s.map(month_map)
    if nums.notna().mean() >= 0.6:
        current_year = datetime.now().year
        return pd.to_datetime({"year": current_year, "month": nums.fillna(1).astype(int), "day": 1}, errors="coerce")
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def read_input_file(uploaded_file) -> Tuple[Dict[str, pd.DataFrame], List[str], List[str]]:
    sheets: Dict[str, pd.DataFrame] = {}
    skipped: List[str] = []
    errors: List[str] = []
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            sheets["CSV_Data"] = df
        elif name.endswith((".xlsx", ".xls")):
            xls = pd.ExcelFile(uploaded_file)
            for sheet in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    if looks_like_metadata_sheet(sheet, df):
                        skipped.append(sheet)
                        continue
                    sheets[sheet] = df
                except Exception as e:
                    errors.append(f"Could not read sheet {sheet}: {e}")
        else:
            errors.append("Unsupported file type. Please upload CSV, XLSX, or XLS.")
    except Exception as e:
        errors.append(f"File read error: {e}")
    return sheets, skipped, errors


def load_sample_data() -> pd.DataFrame:
    sample_path = "data/sample_branch_sales.csv"
    try:
        return pd.read_csv(sample_path)
    except Exception:
        data = {
            "Month": ["February", "March", "April", "May", "June"],
            "Branch": ["Aswan Main Central", "Edfu", "Kom Ombo", "Aswan East", "Aswan Main Central"],
            "FBB": [210, 205, 210, 95, 270],
            "FV": [310, 270, 290, 140, 375],
            "Wallet": [350, 450, 350, 225, 420],
            "Gold": [110, 98, 105, 45, 138],
            "Devices": [35, 30, 30, 14, 45],
            "Mobile_Value": [420000, 350000, 360000, 155000, 510000],
            "Total_Value": [985000, 890000, 880000, 390000, 1210000],
            "Units": [1370, 1530, 1320, 680, 1645],
        }
        return pd.DataFrame(data)


def clean_dataframe(raw_df: pd.DataFrame, remove_duplicates: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    report: Dict[str, Any] = {}
    df = raw_df.copy()
    report["original_rows"] = int(df.shape[0])
    report["original_columns"] = int(df.shape[1])

    df = maybe_promote_header(df)
    df = df.replace(r"^\s*$", np.nan, regex=True)
    rows_before = df.shape[0]
    cols_before = df.shape[1]
    df = df.dropna(how="all").copy()
    df = df.dropna(axis=1, how="all").copy()
    report["empty_rows_removed"] = int(rows_before - df.shape[0])
    report["empty_columns_removed"] = int(cols_before - df.shape[1])

    new_cols, mapping = make_unique_columns(list(df.columns))
    df.columns = new_cols
    report["column_name_mapping"] = mapping

    # Strip string cells
    object_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for col in object_cols:
        df[col] = df[col].apply(lambda x: str(x).strip() if isinstance(x, str) else x)

    # Type correction
    converted_numeric = []
    converted_dates = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        if df[col].dropna().empty:
            continue
        col_l = col.lower()
        if any(k in col_l for k in ["date", "month", "time", "period", "اليوم", "الشهر", "تاريخ"]):
            parsed = parse_month_column(df[col])
            if parsed.notna().mean() >= 0.55:
                df[col] = parsed
                converted_dates.append(col)
                continue
        numeric = df[col].apply(safe_number)
        if numeric.notna().mean() >= 0.75:
            df[col] = numeric
            converted_numeric.append(col)
            continue
        parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        if parsed.notna().mean() >= 0.85:
            df[col] = parsed
            converted_dates.append(col)

    report["converted_numeric_columns"] = converted_numeric
    report["converted_date_columns"] = converted_dates

    duplicates_before = int(df.duplicated().sum())
    if remove_duplicates and duplicates_before > 0:
        df = df.drop_duplicates().copy()
    report["duplicate_rows_detected"] = duplicates_before
    report["duplicate_rows_removed"] = duplicates_before if remove_duplicates else 0

    missing_total = int(df.isna().sum().sum())
    total_cells = int(df.shape[0] * df.shape[1]) if df.shape[0] and df.shape[1] else 1
    missing_by_col = df.isna().sum().sort_values(ascending=False)
    report["missing_total"] = missing_total
    report["missing_pct"] = float(missing_total / total_cells)
    report["missing_by_column"] = missing_by_col[missing_by_col > 0].to_dict()

    outlier_records = []
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        s = df[col].dropna()
        if s.shape[0] < 8 or s.nunique() < 5:
            continue
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0 or pd.isna(iqr):
            continue
        low = q1 - 1.5 * iqr
        high = q3 + 1.5 * iqr
        mask = (df[col] < low) | (df[col] > high)
        count = int(mask.sum())
        if count:
            outlier_records.append({"column": col, "outliers": count, "lower_bound": low, "upper_bound": high})
    report["outliers"] = outlier_records
    report["outlier_total"] = int(sum(x["outliers"] for x in outlier_records))

    # Quality score with bounded penalties
    score = 100
    score -= min(25, report["missing_pct"] * 100)
    score -= min(20, (duplicates_before / max(report["original_rows"], 1)) * 100)
    score -= min(20, (report["outlier_total"] / max(df.shape[0] * max(len(numeric_cols), 1), 1)) * 100)
    if len(converted_numeric) == 0 and len(numeric_cols) == 0:
        score -= 10
    if len(df.columns) < 2 or df.shape[0] < 5:
        score -= 10
    report["data_quality_score"] = max(0, round(float(score), 1))
    report["cleaned_rows"] = int(df.shape[0])
    report["cleaned_columns"] = int(df.shape[1])
    return df, report


def format_number(value: Any, compact: bool = True) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)
    if math.isnan(v):
        return "N/A"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if compact:
        if v >= 1_000_000_000:
            return f"{sign}{v/1_000_000_000:.2f}B"
        if v >= 1_000_000:
            return f"{sign}{v/1_000_000:.2f}M"
        if v >= 1_000:
            return f"{sign}{v/1_000:.2f}K"
    return f"{sign}{v:,.2f}"


def month_sort_key(x: Any) -> int:
    if pd.isna(x):
        return 999
    s = str(x).strip().lower()
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    for i, m in enumerate(months, 1):
        if s == m or s.startswith(m[:3]):
            return i
    try:
        return int(pd.to_datetime(x).month)
    except Exception:
        return 999


def detect_columns(df: pd.DataFrame) -> Dict[str, Any]:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    date_cols = df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]
    month_like = [c for c in df.columns if "month" in c.lower() or "الشهر" in c.lower()]
    branch_like = [c for c in df.columns if any(k in c.lower() for k in ["branch", "store", "region", "area", "فرع", "منطقة"])]
    product_like = [c for c in df.columns if any(k in c.lower() for k in ["product", "service", "category", "item", "خدمة", "منتج", "فئة"])]
    metric_candidates = [c for c in numeric_cols if any(k in c.lower() for k in ["sales", "value", "revenue", "total", "amount", "net", "قيمة", "مبيعات", "اجمالي"])]
    units_candidates = [c for c in numeric_cols if any(k in c.lower() for k in ["unit", "qty", "quantity", "volume", "count", "عدد", "كمية"])]
    return {
        "numeric": numeric_cols,
        "date": date_cols,
        "categorical": cat_cols,
        "month_like": month_like,
        "branch_like": branch_like,
        "product_like": product_like,
        "metric_default": metric_candidates[0] if metric_candidates else (numeric_cols[0] if numeric_cols else None),
        "units_default": units_candidates[0] if units_candidates else (numeric_cols[1] if len(numeric_cols) > 1 else None),
        "category_default": branch_like[0] if branch_like else (cat_cols[0] if cat_cols else None),
        "time_default": date_cols[0] if date_cols else (month_like[0] if month_like else None),
    }


def smart_filter_columns(df: pd.DataFrame, categorical_cols: List[str], category_col: Optional[str], time_col: Optional[str]) -> List[str]:
    """Choose the most useful filters automatically.

    The goal is to show meaningful business filters such as Branch, Month, Product,
    Region, Segment, Status, Channel, etc. while avoiding IDs or columns with almost
    every value unique.
    """
    if df.empty:
        return []
    rows = max(len(df), 1)
    scored: List[Tuple[int, str]] = []
    priority_terms = {
        "branch": 120, "store": 115, "region": 110, "area": 110, "zone": 100,
        "month": 105, "year": 90, "period": 95, "date": 90,
        "product": 100, "service": 100, "category": 95, "item": 90,
        "segment": 90, "channel": 90, "status": 80, "type": 75,
        "فرع": 120, "منطقة": 110, "الشهر": 105, "منتج": 100, "خدمة": 100, "فئة": 95,
    }
    avoid_terms = ["id", "code", "phone", "mobile_number", "email", "address", "name", "اسم", "تليفون", "هاتف"]
    for col in categorical_cols:
        if col not in df.columns:
            continue
        unique_count = int(df[col].dropna().astype(str).nunique())
        if unique_count <= 1:
            continue
        unique_ratio = unique_count / rows
        col_l = str(col).lower()
        score = 0
        if col == category_col:
            score += 80
        if col == time_col:
            score += 70
        for term, pts in priority_terms.items():
            if term in col_l:
                score += pts
        if any(term in col_l for term in avoid_terms):
            score -= 80
        # Prefer columns that are useful as slicers: not too unique, not too tiny.
        if 2 <= unique_count <= 12:
            score += 55
        elif 13 <= unique_count <= 50:
            score += 35
        elif 51 <= unique_count <= 200:
            score += 15
        if unique_ratio > 0.8 and rows > 25:
            score -= 70
        if unique_count > 250:
            score -= 60
        if score > 15:
            scored.append((score, col))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # keep unique order and limit to keep the sidebar usable
    out: List[str] = []
    for _, col in scored:
        if col not in out:
            out.append(col)
    return out[:8]


def smart_numeric_filter_columns(numeric_cols: List[str], metric_col: Optional[str], unit_col: Optional[str]) -> List[str]:
    selected: List[str] = []
    for col in [metric_col, unit_col]:
        if col and col in numeric_cols and col not in selected:
            selected.append(col)
    value_terms = ["sales", "value", "revenue", "amount", "total", "net", "unit", "qty", "quantity", "count", "قيمة", "مبيعات", "عدد", "كمية"]
    for col in numeric_cols:
        if col in selected:
            continue
        if any(t in col.lower() for t in value_terms):
            selected.append(col)
        if len(selected) >= 4:
            break
    return selected[:4]


def sort_filter_values(values: List[str]) -> List[str]:
    # Month-aware sorting when possible, otherwise alphabetical.
    try:
        return sorted(values, key=lambda x: (month_sort_key(x), str(x).lower()))
    except Exception:
        return sorted(values)


def describe_active_filters(filters: Dict[str, Any]) -> List[str]:
    active: List[str] = []
    for col, selected in filters.get("categorical", {}).items():
        if selected and "All" not in selected:
            active.append(f"{col}: {', '.join(map(str, selected[:8]))}{'...' if len(selected) > 8 else ''}")
    for col, rng in filters.get("numeric", {}).items():
        if rng is not None:
            active.append(f"{col}: {format_number(rng[0], compact=False)} to {format_number(rng[1], compact=False)}")
    if filters.get("date"):
        col, start, end = filters["date"]
        active.append(f"{col}: {start} to {end}")
    return active or ["No active filters - all cleaned rows are included."]


def apply_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    for col, selected in filters.get("categorical", {}).items():
        if selected and "All" not in selected:
            out = out[out[col].astype(str).isin(selected)]
    for col, rng in filters.get("numeric", {}).items():
        if rng is not None:
            low, high = rng
            out = out[(out[col] >= low) & (out[col] <= high)]
    if filters.get("date"):
        col, start, end = filters["date"]
        out = out[(out[col] >= pd.to_datetime(start)) & (out[col] <= pd.to_datetime(end))]
    return out


def kpi_card(label: str, value: Any, note: str = ""):
    st.markdown(
        f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-note">{note}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def compute_insights(df: pd.DataFrame, metric_col: Optional[str], category_col: Optional[str], time_col: Optional[str], unit_col: Optional[str]) -> List[str]:
    insights: List[str] = []
    if df.empty:
        return ["No rows are available after filtering."]
    if metric_col and metric_col in df.columns:
        total = df[metric_col].sum(skipna=True)
        avg = df[metric_col].mean(skipna=True)
        insights.append(f"Total {metric_col} equals {format_number(total)} and the average row value is {format_number(avg)}.")
    if metric_col and category_col and category_col in df.columns:
        ranking = df.groupby(category_col, dropna=False)[metric_col].sum().sort_values(ascending=False)
        if not ranking.empty:
            top_name, top_value = str(ranking.index[0]), ranking.iloc[0]
            share = top_value / ranking.sum() if ranking.sum() else 0
            insights.append(f"{top_name} is the top contributor in {metric_col}, contributing {share:.1%} of the filtered total.")
            if len(ranking) >= 3:
                concentration = ranking.head(3).sum() / ranking.sum() if ranking.sum() else 0
                insights.append(f"The top 3 {category_col} values contribute {concentration:.1%}, which indicates the level of performance concentration.")
    if metric_col and time_col and time_col in df.columns:
        trend = aggregate_by_time(df, time_col, metric_col)
        if trend.shape[0] >= 2:
            first, last = trend[metric_col].iloc[0], trend[metric_col].iloc[-1]
            change = (last - first) / abs(first) if first else np.nan
            direction = "increased" if last >= first else "declined"
            if not pd.isna(change):
                insights.append(f"{metric_col} {direction} by {change:.1%} from the first to the last visible period.")
    if metric_col and unit_col and unit_col in df.columns and metric_col != unit_col:
        total_units = df[unit_col].sum(skipna=True)
        total_value = df[metric_col].sum(skipna=True)
        if total_units:
            insights.append(f"Average {metric_col} per {unit_col} is {format_number(total_value / total_units)}.")
    return insights


def aggregate_by_time(df: pd.DataFrame, time_col: str, metric_col: str) -> pd.DataFrame:
    tmp = df[[time_col, metric_col]].copy()
    if pd.api.types.is_datetime64_any_dtype(tmp[time_col]):
        tmp["_time"] = tmp[time_col].dt.to_period("M").dt.to_timestamp()
        grouped = tmp.groupby("_time", as_index=False)[metric_col].sum().sort_values("_time")
        return grouped.rename(columns={"_time": time_col})
    else:
        grouped = tmp.groupby(time_col, as_index=False)[metric_col].sum()
        grouped["_sort"] = grouped[time_col].apply(month_sort_key)
        return grouped.sort_values("_sort").drop(columns="_sort")


def simple_forecast(series: pd.Series, periods: int = 6) -> Tuple[pd.Series, float]:
    y = pd.to_numeric(series, errors="coerce").dropna().values.astype(float)
    if len(y) == 0:
        return pd.Series(dtype=float), 0.0
    if len(y) == 1:
        return pd.Series([y[0]] * periods), 0.0
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    future_x = np.arange(len(y), len(y) + periods)
    pred = intercept + slope * future_x
    pred = np.maximum(pred, 0)
    # R2
    fitted = intercept + slope * x
    ss_res = np.sum((y - fitted) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return pd.Series(pred), float(max(min(r2, 1), -1))


def compute_anomalies(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    records = []
    for col in numeric_cols:
        s = df[col].dropna()
        if s.shape[0] < 8 or s.std() == 0 or pd.isna(s.std()):
            continue
        mean, std = s.mean(), s.std()
        z = (df[col] - mean) / std
        idxs = df.index[z.abs() >= 2.5].tolist()
        for i in idxs[:30]:
            records.append({"row_index": int(i), "column": col, "value": df.at[i, col], "z_score": float(z.loc[i])})
    return pd.DataFrame(records)


def generate_context(df: pd.DataFrame, report: Dict[str, Any], metric_col: Optional[str], category_col: Optional[str], time_col: Optional[str], unit_col: Optional[str], insights: List[str]) -> str:
    lines: List[str] = []
    lines.append(f"Dataset shape after cleaning/filtering: {df.shape[0]} rows and {df.shape[1]} columns.")
    lines.append(f"Columns: {', '.join(map(str, df.columns[:80]))}")
    lines.append(f"Data quality score: {report.get('data_quality_score', 'N/A')}/100.")
    lines.append(f"Duplicates removed: {report.get('duplicate_rows_removed', 0)}. Missing cells: {report.get('missing_total', 0)}.")
    if report.get("missing_by_column"):
        missing_top = list(report["missing_by_column"].items())[:8]
        lines.append(f"Top missing columns: {missing_top}")
    if report.get("outliers"):
        lines.append(f"Outlier summary: {report.get('outliers')[:8]}")
    if metric_col and metric_col in df.columns:
        lines.append(f"Selected main metric: {metric_col}; total={df[metric_col].sum(skipna=True):,.2f}; average={df[metric_col].mean(skipna=True):,.2f}.")
    if category_col and metric_col and category_col in df.columns:
        top = df.groupby(category_col, dropna=False)[metric_col].sum().sort_values(ascending=False).head(10)
        lines.append(f"Top {category_col} by {metric_col}: {top.to_dict()}")
    if time_col and metric_col and time_col in df.columns:
        trend = aggregate_by_time(df, time_col, metric_col)
        lines.append(f"Time trend for {metric_col}: {trend.to_dict(orient='records')[:12]}")
    if unit_col and unit_col in df.columns:
        lines.append(f"Selected unit/volume metric: {unit_col}; total={df[unit_col].sum(skipna=True):,.2f}.")
    lines.append("Auto insights: " + " | ".join(insights[:10]))
    return "\n".join(lines)[:18000]


def local_answer(question: str, context: str) -> str:
    q = question.lower()
    if any(w in q for w in ["top", "highest", "best", "اعلى", "أفضل", "اكبر"]):
        return "The top contributor is shown in the Overview and Ranking sections. Select the relevant metric and category from the sidebar to make the answer specific."
    if any(w in q for w in ["missing", "quality", "clean", "ناقص", "جودة", "تنظيف"]):
        return "Check the Cleaning & Quality tab. It shows missing values, duplicates, outliers, data type fixes, and the data quality score."
    if any(w in q for w in ["forecast", "predict", "توقع", "تنبؤ"]):
        return "Check the Forecast tab. It uses the visible historical trend to estimate the next periods, but the forecast is indicative and improves with more historical data."
    return "AI API is not configured. Add GROQ_API_KEY in Streamlit Secrets to enable multilingual AI answers. The dashboard sections still provide the required calculations and insights."


def ask_groq(question: str, context: str) -> str:
    api_key = str(get_secret("GROQ_API_KEY", "") or "").strip()
    model = str(get_secret("GROQ_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile").strip()
    if not api_key:
        return local_answer(question, context)
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        system_prompt = (
            "You are a senior business data analyst. Answer in the same language as the user's question. "
            "Use only the dashboard context provided. Do not invent numbers. If the context is insufficient, say what is missing. "
            "Give direct, practical answers with business reasoning, and mention the dashboard section that supports the answer when possible."
        )
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Dashboard context:\n{context}\n\nQuestion:\n{question}"},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI request failed: {e}\n\nFallback answer: {local_answer(question, context)}"


def _p(text: Any, style) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>") if text is not None else "", style)


def _bullet_list(items: List[str], style, max_items: int = 12) -> List[Any]:
    body: List[Any] = []
    if not items:
        body.append(_p("No items available for the current dashboard view.", style))
        return body
    for item in items[:max_items]:
        body.append(_p(f"- {item}", style))
    return body


def top_correlation_pairs(df: pd.DataFrame, numeric_cols: List[str], max_pairs: int = 5) -> List[str]:
    if len(numeric_cols) < 2 or df.empty:
        return []
    corr = df[numeric_cols].corr(numeric_only=True)
    pairs: List[Tuple[float, str, str]] = []
    for i, c1 in enumerate(corr.columns):
        for c2 in corr.columns[i+1:]:
            val = corr.loc[c1, c2]
            if pd.notna(val):
                pairs.append((abs(float(val)), c1, c2))
    pairs.sort(reverse=True)
    return [f"{c1} vs {c2}: correlation {corr.loc[c1, c2]:.2f}" for _, c1, c2 in pairs[:max_pairs]]


def generate_pdf_report(
    summary: Dict[str, Any],
    insights: List[str],
    report: Dict[str, Any],
    alerts: List[str],
    df: Optional[pd.DataFrame] = None,
    metric_col: Optional[str] = None,
    category_col: Optional[str] = None,
    time_col: Optional[str] = None,
    unit_col: Optional[str] = None,
    active_filters: Optional[List[str]] = None,
    numeric_cols: Optional[List[str]] = None,
) -> Optional[bytes]:
    """Generate a full PDF that explains the dashboard pages and visuals, not just Q&A."""
    if not REPORTLAB_AVAILABLE:
        return None
    df = df.copy() if df is not None else pd.DataFrame()
    numeric_cols = numeric_cols or []
    active_filters = active_filters or ["No active filters - all cleaned rows are included."]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=1.1*cm, bottomMargin=1.1*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=22, leading=26, textColor=colors.HexColor("#111827"), spaceAfter=12)
    h_style = ParagraphStyle("HeaderCustom", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#0369a1"), spaceBefore=12, spaceAfter=7)
    h3_style = ParagraphStyle("SubHeaderCustom", parent=styles["Heading3"], fontSize=11.5, leading=15, textColor=colors.HexColor("#111827"), spaceBefore=7, spaceAfter=4)
    body_style = ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontSize=9.2, leading=12.3, textColor=colors.HexColor("#111827"), spaceAfter=4)
    small_style = ParagraphStyle("SmallCustom", parent=styles["BodyText"], fontSize=8.2, leading=10.5, textColor=colors.HexColor("#475467"), spaceAfter=3)

    story: List[Any] = []
    story.append(_p("Universal Data Analyzer Pro - Dashboard Explanation Report", title_style))
    story.append(_p(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", small_style))
    story.append(_p("This report explains what the dashboard found, what each page means, and how each visual should be interpreted from the current filtered view.", body_style))
    story.append(Spacer(1, 10))

    # KPI summary table
    story.append(_p("1. Current Dashboard Snapshot", h_style))
    table_data = [[_p("Metric", body_style), _p("Value", body_style)]] + [[_p(k, body_style), _p(v, body_style)] for k, v in summary.items()]
    table = Table(table_data, colWidths=[6.7*cm, 8.7*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(table)
    story.append(_p("Active filters", h3_style))
    story.extend(_bullet_list(active_filters, small_style, max_items=12))

    story.append(_p("2. Executive Business Summary", h_style))
    story.extend(_bullet_list(insights, body_style, max_items=12))
    if alerts:
        story.append(_p("Critical alerts", h3_style))
        story.extend(_bullet_list(alerts, body_style, max_items=8))

    # Cleaning page explanation
    story.append(PageBreak())
    story.append(_p("3. Page-by-Page Dashboard Explanation", h_style))
    story.append(_p("Page 1 - Cleaning & Quality", h3_style))
    story.append(_p("This page validates whether the dataset is reliable enough for business decisions. It shows the Data Quality Score, rows removed, duplicate rows, missing values, type corrections, and outlier detection. The goal is to prevent decisions based on inflated, incomplete, or inconsistent data.", body_style))
    dq = [
        ["Data quality score", f"{report.get('data_quality_score', 'N/A')}/100"],
        ["Original rows", str(report.get("original_rows", "N/A"))],
        ["Cleaned rows", str(report.get("cleaned_rows", "N/A"))],
        ["Duplicates removed", str(report.get("duplicate_rows_removed", 0))],
        ["Missing cells", str(report.get("missing_total", 0))],
        ["Outlier points", str(report.get("outlier_total", 0))],
    ]
    dq_table = Table([[ _p("Check", body_style), _p("Result", body_style) ]] + [[_p(a, small_style), _p(b, small_style)] for a,b in dq], colWidths=[7.3*cm, 8.1*cm])
    dq_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]))
    story.append(dq_table)

    # Overview
    story.append(_p("Page 2 - Executive Overview", h3_style))
    if metric_col and metric_col in df.columns:
        total = format_number(df[metric_col].sum())
        story.append(_p(f"This page answers the first management question: what happened overall? The main KPI total for {metric_col} is {total}. The page also shows either a time trend or a distribution chart, plus ranking by the selected primary category.", body_style))
        if category_col and category_col in df.columns and not df.empty:
            ranking = df.groupby(category_col, dropna=False)[metric_col].sum().sort_values(ascending=False)
            if not ranking.empty:
                top = ranking.index[0]
                top_val = ranking.iloc[0]
                share = top_val / ranking.sum() if ranking.sum() else np.nan
                story.append(_p(f"Top contributor: {top} with {format_number(top_val)} ({share:.1%} of current filtered total).", body_style))
        if time_col and time_col in df.columns:
            trend = aggregate_by_time(df, time_col, metric_col)
            if not trend.empty:
                best = trend.loc[trend[metric_col].idxmax()]
                story.append(_p(f"Strongest period in the trend: {best[time_col]} with {format_number(best[metric_col])}.", body_style))
    else:
        story.append(_p("This page needs a numeric main metric to produce KPI totals, trends, and rankings.", body_style))

    # Deep analysis
    story.append(_p("Page 3 - Deep Analysis", h3_style))
    story.append(_p("This page explains relationships and unusual patterns. The scatter plot compares two numeric measures, the correlation heatmap shows which metrics move together, anomaly detection flags unusual records, and benchmarking ranks categories against the average and the best performer.", body_style))
    corr_pairs = top_correlation_pairs(df, numeric_cols, max_pairs=5)
    if corr_pairs:
        story.append(_p("Strongest visible metric relationships", h3_style))
        story.extend(_bullet_list(corr_pairs, small_style, max_items=5))
    anomalies = compute_anomalies(df, numeric_cols)
    story.append(_p(f"Anomaly detection found {len(anomalies)} strong z-score anomaly rows in the current view.", body_style))

    # Forecast page
    story.append(PageBreak())
    story.append(_p("Page 4 - Forecast & What-if", h3_style))
    if metric_col and time_col and metric_col in df.columns and time_col in df.columns:
        trend = aggregate_by_time(df, time_col, metric_col)
        if len(trend) >= 2:
            forecast_values, r2 = simple_forecast(trend[metric_col], periods=6)
            story.append(_p(f"The forecast page estimates the next periods for {metric_col} using a simple trend model. The current trend fit R² is {r2:.2f}. This forecast is indicative, not a final planning forecast, because reliability improves with more historical periods, targets, campaigns, and seasonality data.", body_style))
            story.append(_p("Next forecast values", h3_style))
            forecast_rows = [[_p("Forecast period", small_style), _p("Expected value", small_style)]]
            for i, v in enumerate(forecast_values, 1):
                forecast_rows.append([_p(f"Forecast {i}", small_style), _p(format_number(v), small_style)])
            ft = Table(forecast_rows, colWidths=[7.3*cm, 8.1*cm])
            ft.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]))
            story.append(ft)
        else:
            story.append(_p("Forecasting needs at least two time periods after filtering.", body_style))
    else:
        story.append(_p("Forecasting needs both a selected main metric and a valid time column.", body_style))
    story.append(_p("The what-if section lets management test how performance changes if the selected metric increases or decreases. It is useful for target planning, branch improvement scenarios, and estimating the impact of upselling.", body_style))

    # Comparison and AI
    story.append(_p("Page 5 - Comparison Mode", h3_style))
    story.append(_p("This page compares selected categories, such as branches, products, services, segments, or regions. If a time column is available, it shows how each selected category performs over time. This helps detect consistent performers, declining performers, and categories that require intervention.", body_style))
    story.append(_p("Page 6 - AI Chat", h3_style))
    story.append(_p("The AI Chat answers natural-language questions in the user's language using summarized dashboard context. The API key is stored in Streamlit Secrets and is not exposed in the frontend. The chat should be used to explain the dashboard, identify risks, and translate insights into business actions.", body_style))
    story.append(_p("Page 7 - Executive PDF", h3_style))
    story.append(_p("This page exports the current dashboard view into a PDF report. The report reflects the current filters, selected metric, selected category, cleaning results, alerts, trends, and dashboard interpretation.", body_style))

    # Recommendations
    story.append(_p("4. Recommended Next Actions", h_style))
    recommendations = [
        "Validate column definitions before using the numbers for incentives or official performance decisions.",
        "Use the Data Quality page before presenting results; missing values, duplicates, and outliers can change the story.",
        "Use the Executive Overview to identify the strongest contributors, then investigate their practices for replication.",
        "Use the Deep Analysis page to identify relationships between value, volume, and other performance metrics.",
        "Treat the forecast as directional unless the dataset contains enough historical periods and target/campaign context.",
        "Use Comparison Mode to review month-over-month or branch-over-branch changes before taking action.",
    ]
    story.extend(_bullet_list(recommendations, body_style, max_items=10))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def alert_system(df: pd.DataFrame, report: Dict[str, Any], metric_col: Optional[str], category_col: Optional[str]) -> List[str]:
    alerts: List[str] = []
    score = report.get("data_quality_score", 100)
    if score < 70:
        alerts.append(f"Data quality score is {score}/100, which may reduce confidence in business decisions.")
    if report.get("duplicate_rows_detected", 0) > 0:
        alerts.append(f"{report['duplicate_rows_detected']} duplicate rows were detected. Duplicates can overstate totals.")
    if report.get("missing_pct", 0) > 0.1:
        alerts.append(f"Missing values represent {report['missing_pct']:.1%} of cells. Missing data should be reviewed before final reporting.")
    if report.get("outlier_total", 0) > 0:
        alerts.append(f"{report['outlier_total']} outlier points were detected. Review them before using the results for incentives or targets.")
    if metric_col and category_col and metric_col in df.columns and category_col in df.columns:
        r = df.groupby(category_col)[metric_col].sum().sort_values(ascending=False)
        if len(r) >= 3 and r.sum() != 0:
            share = r.head(1).sum() / r.sum()
            if share > 0.45:
                alerts.append(f"The top {category_col} contributes {share:.1%} of {metric_col}; performance is concentrated and may be risky.")
    return alerts

# -----------------------------
# Sidebar: data source
# -----------------------------
st.markdown('<div class="main-title">Universal Data Analyzer Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Smart cleaning, deep analytics, forecasting, reporting, and secure multilingual AI chat with Groq via Streamlit Secrets.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("1) Data Source")
    uploaded = st.file_uploader("Upload CSV / Excel", type=["csv", "xlsx", "xls"])
    use_sample = st.checkbox("Load sample branch-sales data", value=uploaded is None)
    remove_dupes = st.checkbox("Remove duplicate rows", value=True)

raw_sheets: Dict[str, pd.DataFrame] = {}
skipped_sheets: List[str] = []
load_errors: List[str] = []

if uploaded is not None:
    raw_sheets, skipped_sheets, load_errors = read_input_file(uploaded)
elif use_sample:
    raw_sheets = {"Sample_Branch_Sales": load_sample_data()}

if load_errors:
    for e in load_errors:
        st.error(e)

if not raw_sheets:
    st.info("Upload a CSV/Excel file or enable the sample data from the sidebar.")
    st.stop()

with st.sidebar:
    sheet_name = st.selectbox("Choose data sheet", list(raw_sheets.keys()))
    if skipped_sheets:
        with st.expander("Skipped metadata/log sheets"):
            st.write(skipped_sheets)

raw_df = raw_sheets[sheet_name]
clean_df, cleaning_report = clean_dataframe(raw_df, remove_duplicates=remove_dupes)
columns_info = detect_columns(clean_df)

with st.sidebar:
    st.header("2) Analysis Setup")
    numeric_cols = columns_info["numeric"]
    categorical_cols = columns_info["categorical"]
    date_cols = columns_info["date"]
    metric_col = st.selectbox("Main metric", numeric_cols, index=numeric_cols.index(columns_info["metric_default"]) if columns_info["metric_default"] in numeric_cols else 0) if numeric_cols else None
    unit_col = st.selectbox("Units / volume metric", ["None"] + numeric_cols, index=(numeric_cols.index(columns_info["units_default"]) + 1 if columns_info["units_default"] in numeric_cols else 0)) if numeric_cols else "None"
    unit_col = None if unit_col == "None" else unit_col
    category_options = categorical_cols + date_cols
    category_col = st.selectbox("Primary category", ["None"] + category_options, index=(category_options.index(columns_info["category_default"]) + 1 if columns_info["category_default"] in category_options else 0)) if category_options else "None"
    category_col = None if category_col == "None" else category_col
    time_options = date_cols + columns_info["month_like"]
    time_options = list(dict.fromkeys([c for c in time_options if c in clean_df.columns]))
    time_col = st.selectbox("Time column", ["None"] + time_options, index=(time_options.index(columns_info["time_default"]) + 1 if columns_info["time_default"] in time_options else 0)) if time_options else "None"
    time_col = None if time_col == "None" else time_col

    st.header("3) Smart Filters")
    filters: Dict[str, Any] = {"categorical": {}, "numeric": {}, "date": None}

    auto_cats = smart_filter_columns(clean_df, categorical_cols, category_col, time_col)
    auto_nums = smart_numeric_filter_columns(numeric_cols, metric_col, unit_col)
    if auto_cats:
        st.caption("Auto-detected filters: " + ", ".join(auto_cats))
    else:
        st.caption("No strong categorical filters were detected automatically. You can add filters manually below.")

    filter_cats = st.multiselect(
        "Categorical filters",
        categorical_cols,
        default=auto_cats,
        help="The app auto-selects useful slicers such as Branch, Month, Product, Service, Region, Status, Channel, or Segment."
    )
    for col in filter_cats:
        raw_values = clean_df[col].dropna().astype(str).unique().tolist()
        values = ["All"] + sort_filter_values(raw_values)[:500]
        selected = st.multiselect(f"Filter {col} ({len(raw_values)} values)", values, default=["All"])
        filters["categorical"][col] = selected

    numeric_filter_cols = st.multiselect(
        "Numeric range filters",
        numeric_cols,
        default=auto_nums,
        help="Optional range sliders for metrics such as Sales, Value, Revenue, Units, Quantity, or Count."
    )
    for col in numeric_filter_cols:
        series = clean_df[col].dropna()
        if series.empty:
            continue
        min_v, max_v = float(series.min()), float(series.max())
        if min_v == max_v:
            continue
        rng = st.slider(
            f"Filter range for {col}",
            min_value=min_v,
            max_value=max_v,
            value=(min_v, max_v),
            step=(max_v - min_v) / 100 if max_v != min_v else 1.0,
            format="%.2f"
        )
        # Keep full-range sliders informational only; apply only if user narrows them.
        if rng[0] > min_v or rng[1] < max_v:
            filters["numeric"][col] = rng

    if date_cols:
        date_filter_col = st.selectbox("Date filter column", ["None"] + date_cols, index=1 if len(date_cols) > 0 else 0)
        if date_filter_col != "None":
            min_d, max_d = clean_df[date_filter_col].min(), clean_df[date_filter_col].max()
            start, end = st.date_input("Date range", value=(min_d.date(), max_d.date()))
            filters["date"] = (date_filter_col, start, end)

filtered_df = apply_filters(clean_df, filters)
active_filter_summary = describe_active_filters(filters)
insights = compute_insights(filtered_df, metric_col, category_col, time_col, unit_col)
alerts = alert_system(filtered_df, cleaning_report, metric_col, category_col)

# -----------------------------
# KPI row
# -----------------------------
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    kpi_card("Rows", f"{filtered_df.shape[0]:,}", "After cleaning and filters")
with col2:
    kpi_card("Columns", f"{filtered_df.shape[1]:,}", "Detected analytical fields")
with col3:
    val = format_number(filtered_df[metric_col].sum()) if metric_col else "N/A"
    kpi_card("Main Metric Total", val, metric_col or "No numeric metric")
with col4:
    top_label = "N/A"
    if metric_col and category_col and not filtered_df.empty:
        temp = filtered_df.groupby(category_col)[metric_col].sum().sort_values(ascending=False)
        if not temp.empty:
            top_label = str(temp.index[0])[:26]
    kpi_card("Top Contributor", top_label, category_col or "No category selected")
with col5:
    score = cleaning_report.get("data_quality_score", 0)
    kpi_card("Data Quality", f"{score}/100", "Cleaning score")

with st.expander("Current smart filters", expanded=False):
    for item in active_filter_summary:
        st.write("• " + item)

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs([
    "Cleaning & Quality",
    "Executive Overview",
    "Deep Analysis",
    "Forecast & What-if",
    "Comparison Mode",
    "AI Chat",
    "Full Dashboard PDF",
])

with tabs[0]:
    st.markdown('<div class="section-header">Cleaning & Data Quality Report</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cleaning_report.get("data_quality_score", 0),
            title={"text": "Data Quality Score"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#0f62fe"}, "steps": [
                {"range": [0, 60], "color": "#fee2e2"},
                {"range": [60, 80], "color": "#fef3c7"},
                {"range": [80, 100], "color": "#dcfce7"},
            ]},
        ))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.write("**Before / After Cleaning**")
        st.dataframe(pd.DataFrame([
            ["Original rows", cleaning_report["original_rows"]],
            ["Cleaned rows", cleaning_report["cleaned_rows"]],
            ["Original columns", cleaning_report["original_columns"]],
            ["Cleaned columns", cleaning_report["cleaned_columns"]],
            ["Empty rows removed", cleaning_report["empty_rows_removed"]],
            ["Empty columns removed", cleaning_report["empty_columns_removed"]],
            ["Duplicates detected", cleaning_report["duplicate_rows_detected"]],
            ["Duplicates removed", cleaning_report["duplicate_rows_removed"]],
            ["Missing cells", cleaning_report["missing_total"]],
            ["Outlier points", cleaning_report["outlier_total"]],
        ], columns=["Check", "Result"]), use_container_width=True, hide_index=True)

    if alerts:
        st.markdown("**Critical Alerts**")
        for a in alerts:
            st.markdown(f'<div class="warning-card">{a}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ok-card">No critical alerts detected in the current view.</div>', unsafe_allow_html=True)

    c3, c4 = st.columns([1, 1])
    with c3:
        st.write("**Missing Values by Column**")
        missing_df = pd.DataFrame(list(cleaning_report.get("missing_by_column", {}).items()), columns=["Column", "Missing Values"])
        if missing_df.empty:
            st.success("No missing values detected.")
        else:
            st.dataframe(missing_df, use_container_width=True, hide_index=True)
    with c4:
        st.write("**Outlier Detection**")
        out_df = pd.DataFrame(cleaning_report.get("outliers", []))
        if out_df.empty:
            st.success("No major IQR outliers detected.")
        else:
            st.dataframe(out_df, use_container_width=True, hide_index=True)

    st.write("**Column Type Corrections**")
    st.write({
        "Converted to numeric": cleaning_report.get("converted_numeric_columns", []),
        "Converted to date": cleaning_report.get("converted_date_columns", []),
    })
    st.write("**Cleaned Data Preview**")
    st.dataframe(filtered_df.head(200), use_container_width=True)
    csv_bytes = filtered_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Download cleaned filtered CSV", csv_bytes, "cleaned_filtered_data.csv", "text/csv")

with tabs[1]:
    st.markdown('<div class="section-header">Executive Overview</div>', unsafe_allow_html=True)
    if not metric_col:
        st.warning("Select a numeric main metric from the sidebar.")
    else:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            if time_col and time_col in filtered_df.columns:
                trend = aggregate_by_time(filtered_df, time_col, metric_col)
                fig = px.line(trend, x=time_col, y=metric_col, markers=True, title=f"{metric_col} Trend")
                st.plotly_chart(fig, use_container_width=True)
            else:
                fig = px.histogram(filtered_df, x=metric_col, nbins=25, title=f"Distribution of {metric_col}")
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("**Auto-Generated Insights**")
            for item in insights:
                st.markdown(f'<div class="insight-card">{item}</div>', unsafe_allow_html=True)

        if category_col and category_col in filtered_df.columns:
            ranking = filtered_df.groupby(category_col, dropna=False)[metric_col].sum().sort_values(ascending=False).head(15).reset_index()
            fig = px.bar(ranking, x=metric_col, y=category_col, orientation="h", title=f"Top {category_col} by {metric_col}")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(ranking, use_container_width=True, hide_index=True)

with tabs[2]:
    st.markdown('<div class="section-header">Deep Analysis</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        if len(numeric_cols) >= 2:
            x_col = st.selectbox("Scatter X", numeric_cols, index=0)
            y_col = st.selectbox("Scatter Y", numeric_cols, index=1 if len(numeric_cols) > 1 else 0)
            color_col = category_col if category_col in filtered_df.columns else None
            fig = px.scatter(filtered_df, x=x_col, y=y_col, color=color_col, hover_data=[category_col] if category_col else None, title=f"{x_col} vs {y_col}")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Need at least two numeric columns for scatter analysis.")
    with c2:
        if len(numeric_cols) >= 2:
            corr = filtered_df[numeric_cols].corr(numeric_only=True)
            fig = px.imshow(corr, text_auto=True, title="Correlation Heatmap")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Need at least two numeric columns for correlation analysis.")

    c3, c4 = st.columns([1, 1])
    with c3:
        st.write("**Anomaly Detection**")
        anomalies = compute_anomalies(filtered_df, numeric_cols)
        if anomalies.empty:
            st.success("No strong z-score anomalies detected.")
        else:
            st.dataframe(anomalies.head(100), use_container_width=True, hide_index=True)
    with c4:
        st.write("**Benchmarking**")
        if metric_col and category_col:
            bench = filtered_df.groupby(category_col, dropna=False)[metric_col].agg(["sum", "mean", "count"]).reset_index()
            avg_sum = bench["sum"].mean()
            best_sum = bench["sum"].max()
            bench["vs_average_%"] = np.where(avg_sum != 0, (bench["sum"] - avg_sum) / avg_sum, np.nan)
            bench["vs_best_%"] = np.where(best_sum != 0, bench["sum"] / best_sum, np.nan)
            bench = bench.sort_values("sum", ascending=False)
            st.dataframe(bench, use_container_width=True, hide_index=True)
        else:
            st.info("Select main metric and category to enable benchmarking.")

with tabs[3]:
    st.markdown('<div class="section-header">Forecast & What-if Scenarios</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.2, 1])
    with c1:
        periods = st.slider("Forecast periods", 1, 12, 6)
        if metric_col and time_col and time_col in filtered_df.columns:
            trend = aggregate_by_time(filtered_df, time_col, metric_col)
            forecast_values, r2 = simple_forecast(trend[metric_col], periods=periods)
            future_labels = [f"Forecast {i+1}" for i in range(periods)]
            actual = pd.DataFrame({"Period": trend[time_col].astype(str), "Value": trend[metric_col], "Type": "Actual"})
            future = pd.DataFrame({"Period": future_labels, "Value": forecast_values, "Type": "Forecast"})
            chart_df = pd.concat([actual, future], ignore_index=True)
            fig = px.line(chart_df, x="Period", y="Value", color="Type", markers=True, title=f"Forecast for {metric_col}")
            st.plotly_chart(fig, use_container_width=True)
            st.info(f"Forecast is indicative. Simple trend fit R² = {r2:.2f}. More months improve reliability.")
        else:
            st.warning("Select both a main metric and a time column to enable forecasting.")
    with c2:
        st.write("**What-if Scenario**")
        if metric_col:
            pct = st.slider("Change selected metric by", -50, 100, 10, step=5)
            current_total = filtered_df[metric_col].sum()
            scenario_total = current_total * (1 + pct / 100)
            impact = scenario_total - current_total
            st.metric("Current total", format_number(current_total))
            st.metric("Scenario total", format_number(scenario_total), delta=format_number(impact))
            st.markdown(f"If **{metric_col}** changes by **{pct}%**, the total changes by **{format_number(impact)}**.")
        else:
            st.info("Select a numeric metric first.")

    if category_col and metric_col:
        st.write("**Scenario by Category**")
        scenario_category = st.selectbox("Apply scenario to one category", ["All"] + sorted(filtered_df[category_col].dropna().astype(str).unique().tolist()))
        pct2 = st.slider("Category-level change", -50, 100, 15, step=5, key="cat_scenario_pct")
        base = filtered_df.copy()
        if scenario_category != "All":
            mask = base[category_col].astype(str) == scenario_category
            base.loc[mask, "_Scenario_Value"] = base.loc[mask, metric_col] * (1 + pct2/100)
            base.loc[~mask, "_Scenario_Value"] = base.loc[~mask, metric_col]
        else:
            base["_Scenario_Value"] = base[metric_col] * (1 + pct2/100)
        st.metric("Scenario impact", format_number(base["_Scenario_Value"].sum() - base[metric_col].sum()))

with tabs[4]:
    st.markdown('<div class="section-header">Comparison Mode</div>', unsafe_allow_html=True)
    if category_col and metric_col:
        values = sorted(filtered_df[category_col].dropna().astype(str).unique().tolist())
        selected_values = st.multiselect(f"Compare {category_col}", values, default=values[:2])
        comp_df = filtered_df[filtered_df[category_col].astype(str).isin(selected_values)] if selected_values else filtered_df
        if time_col and time_col in comp_df.columns:
            comp = comp_df.groupby([category_col, time_col], dropna=False)[metric_col].sum().reset_index()
            if not pd.api.types.is_datetime64_any_dtype(comp[time_col]):
                comp["_sort"] = comp[time_col].apply(month_sort_key)
                comp = comp.sort_values("_sort").drop(columns="_sort")
            fig = px.line(comp, x=time_col, y=metric_col, color=category_col, markers=True, title=f"{category_col} Comparison Over Time")
            st.plotly_chart(fig, use_container_width=True)
        comp_summary = comp_df.groupby(category_col, dropna=False)[metric_col].agg(["sum", "mean", "count"]).sort_values("sum", ascending=False).reset_index()
        st.dataframe(comp_summary, use_container_width=True, hide_index=True)
    else:
        st.info("Select a main metric and a category to enable comparison mode.")

with tabs[5]:
    st.markdown('<div class="section-header">Secure Multilingual AI Chat</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="insight-card">
The API key is read from <b>Streamlit Secrets</b>, not from the frontend. The chat receives a summarized analytical context, not the full raw dataset.
</div>
""",
        unsafe_allow_html=True,
    )
    if "chat_count" not in st.session_state:
        st.session_state.chat_count = 0
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    limit = int(get_secret("CHAT_QUESTION_LIMIT", 30) or 30)
    st.caption(f"Session questions used: {st.session_state.chat_count}/{limit}")
    context = generate_context(filtered_df, cleaning_report, metric_col, category_col, time_col, unit_col, insights)

    suggested = [
        "What is the main business story in this dataset?",
        "Which branch or category is the strongest performer and why?",
        "ما أهم مشاكل جودة البيانات هنا؟",
        "What should management do next based on the dashboard?",
        "هل التوقع موثوق؟ وما الذي ينقصه؟",
    ]
    with st.expander("Suggested questions"):
        for s in suggested:
            st.write("• " + s)

    question = st.text_area("Ask any question about the current dashboard view", height=100, placeholder="Ask in Arabic, English, or any language...")
    if st.button("Ask AI", type="primary"):
        if not question.strip():
            st.warning("Write a question first.")
        elif st.session_state.chat_count >= limit:
            st.error("Session question limit reached. Refresh the app or increase CHAT_QUESTION_LIMIT in Secrets.")
        else:
            with st.spinner("Analyzing..."):
                answer = ask_groq(question.strip(), context)
            st.session_state.chat_count += 1
            st.session_state.chat_history.append((question.strip(), answer))

    for q, a in reversed(st.session_state.chat_history[-10:]):
        st.markdown(f"**Q:** {q}")
        st.markdown(f"**A:** {a}")
        st.divider()

with tabs[6]:
    st.markdown('<div class="section-header">Full Dashboard Explanation PDF</div>', unsafe_allow_html=True)
    summary_dict = {
        "Rows analyzed": f"{filtered_df.shape[0]:,}",
        "Columns analyzed": f"{filtered_df.shape[1]:,}",
        "Main metric": metric_col or "N/A",
        "Main metric total": format_number(filtered_df[metric_col].sum()) if metric_col else "N/A",
        "Primary category": category_col or "N/A",
        "Data quality score": f"{cleaning_report.get('data_quality_score', 'N/A')}/100",
        "Duplicate rows removed": str(cleaning_report.get("duplicate_rows_removed", 0)),
        "Missing cells": str(cleaning_report.get("missing_total", 0)),
        "Outlier points": str(cleaning_report.get("outlier_total", 0)),
        "Active filters": "; ".join(active_filter_summary[:5]),
    }
    st.write("This PDF explains the current dashboard view, filters, cleaning results, visuals, insights, forecast, and recommendations.")
    st.dataframe(pd.DataFrame(list(summary_dict.items()), columns=["Item", "Value"]), use_container_width=True, hide_index=True)
    if REPORTLAB_AVAILABLE:
        pdf_bytes = generate_pdf_report(
            summary_dict,
            insights,
            cleaning_report,
            alerts,
            df=filtered_df,
            metric_col=metric_col,
            category_col=category_col,
            time_col=time_col,
            unit_col=unit_col,
            active_filters=active_filter_summary,
            numeric_cols=numeric_cols,
        )
        if pdf_bytes:
            st.download_button("Download Full Dashboard Report PDF", pdf_bytes, "dashboard_explanation_report.pdf", "application/pdf")
    else:
        st.warning("PDF export needs reportlab. Add reportlab to requirements.txt or install it locally.")

    st.write("**Raw dashboard context sent to AI**")
    with st.expander("Show summarized context"):
        st.text(generate_context(filtered_df, cleaning_report, metric_col, category_col, time_col, unit_col, insights))

