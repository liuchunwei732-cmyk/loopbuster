"""
tool_lib — 工具名、参数、输出模板的集中定义。

所有模板使用 `${placeholder}` 格式，generator.py 在展开时替换。
非确定性字段（时间戳、UUID）在生成时动态注入。
"""

from __future__ import annotations

import random

# ======================================================================
# 工具名池
# ======================================================================

TOOL_NAMES = [
    "web_search",
    "web_fetch",
    "read_file",
    "write_file",
    "python_repl",
    "bash_shell",
    "list_directory",
    "api_call",
    "parse_data",
    "summarize_text",
    "search_database",
    "get_weather",
    "search_wikipedia",
    "calculate",
    "send_email",
    "read_news",
    "translate",
    "analyze_sentiment",
    "create_document",
    "get_current_time",
]

# ======================================================================
# 工具 → 常见参数模板
# key 是工具名，value 是参数模板列表
# 每个模板是一个 dict，value 中包含 ${placeholder}
# ======================================================================

ARG_TEMPLATES: dict[str, list[dict]] = {

    "web_search": [
        {"query": "${query}"},
        {"query": "${query}", "max_results": "10"},
        {"query": "${query} ${year}"},
        {"query": "${topic} vs ${related_topic}"},
        {"query": "how to ${action} in ${language}"},
        {"query": "${city} ${info_type}"},
    ],

    "web_fetch": [
        {"url": "https://en.wikipedia.org/wiki/${topic}"},
        {"url": "https://news.ycombinator.com/item?id=${id}"},
        {"url": "https://api.github.com/repos/${owner}/${repo}"},
    ],

    "read_file": [
        {"path": "/data/${filename}.${ext}"},
        {"path": "./logs/${date}/${service}.log"},
        {"path": "${project}/src/${module}.py"},
    ],

    "write_file": [
        {"path": "/output/${filename}.${ext}", "content": "${content}"},
        {"path": "./${project}/README.md", "content": "# ${project_title}\n\n${description}"},
    ],

    "python_repl": [
        {"code": "import ${library}\nprint(${library}.__version__)"},
        {"code": "${operation}('${dataset}')"},
        {"code": "print(${expression})"},
        {"code": "import pandas as pd\ndf = pd.${method}('${file}')\ndf.head()"},
    ],

    "bash_shell": [
        {"command": "ls -la ${directory}"},
        {"command": "grep -r '${pattern}' ${directory}"},
        {"command": "cat ${filepath}"},
        {"command": "python ${script}.py --input ${input_file} --output ${output_file}"},
    ],

    "list_directory": [
        {"path": "${directory}"},
        {"path": "${directory}", "recursive": "true"},
    ],

    "api_call": [
        {"url": "https://api.${service}.com/v1/${endpoint}", "method": "GET"},
        {"url": "https://api.${service}.com/v1/${endpoint}", "method": "POST", "body": "${payload}"},
    ],

    "parse_data": [
        {"text": "${text}", "format": "${format_type}"},
        {"data": "${data}", "extract": "${field}"},
    ],

    "summarize_text": [
        {"text": "${text}", "max_length": "${length}"},
    ],

    "search_database": [
        {"query": "SELECT * FROM ${table} WHERE ${condition}"},
        {"query": "SELECT COUNT(*) FROM ${table}"},
    ],

    "get_weather": [
        {"city": "${city}"},
        {"city": "${city}", "units": "${unit}"},
    ],

    "search_wikipedia": [
        {"query": "${topic}"},
        {"query": "${topic}", "lang": "${lang}"},
    ],

    "calculate": [
        {"expression": "${expression}"},
    ],

    "send_email": [
        {"to": "${recipient}", "subject": "${subject}", "body": "${email_body}"},
    ],

    "read_news": [
        {"category": "${category}", "count": "5"},
    ],

    "translate": [
        {"text": "${text}", "source_lang": "${source}", "target_lang": "${target}"},
    ],

    "analyze_sentiment": [
        {"text": "${text}"},
    ],

    "create_document": [
        {"title": "${title}", "content": "${content}", "format": "markdown"},
    ],

    "get_current_time": [
        {},
    ],
}

# ======================================================================
# 参数占位符的取值池
# generator.py 在展开时从此处随机取值
# ======================================================================

PLACEHOLDER_POOL: dict[str, list[str]] = {

    # --- 编程语言相关 ---
    "language": ["Python", "JavaScript", "TypeScript", "Rust", "Go", "Java", "C++", "Ruby", "Swift", "Kotlin"],
    "library": ["pandas", "numpy", "requests", "flask", "django", "torch", "transformers", "pytest", "celery", "fastapi"],
    "framework": ["React", "Vue", "Angular", "Django", "Flask", "Spring", "Rails", "Next.js", "Express"],
    "error_type": ["TypeError", "ValueError", "KeyError", "AttributeError", "IndexError", "ImportError", "RuntimeError", "ZeroDivisionError"],
    "action": ["install", "configure", "debug", "optimize", "migrate", "deploy", "test", "refactor"],
    "operation": ["analyze", "transform", "clean", "merge", "validate", "visualize", "train", "predict"],
    "expression": ["2 + 2", "sum(range(100))", "len('hello world')", "max([3, 7, 2, 9])", "sorted([5, 3, 8, 1])"],
    "script": ["train_model", "process_data", "generate_report", "backup_db", "cleanup_logs"],
    "input_file": ["data.csv", "input.json", "source.txt", "log.txt", "config.yaml"],
    "output_file": ["results.csv", "output.json", "report.md", "summary.txt"],

    # --- 搜索/内容相关 ---
    "query": [
        "how to learn Python", "best machine learning courses",
        "React vs Vue comparison", "what is Kubernetes",
        "Python async programming", "Rust memory safety",
        "distributed systems design", "clean code principles",
        "microservices architecture", "REST API best practices",
        "SQL vs NoSQL databases", "Docker compose tutorial",
        "Git branching strategies", "CI/CD pipeline setup",
        "Linux file permissions", "HTTP status codes",
    ],
    "topic": [
        "Artificial Intelligence", "Machine Learning", "Deep Learning",
        "Natural Language Processing", "Computer Vision", "Reinforcement Learning",
        "Database Systems", "Operating Systems", "Computer Networks",
        "Software Engineering", "Algorithm Design", "Data Structures",
    ],
    "related_topic": [
        "React", "Vue", "Angular", "Svelte", "Solid.js",
        "Python", "JavaScript", "Rust", "Go", "Java",
        "SQL", "NoSQL", "GraphQL", "REST", "gRPC",
    ],
    "city": [
        "Beijing", "Shanghai", "Tokyo", "London", "Paris", "New York",
        "Sydney", "Berlin", "Moscow", "Toronto", "Dubai", "Seoul",
        "Bangkok", "Singapore", "Rome", "Madrid", "San Francisco", "Amsterdam",
        "Hong Kong", "Taipei", "Osaka", "Melbourne", "Vancouver", "Mumbai",
    ],
    "info_type": ["population", "area", "weather", "history", "economy", "transportation"],
    "category": ["technology", "science", "business", "sports", "entertainment", "health", "world"],

    # --- 文件/项目相关 ---
    "filename": ["data", "config", "main", "utils", "models", "test_main", "constants", "schema"],
    "ext": ["py", "js", "ts", "json", "yaml", "csv", "md", "txt", "html", "css"],
    "directory": ["/home/user/projects", "./src", "./tests", "/var/log", "/data", "./docs", "./config"],
    "project": ["myapp", "backend", "frontend", "cli-tool", "data-pipeline", "api-service", "web-app"],
    "module": ["main", "utils", "models", "views", "controllers", "handlers", "middleware"],
    "service": ["nginx", "postgresql", "redis", "app-server", "celery-worker", "prometheus"],
    "filepath": ["/etc/config.yaml", "./.env", "package.json", "docker-compose.yml", "Makefile"],
    "project_title": ["My Project", "Data Pipeline", "API Service", "CLI Tool", "Web Application"],

    # --- 数据库相关 ---
    "table": ["users", "orders", "products", "transactions", "logs", "sessions", "analytics_events"],
    "condition": ["status = 'active'", "created_at > '2024-01-01'", "price > 100", "quantity > 0"],

    # --- API 相关 ---
    "service_name": ["github", "twitter", "slack", "discord", "stripe", "aws", "sendgrid"],
    "endpoint": ["users", "posts", "messages", "events", "search", "analyze"],
    "payload": ['{"name": "test"}', '{"id": 123}', '{"action": "start"}', '{"query": "search_term"}'],
    "owner": ["facebook", "google", "microsoft", "apple", "amazon", "netflix", "uber", "airbnb"],
    "repo": ["react", "tensorflow", "kubernetes", "pytorch", "go", "rust", "vscode", "linux"],

    # --- 文本/内容相关 ---
    "text": [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is a high-level programming language.",
        "The capital of France is Paris.",
        "Water freezes at 0 degrees Celsius.",
        "The Earth orbits around the Sun.",
        "HTTP is the foundation of data communication on the web.",
        "An algorithm is a step-by-step procedure for solving a problem.",
    ],
    "format_type": ["json", "xml", "csv", "yaml", "markdown", "html"],
    "field": ["name", "date", "price", "count", "status", "author", "title"],
    "data": ["[1, 2, 3, 4, 5]", '{"a": 1, "b": 2}', "2024-01-01,2024-01-02,2024-01-03"],
    "length": ["100", "200", "500"],

    # --- 邮件相关 ---
    "recipient": ["user@example.com", "admin@company.com", "support@service.com", "team@startup.io"],
    "subject": ["Weekly Report", "Meeting Notes", "Project Update", "Bug Report", "Feature Request"],
    "email_body": ["Please find the attached report.", "Let's schedule a meeting.", "The deployment was successful."],

    # --- 翻译/情感 ---
    "source": ["en", "zh", "ja", "ko", "fr", "de", "es"],
    "target": ["zh", "en", "ja", "fr", "de", "es", "ko"],

    # --- 其他 ---
    "content": [
        "This is a sample content for testing.",
        "Lorem ipsum dolor sit amet.",
        "Data analysis results and conclusions.",
    ],
    "description": [
        "A sample description for the project.",
        "This project handles data processing tasks.",
    ],
    "title": ["Analysis Report", "Meeting Summary", "Project Proposal", "Technical Documentation"],
    "year": ["2024", "2025", "2026"],
    "date": ["2024-01-15", "2024-06-30", "2025-03-20", "2025-11-08", "2026-02-14"],
    "unit": ["celsius", "fahrenheit"],
    "dataset": ["iris.csv", "titanic.csv", "sales_data.csv", "user_behavior.csv", "stock_prices.csv"],
    "method": ["read_csv", "read_excel", "read_json", "read_sql"],
    "id": ["12345", "67890", "11223", "44556", "78901"],
    "lang": ["en", "zh", "ja", "fr"],
    "url": ["https://example.com", "https://test.org", "https://demo.io"],
    "time": ["14:30:00", "09:15:00", "23:45:00", "08:00:00", "17:30:00"],
    "username": ["alice", "bob", "charlie", "dave", "eve"],
    "num_results": ["5", "10", "20"],
    "port": ["3000", "8080", "5000", "8000", "5432"],
}

# ======================================================================
# 输出模板
# 每种工具对应一组输出模板，也是 ${placeholder} 格式
# ======================================================================

OUTPUT_TEMPLATES: dict[str, list[str]] = {

    "web_search": [
        "Found ${num_results} results for ${query}. Result 1: ${snippet}",
        "Top result for ${query}: ${snippet} (relevance: ${relevance})",
        "Search results for '${query}':\n1. ${snippet}\n2. ${snippet2}",
    ],

    "web_fetch": [
        "Fetched page ${url}: ${page_title}\nContent length: ${content_length} bytes",
        "Page loaded: ${page_title}. ${paragraphs} paragraphs found.",
    ],

    "read_file": [
        "Read ${filepath}: ${line_count} lines, ${char_count} characters",
        "File content:\n${file_content}",
        "Successfully loaded ${filepath} (${size} KB)",
    ],

    "write_file": [
        "Written ${char_count} bytes to ${filepath}",
        "File saved: ${filepath}",
    ],

    "python_repl": [
        "${result_output}",
        "Execution result:\n${result_output}",
        "> ${result_output}",
    ],

    "bash_shell": [
        "Command executed. Output:\n${shell_output}",
        "Exit code: 0\n${shell_output}",
        "${shell_output}",
    ],

    "list_directory": [
        "Contents of ${directory}:\n${file_list}",
        "Found ${file_count} items in ${directory}",
    ],

    "api_call": [
        "HTTP ${status_code}: ${response_body}",
        "Response from ${url}: ${response_body}",
        "${status_code} OK\n${response_body}",
    ],

    "parse_data": [
        "Parsed ${format_type}: ${parsed_result}",
        "Extracted ${field}: ${field_value}",
    ],

    "summarize_text": [
        "Summary (${compression_ratio}% reduction):\n${summary_text}",
        "Key points:\n- ${point1}\n- ${point2}",
    ],

    "search_database": [
        "Query returned ${row_count} rows:\n${query_result}",
        "Found ${row_count} records. ${query_result}",
    ],

    "get_weather": [
        "${city}: ${temperature}°${unit_abbr}, ${condition}",
        "Weather in ${city}: ${temperature}°${unit_abbr}, humidity ${humidity}%",
    ],

    "search_wikipedia": [
        "Wikipedia: ${topic}\n${wikipedia_snippet}",
        "${topic}: ${wikipedia_snippet}",
    ],

    "calculate": [
        "Result: ${calc_result}",
        "${expression} = ${calc_result}",
    ],

    "send_email": [
        "Email sent to ${recipient} with subject '${subject}'",
        "Message delivered: ${message_id}",
    ],

    "read_news": [
        "Top ${category} news:\n1. ${headline1}\n2. ${headline2}\n3. ${headline3}",
        "Latest ${category}: ${headline1}",
    ],

    "translate": [
        "Translation (${source} → ${target}):\n${translated_text}",
        "${translated_text}",
    ],

    "analyze_sentiment": [
        "Sentiment: ${sentiment_label} (confidence: ${sentiment_score})",
        "${sentiment_label} (${sentiment_score})",
    ],

    "create_document": [
        "Document '${title}' created (${doc_length} words)",
        "Created: ${title}.md",
    ],

    "get_current_time": [
        "Current time: ${current_time}",
        "${current_time}",
    ],
}

# ======================================================================
# 输出占位符取值池
# ======================================================================

OUTPUT_PLACEHOLDER_POOL: dict[str, list[str]] = {

    "snippet": [
        "Python is a versatile programming language used in web development and data science.",
        "Machine learning algorithms can be categorized into supervised and unsupervised learning.",
        "React is a JavaScript library for building user interfaces maintained by Meta.",
        "Docker containers provide a consistent environment for application deployment.",
        "Kubernetes automates deployment, scaling, and management of containerized applications.",
    ],
    "snippet2": [
        "JavaScript is commonly used for front-end web development alongside HTML and CSS.",
        "Deep learning models require large amounts of data and computational resources.",
        "Vue.js is a progressive framework for building user interfaces.",
        "Git is a distributed version control system for tracking changes in source code.",
        "PostgreSQL is a powerful open-source relational database management system.",
    ],

    "page_title": [
        "Wikipedia - Artificial Intelligence",
        "GitHub - TensorFlow Repository",
        "Hacker News - Latest Discussions",
        "MDN Web Docs - JavaScript Guide",
    ],
    "content_length": ["2048", "4096", "8192", "16384"],
    "paragraphs": ["5", "8", "12", "15"],

    "line_count": ["42", "128", "256", "512", "1024"],
    "char_count": ["2048", "8192", "16384", "32768"],
    "file_content": [
        "import os\nimport sys\n\ndef main():\n    print('hello world')\n\nif __name__ == '__main__':\n    main()",
        "# Configuration\nDEBUG = True\nDATABASE_URL = 'postgresql://localhost/db'\nSECRET_KEY = 'your-secret-key'",
        "name,age,city\nAlice,30,New York\nBob,25,London\nCharlie,35,Tokyo",
    ],
    "size": ["2", "8", "32", "128"],

    "result_output": [
        "3.141592653589793",
        "[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]",
        "{'name': 'Alice', 'age': 30, 'city': 'New York'}",
        "Hello, World!",
        "pandas version: 2.0.3",
        "numpy version: 1.24.3",
        "True",
        "42",
    ],

    "shell_output": [
        "total 24\ndrwxr-xr-x  2 user group  4096 Jan 15 10:30 src\ndrwxr-xr-x  2 user group  4096 Jan 15 10:30 tests",
        "Python 3.11.4\npip 23.1.2\nsetuptools 67.8.0",
        "Found 2 matching files:\n  ./src/main.py\n  ./src/utils.py",
    ],

    "file_list": [
        "main.py\nutils.py\nmodels.py\ntests/\nREADME.md\nrequirements.txt",
        "index.html\nstyle.css\napp.js\nimages/",
    ],
    "file_count": ["3", "5", "8", "12"],

    "status_code": ["200", "201", "204", "301", "400", "404", "500"],
    "response_body": [
        '{"status": "ok", "data": []}',
        '{"id": 123, "name": "test"}',
        '{"message": "success"}',
        '{"error": "not found"}',
        "<html><body><h1>Hello</h1></body></html>",
    ],

    "parsed_result": [
        "{'name': 'Alice', 'age': 30}",
        "[Row(id=1), Row(id=2), Row(id=3)]",
        "3 key-value pairs extracted",
    ],
    "field_value": ["Alice", "2024-01-15", "42.99", "active", "John Doe"],

    "compression_ratio": ["60", "75", "80"],
    "summary_text": [
        "The document discusses machine learning applications in healthcare.",
        "Key topics include data preprocessing, model selection, and evaluation.",
    ],
    "point1": ["Data was collected from 1000 participants", "The model achieved 95% accuracy"],
    "point2": ["Results show significant improvement", "Further research is needed"],

    "row_count": ["5", "10", "25", "100", "0"],
    "query_result": [
        "[(1, 'Alice', 'active'), (2, 'Bob', 'active')]",
        "[(42,), (57,), (83,)]",
        "No matching records found.",
    ],

    "temperature": ["12", "15", "18", "20", "22", "25", "28", "30", "32", "35"],
    "unit_abbr": ["C", "F"],
    "condition": ["sunny", "cloudy", "rainy", "windy", "foggy", "partly cloudy", "clear"],
    "humidity": ["45", "55", "65", "75", "85", "95"],

    "wikipedia_snippet": [
        "Artificial intelligence is intelligence demonstrated by machines.",
        "Machine learning is the study of computer algorithms that improve through experience.",
        "Python is a high-level, interpreted programming language with dynamic semantics.",
    ],

    "calc_result": ["4", "42", "15", "0", "100", "3.14", "2.71"],
    "relevance": ["0.95", "0.87", "0.92", "0.78"],

    "message_id": ["<abc123@mail.example.com>", "<msg_456@mail.example.com>"],
    "headline1": ["New AI Model Achieves Breakthrough", "Tech Company Launches New Product"],
    "headline2": ["Stock Market Reaches All-Time High", "Scientists Discover New Species"],
    "headline3": ["Climate Summit Concludes with Agreement", "Olympic Games Opening Ceremony"],

    "translated_text": [
        "Bonjour, comment allez-vous?",
        "你好，世界！",
        "こんにちは、世界！",
        "Hola, ¿cómo estás?",
    ],

    "sentiment_label": ["positive", "negative", "neutral", "mixed"],
    "sentiment_score": ["0.95", "0.87", "0.45", "0.52"],

    "doc_length": ["250", "500", "1000", "2000"],

    "current_time": ["2024-01-15 14:30:00", "2024-06-30 09:15:00", "2025-03-20 23:45:00"],
}


# ======================================================================
# 辅助函数
# ======================================================================

def resolve_placeholder(template: str, pool: dict[str, list[str]] | None = None) -> str:
    """将模板中的 ${placeholder} 替换为随机取值。

    Args:
        template: 包含 ${placeholder} 的模板字符串
        pool: 取值池，默认使用 PLACEHOLDER_POOL

    Returns:
        替换后的字符串
    """
    import re
    if pool is None:
        pool = {**PLACEHOLDER_POOL, **OUTPUT_PLACEHOLDER_POOL}

    def _replacer(match):
        key = match.group(1)
        values = pool.get(key)
        if values:
            return random.choice(values)
        return f"<{key}>"

    return re.sub(r'\$\{(\w+)\}', _replacer, template)


def pick_random_tool() -> str:
    """随机选一个工具名。"""
    return random.choice(TOOL_NAMES)


def pick_arg_template(tool: str) -> dict:
    """为指定工具随机选一个参数模板。"""
    templates = ARG_TEMPLATES.get(tool, [{}])
    return random.choice(templates)


def resolve_args(template: dict) -> dict:
    """将参数模板中的占位符全部替换为实际值。

    返回可以直接用的 args dict。
    """
    resolved = {}
    for key, value in template.items():
        resolved[key] = resolve_placeholder(str(value))
    return resolved


def resolve_output(tool: str, args: dict | None = None) -> str:
    """为指定工具生成一个随机输出。"""
    templates = OUTPUT_TEMPLATES.get(tool, ["Processed successfully."])
    template = random.choice(templates)
    return resolve_placeholder(template)
