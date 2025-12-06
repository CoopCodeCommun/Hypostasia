from core.models import Prompt, TextInput

# Get or Create the main prompt
prompt = Prompt.objects.get(name="Analyse Standard Hypostasia")
print(f"Updating prompt '{prompt.name}'")

# Update ONLY the "Format JSON" input
format_input = TextInput.objects.get(prompt=prompt, name="Format JSON")

format_input.content = """RÉPONSE ATTENDUE :
Vous devez répondre avec un objet JSON contenant une clé "arguments".
Format attendu :
{
  "arguments": [
      {
        "text_quote": "Citation exacte du texte ici...",
        "summary": "Résumé de l'argument...",
        "stance": "pour" | "contre" | "neutre"
      },
      ...
  ]
}
Si aucun argument n'est trouvé, renvoyez : { "arguments": [] }
"""
format_input.save()

print("Updated Format JSON input.")
print("Prompt update complete.")
