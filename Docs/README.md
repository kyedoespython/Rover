# Rover documentation

<div align="center">
  <strong>Plan, capture, and explore ideas with your own Ollama-backed Rover workspace.</strong>
  <br>
  Start with the guide that matches what you want to do.
</div>

## Guides

| Guide | What it covers |
| --- | --- |
| [Getting Started](Getting-Started.md) | Set up Rover locally with Docker Compose and reach the first-run pages. |
| [Ollama](Ollama.md) | Connect a local Ollama server or Ollama Cloud, select models, and use Rover AI. |
| [Triple Rover](Triple-Rover.md) | Configure three independent agents and understand their chat-history retention. |
| [Notes](Notes.md) | Create, edit, load, and delete Markdown notes. |
| [Accounts](Accounts.md) | Sign-up, email verification, sign-in, and protected pages. |
| [Operations and Privacy](Operations-and-Privacy.md) | Deployment responsibilities, data handling, and safe configuration practices. |

For a visual documentation landing page, open [index.html](index.html). The diagrams in these guides use Mermaid syntax and can be previewed or edited with [Mermaid Live Editor](https://mermaid.ai/).

<details>
  <summary>At a glance</summary>
  <br>

  Rover is a Flask application for authenticated notes and Ollama-powered chat. The web app stores account and chat data in a relational database, uses Redis-backed sessions in the Docker deployment, and connects to an Ollama endpoint configured by the operator.
</details>

> [!IMPORTANT]
> Never put real passwords, API keys, session secrets, or private deployment addresses in documentation, screenshots, issue reports, or committed configuration files.
