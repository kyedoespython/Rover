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
4. The saved key becomes active automatically. To switch keys, open **Settings → Integrations**, select a saved key, and choose **Activate selected key**. Use **Deactivate key** to stop using it; Ollama Cloud requires an active key.
5. Rover keeps your current model if available; otherwise, it selects `gemma4:31b` when available, or the first available model. You can choose a different model and save the integration settings.

Rover displays saved key labels, not the secret. Re-enter a key if it needs to be replaced. Configure a stable `OLLAMA_API_KEY_ENCRYPTION_KEY` in the deployment environment for encrypted-at-rest credentials. Keep it private, separate from `SECRET_KEY`, and backed up securely; changing the encryption secret can make existing saved keys unusable.

## Select and use a model

In Rover AI, open **Models** below the message field. Models are grouped by integration and saved key; selecting one configures the provider without reloading. New accounts have no AI provider selected until a model is chosen. Existing accounts keep their previous selection. Gemini and Ollama are supported; other providers such as Groq are not yet integrated.

You can also open **Chatbot settings and computer permissions**, select a saved Gemini or Ollama key under **Model provider and saved API key**, and choose **Load models**. Rover selects an available model; use **AI model** and **Save chatbot settings** to change it. The configured local or custom Ollama endpoint is also listed. Ollama Cloud keys remain visible but unavailable when a local or custom endpoint is configured, because Rover never sends those keys to other endpoints.

The chooser loads each integration's model list when opened and reports errors independently. Model availability does not guarantee generation or billing access. Switching providers sends subsequent prompts, checked files, and relevant existing chat history to the newly selected provider. End the chat session first if that history should not be shared.

The Integrations page checks models offered by the configured endpoint and saves the selected model for the account. The single Rover AI panel can also have its own chatbot name and model setting. Triple Rover slots each have independent model settings.

The assistant panel displays connection and model errors when they occur. If it reports the service is unreachable or the model is missing, verify:

- The Ollama service is running and reachable from the Rover web process.
- The configured base URL is correct for the current network/container.
- The model is installed or available on that Ollama endpoint.
- For Ollama Cloud, a valid saved API key is selected.

If Ollama Cloud reports that payment or usage credits are required, review the account's [usage and billing](https://ollama.com/settings) and [pricing](https://ollama.com/pricing).

Drag the panel's height handle or use its arrow keys to resize it. The message field can also be resized by dragging its bottom-right corner or focusing that corner and using the arrow keys.

## Data sent to Ollama

When a user sends a chat message, Rover sends the selected model the message, selected attachments, and relevant conversation history. Do not include secrets or sensitive personal data in prompts or files unless the user and deployment policy permit it.

## Google Gemini

Save a **Google Gemini API Key** in the Design Dashboard, then select a Gemini model using **Models** in Rover AI. You can also configure it under **Settings → Integrations**. Gemini uses Google's API, not the configured Ollama endpoint. Its key is encrypted at rest using the same stable encryption secret described above and is sent only to Google's Gemini API.

When Gemini is active, Rover sends the prompt, selected attachments, and relevant chat history to Google. Existing chat history can include messages from an earlier provider; end the session first if you do not want that history sent. The status check lists models but does not confirm that generation or billing will succeed. Gemini responses are displayed after generation completes; account usage limits and pricing are controlled by Google.

## Files and working folders

Drop UTF-8 text, Markdown, or source-code files into Rover AI, or use **browse** to select them. Check saved files to send them with each message to the active provider; uncheck them to stop sending them. Rover stores up to 20 files per account, each up to 64 KiB, and sends at most 128 KiB of selected file content per message. Delete a saved file when it is no longer needed; ending a chat session does not delete it.

Rover encrypts each saved filename and content in the database with authenticated encryption using `OLLAMA_API_KEY_ENCRYPTION_KEY` (or `SECRET_KEY` if unset). This is encryption at rest, not end-to-end encryption: Rover decrypts selected files to send them to the active provider. Chat messages and model responses are saved as chat history and could contain file excerpts, so deleting an attachment does not remove excerpts from history or backups. Keep the encryption key stable and backed up; losing or changing it makes existing files unreadable.

Under **Chatbot settings and computer permissions**, choose a working folder using the browser's permission prompt and opt into folder reading or writing. Selecting a folder requests browser read access; Rover only reads or writes files when the corresponding option is enabled. Enter a file name and choose **Add folder file to Rover AI** to save an encrypted copy, or save the latest reply to a Markdown file after confirming the write. The original files on the computer are not encrypted by Rover. Folder access is limited to the selected folder and current page; select it again after reloading. The folder picker requires a supported browser such as Chrome or Edge and a secure context such as HTTPS.

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
