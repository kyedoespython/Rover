# Ollama integration

Rover uses Ollama for text generation in its single Rover AI panel and Triple Rover agents. Rover does not download models itself; the selected model must be available from the configured Ollama endpoint.

## Configure the endpoint

Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in the application's private environment:

- **Local Ollama:** point `OLLAMA_BASE_URL` at the Ollama server reachable by the web app. Local Ollama normally does not require an API key.
- **Ollama Cloud:** production defaults to the official HTTPS endpoint (`https://ollama.com`) when `OLLAMA_BASE_URL` is unset. Save an Ollama API key in Rover. For local development, set `OLLAMA_BASE_URL=https://ollama.com` explicitly to use Cloud.
- **Custom Ollama-compatible endpoint:** configure its URL as appropriate. Rover does not forward saved Ollama keys to local or custom endpoints.

The Docker Compose default targets an Ollama service on the Docker host. Network reachability depends on where Rover and Ollama run; check the URL from the web container's network perspective.

On Render, leave `OLLAMA_BASE_URL` unset to use Ollama Cloud by default, or set it to the endpoint your deployment can reach. Saved Cloud keys are sent only when the configured URL is the official HTTPS `ollama.com` endpoint; they are not sent to local or custom endpoints.

## Add a Cloud API key

1. Sign in with a verified account.
2. Open the **Design Dashboard** and select **API Key**.
3. Give the key a recognizable label, choose **Ollama API Key**, enter the secret, and save it.
4. Open **Settings → Integrations**, choose an available model and saved key, then save.

Rover displays saved key labels, not the secret. Re-enter a key if it needs to be replaced. Configure a stable `OLLAMA_API_KEY_ENCRYPTION_KEY` in the deployment environment for encrypted-at-rest credentials. Keep it private, separate from `SECRET_KEY`, and backed up securely; changing the encryption secret can make existing saved keys unusable.

## Select and use a model

The Integrations page checks models offered by the configured endpoint and saves the selected model for the account. The single Rover AI panel can also have its own chatbot name and model setting. Triple Rover slots each have independent model settings.

The assistant panel shows connection/model status. If it reports the service is unreachable or the model is missing, verify:

- The Ollama service is running and reachable from the Rover web process.
- The configured base URL is correct for the current network/container.
- The model is installed or available on that Ollama endpoint.
- For Ollama Cloud, a valid saved API key is selected.

## Data sent to Ollama

When a user sends a chat message, Rover sends the selected model the message and relevant conversation history. A Markdown file added through the single Rover panel is included in the draft; the user must press **Send** before it is sent to Ollama. Do not include secrets or sensitive personal data in prompts unless the user and deployment policy permit it.

```mermaid
sequenceDiagram
    actor User
    participant UI as Rover chat UI
    participant App as Rover Flask app
    participant Ollama as Configured Ollama endpoint
    User->>UI: Enter message and press Send
    UI->>App: Authenticated chat request
    App->>Ollama: Model, conversation context, and message
    Ollama-->>App: Generated response
    App-->>UI: Response and saved chat entry
    UI-->>User: Display response
```

<details>
  <summary>Local Ollama versus Ollama Cloud</summary>
  <br>

  Local Ollama usually works without a Rover API key. Ollama Cloud requires an API key saved in Rover. Rover sends saved Ollama credentials only to the official HTTPS Ollama Cloud host; a locally configured or custom endpoint does not receive those saved credentials.
</details>
