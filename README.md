# Universal Data Analyzer Pro — Streamlit + Groq

This is a Streamlit web app for smart data analysis. It supports Excel/CSV upload, automatic data cleaning, deep analysis, forecasting, PDF summary export, and multilingual AI chat using Groq API through Streamlit Secrets.

## Main Features

### Data Cleaning
- Auto-detects and skips metadata/log sheets such as removal logs and notes.
- Removes empty rows and empty columns.
- Converts text-based numbers into numeric columns.
- Detects date/month columns.
- Removes duplicate rows.
- Detects missing values.
- Detects outliers using IQR.
- Produces a Data Quality Score from 0 to 100.
- Shows a Before/After cleaning report.

### Deep Analytics
- KPI cards.
- Trend analysis.
- Top category ranking.
- Correlation analysis.
- Anomaly detection.
- Benchmarking against average and best performer.
- Scatter analysis.
- Comparison mode.
- Forecasting.
- What-if scenarios.
- Auto-generated business insights.
- Critical alerts.

### AI Chat
- Uses Groq API securely through Streamlit Secrets.
- The API key is not stored in the frontend.
- The chat answers in the same language as the user's question.
- The app sends a summarized dashboard context to the model, not the full raw dataset.
- Includes a per-session question limit.

---

## Local Setup

1. Install Python 3.10+.
2. Open this folder in VS Code or terminal.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a local secrets file:

```text
.streamlit/secrets.toml
```

You can copy the example file:

```text
.streamlit/secrets.toml.example
```

5. Add your Groq key:

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL = "llama-3.3-70b-versatile"
APP_PASSWORD = "team123"
CHAT_QUESTION_LIMIT = 30
```

6. Run the app:

```bash
streamlit run app.py
```

7. Open the local URL shown in the terminal.

---

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload these files:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `.gitignore`
   - `data/sample_branch_sales.csv`

3. Do **not** upload `.streamlit/secrets.toml`.
4. Go to Streamlit Community Cloud.
5. Create a new app from your GitHub repo.
6. Open app settings, then Secrets.
7. Paste:

```toml
GROQ_API_KEY = "gsk_your_key_here"
GROQ_MODEL = "llama-3.3-70b-versatile"
APP_PASSWORD = "team123"
CHAT_QUESTION_LIMIT = 30
```

8. Save and redeploy.
9. Share the Streamlit app link with the team.

---

## Team Testing

The team only needs the Streamlit app link and password.
They do not need the Groq API key.
The key stays inside Streamlit Secrets.

Recommended workflow:

1. Open the app link.
2. Enter the password.
3. Upload Excel/CSV.
4. Review Cleaning & Quality first.
5. Select main metric, category, and time column from the sidebar.
6. Review Overview, Deep Analysis, Forecast, and Comparison.
7. Ask the AI Chat questions in Arabic or English.
8. Download the Executive Summary PDF.

---

## Security Notes

- Never put the Groq key inside `app.py`.
- Never upload `.streamlit/secrets.toml` to GitHub.
- Use a project-specific Groq key.
- Use `APP_PASSWORD` to prevent random visitors from using your app.
- Use `CHAT_QUESTION_LIMIT` to avoid unnecessary usage or rate-limit errors.
- After the project, revoke/delete the Groq key if needed.

---

## Suggested AI Questions

- What is the main business story in this dataset?
- Which branch is the strongest performer and why?
- Which services or products drive most of the value?
- What are the main data quality issues?
- What should management do next?
- هل التوقع موثوق؟ وما البيانات الناقصة لتحسينه؟
- ما أهم المشاكل التي قد تؤثر على القرار الإداري؟

---

## Discussion Answer

If asked how the AI is connected:

> The AI chat is connected through Groq API using Streamlit Secrets. The API key is not exposed in the frontend or source code. The app sends summarized analytical context to the model instead of raw full data, which makes the chat faster, safer, and more focused on business insights.
