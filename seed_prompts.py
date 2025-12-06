
import os
import django
import sys

# Setup Django environment
sys.path.append('/home/jonas/Gits/Test antigravity/V3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Prompt, TextInput, AIModel

def seed_prompts():
    print("Seeding Prompts...")
    
    # 1. Create or Update the Main Analysis Prompt
    prompt_name = "Analyse Standard Hypostasia"
    prompt, created = Prompt.objects.get_or_create(name=prompt_name)
    
    if created:
        print(f"Created new prompt: {prompt_name}")
    else:
        print(f"Updating existing prompt: {prompt_name}")
        prompt.inputs.all().delete() # Reset inputs
        
    # Try to link to a real AI Model if available
    real_model = AIModel.objects.exclude(provider='mock').filter(is_active=True).first()
    if real_model:
        print(f" Linking to AI Model: {real_model.name}")
        prompt.default_model = real_model
        prompt.save()
    else:
        print(" Warning: No active real AI Model found. Prompt remains unlinked (or Mock).")

    # 2. Add Inputs
    
    # Context
    TextInput.objects.create(
        prompt=prompt,
        name="Context",
        role="context",
        order=1,
        content="""Tu es un expert en analyse rhétorique et en extraction d'arguments.
Ta mission est d'analyser le texte fourni ci-dessous et d'en extraire les principaux arguments/thèses.
"""
    )
    
    # Instruction
    TextInput.objects.create(
        prompt=prompt,
        name="Instruction",
        role="instruction",
        order=2,
        content="""Pour chaque argument identifié :
1. Repère la citation EXACTE (mot pour mot) dans le texte qui supporte cet argument. C'est CRUCIAL que le texte soit copié à l'identique pour le surlignage.
2. Synthétise l'argument en une phrase claire.
3. Détermine la posture (pour/contre/neutre) par rapport au sujet principal du texte.

Si le texte est long, extrais environ 5 à 10 arguments majeurs.
Ignore les sections de navigation, pied de page ou publicités.
"""
    )
    
    # Format
    TextInput.objects.create(
        prompt=prompt,
        name="Format JSON",
        role="format",
        order=3,
        content="""Réponds UNIQUEMENT avec un tableau JSON strict. Ne mets pas de markdown, pas de ```json. 
Structure attendue :
[
  {
    "text_quote": "Citation exacte présente dans le texte...",
    "summary": "Résumé de l'argument...",
    "stance": "pour" | "contre" | "neutre"
  },
  ...
]
"""
    )
    
    print("Prompts seeded successfully.")

if __name__ == "__main__":
    seed_prompts()
