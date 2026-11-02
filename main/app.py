from flask import Flask
from flask import Response
from flask import stream_with_context
from flask import render_template
from flask import jsonify
from flask import request
from flask import url_for

import ollama


app = Flask(__name__)

@app.route("/")
def Rover_Dashboard():

    return render_template("/Home/Home.html")

@app.route("/About-Page")
def About_Page():
    return render_template("About.html")

@app.route("/Rover", methods=["POST"])
def send_message():
    data = request.form.get("userInput")
    if not data:
        return jsonify({"error": "No user input provided"}), 400

    def generate():
        stream = ollama.chat(
            model="qwen3:8b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise assistant. "
                        "Answer directly in 1-3 sentences. "
                        "No preamble, no step-by-step breakdowns, "
                        "no explanations unless explicitly asked. "
                        "If code is requested, provide only the code."
                    )
                },
                {"role": "user", "content": data}
            ],
            stream=True
        )
        for chunk in stream:
            yield chunk.message.content

    return Response(stream_with_context(generate()), mimetype="text/plain")