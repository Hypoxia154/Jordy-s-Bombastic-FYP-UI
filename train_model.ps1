# train_model.ps1
# This script creates a custom Ollama model from the Modelfile in this directory.

Write-Host "Removing existing model 'my-real-estate-bot'..."
ollama rm my-real-estate-bot

Write-Host "Creating custom model 'my-real-estate-bot'..."
ollama create my-real-estate-bot -f Modelfile

if ($?) {
    Write-Host "Success! Model 'my-real-estate-bot' is ready."
} else {
    Write-Host "Error: Failed to create model. Make sure Ollama is running."
}
