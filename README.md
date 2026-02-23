# 🔗 SQL Lineage Tracker

A super simple, visual way to understand your SQL data flow.

Ever looked at a massive folder of SQL files and wondered, *"Wait, which table feeds into which?"* or *"If I change this column, what breaks downstream?"*

**SQL Lineage Tracker** figures that out for you. You just point it at your SQL files, and it pops open a beautiful, interactive graph in your browser showing exactly how your tables and columns connect.

---

## ✨ Why use it?

- **It's visual:** No more reading thousands of lines of code to understand the architecture.
- **Column-level tracking:** It doesn't just show table dependencies. It shows exactly how every single column is created (e.g., `SUM(amount) AS total`).
- **Supports everything:** Works with PostgreSQL, MySQL, Snowflake, BigQuery, Databricks, and 15+ other dialects.
- **Instant web UI:** Runs a gorgeous dark-mode web app locally on your machine.
- **Private:** Processes everything locally. No data leaves your computer.

## 🚀 How to use it

### 1. Install it
Just install it using pip:

```bash
pip install sqllineage-tracker
```

### 2. Run the Web App (Easiest Way)
The best way to use the tracker is through the built-in web interface:

```bash
sqllineage serve
```

1. Open [http://localhost:8000](http://localhost:8000) in your browser.
2. Drag and drop your `.sql` files into the upload box.
3. Turn on **Column-level lineage** in the settings.
4. Click **Analyze Lineage**!

### 3. Or... Use the CLI
If you just want a quick terminal output, you can run the analyzer directly from the command line:

```bash
# See how your ecommerce tables connect
sqllineage analyze examples/ecommerce/*.sql

# Include column-level details in the output
sqllineage analyze examples/ecommerce/*.sql --columns

# If you use a specific dialect, let it know (e.g., snowflake, bigquery, postgres)
sqllineage analyze my_query.sql --dialect postgres
```

---

## 💻 Running the Examples

Want to see what it looks like before trying it on your own code? Clone this repo and run it on our example files!

```bash
git clone https://github.com/Shammyhero/sql-lineage-tracker.git
cd sql-lineage-tracker

sqllineage serve
```
Then upload the files from the `examples/ecommerce/` folder into the web interface.

---

## 🛠️ For Developers

Want to use the lineage engine inside your own Python script?

```python
from sqllineage import resolve_files

# Parse files and build the dependency graph
graph = resolve_files(["file1.sql", "file2.sql"], dialect="postgres")

# See what relies on this table
print(graph.get_downstream("raw.users"))
```

## 📜 License
MIT License. Do whatever you want with it!
