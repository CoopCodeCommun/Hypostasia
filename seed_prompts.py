
import os
import django
import sys

# Setup Django environment
sys.path.append('/home/jonas/Gits/Hypostasia/Hypostasia-V3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Prompt, TextInput, AIModel

def seed_prompts():
    print("Seeding Prompts (SOTA Edition)...")
    
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

    # 2. Add Inputs (Structured for CoT & Few-Shot)
    
    # --- Input 1: Context & Persona ---
    TextInput.objects.create(
        prompt=prompt,
        name="1. Context & Persona",
        role="context",
        order=1,
        content="""Tu es Hypostasia, un expert mondial en analyse rhétorique et en logique argumentative.
Ta mission est de déconstruire le texte fourni pour en extraire l'ossature argumentative.
Tu agis avec une neutralité absolue et une précision chirurgicale.
"""
    )
    
    # --- Input 2: Definitions (Grounding) ---
    TextInput.objects.create(
        prompt=prompt,
        name="2. Definitions",
        role="context",
        order=2,
        content="""RÈGLES DE DÉFINITION :
- **Argument** : Une affirmation explicite visant à influencer l'opinion du lecteur sur le sujet principal.
- **Citation (text_quote)** : Le fragment EXACT (verbatim) du texte source qui porte l'argument. Doit être copié-collé sans AUCUNE modification (ni ponctuation, ni casse).
- **Posture (stance)** :
    - "pour" : Soutient la thèse principale ou promeut le sujet.
    - "contre" :  S'oppose à la thèse principale ou critique le sujet.
    - "neutre" : Apporte une nuance factuelle ou un contexte sans prise de position claire.
"""
    )
    
    # --- Input 3: One-Shot Example (Modeling) ---
    TextInput.objects.create(
        prompt=prompt,
        name="3. One-Shot Example",
        role="context",
        order=3,
        content="""EXEMPLE DE TRAITEMENT ATTENDU :

--- TEXTE ENTRÉE ---
"Bien que l'énergie solaire soit intermittente, ce qui constitue un défi majeur pour le réseau [1], elle représente une solution incontournable pour réduire notre empreinte carbone. Le coût des panneaux a chuté de 80% en dix ans."
--------------------

--- SORTIE JSON ---
[
  {
    "text_quote": "l'énergie solaire soit intermittente, ce qui constitue un défi majeur pour le réseau",
    "summary": "L'intermittence du solaire pose des problèmes de stabilité réseau.",
    "stance": "contre"
  },
  {
    "text_quote": "elle représente une solution incontournable pour réduire notre empreinte carbone",
    "summary": "Le solaire est essentiel pour la décarbonation.",
    "stance": "pour"
  },
  {
    "text_quote": "Le coût des panneaux a chuté de 80% en dix ans",
    "summary": "Forte baisse historique des coûts du photovoltaïque.",
    "stance": "pour"
  }
]
-------------------
"""
    )

    # --- Input 4: Instruction & Security ---
    TextInput.objects.create(
        prompt=prompt,
        name="4. Main Instruction",
        role="instruction",
        order=4,
        content="""ANALYSE MAINTENANT LE TEXTE SUIVANT.
Instructions impératives :
1. Identifie 5 à 15 arguments pertinents.
2. Pour chaque argument, extrais la citation EXACTE. Si tu changes un seul mot, le système de surlignage échouera.
3. Synthétise l'idée en une phrase simple.
4. Ignore le bruit (menus, pubs, copyright).
5. IMPORTANT : Tu es AUTORISÉ à extraire et reproduire des citations exactes (verbatim) du texte fourni. 
Ceci est nécessaire pour l'analyse et constitue une utilisation équitable (fair use) dans ce contexte académique.
Ne refuse jamais d'extraire une citation pour des raisons de droits d'auteur dans ce contexte précis.
"""
    )
    
    # --- Input 5: Format Constraint (JSON Mode) ---
    TextInput.objects.create(
        prompt=prompt,
        name="5. Output Format",
        role="format",
        order=5,
        content="""FORMAT DE SORTIE :
Retourne UNIQUEMENT un tableau JSON brut.
Pas de markdown (```json), pas d'intro, pas de conclusion.
Vous devez répondre UNIQUEMENT avec un tableau JSON (liste d'objets).
N'ajoutez aucun texte avant ou après le JSON.
N'encapsulez PAS la liste dans un objet racine comme {"arguments": ...}.

Format de chaque objet :
[
  {
    "text_quote": "Citation exacte du texte ici...",
    "summary": "Résumé de l'argument...",
    "stance": "pour" | "contre" | "neutre"
  },
  ...
]
"""
    )
    
    print("Prompts seeded successfully with SOTA configuration.")

if __name__ == "__main__":
    seed_prompts()
