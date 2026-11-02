document.getElementById('chatForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const output = document.getElementById('output');
    output.textContent = '';

    const res = await fetch('/Rover', {
        method: 'POST',
        body: formData
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        output.textContent += decoder.decode(value, { stream: true });
    }
});   