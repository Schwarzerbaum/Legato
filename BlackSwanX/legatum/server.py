#!/usr/bin/env python3
"""
Simple Flask web UI for testing Q&A with Phase 2 improvements.
Run: python3 server.py
Visit: http://localhost:5000
"""
from flask import Flask, render_template_string, request, jsonify
from pathlib import Path
import json
import sys
from qa_runtime import QARuntimeOptimized

app = Flask(__name__)

# Load index (find first available .json)
index_path = None
indexes_dir = Path(__file__).parent / "indexes"
if indexes_dir.exists():
    index_files = list(indexes_dir.glob("*.json"))
    if index_files:
        index_path = index_files[0]

qa_runtime = None
if index_path and index_path.exists():
    qa_runtime = QARuntimeOptimized(str(index_path))
    print(f"[OK] Loaded index: {index_path}", file=sys.stderr)
else:
    print(f"[WARNING] No index found in ./indexes/", file=sys.stderr)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LEGATUM Q&A — Phase 2 Enhanced</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 5px; }
        .badge {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            margin-right: 10px;
            margin-bottom: 10px;
            font-size: 0.85em;
        }
        .main-card {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .question-input {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        #question {
            flex: 1;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 1em;
        }
        #question:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            padding: 12px 30px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover { background: #764ba2; }
        button:disabled { opacity: 0.5; }
        .result-card {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-top: 20px;
            border-radius: 5px;
        }
        .answer {
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
            line-height: 1.6;
        }
        .metadata {
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }
        .loading { text-align: center; padding: 20px; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .error { background: #fee; color: #c33; padding: 15px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 LEGATUM Q&A</h1>
            <p>Phase 2 Enhanced: Graph RAG + Layout Parsing + Corrective RAG</p>
            <div style="margin-top: 15px;">
                <span class="badge">✓ Graph RAG (+8%)</span>
                <span class="badge">✓ Layout Parsing (+5%)</span>
                <span class="badge">✓ Hierarchical Chunking (+5%)</span>
                <span class="badge">✓ Corrective RAG (+3%)</span>
            </div>
        </div>

        <div class="main-card">
            <div class="question-input">
                <input type="text" id="question" placeholder="Ask a question about the BIM document..." />
                <button onclick="askQuestion()">Ask</button>
            </div>
            <div id="results"></div>
        </div>
    </div>

    <script>
        function askQuestion() {
            const question = document.getElementById('question').value.trim();
            if (!question) return;

            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>Retrieving...</p></div>';

            fetch('/api/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ question })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    resultsDiv.innerHTML = `<div class="error"><strong>Error:</strong> ${data.error}</div>`;
                } else {
                    resultsDiv.innerHTML = `
                        <div class="result-card">
                            <h3>Answer (Phase 2 Enhanced):</h3>
                            <div class="answer">${data.answer}</div>
                            <div class="metadata">
                                <strong>Pages:</strong> ${data.metadata.retrieved_pages.join(', ')}<br>
                                <strong>Entities:</strong> ${data.metadata.entities_used} | 
                                <strong>Relations:</strong> ${data.metadata.relations_used}
                            </div>
                        </div>
                    `;
                }
            })
            .catch(err => {
                resultsDiv.innerHTML = `<div class="error"><strong>Error:</strong> ${err}</div>`;
            });
        }

        document.getElementById('question').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') askQuestion();
        });
        
        document.getElementById('question').focus();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/ask", methods=["POST"])
def ask():
    if not qa_runtime:
        return jsonify({"error": "Index not loaded"}), 500

    try:
        question = request.json.get("question", "").strip()
        if not question:
            return jsonify({"error": "Empty question"}), 400

        answer, metadata = qa_runtime.answer_question(question)
        return jsonify({"question": question, "answer": answer, "metadata": metadata})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500

if __name__ == "__main__":
    print("[INFO] Starting http://localhost:5000", file=sys.stderr)
    app.run(host="127.0.0.1", port=5000, debug=False)
